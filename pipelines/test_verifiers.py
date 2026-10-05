import json
from harness.verifiers import verify_sql, verify_qa

DB_DIR = "data/bird/minidev/MINIDEV/dev_databases"

bird = json.load(open("data/bird_sample_150.json"))
bad_sql = []
for q in bird:
    db = f"{DB_DIR}/{q['db_id']}/{q['db_id']}.sqlite"
    try:
        ok = verify_sql(db, q["SQL"], q["SQL"])
    except Exception as e:
        ok = False
        print("ERROR on", q["question_id"], e)
    if not ok:
        bad_sql.append(q["question_id"])
print(f"SQL: {len(bird) - len(bad_sql)}/{len(bird)} pass", bad_sql)

hp = json.load(open("data/hotpot_sample_150.json"))
bad_qa = [q["id"] for q in hp if not verify_qa(q["answer"], q["answer"])]
print(f"QA: {len(hp) - len(bad_qa)}/{len(hp)} pass", bad_qa)
