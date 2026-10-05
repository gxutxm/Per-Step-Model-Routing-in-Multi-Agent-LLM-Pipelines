"""Offline tests: no API calls. A scripted fake LLM stands in for the models.

Run from the repo root:  python -m pytest pipelines/tests -q
"""
import json
import sqlite3
from pathlib import Path

import jsonschema
import pytest

from pipelines.common.text import TemplateError, last_sql, parse_json_reply, placeholders, render
from pipelines.qa import steps as qa
from pipelines.sql import steps as sql

ROOT = Path(__file__).resolve().parents[2]
MINIDEV = ROOT / "testkit" / "mini_dev_prompt.jsonl"


def schema(pipeline: str, name: str) -> dict:
    return json.loads((ROOT / "pipelines" / pipeline / "schemas" / f"{name}.json").read_text())


def fake_llm(replies: dict):
    """replies: step -> list of replies, consumed in order. Records prompts."""
    calls = []

    def llm(step, prompt):
        calls.append((step, prompt))
        assert "{{" not in prompt, f"unfilled placeholder in {step}"
        return replies[step].pop(0)
    llm.calls = calls
    return llm


# ---------------------------------------------------------------- common

def test_render_strict():
    assert render("a {{x}} b", x=1) == "a 1 b"
    with pytest.raises(TemplateError):
        render("{{x}} {{y}}", x=1)
    with pytest.raises(TemplateError):
        render("{{x}}", x=1, y=2)
    assert render("{{x}}", x="{{y}}") == "{{y}}"  # values are not re-rendered


def test_parsers_tolerate_chatter():
    assert parse_json_reply('Sure!\n```json\n{"a": 1}\n```\nDone') == ({"a": 1}, True)
    assert parse_json_reply('here {"a": [1, 2]} ok') == ({"a": [1, 2]}, True)
    assert parse_json_reply("no json") == (None, False)
    assert last_sql("```sql\nSELECT 1\n```\n```sql\nSELECT 2;\n```") == ("SELECT 2", True)
    assert last_sql("```\nselect x from t\n```") == ("select x from t", True)
    assert last_sql("nothing") == ("", False)


@pytest.mark.parametrize("pipeline,names", [
    ("sql", ["selector", "decomposer", "refiner"]),
    ("qa", ["decomposer", "hop_reader", "composer", "formatter"]),
])
def test_prompt_placeholders_match_input_schemas(pipeline, names):
    for n in names:
        tpl = (ROOT / "pipelines" / pipeline / "prompts" / f"{n}.md").read_text()
        inputs = set(schema(pipeline, f"{n}.input")["properties"])
        if (pipeline, n) == ("qa", "hop_reader"):
            inputs = {"sub_question", "paragraphs"}
        if (pipeline, n) == ("qa", "composer"):
            inputs = {"question", "question_type", "hops"}
        assert placeholders(tpl) == inputs, n


def test_all_schemas_are_valid():
    for f in (ROOT / "pipelines").glob("*/schemas/*.json"):
        jsonschema.Draft202012Validator.check_schema(json.loads(f.read_text()))


# ---------------------------------------------------------------- SQL

@pytest.mark.skipif(not MINIDEV.exists(), reason="testkit/mini_dev_prompt.jsonl missing")
def test_minidev_schemas_roundtrip_and_tasks_valid():
    v = jsonschema.Draft202012Validator(schema("sql", "task"))
    for line in MINIDEV.open():
        row = json.loads(line)
        v.validate(row)
        assert sql.schema_to_ddl(sql.parse_schema(row["schema"])) == row["schema"].strip()


TOY_DDL = """CREATE TABLE client (
    client_id integer, -- example: [1, 2]
    gender text, -- F: female, M: male, example: ['M', 'F']
    birth_date date, -- example: ['1987-09-27']
    district_id integer, -- example: [1, 2]
    PRIMARY KEY (client_id),
    CONSTRAINT fk_client_district_id FOREIGN KEY (district_id) REFERENCES district (district_id)
);

CREATE TABLE district (
    district_id integer, -- example: [1, 2]
    A11 integer, -- average salary, example: [12541, 8114]
    PRIMARY KEY (district_id)
);

CREATE TABLE `Match` (
    id integer, -- example: [1]
    note text, -- example: ['x']
    PRIMARY KEY (id)
);"""


@pytest.fixture
def toy_db(tmp_path):
    p = tmp_path / "toy.sqlite"
    c = sqlite3.connect(p)
    c.executescript("""
        CREATE TABLE district (district_id INTEGER PRIMARY KEY, A11 INTEGER);
        CREATE TABLE client (client_id INTEGER PRIMARY KEY, gender TEXT, birth_date TEXT, district_id INTEGER);
        CREATE TABLE "Match" (id INTEGER PRIMARY KEY, note TEXT);
        INSERT INTO district VALUES (1, 12541), (2, 8114);
        INSERT INTO client VALUES (1, 'M', '1980-01-01', 2), (2, 'F', '1990-05-05', 2), (3, 'M', '1995-01-01', 1);
    """)
    c.commit()
    c.close()
    return p


TOY_TASK = {"question_id": 1, "db_id": "toy", "difficulty": "moderate", "SQL": "...",
            "question": "What is the gender of the youngest client in the lowest average salary branch?",
            "evidence": "Later birthdate refers to younger age; A11 refers to average salary",
            "schema": TOY_DDL}


def test_prune_keeps_keys_and_quoting():
    ddl, stats = sql.prune_schema(TOY_DDL, {"client": ["gender", "birth_date"], "district": "keep_all",
                                            "Match": "drop_all", "ghost": "keep_all"})
    assert "district_id integer" in ddl.split("CREATE TABLE district")[0]  # FK column kept in client
    assert "Match" not in ddl and stats["unknown"] == ["ghost"] and stats["tables_out"] == 2
    sql.parse_schema(ddl)  # still valid DDL
    ddl2, _ = sql.prune_schema(TOY_DDL, {"client": "keep_all"})  # omitted tables are kept
    assert "CREATE TABLE `Match`" in ddl2


def test_sql_pipeline_with_refine(toy_db):
    bad = "```sql\nSELECT gendr FROM client\n```"
    good = ("Sub question 1: ...\n```sql\nSELECT T1.gender FROM client AS T1 JOIN district AS T2 "
            "ON T1.district_id = T2.district_id ORDER BY T2.A11 ASC, T1.birth_date DESC LIMIT 1\n```\nQuestion Solved.")
    llm = fake_llm({
        sql.STEP_SELECTOR: ['```json\n{"client": "keep_all", "district": "keep_all", "Match": "drop_all"}\n```'],
        sql.STEP_DECOMPOSER: ["Sub question 1: gender?\n" + bad],
        sql.STEP_REFINER: [good],
    })
    trace = sql.run(TOY_TASK, llm, toy_db)
    jsonschema.validate(trace, schema("sql", "trace"))
    assert [s for s, _ in llm.calls] == [sql.STEP_SELECTOR, sql.STEP_DECOMPOSER, sql.STEP_REFINER]
    assert "no such column" in llm.calls[2][1]
    assert trace["refines"] == 1 and trace["stop_reason"] == "ok"
    assert sql.execute(trace["final_sql"], toy_db).rows == [("F",)]


def test_sql_pipeline_selector_garbage_falls_back(toy_db):
    llm = fake_llm({sql.STEP_SELECTOR: ["I think client is relevant."],
                    sql.STEP_DECOMPOSER: ["```sql\nSELECT gender FROM client WHERE client_id = 2\n```"]})
    trace = sql.run(TOY_TASK, llm, toy_db)
    jsonschema.validate(trace, schema("sql", "trace"))
    assert trace["steps"][0]["parse_ok"] is False
    assert "CREATE TABLE `Match`" in llm.calls[1][1]  # full schema used


def test_refine_triggers(toy_db):
    assert sql.needs_refine(sql.execute("SELECT * FROM client WHERE 0", toy_db)) == (True, "no data selected")
    assert sql.needs_refine(sql.execute("SELECT NULL", toy_db))[0] is True
    assert sql.needs_refine(sql.execute("SELECT 1", toy_db)) == (False, "")
    assert sql.execute("DELETE FROM client", toy_db).rows is None  # read-only


# ---------------------------------------------------------------- QA

TOY_HOTPOT = {
    "_id": "toy1", "type": "bridge", "level": "hard",
    "question": "The director of Moon Garden was born in which town?",
    "answer": "Riverton",
    "supporting_facts": [["Moon Garden", 1], ["Ana Field", 0]],
    "context": [
        ["Moon Garden", ["Moon Garden is a 2001 film.", "It was directed by Ana Field."]],
        ["Ana Field", ["Ana Field (born 1960 in Riverton) is a director."]],
        ["Sun Garden", ["Sun Garden is a 1999 film directed by Bo Lake."]],
        ["Bo Lake", ["Bo Lake was born in Hilltown."]],
        ["Riverton", ["Riverton is a town."]],
    ],
}


def test_bm25_and_refs():
    task = qa.from_hotpot(TOY_HOTPOT)
    jsonschema.validate(task, schema("qa", "task"))
    assert qa.retrieve(task, "Who directed Moon Garden?")[0]["title"] == "Moon Garden"
    assert qa.resolve_refs("Where was #1 born?", ["Ana Field"]) == "Where was Ana Field born?"
    assert qa.resolve_refs("Where was #2 born?", ["x"]) == "Where was #2 born?"


def test_qa_pipeline_happy_path():
    task = qa.from_hotpot(TOY_HOTPOT)
    llm = fake_llm({
        qa.STEP_DECOMPOSER: ['```json\n{"question_type": "bridge", "sub_questions": '
                             '["Who directed Moon Garden?", "In which town was #1 born?"]}\n```'],
        qa.STEP_HOP: ['{"answer": "Ana Field", "found": true, "evidence": [["Moon Garden", 1]]}',
                      '```json\n{"answer": "Riverton", "found": true, "evidence": [["Ana Field", 0]]}\n```'],
        qa.STEP_COMPOSER: ['{"reasoning": "Ana Field was born in Riverton.", "answer": "Riverton"}'],
        qa.STEP_FORMATTER: ['{"final_answer": "Riverton"}'],
    })
    trace = qa.run(task, llm)
    jsonschema.validate(trace, schema("qa", "trace"))
    assert trace["final_answer"] == "Riverton"
    assert "In which town was Ana Field born?" in llm.calls[2][1]  # #1 resolved before hop 2
    assert "[Ana Field] Ana Field (born 1960 in Riverton)" in llm.calls[3][1]


def test_qa_pipeline_fallbacks():
    task = qa.from_hotpot(TOY_HOTPOT)
    llm = fake_llm({qa.STEP_DECOMPOSER: ["no idea"], qa.STEP_HOP: ['{"answer": "Riverton", "found": true}'],
                    qa.STEP_COMPOSER: ["Riverton!"], qa.STEP_FORMATTER: ["???"]})
    trace = qa.run(task, llm)
    jsonschema.validate(trace, schema("qa", "trace"))
    assert [s["parse_ok"] for s in trace["steps"]] == [False, True, False, False]
    assert trace["final_answer"] == "Riverton"  # carried through the fallbacks
