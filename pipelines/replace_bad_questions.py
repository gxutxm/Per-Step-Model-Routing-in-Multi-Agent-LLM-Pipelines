"""Swap known-bad BIRD gold questions for valid ones of the same difficulty.

Run after sample_tasks.py. Deterministic (seed 42 + 1).
1526: the question says the customer paid 634.8, but the gold SQL filters on 1513.12,
so the gold answer is NULL.
"""
import json, random, sqlite3, threading

SEED = 42
BAD = {1526}
D = "data/bird/minidev/MINIDEV/dev_databases"

full = json.load(open("data/bird/minidev/MINIDEV/mini_dev_sqlite.json"))
sample = json.load(open("data/bird_sample_150.json"))
used = {q["question_id"] for q in sample}


def ok(q, timeout=10):
    con = sqlite3.connect(f"file:{D}/{q['db_id']}/{q['db_id']}.sqlite?mode=ro", uri=True)
    timer = threading.Timer(timeout, con.interrupt)
    timer.start()
    try:
        rows = con.execute(q["SQL"]).fetchall()
    except Exception:
        return False
    finally:
        timer.cancel()
        con.close()
    return bool(rows) and not all(all(v is None for v in r) for r in rows)


rng = random.Random(SEED + 1)
out = []
for q in sample:
    if q["question_id"] in BAD:
        pool = [x for x in full
                if x["difficulty"] == q["difficulty"]
                and x["question_id"] not in used
                and x["question_id"] not in BAD]
        rng.shuffle(pool)
        new = None
        for cand in pool:
            print("trying", cand["question_id"], flush=True)
            if ok(cand):
                new = cand
                break
        if new is None:
            raise SystemExit("no valid replacement found")
        used.add(new["question_id"])
        print("replaced", q["question_id"], "->", new["question_id"])
        out.append(new)
    else:
        out.append(q)

json.dump(out, open("data/bird_sample_150.json", "w"), indent=1)
print("total", len(out))
