import json, sqlite3, collections, statistics
import tiktoken

BIRD_FILE = "data/bird/minidev/MINIDEV/mini_dev_sqlite.json"
DB_DIR = "data/bird/minidev/MINIDEV/dev_databases"
HOTPOT_FILE = "data/hotpot/hotpot_dev_distractor_v1.json"

enc = tiktoken.get_encoding("cl100k_base")


def schema_text(db_id):
    con = sqlite3.connect(f"{DB_DIR}/{db_id}/{db_id}.sqlite")
    rows = con.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL").fetchall()
    con.close()
    return "\n".join(r[0] for r in rows)


bird = json.load(open(BIRD_FILE))
hotpot = json.load(open(HOTPOT_FILE))

bird_counts = collections.Counter(q["difficulty"] for q in bird)
hp_counts = collections.Counter(q["type"] for q in hotpot)

db_tokens = {d: len(enc.encode(schema_text(d))) for d in {q["db_id"] for q in bird}}
avg_per_db = statistics.mean(db_tokens.values())
avg_per_q = statistics.mean(db_tokens[q["db_id"]] for q in bird)

lines = [
    "# Data summary",
    "",
    "## BIRD Mini-Dev (SQLite), 500 questions",
    "BIRD labels difficulty as simple / moderate / challenging (not easy / moderate / hard).",
    "",
]
lines += [f"- {k}: {v}" for k, v in sorted(bird_counts.items())]
lines += [
    "",
    f"Average schema length (tiktoken cl100k_base): {avg_per_db:.0f} tokens per database "
    f"({len(db_tokens)} databases), {avg_per_q:.0f} tokens per question.",
    "",
    "## HotpotQA distractor dev, %d questions" % len(hotpot),
    "",
]
lines += [f"- {k}: {v}" for k, v in sorted(hp_counts.items())]
lines += [
    "",
    "## Samples (seed 42)",
    "- data/bird_sample_150.json: 44 simple, 75 moderate, 31 challenging",
    "- data/hotpot_sample_150.json: 120 bridge, 30 comparison",
]

text = "\n".join(lines)
print(text)
open("reports/data_summary.md", "w").write(text + "\n")
