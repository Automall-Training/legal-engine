# Draft, audit, edit

All three start after intake, the choice of law and the law check, and follow `legal-workflow/references/norms.md`
(side, path first, three layers, risk weight, minimum first, clause test, "where" rule).

## Draft

Before the skeleton pick the relevant card from the [model library](models/catalog.md) (or a sample from the user's
`<profile>/templates/`). In the working report record the model id, the source and section, what was taken as
structure, what was added independently and what was excluded because of another regime; also put it in
`module_data.structure_sources`. Do not load every original. No fitting model → build your own structure and say
plainly that there is no checked structural analogue; never substitute an unrelated official form.

Build the structure by the kind of deal. Establish the required terms and formalities from verified rules; mark
ordinary practice separately. Fill in only what is confirmed. Subject, result, acceptance, price, term and
termination must agree with one another. List incomplete fields separately. A draft with legally material gaps is
called a draft, not a document ready to sign.

## Audit

Read the whole document and the annexes first. Give each clause a stable address: number/heading, page and a short
fragment when needed. For a missing term give the place of insertion. Check the module's special questions and
overall consistency: definitions, references, terms, amounts, order of precedence, annexes and signatures. Never
claim full coverage from sampled pages.

Compare coverage with the fitting model card. A missing typical section is not by itself a breach of law: check
whether this deal needs it. Never import someone else's percentages, terms, consents and risk allocation as a
"standard".

For each material point fill in (this is the clause table of `norms.md` §10):

1. Id and the clause or missing provision.
2. Problem and its concrete consequence.
3. Facts and assumptions the conclusion needs.
4. Legal basis with `source_id`, article, version, link, date; or "contractual recommendation".
5. Proposed wording in the document language (Romanian by default).
6. Type: mandatory fix (a rule requires it; name the sanction or "no sanction") / prudent reading / risk reduction /
   editorial. A prudent reading is never presented as mandatory.
7. Priority and weight: critical (blocks the stated goal or validity), high, medium, low — with the reason:
   sanction, authority, qualitative likelihood of enforcement, market practice. No invented percentages.
8. How to do it lawfully: the path that lets the represented party do what it wants; "not possible" only for a
   direct prohibition, and then with an alternative.
9. Verification status and the open question.

Put the material risks first; never hide an unverified rule at the end. If only an audit was ordered, do not change
the original; put proposed clauses in the report ([`../templates/audit-report.md`](../templates/audit-report.md)).

## Edit and adapt

Fix the source version and the commercial constraints (`module_data.agreed_constraints`). Make a map
"clause → old text → new text → reason/source". Edit locally; do not rewrite the whole contract for cosmetics. More
obligations, a waiver of a right, a liability cap and a change of forum each need a separate explanation; agreed
terms are not changed without an instruction.

For a style edit apply [romanian-drafting.md](romanian-drafting.md) to the whole declared package. Compare the old
and the new meaning, including negations, conditions, terms and the person bound. An earlier clean text is not
editorially checked just because it was once rendered or its hashes checked.

Unknown decisions become options or fields. The clean document holds no analytical comments, risk register or
phrases like "the law needs checking" inside an operative clause; fact fields are allowed only in a document
clearly marked as a draft.

For a source DOCX keep its structure and history as in [files.md](files.md). For a PDF or text first create a
checked DOCX of the baseline transcription, then the redline against it; say plainly that the edits compare with the
rebuilt version, not with the binary PDF.

Deliver the redline, the clean copy and a separate report. Material insertions are in the document language;
explanations and comments in the user's language. An editorial improvement is never presented as a mandatory legal
fix.
