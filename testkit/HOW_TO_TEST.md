# Hand-testing the prompts (task 4)

Goal: 15 SQL + 10 QA tasks through each pipeline on Gemini 3.5 Flash, to find
prompt problems **before** Week 2's 30-task pilot. You are looking for *where* things break,
not for a score.

## Setup (once)

From the repo root, Python 3.11+:

```bash
pip install pytest jsonschema
python -m pytest pipelines/tests -q        # should print: 13 passed
```

`testkit/mini_dev_prompt.jsonl` is the official BIRD Mini-Dev question file (500 questions, from github.com/bird-bench/mini_dev, CC BY-SA 4.0). `testkit/TASKS.md` lists the 15 SQL tasks (5 simple, 5 moderate, 5 challenging, spread
across 11 databases) with the exact command for each.

## SQL: paste mode (works today, no key needed)

1. Run the command from TASKS.md, e.g. `python -m pipelines.manual_run sql --qid 850 --label flash`.
2. The prompt prints and is saved under `testkit/runs/...`. Open the `.prompt.txt` file,
   copy all of it, and paste it into AI Studio (model: Gemini 3.5 Flash, temperature 0).
3. Copy the **whole** reply back into the terminal, then type `END` on its own line.
   Don't tidy the reply; parse failures are findings.
4. The script builds the next step's prompt from the reply. At the end it prints
   predicted vs gold SQL and adds a row to `testkit/results.csv`.

Without the databases, the run stops after the decomposer, so the refiner is not tested.
Once Ashrith has the BIRD databases, add `--db-dir <folder with <db_id>/<db_id>.sqlite>`.
That turns on execution, the refiner, and a quick result-match check.

## QA (once the HotpotQA file is in data/)

```bash
python testkit/pick_tasks.py --hotpot data/hotpot_dev_distractor_v1.json   # adds 10 QA tasks to TASKS.md
```

Then run the commands it lists. The flow is the same: 4 steps, and the hop reader runs once per
sub-question.

## Faster: auto mode (once your API key works)

```bash
pip install litellm
export GEMINI_API_KEY=...
python -m pipelines.manual_run sql --qid 850 --model gemini/<exact model id from AI Studio>
```

All 25 tasks take about 100 calls, well within the free tier. Run them once with Flash, then once with
Flash-Lite: that gives a first look at where the cheap model breaks, which is the project's question.

## What to write in the `notes` column

Name the **first** step that went wrong, and how:

| Step | Typical failure |
|---|---|
| sql.selector | dropped a table or column the gold SQL needs (compare with the gold SQL) |
| sql.decomposer | wrong column, wrong JOIN, wrong aggregation, ignored the evidence, extra columns in SELECT |
| sql.refiner | made a correct query worse, or "fixed" an empty result that was actually right |
| qa.decomposer | bad split; a comparison treated as a bridge question; names changed |
| retrieval | the right paragraph is missing from `retrieved` in trace.json |
| qa.hop_reader | wrong span, or a whole sentence instead of a short answer, or `found` is wrong |
| qa.composer | wrong comparison (dates and numbers), or ignored a correct hop answer |
| qa.formatter | changed the meaning, or the answer is too long for exact match |

Also note any reply that came back in the wrong *format* (no JSON, or two SQL blocks).
Each one needs a prompt fix.

## Bring to Sunday's sync

`results.csv` and your top 3 prompt fixes, each with the task that shows the problem.
