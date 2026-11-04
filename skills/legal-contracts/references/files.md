# DOCX, PDF and text

All files of a matter live in its folder: the user's originals in `input/` (never edited), deliverables in
`output/`, working files in `work/`. The scripts refuse to write inside the engine folder.

## Reading

Keep the original and its SHA-256 (record it in `intake.json` → `input_files`). For a DOCX take into account the
body, tables (nested too), headers and footers, footnotes and endnotes, comments, hyperlinks, fields, text boxes,
annexes and old revisions. `python-docx` `paragraphs` does not cover all of it. `docx_redline.py inspect` lists text
paragraphs per XML part and whether each is a safe edit target, but it does not replace reading every object and
note or a visual map of the document. Indexes start at zero, separately in each XML part; they do not match the
numbers of clauses or tables.

For a PDF extract text page by page (pypdf / pdfplumber from the engine's environment) and compare visually; check
tables and column order separately. If pages are scanned, check that OCR and its language packs (Romanian, Russian
or the original's language) are present. A local Tesseract / OCRmyPDF is fine; an external OCR only where sending
the data out is allowed. Never call OCR done because the program is installed.

Mark doubtful places `[OCR UNCERTAIN: p. …]` in the working transcript; never fill amounts, negations, article
numbers or names by guess. A material unreadable fragment keeps the conclusion conditional. A DOCX rebuilt from a
PDF or text is a separate, checked baseline for the redline, not the user's original Word file.

## Editing

A full Word or compatible editor with revisions is preferred for fields, new clauses, renumbering, tables,
footnotes, moved text, old revisions and complex formatting. Never accept existing revisions without a decision on
the baseline. Never edit a signed file in place; a cryptographic signature does not survive as a valid signature of
the new text.

`scripts/docx_redline.py` (lxml, no network):

- creates `w:del` with `w:delText`, `w:ins`, unique ids, an author and UTC time, and turns on `w:trackRevisions`;
- replaces or deletes one contiguous fragment in a simple paragraph, including text split over several runs; one
  operation per paragraph. An insertion is a replacement of a unique neighbouring fragment by its extension;
- keeps the formatting of deleted and untouched text; new text inherits the style of the first replaced run, which
  needs a visual check. Mixed formatting of new text needs an editor;
- keeps the ZIP content and every untouched part (relations, embedded files, tables, notes, comments). The clean
  copy accepts the new revisions; existing comments are kept and need a separate decision before delivery;
- refuses old revisions, a digital signature, macros, protection, a changed source paragraph, an ambiguous match,
  fields/links/comments/objects inside the target paragraph and structural edits. A refusal never permits deleting
  the unsupported object.

```bash
python3 <skill-dir>/scripts/docx_redline.py inspect <matter>/input/contract.docx > <matter>/work/inventory.json
python3 <skill-dir>/scripts/docx_redline.py apply <matter>/input/contract.docx <matter>/work/changes.json <matter>/output/redline-v1
python3 <skill-dir>/scripts/docx_redline.py verify <matter>/input/contract.docx <matter>/output/redline-v1/tracked.docx <matter>/output/redline-v1/clean.docx
```

`changes.json` (example in [`../assets/changes.json`](../assets/changes.json); its numbers are synthetic, not
recommended terms):

```json
{"author": "Legal review", "changes": [{"part": "word/document.xml", "paragraph": 2,
  "expected_paragraph": "Plata se efectuează în 10 zile.", "old": "10 zile", "new": "15 zile"}]}
```

Write a plan only for an agreed edit. The author is the role (for example "Legal review"), never a person's name
unless the user asks. The script translates no comments, takes no legal decision and does not recalculate Word
fields. The output folder must be new; nothing is overwritten; it appears only after verification passed.
In `apply`, "accept = clean" holds by construction (both come from the same edit); the real tests are
"reject = original" and `verify` on files edited outside the helper.

## Checking the result

Before the technical check do a separate editorial check by [romanian-drafting.md](romanian-drafting.md). The
register checker checks source records and `docx_redline.py verify` the structure of revisions; neither checks
person or legal register. Run `check_ro_style.py` on the final Word file too, so errors from a source template or a
repeated block do not slip through.

1. XML: real revisions with correct metadata; the clean copy has no revisions.
2. Accepting all supported revisions equals the clean copy in XML structure and formatting; rejecting them equals
   the original (technical run splits with the same properties are allowed).
3. Compare clause numbers, cross-references and fields, amounts, tables, notes, party details and annexes. After
   updating fields in an editor, compare again; the XML check does not prove dynamic fields right.
4. Render with Word or LibreOffice (+ Poppler for page images) and look at every page of the redline and the clean
   copy.
5. If Word is available, check on a copy that the revisions show and can be accepted and rejected. If only XML or
   LibreOffice was checked, say exactly that: Word UI compatibility is not confirmed by this test.
6. The clean legal text holds no report or reviewer's notes. Remove only your own analytical comments after the
   redline is saved; handle historical comments deliberately. The separate report is in the conversation language.

Coloured or struck-through text is not Track Changes. Without DOCX, rendering or OCR, deliver what is possible (a
draft, a table of edits) and name the missing operations.

Service JSON and CLI messages may be in English. Explain results and errors to the user in their language; never
paste unexplained diagnostics into a legal opinion.
