Given a 【Database schema】 description, a knowledge 【Evidence】 and the 【Question】, you need to use valid SQLite and understand the database and knowledge, and then decompose the question into subquestions for text-to-SQL generation.
When generating SQL, we should always consider constraints:
【Constraints】
- In `SELECT <column>`, just select needed columns in the 【Question】 without any unnecessary column or value
- In `FROM <table>` or `JOIN <table>`, do not include unnecessary table
- If use max or min func, `JOIN <table>` FIRST, THEN use `SELECT MAX(<column>)` or `SELECT MIN(<column>)`
- If [Value examples] of <column> has 'None' or None, use `JOIN <table>` or `WHERE <column> is NOT NULL` is better
- If use `ORDER BY <column> ASC|DESC`, add `GROUP BY <column>` before to select distinct values
- Wrap column names that contain spaces or symbols in backticks, exactly as written in the schema
【Output format】
- Write each sub question as "Sub question N: ...", followed by its SQL in a ```sql code block.
- The SQL of the LAST sub question must answer the whole 【Question】 on its own.
- End with the line "Question Solved."

==========

【Database schema】
CREATE TABLE frpm (
    CDSCode text, -- example: ['01100170109835', '01100170112607']
    `Charter School (Y/N)` integer, -- 0: N, 1: Y, example: [1, 0]
    `Enrollment (Ages 5-17)` real, -- example: [5271.0, 4734.0]
    `Free Meal Count (Ages 5-17)` real, -- eligible free rate = Free Meal Count / Enrollment, example: [3864.0, 2637.0]
    PRIMARY KEY (CDSCode)
);

CREATE TABLE satscores (
    cds text, -- California Department Schools, example: ['10101080000000', '10101080109991']
    sname text, -- school name, example: ['Middle College High', 'John F. Kennedy High']
    NumTstTakr integer, -- Number of Test Takers in this school, example: [24305, 4942]
    AvgScrMath integer, -- average scores in Math, example: [699, 698]
    NumGE1500 integer, -- Number of Test Takers Whose Total SAT Scores Are Greater or Equal to 1500; Excellence Rate = NumGE1500 / NumTstTakr, example: [5837, 2125]
    PRIMARY KEY (cds),
    CONSTRAINT fk_satscores_cds FOREIGN KEY (cds) REFERENCES frpm (CDSCode)
);
【Question】
List school names of charter schools with an SAT excellence rate over the average.
【Evidence】
Charter schools refers to `Charter School (Y/N)` = 1 in the table frpm; Excellence rate = NumGE1500 / NumTstTakr


Decompose the question into sub questions, considering 【Constraints】, and generate the SQL after thinking step by step:
Sub question 1: Get the average value of SAT excellence rate of charter schools.
SQL
```sql
SELECT AVG(CAST(T2.`NumGE1500` AS REAL) / T2.`NumTstTakr`)
    FROM frpm AS T1
    INNER JOIN satscores AS T2
    ON T1.`CDSCode` = T2.`cds`
    WHERE T1.`Charter School (Y/N)` = 1
```

Sub question 2: List out school names of charter schools with an SAT excellence rate over the average.
SQL
```sql
SELECT T2.`sname`
  FROM frpm AS T1
  INNER JOIN satscores AS T2
  ON T1.`CDSCode` = T2.`cds`
  WHERE T2.`sname` IS NOT NULL
  AND T1.`Charter School (Y/N)` = 1
  AND CAST(T2.`NumGE1500` AS REAL) / T2.`NumTstTakr` > (
    SELECT AVG(CAST(T4.`NumGE1500` AS REAL) / T4.`NumTstTakr`)
    FROM frpm AS T3
    INNER JOIN satscores AS T4
    ON T3.`CDSCode` = T4.`cds`
    WHERE T3.`Charter School (Y/N)` = 1
  )
```

Question Solved.

==========

【Database schema】
CREATE TABLE account (
    account_id integer, -- the id of the account, example: [11382, 11362]
    district_id integer, -- location of branch, example: [77, 76]
    frequency text, -- frequency of the account, example: ['POPLATEK MESICNE', 'POPLATEK TYDNE']
    `date` date, -- the creation date of the account, example: ['1997-12-29', '1997-12-28']
    PRIMARY KEY (account_id),
    CONSTRAINT fk_account_district_id FOREIGN KEY (district_id) REFERENCES district (district_id)
);

CREATE TABLE client (
    client_id integer, -- the unique number, example: [13998, 13971]
    gender text, -- F: female, M: male, example: ['M', 'F']
    birth_date date, -- birth date, example: ['1987-09-27', '1986-08-13']
    district_id integer, -- location of branch, example: [77, 76]
    PRIMARY KEY (client_id),
    CONSTRAINT fk_client_district_id FOREIGN KEY (district_id) REFERENCES district (district_id)
);

CREATE TABLE district (
    district_id integer, -- location of branch, example: [77, 76]
    A4 text, -- number of inhabitants, example: ['95907', '95616']
    A11 integer, -- average salary, example: [12541, 11277]
    PRIMARY KEY (district_id)
);
【Question】
What is the gender of the youngest client who opened account in the lowest average salary branch?
【Evidence】
Later birthdate refers to younger age; A11 refers to average salary

Decompose the question into sub questions, considering 【Constraints】, and generate the SQL after thinking step by step:
Sub question 1: What is the district_id of the branch with the lowest average salary?
SQL
```sql
SELECT `district_id`
  FROM district
  ORDER BY `A11` ASC
  LIMIT 1
```

Sub question 2: What is the youngest client who opened account in the lowest average salary branch?
SQL
```sql
SELECT T1.`client_id`
  FROM client AS T1
  INNER JOIN district AS T2
  ON T1.`district_id` = T2.`district_id`
  ORDER BY T2.`A11` ASC, T1.`birth_date` DESC
  LIMIT 1
```

Sub question 3: What is the gender of the youngest client who opened account in the lowest average salary branch?
SQL
```sql
SELECT T1.`gender`
  FROM client AS T1
  INNER JOIN district AS T2
  ON T1.`district_id` = T2.`district_id`
  ORDER BY T2.`A11` ASC, T1.`birth_date` DESC
  LIMIT 1
```
Question Solved.

==========

【Database schema】
{{schema}}
【Question】
{{question}}
【Evidence】
{{evidence}}

Decompose the question into sub questions, considering 【Constraints】, and generate the SQL after thinking step by step:
