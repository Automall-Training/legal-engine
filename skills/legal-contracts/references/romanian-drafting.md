# Romanian legal register and text review

Read when drafting, auditing or editing Romanian contracts, annexes, standard terms (TCG), DPAs and the package
agreed with them.

## Register by genre

In the operative terms of a contract use the name of the defined party in the third person: `Furnizorul`,
`Prestatorul`, `Beneficiarul`, `Operatorul`. Keep one term for one role; do not swap `Furnizorul` for `Operatorul`
outside data processing. Do not mix the contract with a brand's voice: `anulăm`, `restituim`, `noi`, `nostru`. A
general writing tip to use "I/we when appropriate" does not set the style of a contract; the chosen legal genre does.

In a related privacy or cookie notice the third person identifies the responsible legal entity without doubt.
Addressing a person as `dumneavoastră` is acceptable in a standalone notice when that style was chosen. The user's
explicit instruction to keep another voice wins. This is an editorial standard, not a claim that the first person
makes a contract void.

Keep the first person where it belongs, in a signatory's individual declaration: `Solicit expres…`,
`Îmi exprim acordul…`, `Confirm că…`. Never turn a client's declaration of will into a supplier's statement. Do not
rewrite an exact quote of a law, interface text or an accepted offer to unify the voice. Check its purpose and
limits; quotation marks or a file named `formulare` are not an exemption for the whole text.

## Edit without changing obligations

Example: `Dacă anulăm un serviciu…, restituim…` → `Dacă Furnizorul anulează un serviciu…, acesta restituie…`. Check
that the condition, the object of the refund, the term, negations, modality, exceptions and the other party's
rights stay the same. Never add an amount, an obligation or a right to withdraw as part of a style edit. If it is
unclear which company "we" means, establish the role from the document; never assign it by a mass replacement.

Re-read imperative forms addressed to the client in contract clauses. Operative provisions can be stated through the
actions and rights of `Beneficiarul` or `consumatorul`; buttons and signed declarations keep the person they need.
Avoid an impersonal construction that hides the responsible party.

## Check before delivery

1. Make an explicit list of files: all contract text, tables, annexes and each party's repeated versions. Do not
   limit it to the changed paragraphs or to one member of a family of files.
2. Run `check_ro_style.py` on the source Romanian text and then on the final clean DOCX files. In a document with
   revisions it reads the accepted version: deleted fragments in the history need no "fix". The script changes
   nothing.
3. Review each hit in context. Fix the form or keep a pointed exception with `id`, `text_sha256`, `role`, `reason`
   from the report. No empty reasons, no exceptions for a whole folder, no automatic pass for all quotes. When the
   paragraph changes, the old decision becomes invalid.
4. Run the check again. A non-zero exit means unresolved hits, incomplete coverage of objects or an invalid
   decision; it is not a test of legal validity. List and review unread images and OLE objects separately.
5. Re-read the full final text for terminology, person, agreement, genre and preserved meaning, then do the usual
   Word check of all pages. Zero lexical hits never replace this editorial reading.

```bash
python3 <skill-dir>/scripts/check_ro_style.py <matter>/output/contract.ro.md <matter>/output/anexa.ro.md --root <matter> --report <matter>/output/style-source.json
python3 <skill-dir>/scripts/check_ro_style.py <matter>/output/redline-v1/clean.docx --root <matter> --review <matter>/output/style-decisions.json --report <matter>/output/style-final.json
```

Decisions file: `{"exceptions": [{"id": "<id from the report>", "text_sha256": "<hash from the report>",
"role": "personal_declaration", "reason": "The signatory's own request for early start; not a supplier's promise."}]}`.
Other roles: `interface_label`, `quoted_source`, `user_selected_voice`, `false_positive`. The `--profile notice`
does not flag the second person of a notice but still looks for the first person. The script uses a finite word
list and does not promise to catch every Romanian form.

The delivery report keeps four results apart: check of the applicable rules, editorial check, OOXML / Track
Changes, visual check. Success of the last two is never presented as confirming the first two.
