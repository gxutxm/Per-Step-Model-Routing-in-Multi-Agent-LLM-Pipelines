# Data summary

## BIRD Mini-Dev (SQLite), 500 questions
BIRD labels difficulty as simple / moderate / challenging (not easy / moderate / hard).

- challenging: 102
- moderate: 250
- simple: 148

Average schema length (tiktoken cl100k_base): 786 tokens per database (11 databases), 833 tokens per question.

## HotpotQA distractor dev, 7405 questions

- bridge: 5918
- comparison: 1487

## Samples (seed 42)
- data/bird_sample_150.json: 44 simple, 75 moderate, 31 challenging
- data/hotpot_sample_150.json: 120 bridge, 30 comparison

## Notes
- BIRD question 1526 was replaced by 281 (same difficulty: challenging). The 1526 question asks about a customer who paid 634.8, but its gold SQL filters on 1513.12, so the gold answer is NULL. pipelines/replace_bad_questions.py does the swap and must run after sample_tasks.py.
- After the swap, all 150 BIRD gold queries return non-empty, non-NULL results.
- SQL verifier: result rows compared as a multiset (duplicates matter), order enforced only when the gold query contains ORDER BY. The ORDER BY check is a regex on the gold text, so an ORDER BY inside a subquery can trigger it. Queries are read-only with a 30 second timeout.
- QA verifier: SQuAD-style normalization, pass if exact match or token F1 >= 0.8.
- Schema length counts CREATE statements only (no column descriptions or sample values), using tiktoken cl100k_base as an approximation for Qwen.
- HotpotQA came from the Hugging Face copy (hotpotqa/hotpot_qa, distractor, validation) because the CMU server was down. Its ID field is `id`.
- Tests: python -m pipelines.test_verifiers (gold vs gold) and python -m pipelines.test_verifiers_negative (16 checks that wrong answers fail).
