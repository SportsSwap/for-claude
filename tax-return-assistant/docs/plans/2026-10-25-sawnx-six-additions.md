# Sawnx six additions: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Things to check, client spreadsheets, emails, a progress bar, recent searches and an info request in Sawnx.

**Architecture:** Readers report doubts in `ExtractResult.doubts`; the pipeline saves them per document and
`tra/to_check.py` assembles each document's list for Sawnx. Spreadsheets and emails are new document types with
their own extractors, and email attachments are ingested from inside `ingest_file`, so every entry point gets
them. The web pieces stay thin over new service modules.

**Tech Stack:** Python 3.11+, Flask, openpyxl, pdfplumber, `email` (stdlib), `olefile` (new), pytest.

**Spec:** `docs/specs/2026-10-25-sawnx-six-additions-design.md`

## Global Constraints

- TFN, Medicare, card, BSB, account, licence and passport numbers never reach a file, log, filename or page:
  redact first, and write only through `tra.privacy.guard` (`atomic_write_text`, `check_value`, and the new
  `atomic_write_bytes`).
- Client codes only in files, folders, filenames, logs and audit entries; names only in `TRA_HOME\clients.json`.
  Original filenames and attachment filenames are never recorded.
- Every figure is written `confirmed=False`. Never guess a label: no match or several matches → a doubt.
- Tests make their data at runtime. No checksum-valid TFN, Medicare or card number in any file
  (`tests/test_repo_hygiene.py`).
- New dependency: `olefile>=0.46` only.
- **Do not commit.** The owner decides. Each task ends with its tests green instead.
- Run tests with `.venv\Scripts\python -m pytest` (Windows). The full suite takes about 7 minutes, so run it in
  the background.
- Sawnx copy is plain Australian English, like the existing pages.

## Review Focus

1. An identifier in a spreadsheet cell or an email signature next to an amount must be blanked and must not
   appear in figures.csv, reading_notes.json or the page (Tasks 3 and 4 tests).
2. A reply email quoting the client's earlier message must not give the same amount twice (Task 4 test).
3. A damaged attachment must not stop the email being filed; it is filed for manual entry (Task 5 test).
4. Amounts typed as text ("$1,234.50", "(120.00)") are read, and a "Total" row is not counted again (Task 3 test).
5. Importing the same email twice files nothing new, attachments included (Task 5 test).

---

### Task 1: Doubts, reading notes and the to-check list

**Files:**
- Modify: `src/tra/ingest/extractors/base.py` (`ExtractResult.doubts`), `income_statement.py`, `dividends.py`,
  `phi.py`, `interest.py`, `receipt.py`
- Modify: `src/tra/workspace.py` (`reading_notes_json`), `src/tra/ingest/pipeline.py`
- Create: `src/tra/reading_notes.py`, `src/tra/to_check.py`
- Test: `tests/test_to_check.py`

**Interfaces:**
- Produces: `ExtractResult.doubts: list[str]`;
  `save_reading_notes(ws, doc_id: str, doubts: list[str], from_email: str | None = None) -> None`;
  `load_reading_notes(ws) -> dict[str, dict]`;
  `@dataclass(frozen=True) CheckItem(text: str, risk: str = "", figure_id: str | None = None)`;
  `things_to_check(ws, doc_id: str) -> list[CheckItem]`; `to_check_by_figure(ws) -> dict[str, list[str]]`;
  `to_check_counts(ws) -> dict[str, int]`.

- [ ] **Step 1: Write the failing tests** in `tests/test_to_check.py`:
  - `test_dividend_missing_credit_is_a_doubt`: DIVSTMT text with franked but no franking credit → `"Didn't find
    the franking credit."` in `result.doubts`. Same pattern for an income statement without tax withheld and a PHI
    statement missing the 1 Apr–30 Jun lines.
  - `test_withholding_wording_is_a_doubt`: the "withholding tax" layout → a doubt containing "TFN withholding".
  - `test_ingest_saves_doubts`: ingest a made-up dividend PDF without a credit line →
    `load_reading_notes(ws)[doc_id]["doubts"]` holds the doubt.
  - `test_things_to_check_collects_sources`: a document with a doubt, an I2 note and an unconfirmed
    `notes="suggested label"` figure → three items; the note's item has `risk="Low"`; the figure item has its
    `figure_id`.
  - `test_confirmed_figure_drops_off`: confirm the figure → its item is gone, the document items stay.
  - `test_ai_figure_and_missing_page`: an unconfirmed `method="ai"` figure with `page=None` → one item saying it
    was read by the AI reader or Claude and the page isn't known.
  - `test_counts`: `to_check_counts(ws)` matches `len(things_to_check(ws, d))` for each document.
  - `test_failed_import_leaves_no_reading_notes`: make `file_document` raise → reading_notes.json unchanged.
- [ ] **Step 2: Run the tests to see them fail:** `.venv\Scripts\python -m pytest tests/test_to_check.py -q`.
  Expected: errors about the missing `doubts` and modules.
- [ ] **Step 3: Implement.** Doubts go in where each extractor now decides `partial` (name the missing field in
  plain words). In `ingest_file`, `save_reading_notes` runs inside `restore_on_error(...)` (add
  `ws.reading_notes_json` to it) before `file_document`, and only when there are doubts or a `from_email`.
  `things_to_check` reads `ingest_notes.json` entries whose `doc_ids` include the document (check ids I1 I2 I3 I6
  I7 A2 A3) and the figures from `read_figures`. Figure item wording: `"F003: label suggested (Gifts or
  donations). Check it before confirming."`.
- [ ] **Step 4: Run the tests to see them pass**, then `.venv\Scripts\python -m pytest tests/test_extractors_income.py
  tests/test_extractors_other.py tests/test_pipeline_cli.py -q`. Expected: all pass.

### Task 2: Things to check in Sawnx

**Files:**
- Create: `src/tra/web/templates/_tocheck.html` (the box), `src/tra/web/templates/_import_results.html` (moved
  out of `client_files.html`)
- Modify: `client_files.html`, `_docpanel.html`, `client_figures.html`, `_doclist.html`, `sawnx.css`,
  `src/tra/web/client_routes.py` (`render_files`, figures view), `src/tra/web/services/imports.py`
  (`ImportOutcome.to_check: list[CheckItem]`), `src/tra/web/services/doclist.py` (`DocRow.to_check: int = 0`)
- Test: `tests/test_web_to_check.py`

**Interfaces:** Consumes Task 1's functions. Produces `_import_results.html` (expects `results`, `doc_types`) for
Task 6.

- [ ] **Step 1: Write the failing tests** (using `tests/webctx.py`):
  - `test_doc_panel_shows_things_to_check`: GET `files?view=<doc>` → `"Things to check"` and the doubt text appear
    before the `Open` link in the HTML.
  - `test_import_results_list_items`: POST an import of a dividend PDF with no credit → the doubt is in the results.
  - `test_figures_tab_line_under_figure`: a suggested-label figure → `"label suggested"` under its row.
  - `test_doclist_count`: the Files list shows the count marker (`class="tocheck"`) for the document.
  - `test_nothing_to_check_shows_no_box`: a fully read income statement → no `"Things to check"`.
- [ ] **Step 2: Run to see them fail:** `.venv\Scripts\python -m pytest tests/test_web_to_check.py -q`.
- [ ] **Step 3: Implement.** `import_file` fills `outcome.to_check = things_to_check(ws, doc.doc_id)` after a
  successful read. The results template shows those items (risk badge when `risk` is set) in place of the plain
  notes loop. Keep the notes loop for duplicates and errors.
- [ ] **Step 4: Run** the new tests and `tests/test_web_*.py`. Expected: all pass.

### Task 3: Client spreadsheets

**Files:**
- Modify: `src/tra/ingest/readers.py` (`_xlsx_pages`: one page per sheet, `csv.writer` rows),
  `src/tra/ingest/pipeline.py` (routing), `src/tra/ingest/extractors/__init__.py`, `config/doc_types.yaml`
  (`CLIENTXLS`, category Other, no keywords), `config/checks.yaml` (`annual_statement_types` += CLIENTXLS, EMAIL)
- Create: `src/tra/ingest/extractors/client_sheet.py`, `src/tra/ingest/extractors/words.py`, `config/sheet_words.yaml`
- Test: `tests/test_client_sheet.py`

**Interfaces:**
- Produces: `load_sheet_words(path=None) -> dict[str, tuple[str, ...]]` (label key → words);
  `match_labels(text: str, words) -> list[str]` (label keys whose words occur as whole words; longest phrase wins
  within a label); `ClientSheetExtractor` (`doc_types = {"CLIENTXLS"}`), with constants `MAX_FIGURES = 200`,
  `MAX_DOUBTS = 20`. Task 4 reuses `words.py`.

- [ ] **Step 1: Write the failing tests** (spreadsheets built with openpyxl/csv in `tmp_path`):
  - `test_rows_with_words_become_suggested_figures`: rows `Red Cross donation | 500`, `Union fees | $480.00` →
    figures `ded.d9` 500.00 and `ded.d5` 480.00, `confirmed=False`, `notes="suggested label"`,
    descriptions `"Sheet 1 row 2: Red Cross donation"`, page 1.
  - `test_unknown_row_is_a_doubt`: `Misc | 120` → no figure; doubt `"Sheet 1 row 4: Misc $120.00 has no label, so
    it wasn't added."`.
  - `test_ambiguous_word_is_a_doubt`: `Interest | 55.10` → no figure; a doubt saying it could be more than one label.
  - `test_text_amounts_negatives_and_totals`: `"$1,234.50"`, `"(120.00)"`, and a `Total` row → two figures
    (1234.50 and -120.00), the total not counted.
  - `test_share_sales_sheet`: headers `Company | Date bought | Date sold | Units | Cost base | Proceeds` → no figures,
    one doubt mentioning CGT events.
  - `test_second_sheet_is_page_2`: rows on sheet 2 have `page=2` and "Sheet 2" in the description.
  - `test_csv_file_is_read_too`, `test_xero_export_still_reads` (existing Xero P&L xlsx → XEROPL figures unchanged).
  - `test_identifier_in_cell_never_written` (Review Focus 1): a runtime-generated TFN in the cell next to a
    donation → absent from figures.csv and reading_notes.json; the figure is still added.
  - `test_doubts_capped`: 30 unknown rows → 20 doubts plus `"and 10 more rows without a label."`.
- [ ] **Step 2: Run to see them fail:** `.venv\Scripts\python -m pytest tests/test_client_sheet.py -q`.
- [ ] **Step 3: Implement.** Routing in `ingest_file`: with no `override_type`, when the suffix is `.xlsx` or `.csv`
  and `classify` gives `OTHER` or `RECEIPT`, use `CLIENTXLS`. Parse each page with `csv.reader`. The header is the
  first of the first 10 rows that has two or more text cells and no amount. Columns come from header words
  (amount/$/cost/total/value/paid; description/item/details/expense/payee; category/type; date), falling back to
  the most money-like and the most text-like column. `parse_status = "partial"` when there are figures, else
  `"manual_needed"`. Word list: one entry per label key, for at least D1–D5, D9, D10, D15, interest income,
  dividends (both franked and unfranked keys, so "dividend" alone is ambiguous) and rent gross/other.
- [ ] **Step 4: Run** the new tests and `tests/test_readers_classify.py tests/test_xero.py tests/test_checks_doc_dates.py`.
  Expected: all pass.

### Task 4: Reading emails

**Files:**
- Create: `src/tra/ingest/emails.py`, `src/tra/ingest/extractors/email_body.py`, `tests/msgfile.py` (a tiny
  compound-file writer for test `.msg` files)
- Modify: `src/tra/ingest/readers.py` (`.eml`/`.msg` in `SUPPORTED`; page text from `read_email`),
  `src/tra/ingest/pipeline.py` (`EMAIL` for those suffixes), `config/doc_types.yaml` (`EMAIL`, category Other),
  `src/tra/ingest/extractors/__init__.py`, `pyproject.toml` (`olefile>=0.46`)
- Test: `tests/test_emails.py`

**Interfaces:**
- Produces: `@dataclass Attachment(suffix: str, data: bytes)`;
  `@dataclass EmailContent(subject: str, sent: datetime | None, body: str, attachments: list[Attachment],
  skipped: list[str])`; `read_email(path: Path) -> EmailContent`; `email_page_text(content: EmailContent) -> str`
  (`"Subject: …\nDate: 14/08/2026\n\n" + body`); `EmailBodyExtractor` (`doc_types = {"EMAIL"}`, uses
  `words.match_labels`); `MAX_ATTACHMENTS = 20`.

- [ ] **Step 1: Write the failing tests:**
  - `test_eml_plain_body_and_attachments`: an `EmailMessage` with a text body, a PDF attachment and an inline PNG
    with a Content-ID → body read, one attachment (`.pdf`), the image skipped.
  - `test_eml_html_only_body`: HTML with `<p>`, `<br>`, `&amp;` and a `<style>` → readable lines, no tags or CSS.
  - `test_eml_attached_email`: a `message/rfc822` part → an attachment with suffix `.eml`.
  - `test_msg_subject_body_date_attachment`: `tests/msgfile.write_msg(...)` → the same fields from `.msg`.
  - `test_msg_embedded_message_skipped`: an embedded-message attachment → listed in `skipped`, not in attachments.
  - `test_body_lines_become_figures`: `"Donations to Red Cross: $500"` and `"Work phone $480.00 for the year"` →
    `ded.d9` 500.00 and `ded.d5` 480.00, suggested label, page 1.
  - `test_quoted_reply_ignored` (Review Focus 2): the same lines again under `"On 3 Aug 2026, … wrote:"` and as
    `>` lines → still two figures.
  - `test_unlabelled_amount_line_is_a_doubt`: `"Misc stuff $120"` → doubt; a phone number line gives nothing.
  - `test_signature_identifier_blanked` (Review Focus 1): a runtime BSB and account number in the signature →
    not in any written file; the redaction counts show them.
  - `test_sender_not_in_text`: the `From:` display name isn't in `email_page_text`.
- [ ] **Step 2: Run to see them fail:** `.venv\Scripts\python -m pip install olefile` then
  `.venv\Scripts\python -m pytest tests/test_emails.py -q`.
- [ ] **Step 3: Implement.** `.eml`: `email.message_from_bytes(data, policy=email.policy.default)`,
  `get_body(("plain", "html"))`, `iter_attachments()`; strip HTML with `html.parser.HTMLParser`. `.msg`:
  `olefile.OleFileIO`; prefer the Unicode (`001F`) property streams, fall back to `001E`; read the FILETIME of
  `0x0039` from `__properties_version1.0` (32-byte header at the top level, 16-byte entries). The body extractor
  stops at the first reply marker (`On … wrote:`, `-----Original Message-----`, `From:` after a blank line) and
  ignores `>` lines. An amount needs `$` or cents. `test_msgfile` writer: 512-byte sectors, every stream in the
  normal FAT (the mini-stream cutoff set so olefile never uses the mini stream).
- [ ] **Step 4: Run** the new tests and `tests/test_readers_classify.py tests/test_intray.py`. Expected: all pass.

### Task 5: Email attachments filed and read

**Files:**
- Modify: `src/tra/ingest/pipeline.py` (`IngestReport.attachments: list[IngestReport]`; attachments after the
  email is filed; `store_document` moved here from `web/services/imports._store_only`, which becomes a thin
  wrapper), `src/tra/web/services/imports.py` (`READ_TYPES` += `.eml`, `.msg`; `ImportOutcome.attachments`),
  `_import_results.html`, `client_files.html` (helper text: emails can be read)
- Test: `tests/test_email_ingest.py`

**Interfaces:** Consumes `read_email` and `save_reading_notes(..., from_email=)`.
Produces `ingest_file(..., _depth: int = 0)`; `store_document(path, ws, store, folder: str, audit) -> IngestReport`.

- [ ] **Step 1: Write the failing tests:**
  - `test_email_and_attachments_filed`: an email with a made-up dividend PDF and a client xlsx → three documents
    (`EMAIL`, `DIVSTMT`, `CLIENTXLS`); both attachments have `from_email` = the email's doc id; figures from all three.
  - `test_word_attachment_stored_only`: a `.docx` attachment → filed in Other with `parse_status="stored"`.
  - `test_unusable_attachment_is_a_doubt`: a `.zip` → not filed; the email's doubts say `"Attachment 1 (.zip)
    wasn't filed."`.
  - `test_damaged_attachment` (Review Focus 3): a `.pdf` attachment that isn't a PDF → the email is filed, and the
    attachment is filed `manual_needed` with I1.
  - `test_same_email_twice` (Review Focus 5): the second import files nothing; attachments aren't re-read.
  - `test_attachment_names_never_recorded`: the attachment's original filename isn't in index.csv, the audit log
    or reading_notes.json.
  - `test_nested_email_depth`: an email inside an attached email is stored only.
  - `test_temp_files_deleted`: `_uploads` is empty afterwards.
  - `test_sawnx_import_shows_attachments`: POST import of the email → results list each attachment under it.
- [ ] **Step 2: Run to see them fail:** `.venv\Scripts\python -m pytest tests/test_email_ingest.py -q`.
- [ ] **Step 3: Implement.** Attachments run after the email's own audit record, each in its own `try`, so one
  failure can't undo the email. Temporary names use `secrets.token_hex(8)` plus the suffix, as imports do now.
- [ ] **Step 4: Run** the new tests and `tests/test_web_import.py tests/test_intray.py tests/test_pipeline_cli.py`.
  Expected: all pass.

### Task 6: Progress bar

**Files:**
- Modify: `src/tra/web/client_routes.py` (`import_docs`: `fragment=1` returns `_import_results.html` alone;
  `first_position` sets "File N"), `src/tra/web/static/sawnx.js`, `sawnx.css`, `client_files.html` (a hidden
  `<div id="progress" role="status" aria-live="polite">` and a results container)
- Test: `tests/test_web_progress.py`

**Interfaces:** Consumes `_import_results.html`. Produces the JS function `timeLeft(doneSeconds: number[],
remaining: number) -> string` ("working out time left…", "about 40 s left", "about 2 min left").

- [ ] **Step 1: Write the failing tests:**
  - `test_fragment_returns_results_only`: POST with `fragment=1` → 200, contains `File 3` when
    `first_position=3`, no `<html`.
  - `test_fragment_error_still_200`: an unreadable type → the error line in the fragment.
  - `test_fragment_cabinet_store`: `cab=CORR` with `fragment=1` → the stored result.
  - `test_plain_post_unchanged`: no `fragment` → the full page, as before.
- [ ] **Step 2: Run to see them fail:** `.venv\Scripts\python -m pytest tests/test_web_progress.py -q`.
- [ ] **Step 3: Implement.** The script runs on submit only when `fetch` and `FormData` exist. It sends one file at
  a time with that file's `mode_0` and `folder_0`, appends each fragment, updates the bar (`<progress>` plus text),
  and at the end shows `"Done: 8 files in 1 min 12 s"` with a "Show the documents" link (reload). If a request
  fails, it shows the error and carries on with the next file.
- [ ] **Step 4: Run** the tests. Then check by hand in the browser pane with `.\tra demo` data and five made-up
  files: the bar advances, time left appears after file 1, and the results match a plain import.

### Task 7: Recent searches

**Files:**
- Create: `src/tra/web/recent.py`
- Modify: `src/tra/web/home_routes.py` (`/search/open/<code>`; remember on a single match),
  `src/tra/web/context.py` (`recent_clients`), `base.html`, `search.html`, `sawnx.js`, `sawnx.css`
- Test: `tests/test_web_recent.py`

**Interfaces:** Produces `remember(tra_home, user: str, code: str) -> None`,
`recent_codes(tra_home, user: str) -> list[str]`, `MAX_RECENT = 5`, location `sawnx_recent.json`.

- [ ] **Step 1: Write the failing tests:**
  - `test_open_from_search_remembers_and_redirects`: GET `/search/open/TEST01` → 302 to
    `/c/TEST01/2026/files`; `recent_codes` == `["TEST01"]`.
  - `test_single_match_remembered`, `test_two_matches_not_remembered`.
  - `test_keeps_five_newest_no_repeats`: seven clients → five, newest first, a repeat moves to the front.
  - `test_only_codes_stored`: search by the client's name → the file has the code, not the name or the typed text.
  - `test_menu_and_empty_search_page`: base page HTML has the recent list with the name from clients.json; `/search`
    with no `q` lists it too.
  - `test_deleted_client_dropped`, `test_bad_code_404`.
- [ ] **Step 2: Run to see them fail:** `.venv\Scripts\python -m pytest tests/test_web_recent.py -q`.
- [ ] **Step 3: Implement.** Per user `getpass.getuser()`; `validate_client_code` on input; write with
  `check_value` + `atomic_write_text`. The menu is a `<div class="recent-menu" hidden>` under the search box; the
  script un-hides it on focus and hides it on blur or Escape.
- [ ] **Step 4: Run** the tests and `tests/test_web_clients.py`. Expected: all pass.

### Task 8: Info request

**Files:**
- Create: `src/tra/info_request.py`, `src/tra/docx_writer.py`, `config/info_request.yaml`
- Modify: `src/tra/privacy/guard.py` (`atomic_write_bytes`), `src/tra/web/client_routes.py`
  (`POST /c/<code>/<fy>/info-request`), `client_files.html` (the button), `config/doc_types.yaml` (`INFOREQ`)
- Test: `tests/test_info_request.py`

**Interfaces:**
- Produces: `@dataclass InfoRequest(year: int, from_last_year: bool, title: str, greeting: str, intro: str,
  sections: list[tuple[str, list[str]]], closing: str)`; `build_request(ws) -> InfoRequest`;
  `write_docx(path: Path, paragraphs: list[tuple[str, str]], location: str) -> None` (styles `title`, `heading`,
  `item` (with "☐ "), `text`); `atomic_write_bytes(path: Path, data: bytes, location: str, *, texts: list[str])`
  (runs `check_value(texts, location)` first).

- [ ] **Step 1: Write the failing tests:**
  - `test_items_from_last_year`: FY2025 confirmed figures (salary "SAMPLE CO PTY LTD – gross payments", interest
    from two banks, a franked dividend, D5, D9) → sections Income, Interest, Dividends and Deductions you claimed
    last year. The payers appear; `"$"` and the amounts don't.
  - `test_unconfirmed_last_year_ignored`.
  - `test_cgt_last_year`: a FY2025 cgt_events row → a "Things you sold" item.
  - `test_prior_year_csv_fallback`: only `prior_year.csv` → item names without payers.
  - `test_no_last_year_standard_checklist`: `from_last_year is False`; the intro says it isn't based on last year.
  - `test_docx_opens`: `write_docx` output is a zip with `word/document.xml` containing the text, and it opens with
    `zipfile`. The same input gives the same bytes.
  - `test_guard_blocks_identifier`: a runtime TFN in a paragraph → `SensitiveDataBlocked`, no file.
  - `test_route_files_in_correspondence_letters`: POST → redirect to `files?cab=CORR&view=D001`; the document is
    `INFOREQ` in Letters, named `TEST01_CORR_INFOREQ_<today>.docx`; `info_request_made` is in the audit; no client
    name in the file (set one in clients.json first); `_uploads` empty.
- [ ] **Step 2: Run to see them fail:** `.venv\Scripts\python -m pytest tests/test_info_request.py -q`.
- [ ] **Step 3: Implement.** The payer is the text before `" – "` or `": "` in a figure's description (reuse
  `doc_summary._issuer`'s rule; move it to a shared helper if needed). Six payers at most per line. The year line
  is `"Information request: 2026 income year (1 July 2025 – 30 June 2026)"`. The zip uses
  `ZipInfo(date_time=(2026, 1, 1, 0, 0, 0))` for every part.
- [ ] **Step 4: Run** the tests and `tests/test_cabinets.py`. Expected: all pass.

### Task 9: Documents and the full check

**Files:** `README.md`, `CLAUDE.md`, `docs/obsidian/Tax Return Assistant/*.md` (CRLF) and
`C:\Users\Nicho\Claude code\Nicholas Vault\Projects\Tax Return Assistant\*.md` (LF)

- [ ] **Step 1:** Run the full suite in the background: `.venv\Scripts\python -m pytest -q`. Expected: all pass;
  note the count.
- [ ] **Step 2:** `.venv\Scripts\python -m pyflakes src tests`. Expected: no output.
- [ ] **Step 3:** README: a "How to" section for each feature (exact clicks), emails and spreadsheets in the
  supported-files table, the olefile note for firm IT, and the new test count. CLAUDE.md: test count and a status
  line. Obsidian: How it works, How to run it, Decisions log (the owner's eight decisions), Known issues and ideas
  (In Tray progress, OCR), and the test count in Tax Return Assistant.md, in both copies with the right line endings.
- [ ] **Step 4:** Demo check in Sawnx: `.\tra web`, import a made-up email with two attachments and a client
  spreadsheet; watch the bar; open Things to check; make an info request and open it in Word.
