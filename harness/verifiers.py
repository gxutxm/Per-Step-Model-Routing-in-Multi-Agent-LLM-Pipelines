import re, string, sqlite3, collections, threading

# ---------- SQL ----------
def _run(db_path, sql, timeout=30):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    timer = threading.Timer(timeout, con.interrupt)
    timer.start()
    try:
        return con.execute(sql).fetchall()
    finally:
        timer.cancel()
        con.close()


def verify_sql(db_path, pred_sql, gold_sql):
    try:
        pred = _run(db_path, pred_sql)
    except Exception:
        return False
    gold = _run(db_path, gold_sql)
    if re.search(r"\border\s+by\b", gold_sql, re.I):
        return pred == gold
    return collections.Counter(pred) == collections.Counter(gold)


# ---------- QA ----------
def normalize(s):
    s = s.lower()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def exact_match(pred, gold):
    return normalize(pred) == normalize(gold)


def f1(pred, gold):
    p, g = normalize(pred).split(), normalize(gold).split()
    common = collections.Counter(p) & collections.Counter(g)
    same = sum(common.values())
    if same == 0:
        return 0.0
    prec, rec = same / len(p), same / len(g)
    return 2 * prec * rec / (prec + rec)


def verify_qa(pred, gold, threshold=0.8):
    return exact_match(pred, gold) or f1(pred, gold) >= threshold
