import os, sqlite3, tempfile
from harness.verifiers import verify_sql, verify_qa

# tiny throwaway database: values 1, 1, 2 (note the duplicate)
fd, db = tempfile.mkstemp(suffix=".sqlite")
os.close(fd)
con = sqlite3.connect(db)
con.execute("CREATE TABLE t (a INTEGER)")
con.executemany("INSERT INTO t VALUES (?)", [(1,), (1,), (2,)])
con.commit()
con.close()

checks = [
    # SQL: (description, result, expected)
    ("same query passes", verify_sql(db, "SELECT a FROM t", "SELECT a FROM t"), True),
    ("row order ignored when gold has no ORDER BY",
     verify_sql(db, "SELECT a FROM t ORDER BY a DESC", "SELECT a FROM t"), True),
    ("row order enforced when gold has ORDER BY",
     verify_sql(db, "SELECT a FROM t ORDER BY a DESC", "SELECT a FROM t ORDER BY a"), False),
    ("duplicate rows matter",
     verify_sql(db, "SELECT DISTINCT a FROM t", "SELECT a FROM t"), False),
    ("wrong rows fail", verify_sql(db, "SELECT 99", "SELECT a FROM t"), False),
    ("syntax error fails", verify_sql(db, "SELEC a FROM t", "SELECT a FROM t"), False),
    ("missing table fails", verify_sql(db, "SELECT a FROM nope", "SELECT a FROM t"), False),
    ("write attempt fails (read-only)",
     verify_sql(db, "DELETE FROM t", "SELECT a FROM t"), False),
    # QA
    ("case ignored", verify_qa("YES", "yes"), True),
    ("article ignored", verify_qa("The Beatles", "Beatles"), True),
    ("punctuation ignored", verify_qa("St. Louis", "St Louis"), True),
    ("yes vs no fails", verify_qa("no", "yes"), False),
    ("wrong answer fails", verify_qa("Paris", "London"), False),
    ("padded yes fails", verify_qa("yes it is", "yes"), False),
    ("partial name fails", verify_qa("Obama", "Barack Obama"), False),
    ("empty prediction fails", verify_qa("", "yes"), False),
]

failed = 0
for name, got, want in checks:
    status = "ok  " if got == want else "FAIL"
    if got != want:
        failed += 1
    print(status, name, "(got", got, "expected", want, ")")

os.remove(db)
print(f"\n{len(checks) - failed}/{len(checks)} checks behave as expected")
