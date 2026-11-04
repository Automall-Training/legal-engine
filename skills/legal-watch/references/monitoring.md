# Monitoring: a run, its statuses and the digest

`watch run [--acts all|p1|<ids>] [--dry-run]` reads every watched act from its official source, compares it with
the version held, stores a new text when it differs, writes `laws/runs/<date>/run.json` and `digest.md`, and
flags dependent contract clauses. `--dry-run` writes the run files but no state, texts or flags.

## Sources

| Kind | Site | What is read |
|---|---|---|
| `legis_md` | www.legis.md (Moldova, State Register of Legal Acts) | the act's card: amendments with their dates, the bar of versions, repeal. A `doc_id` points to one version; later versions are listed on its page |
| `just_ro` | legislatie.just.ro (Romania, Legislative Portal) | the act's heading and its list of consolidations, delayed application dates, repeal notes; when the portal fails, an archived copy (Wayback Machine) is read and marked as such |
| `eurlex` | EUR-Lex and the Publications Office (EU) | in-force status, consolidated versions and their dates |
| Moldovan Official Gazette | monitorul.gov.md | new issues since the last run; items whose title names a watched act are **signals** to check that act, not changes |

## Statuses of an act

| Status | Meaning | Checked? |
|---|---|---|
| `baseline` | first reading: the version in force is recorded | yes |
| `unchanged` | the version in force equals the one held | yes |
| `new_in_force` | a newer version is in force | yes, a change |
| `new_future` | a version with a later start date was published | yes, a change of kind `future` |
| `repealed` | the act is repealed | yes, a change |
| `fetch_failed` | the site did not answer | **no** |
| `blocked_403` | the site blocked automatic access (anti-bot page) | **no** |
| `parse_failed` | the page could not be read reliably, or the reader is not yet calibrated on this site | **no** |
| `stale_fallback` | only an archived copy was read | **no** |

A reading is accepted only from a reader calibrated on a live page of that site. A change found by an
uncalibrated reader is reported as *possible*: it does not move the held version and flags no contract until it is
confirmed by hand.

**Result of the run:** `OK` (every p1 act checked, no change) → exit 0; `CHANGES` → exit 1; `INCOMPLETE` (a p1
act not verified) → exit 2. Only `OK` allows the words "no changes".

## Host check (the agent reads the page)

For each act left not verified that the user wants closed now:

1. Open the official page (from the catalog's `official_url` or the act's source) with the host's web tools; if
   they are blocked, the user's own browser through the browser tools.
2. Fill a version card as in `<legal-research>/references/version-check.md`, `scope: "text"`, `held_version` =
   the version in `watch show`. Save the text read next to the card and give `text_file` and `text_sha256`.
3. `python3 <legal-research>/scripts/check_version.py <card> --root <folder>` must pass; then
   `watch record --card <card> --root <folder>`. The act joins today's run as checked by hand (`via: host`); the
   digest is rewritten.

A card that is not from today, fails its checker, or is `not_verified` changes nothing.

## The digest

`laws/runs/<date>/digest.md`, in the language of the watchlist: the result line, changes (confirmed first),
contracts to re-review with the proposed matter, acts not verified with the reason and the offer to check them by
hand, first readings, Official Gazette signals, and the date of the last complete run (a weekly schedule that has
not completed for 9 days is marked overdue). When talking to the user, translate it into consequences: what the
change does for their firms, from when, and the simplest lawful way to adapt.
