"""Pick the hand-test tasks: 5 per BIRD difficulty, 5 per HotpotQA type.

    python testkit/pick_tasks.py                       # SQL only
    python testkit/pick_tasks.py --hotpot data/hotpot_dev_distractor_v1.json

Fixed seed, and each pick comes from a different database where possible, so
the 15 SQL tasks cover the schema variety. These are hand-test tasks only;
Ashrith's sampler picks the real 300.
"""
import argparse
import json
import random
from pathlib import Path

KIT = Path(__file__).parent
SEED = 691


def pick_sql(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    rng = random.Random(SEED)
    out = []
    for diff in ("simple", "moderate", "challenging"):
        pool = [r for r in rows if r["difficulty"] == diff]
        rng.shuffle(pool)
        seen, chosen = set(), []
        for r in pool:  # first pass: distinct databases
            if r["db_id"] not in seen and len(chosen) < 5:
                chosen.append(r); seen.add(r["db_id"])
        out += chosen
    return out


def pick_qa(path):
    recs = json.load(open(path, encoding="utf-8"))
    rng = random.Random(SEED)
    out = []
    for typ in ("bridge", "comparison"):
        pool = [r for r in recs if r["type"] == typ]
        out += rng.sample(pool, 5)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--minidev", default=str(KIT / "mini_dev_prompt.jsonl"))
    ap.add_argument("--hotpot")
    a = ap.parse_args()
    lines = ["# Hand-test tasks", "", "## SQL (BIRD Mini-Dev)", "",
             "| # | qid | difficulty | db | question | command |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(pick_sql(a.minidev), 1):
        q = r["question"].replace("|", "/")
        lines.append(f"| {i} | {r['question_id']} | {r['difficulty']} | {r['db_id']} | {q} | "
                     f"`python -m pipelines.manual_run sql --qid {r['question_id']} --label flash` |")
    if a.hotpot:
        lines += ["", "## QA (HotpotQA distractor dev)", "", "| # | id | type | question | command |", "|---|---|---|---|---|"]
        for i, r in enumerate(pick_qa(a.hotpot), 1):
            q = r["question"].replace("|", "/")
            lines.append(f"| {i} | {r['_id']} | {r['type']} | {q} | "
                         f"`python -m pipelines.manual_run qa --hotpot {a.hotpot} --id {r['_id']} --label flash` |")
    else:
        lines += ["", "## QA", "", "Run again with `--hotpot <path>` once the HotpotQA file is in data/."]
    (KIT / "TASKS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
