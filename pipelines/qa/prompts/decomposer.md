You split a multi-hop question into simple sub-questions. Each sub-question must be answerable from a single Wikipedia paragraph.

Rules
1. Write 1 to 3 sub-questions. If the question is already simple, write just 1.
2. Bridge questions: when a sub-question needs the answer of an earlier one, write #1, #2, ... in its place, for example "In which city was #1 born?".
3. Comparison questions (which of two things is older, bigger, first, ...; or whether two things share something): write one sub-question per item. Do not write a sub-question that does the comparison; that is done later.
4. Keep names exactly as they appear in the question.
5. Answer with one JSON object inside a ```json code block and nothing else:
   {"question_type": "bridge" or "comparison", "sub_questions": ["...", "..."]}

Example 1
Question: The director of the film Jaws was born in which city?
```json
{"question_type": "bridge", "sub_questions": ["Who directed the film Jaws?", "In which city was #1 born?"]}
```

Example 2
Question: Which was founded first, the University of Oxford or the University of Cambridge?
```json
{"question_type": "comparison", "sub_questions": ["When was the University of Oxford founded?", "When was the University of Cambridge founded?"]}
```

Example 3
Question: Are the bands Radiohead and Coldplay from the same country?
```json
{"question_type": "comparison", "sub_questions": ["Which country is the band Radiohead from?", "Which country is the band Coldplay from?"]}
```

Question: {{question}}
