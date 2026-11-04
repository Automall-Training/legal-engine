# Structure of the act and issuing a transaction package

Applies to an authorised restructuring of commercial contracts, standard terms (TCG) and annexes. It completes the
chosen model card; it does not impose the same architecture on an NDA, a notice or fixed official clauses.

## Why the style check is not enough

A text can pass the grammatical-person check and still be hard to use: obligations without their own address, many
topics in one paragraph, scattered commercial fields, incompatible branches and unreconciled totals. Register,
structure, legal meaning, figures and pagination are separate checks. Passing one never closes the others.

## Structure before drafting

1. Keep the internal library apart from the copy for the client. Establish which documents are actually issued and
   on what condition. Never call a package with all firms, courses and variants "ready to sign".
2. In the body of the contract give each autonomous obligation a stable number, for example 4.1, 4.2. Group by
   subject: delivery, access, changes, price, rights, data, termination. Do not split each sentence mechanically: a
   condition and its exception stay with their rule.
3. Use a commercial sheet for the parameters of the deal, a specification for the services and a payment schedule
   only if there are instalments. Keep one source for price, places, currency and terms; references in the other
   acts point to that source and never create independent values.
4. Tables have one field or one service per row, clear units and real space to fill in. An item not included is
   written as such. Never turn an unknown field into zero, "unlimited" or an invented promise.
5. Check the sum of the components after discounts, the instalments, the rounding and the number of services. Keep
   apart the total included, the maximum frequency, the duration and the scheduling interval. A monthly cap is not a
   service guaranteed every month.
6. Read any model also as a commercial proposal. Voluntary warranties, waivers of rights, penalties, refund amounts
   and terms are never imported as mere formatting. Name the substantive changes and their basis; keep mandatory
   rights and contracts already accepted.
7. For B2B/B2C variants keep the classification by the real purpose, not only by the form of the person. An issued
   copy holds only the applicable branch and the selected course or service. Notices and individual declarations are
   separate; the organisation's signature never replaces the individual's choices.

## Mandatory control of the result

- Old → new map: no obligation, condition, exception, reference or form disappears silently. Substantive changes
  are kept apart from renumbering and moves.
- Search numeric references in all dependent documents, including separate acceptances, TCG and forms. Check the
  target and the meaning, not only that the number exists.
- Run `check_structure.py` on each restructured contract source. Review manually the flagged dense paragraphs, all
  tables and external references. The script checks only its Markdown conventions (`## N` articles, `N.M` clauses)
  and the arithmetic of an explicitly supplied JSON manifest; it does not read law and proves no compliance.
- For figures use a checked manifest with `total`, optional `components` and `installments` (decimal amounts as
  strings); `deliveries` may declare `total`, `periods` and `per_period_cap`. `cap × periods` is a maximum, not an
  implied total. Never put a manifest with invented values into the client's package.
- Check tables and signatures visually: repeated headers, readable rows, signature and date together, no isolated
  blocks on nearly empty pages.
- When comparing or reusing Word blocks, equal text does not prove an equal role: a heading may repeat a table of
  contents entry. Check style, numbering and the start of each act, not only the text; separate consecutive tables
  with a real paragraph so their headers do not merge. Compare the kept parts of the package too, not only the text
  projection of the revisions.
- If data for issuing is missing, deliver the fillable models and selection instructions. Label their state exactly
  and keep the questions in the matter, without hiding the gaps.

```bash
python3 <skill-dir>/scripts/check_structure.py <matter>/output/contract.ro.md --commercial <matter>/output/manifest.json --report <matter>/output/structure.json
```

## Own structural model

The [commercial sheet and annexes](../templates/transaction-pack.ro.md) are this engine's own editorial structure,
with no predefined amounts, periods or warranties. Use them with the relevant commercial model card and the law
checked for the deal. It is not an official act and does not justify the applicability of any clause.
