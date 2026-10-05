"""Pipeline B: multi-hop QA over HotpotQA (distractor setting), 4 LLM steps.

    Decomposer -> 1-3 sub-questions, bridge hops use #1/#2      ("qa.decomposer")
    [BM25]     -> top-3 of the question's 10 paragraphs per hop (no LLM, not routed)
    Hop reader -> one call per sub-question, short answer + cited sentences ("qa.hop_reader")
    Composer   -> combines hop answers into an answer           ("qa.composer")
    Formatter  -> answer-key form: span or yes/no              ("qa.formatter")

Every step has a fallback so a bad output degrades the run instead of crashing
it; how far that degradation travels is what the fragility analysis measures.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Callable

from pipelines.common.text import load_template, parse_json_reply, render

PROMPTS = Path(__file__).parent / "prompts"
STEP_DECOMPOSER, STEP_HOP, STEP_COMPOSER, STEP_FORMATTER = (
    "qa.decomposer", "qa.hop_reader", "qa.composer", "qa.formatter")
MAX_HOPS = 3
TOP_K = 3

LLM = Callable[[str, str], str]

# --------------------------------------------------------------------------- data


def from_hotpot(rec: dict) -> dict:
    """Convert one HotpotQA record into our task format (schemas/task.json)."""
    return {
        "task_id": rec["_id"],
        "question": rec["question"],
        "type": rec["type"],
        "level": rec.get("level"),
        "paragraphs": [{"title": t, "sentences": s} for t, s in rec["context"]],
        "gold_answer": rec["answer"],
        "supporting_facts": [[t, i] for t, i in rec["supporting_facts"]],
    }


# --------------------------------------------------------------------------- BM25


_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("a an the of in on at to for and or is was were are be by with as from that which who whom "
            "what when where how did do does it its this these those".split())


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


def bm25_rank(query: str, docs: list[str], k1: float = 1.5, b: float = 0.75) -> list[int]:
    """Indices of docs, best first (ties keep original order)."""
    toks = [tokens(d) for d in docs]
    n = len(docs)
    avgdl = sum(map(len, toks)) / max(n, 1) or 1.0
    df = Counter(t for d in toks for t in set(d))
    q = tokens(query)

    def score(d: list[str]) -> float:
        tf = Counter(d)
        s = 0.0
        for t in q:
            if t in tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / avgdl))
        return s

    scores = [score(d) for d in toks]
    return sorted(range(n), key=lambda i: -scores[i])


def retrieve(task: dict, query: str, k: int = TOP_K) -> list[dict]:
    docs = [p["title"] + " " + " ".join(p["sentences"]) for p in task["paragraphs"]]
    return [task["paragraphs"][i] for i in bm25_rank(query, docs)[:k]]


def format_paragraphs(paras: list[dict]) -> str:
    out = []
    for p in paras:
        sents = "\n".join(f"  ({i}) {s.strip()}" for i, s in enumerate(p["sentences"]))
        out.append(f"Title: {p['title']}\n{sents}")
    return "\n\n".join(out)


# --------------------------------------------------------------------------- steps


def render_decomposer(task: dict) -> str:
    return render(load_template(PROMPTS / "decomposer.md"), question=task["question"])


def parse_decomposer(reply: str) -> tuple[dict | None, bool]:
    obj, ok = parse_json_reply(reply)
    if not ok:
        return None, False
    subqs = obj.get("sub_questions")
    qtype = obj.get("question_type")
    if (not isinstance(subqs, list) or not subqs or not all(isinstance(s, str) and s.strip() for s in subqs)
            or qtype not in ("bridge", "comparison")):
        return None, False
    return {"question_type": qtype, "sub_questions": [s.strip() for s in subqs[:MAX_HOPS]]}, True


_REF = re.compile(r"#(\d+)")


def resolve_refs(sub_question: str, answers: list[str]) -> str:
    """Replace #k with the k-th earlier answer (1-based). Unknown refs stay."""
    def sub(m: re.Match) -> str:
        k = int(m.group(1))
        return answers[k - 1] if 0 < k <= len(answers) and answers[k - 1] else m.group(0)
    return _REF.sub(sub, sub_question)


def render_hop(sub_question: str, paras: list[dict]) -> str:
    return render(load_template(PROMPTS / "hop_reader.md"),
                  paragraphs=format_paragraphs(paras), sub_question=sub_question)


def parse_hop(reply: str) -> tuple[dict | None, bool]:
    obj, ok = parse_json_reply(reply)
    if not ok or not isinstance(obj.get("answer"), str) or not isinstance(obj.get("found"), bool):
        return None, False
    ev = obj.get("evidence", [])
    if not isinstance(ev, list):
        return None, False
    clean = [[e[0], int(e[1])] for e in ev
             if isinstance(e, list) and len(e) == 2 and isinstance(e[0], str) and str(e[1]).isdigit()]
    return {"answer": obj["answer"].strip(), "found": obj["found"], "evidence": clean}, True


def evidence_sentences(task: dict, evidence: list) -> list[str]:
    by_title = {p["title"]: p["sentences"] for p in task["paragraphs"]}
    out = []
    for title, i in evidence:
        sents = by_title.get(title, [])
        if 0 <= i < len(sents):
            out.append(f"[{title}] {sents[i].strip()}")
    return out


def format_hops(hops: list[dict]) -> str:
    out = []
    for n, h in enumerate(hops, 1):
        sents = "\n".join(f"    - {s}" for s in h["sentences"]) or "    - (none)"
        found = "" if h["found"] else " (not found in the paragraphs)"
        out.append(f"{n}. Q: {h['resolved_question']}\n   A: {h['answer'] or '(no answer)'}{found}\n{sents}")
    return "\n".join(out)


def render_composer(task: dict, question_type: str, hops: list[dict]) -> str:
    return render(load_template(PROMPTS / "composer.md"), question=task["question"],
                  question_type=question_type, hops=format_hops(hops))


def parse_composer(reply: str) -> tuple[dict | None, bool]:
    obj, ok = parse_json_reply(reply)
    if not ok or not isinstance(obj.get("answer"), str):
        return None, False
    return {"answer": obj["answer"].strip(), "reasoning": str(obj.get("reasoning", ""))}, True


def render_formatter(task: dict, draft: str) -> str:
    return render(load_template(PROMPTS / "formatter.md"), question=task["question"], draft_answer=draft)


def parse_formatter(reply: str) -> tuple[str | None, bool]:
    obj, ok = parse_json_reply(reply)
    if not ok or not isinstance(obj.get("final_answer"), str):
        return None, False
    return obj["final_answer"].strip(), True


# --------------------------------------------------------------------------- pipeline


def run(task: dict, llm: LLM) -> dict:
    """Run the whole pipeline. Returns a trace dict (see schemas/trace.json)."""
    trace: dict = {"task_id": task["task_id"], "pipeline": "qa", "steps": []}

    # 1. Decomposer. Fallback: the original question as the only hop.
    dec, ok = parse_decomposer(llm(STEP_DECOMPOSER, render_decomposer(task)))
    if not ok:
        dec = {"question_type": "bridge", "sub_questions": [task["question"]]}
    trace["steps"].append({"step": STEP_DECOMPOSER, "parse_ok": ok, "output": dec})

    # 2. Retrieval + hop reader, one call per sub-question. Fallback: empty answer.
    hops: list[dict] = []
    for sq in dec["sub_questions"]:
        resolved = resolve_refs(sq, [h["answer"] for h in hops])
        paras = retrieve(task, resolved)
        hop, ok = parse_hop(llm(STEP_HOP, render_hop(resolved, paras)))
        if not ok:
            hop = {"answer": "", "found": False, "evidence": []}
        hop.update(sub_question=sq, resolved_question=resolved,
                   retrieved=[p["title"] for p in paras],
                   sentences=evidence_sentences(task, hop["evidence"]))
        trace["steps"].append({"step": STEP_HOP, "parse_ok": ok, "output": hop})
        hops.append(hop)

    # 3. Composer. Fallback: the last hop's answer.
    comp, ok = parse_composer(llm(STEP_COMPOSER, render_composer(task, dec["question_type"], hops)))
    if not ok:
        comp = {"answer": hops[-1]["answer"], "reasoning": "(fallback: last hop answer)"}
    trace["steps"].append({"step": STEP_COMPOSER, "parse_ok": ok, "output": comp})

    # 4. Formatter. Fallback: the composer's answer unchanged.
    final, ok = parse_formatter(llm(STEP_FORMATTER, render_formatter(task, comp["answer"])))
    if not ok:
        final = comp["answer"]
    trace["steps"].append({"step": STEP_FORMATTER, "parse_ok": ok, "output": {"final_answer": final}})
    trace["final_answer"] = final
    return trace
