"""Writes the JSON Schemas for every step's input and output.

Edit the dicts here and rerun `python -m pipelines.make_schemas`; the .json
files are generated so the two pipelines stay consistent. Step inputs are the
fields that get rendered into the prompt; step outputs are what the parser
returns after reading the model's reply (not the raw reply).
"""
import json
from pathlib import Path

D = "https://json-schema.org/draft/2020-12/schema"
ROOT = Path(__file__).parent


def obj(props: dict, required: list | None = None, title: str = "", desc: str = "") -> dict:
    s = {"$schema": D, "type": "object", "properties": props,
         "required": required if required is not None else list(props), "additionalProperties": False}
    if title:
        s["title"] = title
    if desc:
        s["description"] = desc
    return s


STR = {"type": "string"}
NESTR = {"type": "string", "minLength": 1}
BOOL = {"type": "boolean"}
INT0 = {"type": "integer", "minimum": 0}
TITLE_IDX = {"type": "array", "prefixItems": [STR, INT0], "items": False, "minItems": 2}
PARAGRAPH = obj({"title": STR, "sentences": {"type": "array", "items": STR}})
STEP_BASE = {"step": STR, "parse_ok": BOOL}

QA = {
    "task": obj({
        "task_id": NESTR, "question": NESTR,
        "type": {"enum": ["bridge", "comparison"]},
        "level": {"type": ["string", "null"]},
        "paragraphs": {"type": "array", "items": PARAGRAPH, "minItems": 1},
        "gold_answer": STR,
        "supporting_facts": {"type": "array", "items": TITLE_IDX},
    }, title="QA task", desc="One HotpotQA distractor question in our format (steps.from_hotpot)."),

    "decomposer.input": obj({"question": NESTR}, title="qa.decomposer input"),
    "decomposer.output": obj({
        "question_type": {"enum": ["bridge", "comparison"]},
        "sub_questions": {"type": "array", "items": NESTR, "minItems": 1, "maxItems": 3,
                          "description": "Bridge hops may contain #1, #2 = answer of an earlier hop."},
    }, title="qa.decomposer output"),

    "retrieval.output": obj({
        "resolved_question": NESTR,
        "retrieved": {"type": "array", "items": STR, "maxItems": 3, "description": "Paragraph titles, best first."},
    }, title="BM25 retrieval output (not an LLM step, logged for analysis)"),

    "hop_reader.input": obj({
        "sub_question": {**NESTR, "description": "After #k substitution."},
        "paragraphs": {"type": "array", "items": PARAGRAPH, "minItems": 1, "maxItems": 3},
    }, title="qa.hop_reader input"),
    "hop_reader.output": obj({
        "answer": STR, "found": BOOL,
        "evidence": {"type": "array", "items": TITLE_IDX,
                     "description": "[paragraph title, sentence index]; comparable to HotpotQA supporting_facts."},
    }, title="qa.hop_reader output"),

    "composer.input": obj({
        "question": NESTR, "question_type": {"enum": ["bridge", "comparison"]},
        "hops": {"type": "array", "minItems": 1, "items": obj({
            "resolved_question": NESTR, "answer": STR, "found": BOOL,
            "sentences": {"type": "array", "items": STR}})},
    }, title="qa.composer input"),
    "composer.output": obj({"answer": STR, "reasoning": STR}, title="qa.composer output"),

    "formatter.input": obj({"question": NESTR, "draft_answer": STR}, title="qa.formatter input"),
    "formatter.output": obj({"final_answer": STR}, title="qa.formatter output"),
}

QA["trace"] = obj({
    "task_id": NESTR, "pipeline": {"const": "qa"}, "final_answer": STR,
    "steps": {"type": "array", "items": {"oneOf": [
        obj({**STEP_BASE, "step": {"const": "qa.decomposer"}, "output": QA["decomposer.output"]}),
        obj({**STEP_BASE, "step": {"const": "qa.hop_reader"}, "output": obj({
            **QA["hop_reader.output"]["properties"], "sub_question": NESTR,
            **QA["retrieval.output"]["properties"], "sentences": {"type": "array", "items": STR}})}),
        obj({**STEP_BASE, "step": {"const": "qa.composer"}, "output": QA["composer.output"]}),
        obj({**STEP_BASE, "step": {"const": "qa.formatter"}, "output": QA["formatter.output"]}),
    ]}},
}, title="QA pipeline trace", desc="Returned by qa.steps.run; one per task per model assignment.")

SELECTION = {"type": "object", "additionalProperties": {"oneOf": [
    {"enum": ["keep_all", "drop_all"]}, {"type": "array", "items": STR}]}}

SQL = {
    "task": {"$schema": D, "title": "SQL task",
             "description": "One row of BIRD Mini-Dev mini_dev_prompt.jsonl (extra fields allowed).",
             "type": "object", "required": ["question_id", "db_id", "question", "evidence", "SQL", "schema", "difficulty"],
             "properties": {"question_id": INT0, "db_id": NESTR, "question": NESTR, "evidence": STR,
                            "SQL": NESTR, "schema": NESTR,
                            "difficulty": {"enum": ["simple", "moderate", "challenging"]}}},
    "selector.input": obj({"db_id": NESTR, "schema": NESTR, "question": NESTR, "evidence": STR},
                          title="sql.selector input"),
    "selector.output": {**SELECTION, "$schema": D, "title": "sql.selector output",
                        "description": "table -> keep_all | drop_all | [columns]. Missing tables are kept."},
    "decomposer.input": obj({"schema": NESTR, "question": NESTR, "evidence": STR},
                            title="sql.decomposer input", desc="schema = pruned DDL after the selector."),
    "decomposer.output": obj({"sub_questions": {"type": "array", "items": STR}, "final_sql": STR},
                             title="sql.decomposer output"),
    "refiner.input": obj({"question": NESTR, "evidence": STR, "schema": NESTR, "sql": STR,
                          "sqlite_error": NESTR, "exception_class": STR, "result_preview": STR},
                         title="sql.refiner input"),
    "refiner.output": obj({"sql": STR}, title="sql.refiner output"),
}
SQL["trace"] = obj({
    "task_id": INT0, "pipeline": {"const": "sql"}, "final_sql": STR, "stop_reason": STR, "refines": INT0,
    "steps": {"type": "array", "items": {"oneOf": [
        obj({**STEP_BASE, "step": {"const": "sql.selector"}, "output": {"oneOf": [SELECTION, {"type": "null"}]},
             "stats": {"type": "object"}}),
        obj({**STEP_BASE, "step": {"const": "sql.decomposer"}, "output": SQL["decomposer.output"]}),
        obj({**STEP_BASE, "step": {"const": "sql.refiner"}, "attempt": INT0, "trigger": STR,
             "output": SQL["refiner.output"]}),
    ]}},
}, required=["task_id", "pipeline", "final_sql", "stop_reason", "steps"], title="SQL pipeline trace")


def strip_nested(s):
    """Nested copies must not repeat $schema/title."""
    if isinstance(s, dict):
        return {k: strip_nested(v) for k, v in s.items() if k not in ("$schema",)}
    if isinstance(s, list):
        return [strip_nested(v) for v in s]
    return s


def main():
    for name, group in (("qa", QA), ("sql", SQL)):
        out = ROOT / name / "schemas"
        out.mkdir(exist_ok=True)
        for key, schema in group.items():
            s = {"$schema": D, **strip_nested(schema)}
            (out / f"{key}.json").write_text(json.dumps(s, indent=2) + "\n")
        print(f"wrote {len(group)} schemas to {out}")


if __name__ == "__main__":
    main()
