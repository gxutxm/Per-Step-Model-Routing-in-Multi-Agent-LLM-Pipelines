# Pipelines (owner: Gautam)

Two pipelines. They are what we measure, not what we ship. Both expose one function:

```python
trace = sql.steps.run(task, llm, db_path)   # Pipeline A
trace = qa.steps.run(task, llm)             # Pipeline B
```

`llm(step, prompt) -> reply` comes from the harness (Krishna). The harness asks the policy
(fixed / random / oracle / router) which model serves `step`, checks the cache, calls the
model, and logs the call. The pipelines never pick a model.

| Pipeline | Routable steps (the `step` names the router sees) |
|---|---|
| A. Text-to-SQL | `sql.selector`, `sql.decomposer`, `sql.refiner` (runs 0–2 times) |
| B. Multi-hop QA | `qa.decomposer`, `qa.hop_reader` (1–3 calls), `qa.composer`, `qa.formatter` |

Each step: prompt template in `prompts/`, input/output JSON Schemas in `schemas/`, and
render/parse functions in `steps.py`. The parsers never raise. A reply that can't be
parsed sets `parse_ok: false` and the step falls back as listed below. Those events are
data for the fragility analysis.

| Step | Fallback when the reply can't be parsed |
|---|---|
| sql.selector | use the full schema |
| sql.decomposer | stop, task fails (no SQL) |
| sql.refiner | keep the old SQL and try again (still counts toward the 2-refine limit) |
| qa.decomposer | one hop = the original question |
| qa.hop_reader | empty answer, `found: false` |
| qa.composer | last hop's answer |
| qa.formatter | composer's answer unchanged |

## Pipeline A: what we kept from MAC-SQL and what we changed

Source: Wang et al., *MAC-SQL: A Multi-Agent Collaborative Framework for Text-to-SQL*
(COLING 2025), code at github.com/wbbeyourself/MAC-SQL (`core/const.py`, `core/agents.py`).

**Kept:** the three roles and their order; the constraint list, word for word; the
few-shot examples (same questions and SQL); the decomposer's sub-question format with the
last SQL block as the answer; the refine triggers (SQLite error, empty result, NULL in the
result); no refine on timeout.

**Changed, and why:**
1. **The selector always runs.** MAC-SQL skips it when a database has ≤ 6 columns per
   table on average and ≤ 30 in total. We want every task to have the same routable steps.
2. **Schema format.** We use the official per-question DDL from BIRD Mini-Dev
   (`mini_dev_prompt.jsonl`, `schema` field) instead of MAC-SQL's list format. The few-shot
   schemas were converted to the same DDL style so examples and real input match.
3. **Selector rules.** Dropped "include at least 3 tables" (meaningless for small
   databases). Tables the model leaves out are kept, and key columns are always kept, so
   JOINs stay possible.
4. **Refiner.** It also sees a preview of the first 5 result rows, must finish with one
   ```sql block, and runs at most 2 times (MAC-SQL allows 3 rounds). SQL runs read-only,
   with a 30 s limit.
5. **Bug not copied.** MAC-SQL skips refining any SQL that contains the text "error"
   (for example a column named `error_code`).

## Pipeline B design

HotpotQA distractor setting: each question comes with 10 paragraphs (2 relevant and 8
distractors), so no web search is needed. BM25 picks the top 3 paragraphs per hop and is
not an LLM step. Bridge hops write `#1` for the answer of hop 1. It is replaced before
retrieval, so a wrong hop 1 answer visibly sends hop 2 to the wrong paragraphs, which is
exactly the propagation we want to measure. The hop reader cites `[title, sentence]`
pairs that line up with HotpotQA's `supporting_facts`, so we can tell *which* hop failed
first, not only that the final answer was wrong. The few-shot examples are our own,
not HotpotQA questions.

## Decisions to confirm at the Sunday sync

- **Few-shot overlap.** The MAC-SQL examples use the `financial` and `california_schools`
  databases, which hold 62 of the 500 Mini-Dev questions. None of the example questions
  are in Mini-Dev (checked). Proposal: keep them for fidelity and note it in the report.
- **No provider JSON mode.** All three models get the identical prompt and the same
  lenient parser. Gemini's JSON mode and vLLM's guided decoding would make the tiers
  differ in more than the model itself.
- **Reasoning settings (Krishna).** Qwen3: `enable_thinking=False` in the chat template.
  Gemini: one fixed thinking budget for all calls. Freeze both in Week 2.

## Tests

```bash
pip install pytest jsonschema
python -m pytest pipelines/tests -q              # 13 tests, offline, about 1 s
python -m pipelines.make_schemas                 # regenerate schemas/*.json after editing
```
