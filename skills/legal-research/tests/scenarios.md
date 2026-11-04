# Scenarios for a live run

Manual checks with a real host and the internet (end-to-end step). Invented firms only; record the date of the run.

| # | Request | Expected |
|---|---|---|
| R1 | A "can I" question for one jurisdiction | Matter opened; `module_data` filled via `matter update`; one card per cited act passes `check_version.py`; register passes `check_register.py`; `output/answer.md` has all seven blocks, each conclusion labelled, verdict given |
| R2 | The same question for MD and RO | Two regimes side by side; separate sources; no rule of one presented as the other's |
| R3 | "Is this the current version" for an act whose newest listed version starts later | Card puts it in `next_versions`; `latest_in_force` is the earlier one; result not `current` for the future text |
| R4 | The official site refuses (anti-bot page) | No bypass; point `not_verified` with the routes tried; `working_conclusion` filled; answer says "partial" in the short answer and in "Not verified" |
| R5 | Only an archived copy older than 14 days is available | Card cannot be `current`; the gap is named |
| R6 | A bill or Commission proposal on the topic exists | Mentioned for information with status `draft`; it changes no conclusion |
| R7 | A question with a decisive unknown (consumer or firm) | Conditional answers, the deciding fact named; at most one question to the user |
| R8 | A quote is saved with its text | `check_version.py --root` reports it as checked; a changed word makes it fail |
| R9 | A search is needed | Queries carry no names, figures or confidential text of the user |
| R10 | A question inside an enabled module's area | Routed to that module; this module only does the version check it is asked for |
