Rewrite the draft answer into the shortest form that answers the question, the way a quiz answer key would.

Rules
1. Yes/no question: exactly "yes" or "no".
2. "Which of A or B" question: copy A or B exactly as it is written in the question.
3. Otherwise: only the name, date, number or place. No sentence, no explanation, no trailing period.
4. Never change what the answer means. If the draft is already short, return it unchanged.
5. Answer with one JSON object inside a ```json code block and nothing else:
   {"final_answer": "..."}

Examples
Question: Which was founded first, the University of Oxford or the University of Cambridge?
Draft answer: Oxford was founded first, around 1096.
```json
{"final_answer": "University of Oxford"}
```

Question: Are the bands Radiohead and Coldplay from the same country?
Draft answer: Yes, both bands are from England.
```json
{"final_answer": "yes"}
```

Question: The director of the film Jaws was born in which city?
Draft answer: Steven Spielberg was born in Cincinnati, Ohio.
```json
{"final_answer": "Cincinnati"}
```

Question: {{question}}
Draft answer: {{draft_answer}}
