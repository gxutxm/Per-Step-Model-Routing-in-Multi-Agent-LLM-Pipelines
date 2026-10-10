"""Run gold SQL queries against their BIRD SQLite databases and confirm they return rows.

Run from the repository root:  python -m pipelines.check_gold_queries
Needs the data from:           python -m pipelines.download_data
"""
import json
import random
import sqlite3
import sys
import threading
from pathlib import Path

ROOT = Path("data/bird/minidev/MINIDEV")
QUESTIONS = ROOT / "mini_dev_sqlite.json"
DB_DIR = ROOT / "dev_databases"
N = 5
SEED = 42
TIMEOUT = 30


def run_gold(db_id, sql):
    db_path = DB_DIR / db_id / f"{db_id}.sqlite"
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    timer = threading.Timer(TIMEOUT, con.interrupt)
    timer.start()
    try:
        return con.execute(sql).fetchall()
    finally:
        timer.cancel()
        con.close()


def main():
    questions = json.load(open(QUESTIONS))
    picked = random.Random(SEED).sample(questions, N)
    failures = 0
    for q in picked:
        try:
            rows = run_gold(q["db_id"], q["SQL"])
            ok = bool(rows) and not all(all(v is None for v in r) for r in rows)
            detail = f"{len(rows)} rows, first: {str(rows[0])[:60]}" if rows else "0 rows"
        except Exception as e:
            ok, detail = False, f"error: {e}"
        failures += not ok
        print("PASS" if ok else "FAIL", q["question_id"], q["db_id"], q["difficulty"], detail)
    print(f"\n{N - failures}/{N} gold queries executed and returned results")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
