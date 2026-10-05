【Instruction】
When executing the SQL below, a problem occurred. Please fix the SQL based on the question, the evidence and the database info.
Solve the task step by step if you need to. When you find an answer, verify it carefully.
Write the full corrected SQL in ONE ```sql code block at the end of your answer. Do not write any SQL code block after it.
【Constraints】
- In `SELECT <column>`, just select needed columns in the 【Question】 without any unnecessary column or value
- In `FROM <table>` or `JOIN <table>`, do not include unnecessary table
- If use max or min func, `JOIN <table>` FIRST, THEN use `SELECT MAX(<column>)` or `SELECT MIN(<column>)`
- If [Value examples] of <column> has 'None' or None, use `JOIN <table>` or `WHERE <column> is NOT NULL` is better
- If use `ORDER BY <column> ASC|DESC`, add `GROUP BY <column>` before to select distinct values
- Wrap column names that contain spaces or symbols in backticks, exactly as written in the schema
【Question】
-- {{question}}
【Evidence】
{{evidence}}
【Database info】
{{schema}}
【old SQL】
```sql
{{sql}}
```
【SQLite error】
{{sqlite_error}}
【Exception class】
{{exception_class}}
【Result preview】
{{result_preview}}

Now please fix the old SQL and generate the new SQL again.
【correct SQL】
