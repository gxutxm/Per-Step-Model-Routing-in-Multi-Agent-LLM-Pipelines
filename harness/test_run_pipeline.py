"""Offline tests for run_pipeline.

These tests replace ``litellm.completion`` with fake replies, so they need
no API key, no GPU, no network, and no BIRD databases.

From the repository root:

    python -m unittest discover -s harness -t . -p "test_*.py"
"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from harness.test_harness import HarnessTestCase, fake_response
from run_pipeline import load_sql_task, run_pipeline, run_sql_trace

QID = 1471  # debit_card_specializing
SELECTOR_REPLY = '```json\n{"customers": "keep_all"}\n```'
BAD_SQL_REPLY = "Sub question 1: ratio?\n```sql\nSELECT missing_column FROM customers\n```"
GOOD_SQL_REPLY = "Sub question 1: ratio?\n```sql\nSELECT COUNT(*) FROM customers\n```"


class RunPipelineTests(HarnessTestCase):
    def setUp(self):
        super().setUp()
        os.environ["GEMINI_API_KEY"] = "test-key"

    def replies(self, *texts):
        self.completion.side_effect = [fake_response(t) for t in texts]

    def test_all_flash_returns_sql(self):
        self.replies(SELECTOR_REPLY, GOOD_SQL_REPLY)
        sql = run_pipeline("sql", QID, "flash", db_dir=None)
        self.assertEqual(sql, "SELECT COUNT(*) FROM customers")
        models = [c.kwargs["model"] for c in self.completion.call_args_list]
        self.assertEqual(models, ["gemini/gemini-3.5-flash"] * 2)

    def test_per_step_models_are_used(self):
        self.replies(SELECTOR_REPLY, GOOD_SQL_REPLY)
        trace = run_sql_trace(QID, {"sql.selector": "flash-lite", "sql.decomposer": "flash",
                                    "sql.refiner": "flash"}, db_dir=None)
        self.assertEqual([c["model"] for c in trace["calls"]], ["flash-lite", "flash"])
        self.assertEqual([c["step"] for c in trace["calls"]], ["sql.selector", "sql.decomposer"])

    def test_refiner_runs_against_the_database(self):
        task = load_sql_task(QID)
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / task["db_id"] / f"{task['db_id']}.sqlite"
            db.parent.mkdir()
            with sqlite3.connect(db) as conn:
                conn.execute("CREATE TABLE customers (CustomerID INTEGER, Currency TEXT)")
                conn.execute("INSERT INTO customers VALUES (1, 'EUR')")
            conn.close()
            self.replies(SELECTOR_REPLY, BAD_SQL_REPLY, GOOD_SQL_REPLY)
            trace = run_sql_trace(QID, "flash", db_dir=folder)
        self.assertEqual(trace["final_sql"], "SELECT COUNT(*) FROM customers")
        self.assertEqual([c["step"] for c in trace["calls"]],
                         ["sql.selector", "sql.decomposer", "sql.refiner"])
        self.assertEqual(trace["refines"], 1)

    def test_no_sql_returns_empty_string(self):
        self.replies(SELECTOR_REPLY, "I cannot answer this.")
        self.assertEqual(run_pipeline("sql", QID, "flash", db_dir=None), "")

    def test_sample_row_without_schema_is_completed(self):
        task = load_sql_task({"question_id": QID, "question": "ignored"})
        self.assertIn("CREATE TABLE", task["schema"])

    def test_bad_config_is_rejected(self):
        with self.assertRaises(ValueError):
            run_pipeline("sql", QID, "gpt")
        with self.assertRaises(ValueError):
            run_pipeline("sql", QID, {"sql.selector": "flash"})
        with self.assertRaises(ValueError):
            run_pipeline("qa", QID, "flash")
        self.completion.assert_not_called()


if __name__ == "__main__":
    unittest.main()
