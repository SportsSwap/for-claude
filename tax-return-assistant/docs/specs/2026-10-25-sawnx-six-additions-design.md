# Sawnx: six additions (design)

Date: 25 Oct 2026. Status: agreed with the owner in chat, not yet built.
Builds on `2026-10-14-tax-return-assistant-design.md` (binding) and `2026-10-18-sawnx-design.md`.

## What the owner asked for

1. Read emails (`.eml`, and `.msg` saved from Outlook): the text and the attachments, and pull figures out.
2. Read clients' own spreadsheets (`.xlsx`, `.csv`) and pull figures out, not just store them.
3. A "Make info request" button that builds a request for this year's papers from last year's return.
4. Recent searches: the last 5 clients searched, under the search bar.
5. A progress bar and time left while documents are read.
6. "Things to check": what a reader wasn't sure about in a document, shown before downloading or confirming.

## Decisions (owner, 25 Oct 2026)

| Question | Decision |
|---|---|
| Info request wording | A template filled in from last year's data. No AI. |
| Info request format | A Word document filed in the client's Correspondence cabinet, Letters folder. |
| Amounts in the request | Names only (who paid what), no dollar amounts. |
| Emails with attachments | The email is one document (its text read); each attachment is filed and read as its own document. |
| `.msg` files | Read them; add the `olefile` library. |
| Spreadsheet rows with no label | Not added as figures; listed in Things to check. |
| What counts as a recent search | A client opened from search results, or a search that matches exactly one client. |
| Order | 1 Things to check, 2 spreadsheets, 3 emails, 4 progress, 5 recent searches, 6 info request. |

## Rules that still apply

Redact first; every write goes through the output guard; client codes only in files and logs (names only in
`clients.json`); original and attachment filenames never recorded; every figure arrives unconfirmed; uncertain
treatment flagged, never guessed. Nothing here needs an API key or the AI reader.

## 1. Things to check

**Readers record doubts.** `ExtractResult` gets `doubts: list[str]`: short sentences such as "Didn't find the
franking credit." Built-in extractors add one wherever they now return `partial` (income statement, dividends
including the "withholding tax" wording, PHI, interest, receipts' suggested label), and the new spreadsheet and
email readers add theirs.

**Stored per document.** `reading_notes.json` in the client's work folder: `{doc_id: {"doubts": [...],
"from_email": "D012" | null}}`, written through the guard inside the same roll-back block as the figures, so a
failed import leaves nothing behind. `Workspace.reading_notes_json` is its path.

**Assembled each time** by `tra/to_check.py` (`things_to_check(ws, doc_id)`, `to_check_by_figure(ws)`,
`to_check_counts(ws)`) from:
- the document's doubts, and "Came attached to email D012";
- import review notes for the document (`ingest_notes.json`: I1, I2, I3, I6, I7, A2, A3; not I4), with their risk;
- its **unconfirmed** figures that are AI/Claude-read, have a suggested label, or have no page.

Confirming a figure removes its items; document-level items stay.

**Shown** in the document panel (a box above Open), the import results (replacing the plain notes list), the
Figures tab (a line under each figure), and as a count in the client's document list. No made-up confidence
scores: the built-in readers find a line or don't.

## 2. Client spreadsheets

- `readers.load` gives one page per sheet for `.xlsx`, each row written with `csv.writer` (so cells holding commas
  survive). `.csv` is unchanged. Xero exports keep working (their cells have no commas).
- New document type `CLIENTXLS` ("Client's spreadsheet", folder Other). The pipeline uses it for a spreadsheet
  that classifies as `OTHER` or `RECEIPT`; other types (Xero exports) keep their own readers.
- `ClientSheetExtractor` reads each sheet: finds a header row, the amount column (header word, else the most
  money-like column), the description column (and a category column if there is one), and a date column.
  Skips totals, blanks and zeros.
- Labels come from `config/sheet_words.yaml`: words and phrases per label key, matched as whole words. Exactly one
  label matched → an unconfirmed figure, `notes="suggested label"`, description `Sheet 1 row 4: Red Cross donation`,
  page = sheet number. No match, or more than one (e.g. "interest", "dividend", "insurance") → a doubt naming the
  row and amount. Figures capped at 200 per document, doubts at 20 ("and 14 more rows").
- A sheet whose header looks like share sales (two or more of bought/acquired/sold/disposed/units/cost base/
  proceeds) gives no figures and one doubt: enter them as CGT events.
- `parse_status`: `partial` when there are figures (labels are suggestions), else `manual_needed`. `CLIENTXLS`
  and `EMAIL` join `annual_statement_types` in `config/checks.yaml`, so R7 accepts dates up to 120 days after
  30 June.

## 3. Emails

- `tra/ingest/emails.py`: `read_email(path) -> EmailContent(subject, sent, body, attachments, skipped)`.
  - `.eml`: Python's `email` package. Body: plain text, else HTML with tags stripped (script/style dropped, block
    tags become new lines, entities unescaped).
  - `.msg`: `olefile`. Subject `0x0037`, body `0x1000` (else HTML `0x1013`), sent time `0x0039` from the property
    stream, attachments from `__attach_version1.0_#…` (data `0x3701`, extension from `0x3707`/`0x3704`/`0x3703`).
    An email embedded inside a `.msg` is skipped with a doubt (save it separately).
  - Inline images (signature logos: image with a Content-ID or inline disposition) are skipped. At most 20
    attachments.
- The email's page text is `Subject:` and `Date:` lines plus the body. Sender and recipients aren't included.
  It goes through redaction like any document.
- Document type `EMAIL` (folder Other), always for `.eml`/`.msg`, never keyword-classified. `EmailExtractor` reads
  body lines with one money amount (`$` or cents) and labels them from the same word list; quoted replies (`>`
  lines, "On … wrote:", "Original Message") and lines without a label become doubts or are ignored.
- **Attachments**: after the email is filed, `ingest_file` saves each one under a random name in
  `Work/<code>/FY<year>/_uploads/`, ingests it (readable types) or files it store-only in Other (Word, photos),
  records `from_email`, and deletes the temporary copy. Unusable types (e.g. `.zip`) are not filed; the email gets
  a doubt ("Attachment 3 (.zip) wasn't filed"). An attached email is read as an email; an email inside that is
  stored only. Because this happens in `ingest_file`, `tra ingest`, Sawnx Import and In Tray filing all get it.
- `IngestReport.attachments` and `ImportOutcome.attachments` carry the attachments' results for display.
- `.eml`/`.msg` join `readers.SUPPORTED` and Sawnx `READ_TYPES`. `olefile>=0.46` joins the dependencies.

## 4. Progress bar

- The Import panel's script sends files one at a time to the existing import route with `fragment=1` and
  `first_position`, which returns only that file's results (`_import_results.html`). A bar shows
  "Reading 3 of 8 · about 1 min left" (average seconds per file so far × files left; "working out time left…"
  for the first), and results appear as each finishes. At the end: "Done: 8 files in 1 min 12 s" and a link that
  reloads the page.
- Without the script, the form posts all files at once, as now. The AI reader's time is included because it
  reads inside each file. Claude reading in chat has no bar (it isn't in Sawnx). In Tray's Add is unchanged.

## 5. Recent searches

- `web/recent.py`: `TRA_HOME/sawnx_recent.json`, `{windows user: [client codes]}`, newest first, at most 5, codes
  validated, written through the guard. Never what was typed.
- Search results link through `GET /search/open/<code>`, which remembers the client and goes to their Files tab.
  A search matching exactly one client remembers it too.
- A context value gives `recent_clients` (code, name from `clients.json`, latest year); deleted clients drop off.
  base.html renders a small list under the search box that the script shows on focus; the empty Search page shows
  the same list.

## 6. Info request

- `tra/info_request.py`: `build_request(ws) -> InfoRequest(year, from_last_year, sections)` using
  `ws.for_year(fy - 1)`:
  1. last year's confirmed figures: label keys and payers (the part of the description before " – " or ": ");
  2. last year's CGT events (any rows → a "Things you sold" item; asset names only);
  3. otherwise `prior_year.csv` / `last_return.json` label keys.
  No amounts. Empty → the standard checklist, saying it isn't based on last year.
- Wording and grouping in `config/info_request.yaml` (title, greeting "Dear [client's name],", intro, sections with
  label keys and item sentences, "Anything new this year?", closing). Sawnx never writes the client's name.
- `tra/docx_writer.py` writes a minimal Word file with `zipfile` (content types, relationships, styles,
  document); fixed zip timestamps so the same request is byte-identical. Text is checked by the guard
  (`check_value`) and written with a new `guard.atomic_write_bytes`.
- `POST /c/<code>/<fy>/info-request` builds it in `_uploads`, files it with `store_in_cabinet(Correspondence,
  "Letters", doc_type="INFOREQ")`, deletes the temporary copy, audits `info_request_made` (doc id, whether based on
  last year), and opens the Correspondence cabinet on the new document. The button sits beside Import documents on
  the Files tab (Tax return cabinet).

## Testing

Test-first for each piece. All test data is made up at runtime: emails built with the `email` package; `.msg`
files built by a small compound-file writer in the tests; spreadsheets with openpyxl. No checksum-valid TFN,
Medicare or card numbers in any file. Web pieces through Flask's test client (`tests/webctx.py`). The progress
script is checked by hand in the browser; its server side (fragment responses) is tested.

## Not in scope

OCR for scanned emails/attachments, company and trust returns, sending the info request by email, a progress bar
for In Tray or for Claude reading in chat, AI wording of the request.
