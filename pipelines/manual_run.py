"""Run one task through a pipeline by hand (paste mode) or with a model (auto mode).

Paste mode (no API key needed): each step's prompt is printed AND saved to a
file. Paste it into AI Studio, copy the model's whole reply back into the
terminal, then type END on its own line. The script parses the reply, builds
the next step's prompt, and so on. Bad replies are kept, not retyped: a parse
failure is a finding.

    python -m pipelines.manual_run sql --qid 1471
    python -m pipelines.manual_run sql --qid 1471 --db-dir data/minidev/dev_databases
    python -m pipelines.manual_run qa  --hotpot data/hotpot_dev_distractor_v1.json --id 5a8b57f25542995d1e6f1371

Auto mode (needs `pip install litellm` and GEMINI_API_KEY):
    python -m pipelines.manual_run sql --qid 1471 --model gemini/<model id from AI Studio>

Every run appends one row to testkit/results.csv and saves the full trace
under testkit/runs/.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import string
import sys
import time
from collections import Counter
from pathlib import Path

from pipelines.qa import steps as qa
from pipelines.sql import steps as sql

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "testkit"


def paste_llm(run_dir: Path):
    counter = Counter()

    def llm(step: str, prompt: str) -> str:
        counter[step] += 1
        f = run_dir / f"{step}_{counter[step]}.prompt.txt"
        f.write_text(prompt, encoding="utf-8")
        bar = "=" * 78
        print(f"\n{bar}\nSTEP {step} (call {counter[step]}). Prompt saved to {f.relative_to(ROOT)}\n{bar}")
        print(prompt)
        print(f"{bar}\nPaste the model's FULL reply, then a line with just END:")
        lines = []
        for line in sys.stdin:
            if line.strip() == "END":
                break
            lines.append(line)
        reply = "".join(lines)
        (run_dir / f"{step}_{counter[step]}.reply.txt").write_text(reply, encoding="utf-8")
        return reply
    return llm


def auto_llm(model: str, run_dir: Path):
    import litellm  # noqa: PLC0415 - only needed in auto mode
    counter = Counter()

    def llm(step: str, prompt: str) -> str:
        counter[step] += 1
        t0 = time.monotonic()
        r = litellm.completion(model=model, messages=[{"role": "user", "content": prompt}], temperature=0)
        reply = r.choices[0].message.content or ""
        base = run_dir / f"{step}_{counter[step]}"
        base.with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")
        base.with_suffix(".reply.txt").write_text(reply, encoding="utf-8")
        print(f"  {step} #{counter[step]}: {time.monotonic() - t0:.1f}s, "
              f"{r.usage.prompt_tokens} in / {r.usage.completion_tokens} out")
        return reply
    return llm


# Quick checks for eyeballing only. The official verifiers are Ashrith's.
def _norm(s: str) -> str:
    s = s.lower()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def quick_qa_check(pred: str, gold: str) -> str:
    p, g = _norm(pred).split(), _norm(gold).split()
    common = sum((Counter(p) & Counter(g)).values())
    f1 = 0.0 if not common else 2 * common / (len(p) + len(g))
    return f"EM={int(p == g)} F1={f1:.2f}"


def quick_sql_check(pred: str, gold: str, db: Path | None) -> str:
    if db is None:
        return "not executed (no database)"
    a, b = sql.execute(pred, db), sql.execute(gold, db)
    if a.rows is None:
        return f"pred error: {a.error}"
    return f"match={set(a.rows) == set(b.rows)} (pred {len(a.rows)} rows, gold {len(b.rows or [])} rows)"


def log_row(row: dict) -> None:
    f = KIT / "results.csv"
    new = not f.exists()
    with f.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pipeline", choices=["sql", "qa"])
    ap.add_argument("--qid", type=int, help="BIRD Mini-Dev question_id (sql)")
    ap.add_argument("--minidev", default=str(KIT / "mini_dev_prompt.jsonl"))
    ap.add_argument("--db-dir", help="folder containing <db_id>/<db_id>.sqlite (enables the refiner)")
    ap.add_argument("--hotpot", help="HotpotQA dev distractor JSON (qa)")
    ap.add_argument("--id", help="HotpotQA _id (qa)")
    ap.add_argument("--model", help="litellm model name for auto mode, e.g. gemini/<id>")
    ap.add_argument("--label", default="", help="model label for the log in paste mode, e.g. flash")
    a = ap.parse_args()

    if a.pipeline == "sql":
        tasks = {json.loads(l)["question_id"]: json.loads(l) for l in open(a.minidev, encoding="utf-8")}
        task = tasks[a.qid]
        task_id, kind = str(a.qid), task["difficulty"]
        db = Path(a.db_dir) / task["db_id"] / f"{task['db_id']}.sqlite" if a.db_dir else None
        if db is not None and not db.exists():
            sys.exit(f"database not found: {db}")
    else:
        recs = {r["_id"]: r for r in json.load(open(a.hotpot, encoding="utf-8"))}
        task = qa.from_hotpot(recs[a.id])
        task_id, kind = a.id, task["type"]

    model = a.model or f"paste:{a.label or 'unlabelled'}"
    run_dir = KIT / "runs" / f"{a.pipeline}_{task_id}_{re.sub(r'[^A-Za-z0-9.-]+', '-', model)}_{time.strftime('%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True)
    llm = auto_llm(a.model, run_dir) if a.model else paste_llm(run_dir)

    print(f"\nTask {task_id} ({kind}): {task['question']}")
    if a.pipeline == "sql":
        trace = sql.run(task, llm, db)
        pred, gold = trace["final_sql"], task["SQL"]
        check = quick_sql_check(pred, gold, db) if pred else "no SQL produced"
    else:
        trace = qa.run(task, llm)
        pred, gold = trace["final_answer"], task["gold_answer"]
        check = quick_qa_check(pred, gold)
    (run_dir / "trace.json").write_text(json.dumps(trace, indent=2, default=str), encoding="utf-8")

    parse = " ".join(f"{s['step'].split('.')[1]}:{'ok' if s['parse_ok'] else 'FAIL'}" for s in trace["steps"])
    print(f"\n{'=' * 78}\nPREDICTED: {pred}\nGOLD:      {gold}\nCHECK:     {check}\nPARSE:     {parse}")
    log_row({"time": time.strftime("%Y-%m-%d %H:%M"), "pipeline": a.pipeline, "task_id": task_id, "kind": kind,
             "model": model, "parse": parse, "check": check, "pred": pred, "gold": gold,
             "run_dir": str(run_dir.relative_to(ROOT)), "notes": ""})
    print(f"Logged to testkit/results.csv. Add your notes in the 'notes' column.")


if __name__ == "__main__":
    main()
