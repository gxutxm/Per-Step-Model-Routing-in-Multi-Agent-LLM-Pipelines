As an experienced and professional database administrator, your task is to analyze a user question and a database schema and keep only the tables and columns needed to write SQL for the question.

【Instructions】
1. Discard any table that is not related to the user question and evidence.
2. For each relevant table, sort its columns by relevance to the question and keep the top 6.
3. If a relevant table has 10 or fewer columns, mark it "keep_all".
4. If a table is completely irrelevant to the question and evidence, mark it "drop_all".
5. Keep a table if it is needed only to JOIN two relevant tables. If you are unsure about a table, keep it.
6. Primary key and foreign key columns are kept automatically, so you do not need to list them.
7. Every table in the schema must appear in your answer. Use table and column names exactly as written in the schema, without backticks.
8. Answer with one JSON object inside a ```json code block, then write "Question Solved." and nothing else.

Here is a typical example:

==========
【DB_ID】 banking_system
【Schema】
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

CREATE TABLE loan (
    loan_id integer, -- the id number identifying the loan data, example: [4959, 4960]
    account_id integer, -- the id number identifying the account, example: [10, 80]
    `date` date, -- the date when the loan is approved, example: ['1998-07-12', '1998-04-19']
    amount integer, -- approved amount, example: [1567, 7877]
    duration integer, -- loan duration in months, example: [60, 48]
    payments real, -- monthly payment, example: [3456, 8972]
    status text, -- repayment status, example: ['C', 'A']
    PRIMARY KEY (loan_id),
    CONSTRAINT fk_loan_account_id FOREIGN KEY (account_id) REFERENCES account (account_id)
);

CREATE TABLE district (
    district_id integer, -- location of branch, example: [77, 76]
    A2 text, -- district name, example: ['Hl.m. Praha', 'Benesov']
    A4 text, -- number of inhabitants, example: ['95907', '95616']
    A5 integer, -- number of municipalities with inhabitants < 499, example: [0, 1]
    A6 integer, -- number of municipalities with inhabitants 500-1999, example: [0, 26]
    A7 integer, -- number of municipalities with inhabitants 2000-9999, example: [0, 6]
    A8 integer, -- number of municipalities with inhabitants > 10000, example: [1, 2]
    A9 integer, -- number of cities, example: [1, 5]
    A10 real, -- ratio of urban inhabitants, example: [100.0, 46.7]
    A11 integer, -- average salary, example: [12541, 8507]
    A12 real, -- unemployment rate 1995, example: [0.2, 1.6]
    A13 real, -- unemployment rate 1996, example: [0.43, 1.85]
    A15 integer, -- number of committed crimes 1995, example: [85677, 2159]
    PRIMARY KEY (district_id)
);
【Question】
What is the gender of the youngest client who opened account in the lowest average salary branch?
【Evidence】
Later birthdate refers to younger age; A11 refers to average salary
【Answer】
```json
{
  "account": "keep_all",
  "client": "keep_all",
  "loan": "drop_all",
  "district": ["district_id", "A11", "A2", "A4", "A6", "A7"]
}
```
Question Solved.

==========

Here is a new example, please start answering:

【DB_ID】 {{db_id}}
【Schema】
{{schema}}
【Question】
{{question}}
【Evidence】
{{evidence}}
【Answer】
