# Hand-test tasks

## SQL (BIRD Mini-Dev)

| # | qid | difficulty | db | question | command |
|---|---|---|---|---|---|
| 1 | 850 | simple | formula_1 | Please give the name of the race held on the circuits in Germany. | `python -m pipelines.manual_run sql --qid 850 --label flash` |
| 2 | 1361 | simple | student_club | What is the total cost of the pizzas for all the events? | `python -m pipelines.manual_run sql --qid 1361 --label flash` |
| 3 | 5 | simple | california_schools | How many schools with an average score in Math greater than 400 in the SAT test are exclusively virtual? | `python -m pipelines.manual_run sql --qid 5 --label flash` |
| 4 | 592 | simple | codebase_community | How many users are awarded with more than 5 badges? | `python -m pipelines.manual_run sql --qid 592 --label flash` |
| 5 | 424 | simple | card_games | What proportion of cards do not have a text box with a normal layout? | `python -m pipelines.manual_run sql --qid 424 --label flash` |
| 6 | 1529 | moderate | debit_card_specializing | What is the amount spent by customer "38508" at the gas stations? How much had the customer spent in January 2012? | `python -m pipelines.manual_run sql --qid 1529 --label flash` |
| 7 | 604 | moderate | codebase_community | What is the average of the up votes and the average user age for users creating more than 10 posts? | `python -m pipelines.manual_run sql --qid 604 --label flash` |
| 8 | 79 | moderate | california_schools | Between San Diego and Santa Barbara, which county offers the most number of schools that does not offer physical building? Indicate the amount. | `python -m pipelines.manual_run sql --qid 79 --label flash` |
| 9 | 99 | moderate | financial | Among the accounts who have loan validity more than 12 months, list out the accounts that have the highest approved amount and have account opening date in 1993. | `python -m pipelines.manual_run sql --qid 99 --label flash` |
| 10 | 1227 | moderate | thrombosis_prediction | What is the average age of the male patient with high cholesterol? | `python -m pipelines.manual_run sql --qid 1227 --label flash` |
| 11 | 218 | challenging | toxicology | What percentage of carcinogenic-type molecules does not contain fluorine? | `python -m pipelines.manual_run sql --qid 218 --label flash` |
| 12 | 760 | challenging | superhero | In superheroes with height between 150 to 180, what is the percentage of heroes published by Marvel Comics? | `python -m pipelines.manual_run sql --qid 760 --label flash` |
| 13 | 1171 | challenging | thrombosis_prediction | How many underage patients were examined during the course of the three-year period from 1990 to 1993? | `python -m pipelines.manual_run sql --qid 1171 --label flash` |
| 14 | 1094 | challenging | european_football_2 | How much higher in percentage is Ariel Borysiuk's overall rating than that of Paulin Puel? | `python -m pipelines.manual_run sql --qid 1094 --label flash` |
| 15 | 415 | challenging | card_games | What percentage of cards with format commander and legal status do not have a content warning? | `python -m pipelines.manual_run sql --qid 415 --label flash` |

## QA

Run again with `--hotpot <path>` once the HotpotQA file is in data/.
