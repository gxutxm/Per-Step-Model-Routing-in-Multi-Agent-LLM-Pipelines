"""Pipeline A: Text-to-SQL, 3 LLM steps, after MAC-SQL (Wang et al., COLING 2025).

    Selector  -> keeps relevant tables/columns        (step "sql.selector")
    Decomposer-> sub-questions + SQL, last SQL wins   (step "sql.decomposer")
    Refiner   -> fixes SQL that errors / returns
                 nothing / returns NULLs, max 2 times  (step "sql.refiner")

`run(task, llm, db_path)` is the whole pipeline. `llm(step, prompt) -> reply`
is supplied by the harness, so the router decides the model per step and the
cache/logger see every call. Everything else here is pure and testable.

Task format = one row of BIRD Mini-Dev `mini_dev_prompt.jsonl`:
    question_id, db_id, question, evidence, SQL (gold), schema (DDL), difficulty
"""
from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pipelines.common.text import last_sql, load_template, parse_json_reply, render

PROMPTS = Path(__file__).parent / "prompts"
STEP_SELECTOR, STEP_DECOMPOSER, STEP_REFINER = "sql.selector", "sql.decomposer", "sql.refiner"
MAX_REFINES = 2
EXEC_TIMEOUT_S = 30
PREVIEW_ROWS = 5

LLM = Callable[[str, str], str]

# --------------------------------------------------------------------------- schema


@dataclass
class Table:
    name: str
    columns: list[tuple[str, str]] = field(default_factory=list)  # (name, original line)
    tail: list[str] = field(default_factory=list)                  # PRIMARY KEY / CONSTRAINT lines
    key_columns: set[str] = field(default_factory=set)
    raw_name: str = ""                                             # as written, e.g. `Match`


_CREATE = re.compile(r"^CREATE TABLE\s+(`[^`]+`|\S+)\s*\($")
_COL = re.compile(r"^\s{4}(`[^`]+`|[^\s,]+)\s")
_PAREN_COLS = re.compile(r"\(([^)]*)\)")


def _unquote(name: str) -> str:
    return name.strip().strip("`")


def parse_schema(ddl: str) -> list[Table]:
    """Parse the Mini-Dev DDL format into tables. Raises ValueError if the
    format is not what we expect (that is a data bug, not a model error)."""
    tables: list[Table] = []
    cur: Table | None = None
    for line in ddl.splitlines():
        m = _CREATE.match(line.strip())
        if m:
            cur = Table(_unquote(m.group(1)), raw_name=m.group(1))
            tables.append(cur)
            continue
        if cur is None or not line.strip():
            continue
        if line.strip() == ");":
            cur = None
            continue
        body = line.strip()
        if body.startswith(("PRIMARY KEY", "CONSTRAINT", "FOREIGN KEY", "UNIQUE")):
            cur.tail.append(line.rstrip().rstrip(","))
            first = _PAREN_COLS.search(body)  # columns of this table in the key
            if first:
                cur.key_columns |= {_unquote(c) for c in first.group(1).split(",")}
            continue
        cm = _COL.match(line)
        if not cm:
            raise ValueError(f"unrecognised schema line: {line!r}")
        cur.columns.append((_unquote(cm.group(1)), line.rstrip()))
    if not tables:
        raise ValueError("no CREATE TABLE found")
    return tables


def _strip_trailing_comma(line: str) -> str:
    # "    col text, -- comment"  ->  "    col text -- comment"  (last column only)
    return re.sub(r",(\s*--)", r"\1", line, count=1) if "--" in line else line.rstrip(",")


def _add_trailing_comma(line: str) -> str:
    if "--" in line:
        head, _, comment = line.partition("--")
        return head.rstrip().rstrip(",") + ", --" + comment
    return line.rstrip().rstrip(",") + ","


def schema_to_ddl(tables: list[Table]) -> str:
    out = []
    for t in tables:
        name = t.raw_name or t.name
        lines = [line for _, line in t.columns] + t.tail
        fixed = [_add_trailing_comma(l) if i < len(lines) - 1 else _strip_trailing_comma(l)
                 for i, l in enumerate(lines)]
        out.append(f"CREATE TABLE {name} (\n" + "\n".join(fixed) + "\n);")
    return "\n\n".join(out)


def prune_schema(ddl: str, selection: dict | None) -> tuple[str, dict]:
    """Apply a selector answer to the DDL.

    selection: {table: "keep_all" | "drop_all" | [columns]}. Tables the model
    left out are kept whole (conservative). Unknown names are ignored. Key
    columns are always kept so JOINs stay possible. Returns (ddl, stats)."""
    tables = parse_schema(ddl)
    if not selection:
        return ddl, {"tables_in": len(tables), "tables_out": len(tables), "unknown": [], "omitted": []}
    by_lower = {k.strip().strip("`").lower(): v for k, v in selection.items()}
    known = {t.name.lower() for t in tables}
    unknown = sorted(k for k in by_lower if k not in known)
    kept: list[Table] = []
    omitted = []
    for t in tables:
        choice = by_lower.get(t.name.lower())
        if choice is None:
            omitted.append(t.name)
            kept.append(t)
        elif choice == "drop_all":
            continue
        elif choice == "keep_all" or not isinstance(choice, list):
            kept.append(t)
        else:
            want = {_unquote(str(c)).lower() for c in choice} | {k.lower() for k in t.key_columns}
            cols = [(n, l) for n, l in t.columns if n.lower() in want]
            kept.append(Table(t.name, cols or t.columns, t.tail, t.key_columns, t.raw_name))
    if not kept:  # model dropped everything: an error we can't recover from by pruning
        return ddl, {"tables_in": len(tables), "tables_out": len(tables), "unknown": unknown,
                     "omitted": omitted, "dropped_everything": True}
    return schema_to_ddl(kept), {"tables_in": len(tables), "tables_out": len(kept),
                                 "unknown": unknown, "omitted": omitted}


# --------------------------------------------------------------------------- execution


@dataclass
class ExecResult:
    rows: list[tuple] | None
    error: str = ""
    exception_class: str = ""
    seconds: float = 0.0
    timed_out: bool = False


def execute(sql: str, db_path: str | Path, timeout_s: float = EXEC_TIMEOUT_S) -> ExecResult:
    """Run SQL read-only with a wall-clock limit."""
    t0 = time.monotonic()
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.text_factory = lambda b: b.decode(errors="ignore")
    conn.set_progress_handler(lambda: int(time.monotonic() - t0 > timeout_s), 10_000)
    try:
        rows = conn.execute(sql).fetchall()
        return ExecResult(rows, seconds=time.monotonic() - t0)
    except sqlite3.OperationalError as e:
        timed_out = time.monotonic() - t0 > timeout_s
        return ExecResult(None, "query timed out" if timed_out else " ".join(map(str, e.args)),
                          type(e).__name__, time.monotonic() - t0, timed_out)
    except Exception as e:  # noqa: BLE001 - any failure is information for the refiner
        return ExecResult(None, " ".join(map(str, e.args)), type(e).__name__, time.monotonic() - t0)
    finally:
        conn.close()


def needs_refine(res: ExecResult) -> tuple[bool, str]:
    """MAC-SQL's rule: refine on an error, on an empty result, or on NULLs in
    the result. Timeouts are not refined (MAC-SQL behaviour)."""
    if res.timed_out:
        return False, res.error
    if res.rows is None:
        return True, res.error
    if len(res.rows) == 0:
        return True, "no data selected"
    if any(v is None for row in res.rows[:PREVIEW_ROWS] for v in row):
        return True, "exist None value, you can add `NOT NULL` in SQL"
    return False, ""


def preview(res: ExecResult) -> str:
    if res.rows is None:
        return "(query failed, no rows)"
    if not res.rows:
        return "(0 rows)"
    shown = "\n".join(str(r) for r in res.rows[:PREVIEW_ROWS])
    return f"{len(res.rows)} rows, first {min(PREVIEW_ROWS, len(res.rows))}:\n{shown}"


# --------------------------------------------------------------------------- steps


def render_selector(task: dict) -> str:
    return render(load_template(PROMPTS / "selector.md"), db_id=task["db_id"], schema=task["schema"],
                  question=task["question"], evidence=task.get("evidence") or "None")


def parse_selector(reply: str) -> tuple[dict | None, bool]:
    obj, ok = parse_json_reply(reply)
    if not ok:
        return None, False
    clean = {}
    for k, v in obj.items():
        if v in ("keep_all", "drop_all"):
            clean[str(k)] = v
        elif isinstance(v, list) and all(isinstance(c, str) for c in v):
            clean[str(k)] = v
        else:
            return None, False
    return clean, True


def render_decomposer(task: dict, schema: str) -> str:
    return render(load_template(PROMPTS / "decomposer.md"), schema=schema,
                  question=task["question"], evidence=task.get("evidence") or "None")


_SUBQ = re.compile(r"Sub question\s*(\d+)\s*:\s*(.+)")


def parse_decomposer(reply: str) -> tuple[dict, bool]:
    sql, ok = last_sql(reply)
    subqs = [m.group(2).strip() for m in _SUBQ.finditer(reply or "")]
    return {"sub_questions": subqs, "final_sql": sql}, ok


def render_refiner(task: dict, schema: str, sql: str, res: ExecResult, error: str) -> str:
    return render(load_template(PROMPTS / "refiner.md"), question=task["question"],
                  evidence=task.get("evidence") or "None", schema=schema, sql=sql,
                  sqlite_error=error, exception_class=res.exception_class or "None",
                  result_preview=preview(res))


def parse_refiner(reply: str) -> tuple[str, bool]:
    return last_sql(reply)


# --------------------------------------------------------------------------- pipeline


def run(task: dict, llm: LLM, db_path: str | Path | None) -> dict:
    """Run the whole pipeline. Returns a trace dict (see schemas/trace.json).
    db_path=None runs selector + decomposer only (for prompt testing without
    the BIRD databases); the refiner needs a database to execute against."""
    trace: dict = {"task_id": task["question_id"], "pipeline": "sql", "steps": []}

    # 1. Selector (always runs; MAC-SQL skips it for small DBs, see README).
    reply = llm(STEP_SELECTOR, render_selector(task))
    selection, ok = parse_selector(reply)
    schema, stats = prune_schema(task["schema"], selection if ok else None)
    trace["steps"].append({"step": STEP_SELECTOR, "parse_ok": ok, "output": selection, "stats": stats})

    # 2. Decomposer
    reply = llm(STEP_DECOMPOSER, render_decomposer(task, schema))
    dec, ok = parse_decomposer(reply)
    trace["steps"].append({"step": STEP_DECOMPOSER, "parse_ok": ok, "output": dec})
    sql = dec["final_sql"]
    if not ok:
        trace.update(final_sql="", stop_reason="decomposer produced no SQL")
        return trace

    if db_path is None:
        trace.update(final_sql=sql, stop_reason="not executed (no database)")
        return trace

    # 3. Refiner loop
    for attempt in range(MAX_REFINES + 1):
        res = execute(sql, db_path)
        refine, error = needs_refine(res)
        if not refine or attempt == MAX_REFINES:
            trace.update(final_sql=sql, stop_reason=error or "ok", refines=attempt)
            return trace
        reply = llm(STEP_REFINER, render_refiner(task, schema, sql, res, error))
        new_sql, ok = parse_refiner(reply)
        trace["steps"].append({"step": STEP_REFINER, "parse_ok": ok, "attempt": attempt + 1,
                               "trigger": error, "output": {"sql": new_sql}})
        if ok:
            sql = new_sql
    raise AssertionError("unreachable")
