# Sawnx: a local web front end for the Tax Return Assistant — Design Spec

**Date:** 18 October 2026
**Status:** Draft for review
**Builds on:** [`2026-10-14-tax-return-assistant-design.md`](2026-10-14-tax-return-assistant-design.md) (still binding). This spec replaces only its §3 non-goals "a UI" and "an LLM extractor": both are now in scope, as described here.

---

## 1. Purpose

Preparers do every step of a draft return by clicking instead of typing commands. Sawnx is a website in the browser, laid out like FYI, that runs **only on the preparer's laptop**:

- a client list showing where every job is up to;
- each client's documents stored in folders, to look back at any time, plus the preparer's own file notes;
- on import the preparer picks the return type (Individual) and, per file, "Read for the return" or "Store only"; files to be read are redacted, classified, filed and read straight away;
- figures are confirmed on screen beside the source document;
- one button prepares the return and gives the workpaper;
- review notes are answered on screen, and the job is marked reviewed.

Sawnx is a second way to drive the existing tool. It adds no new tax logic, no new place for client documents and no new privacy rules: it calls the same code `tra` already uses. It never lodges. A registered agent still signs off every return.

### Success criteria

1. A preparer can take DEMO01, TEST01 and a client made from their own fake documents from "New client" to "Reviewed" without opening PowerShell or Excel, and can store extra files, add folders and keep file notes.
2. TEST01 prepared through Sawnx gives the same refund ($993.25) and the same notes as `tra prepare`.
3. Sawnx accepts connections only from the same laptop, and only with the session key.
4. With the AI reader off (the default), Sawnx makes no network call except FYI and Xero, exactly as today.
5. The full test suite passes, including all existing tests.

## 2. Decisions made during brainstorming

| Question | Decision |
|---|---|
| Where it runs | Locally. A small web server inside `tra`, bound to 127.0.0.1. Client documents stay in `TRA_HOME` (or FYI). Nothing is hosted on the internet. |
| How it's built | Flask with server-rendered HTML, plain CSS and a little JavaScript. No Node or build step. |
| AI reading | Built, **off by default**, and switchable on only after the privacy officer approves. It receives only redacted text, only for documents the built-in parsers couldn't read. |
| First version features | Client list and job status, upload and auto-filing, folders and file notes, figures confirmed on screen, prepare and workpaper download, review notes with responses. |
| Import | The preparer picks the return type (only Individual is enabled; Company and Trust show as "coming later") and, per file, "Read for the return" (default) or "Store only". |
| Sensitive data | Unchanged from the main design: text is redacted the moment it is read, and only redacted text exists anywhere afterwards. The stored original is kept unchanged as the firm's record (as in FYI). |
| Look | Black background, FYI-style layout. Mockup made with Claude Design and approved before the screens are coded; polished with the impeccable skill. |
| Data | No database. Sawnx reads and writes the files `tra` already uses, plus `review.json` per client year and `client_notes.json` per client. |

## 3. Non-goals for the first version

- Hosting online, logins, several users, or access from other computers.
- A client portal, email, or sending anything to clients.
- OCR. Image-only PDFs are still filed and flagged for manual entry; the AI reader does not see them.
- Company and trust returns (the import screen lists them as "coming later").
- Moving or renaming documents filed into FYI from Sawnx.
- Editing CGT events and prior-year figures on screen (the CSV files still work, and Sawnx links to them).
- Showing documents filed into FYI inside Sawnx. They get an "Open in FYI" link instead.

## 4. Architecture

### 4.1 Layout

```
src/tra/web/
  __init__.py        create_app(settings, session_key) -> Flask app
  server.py          `tra web`: picks the port, makes the session key, opens the browser
  security.py        session key cookie, Host and Origin checks
  services/          plain functions over the existing code: clients, files, imports, figures,
                     prepare, activity
  client_notes.py    client_notes.json: the preparer's file notes
  app_settings.py    sawnx.json: the AI reader switch and who approved it
  status.py          job status for one client year
  routes.py          the client list, New client and Settings
  client_routes.py   a client's tabs; each view calls a service and renders a template
src/tra/review_store.py                  review.json (outside web/ because tra prepare uses it too)
src/tra/clients.py                       client set-up, shared with `tra new`
  templates/         base.html, clients.html, client_*.html, settings.html
  static/            sawnx.css, sawnx.js (no third-party scripts, no CDN)
src/tra/ingest/extractors/ai_reader.py   the AI reader (off by default, §8)
Sawnx.cmd             double-click launcher in the tool folder (CRLF), runs `tra web`
```

The services hold the behaviour and are tested without HTTP. `routes.py` only translates requests to service calls and results to pages. Templates contain no logic beyond loops and formatting.

### 4.2 Boundaries

- Sawnx calls the existing functions: `ingest_file`, `read_figures` / `write_figures`, `prepare_client`, `DocumentIndex`, `Workspace`, `make_store`, `AuditLog`. It never reimplements them.
- Every write still goes through the output guard (`atomic_write_text`, `check_value`), including `review.json`.
- The CLI keeps working unchanged. Anything done in Sawnx shows up in the CLI and the reverse.

## 5. Security model

| Threat | Control |
|---|---|
| Another computer on the network | Server binds to `127.0.0.1` only. A test fails if any other address is used. |
| Another web page in the same browser calling Sawnx | `tra web` makes a random 32-byte session key and opens `http://127.0.0.1:<port>/?key=<key>`. The key is swapped for an `HttpOnly`, `SameSite=Strict` cookie and removed from the address. Every request without the cookie gets 403. Every POST also checks the `Origin` header. |
| DNS rebinding | Requests whose `Host` header isn't `127.0.0.1:<port>` or `localhost:<port>` get 403. |
| Path tricks when viewing documents | Documents are opened by `doc_id`, looked up in `index.csv`. No file path ever comes from the browser. |
| Original filenames leaking | Uploads are saved under a random temporary name inside `TRA_HOME\Work\<code>\FY<year>\_uploads\`, ingested, then deleted. The original filename is never recorded (as today). |
| Identifiers typed into a response | `review.json` is written through the output guard; a TFN in a response is refused with the usual message. |
| Caching | Pages and documents are sent with `Cache-Control: no-store`. |

The server runs on a fixed port (8766) and falls back to a free one if 8766 is taken. It runs until its console window is closed.

## 6. Screens

All screens: black background, menu on the left (Clients, Settings), search across the top. A banner shows while the rates file is unverified. Fonts are the laptop's own (Segoe UI and Cascadia Mono or Consolas) rather than the mockup's IBM Plex, because Sawnx fetches nothing from the internet.

**Clients (home).** Table: client code, income year, job status badge, documents, figures to confirm, High notes, estimated refund or payable, last change. Search by code; filter by status. A small bar chart of jobs at each status. **New client** opens a form with the `tra new` options: income year, HELP debt, hospital cover days, age band, SAPTO status, spouse, dependants, sole trader, non-resident. Codes are validated with the existing client-code pattern.

**Client page**, five tabs:

- **Files.** The client's documents for the chosen income year, in folders: the standard categories (ATO, Income, Investments, Rental, Health, Deductions, Business, Other) plus folders the preparer adds (for example "Engagement" or "Correspondence"). Folder names are letters, numbers, spaces and hyphens, and go through the output guard. Clicking a document opens it in a viewer panel (the browser's own viewer for PDFs and images; other types download). A locally filed document can be moved to another folder; its filed name stays the same, and the index and audit log record the move.
- **Import** (a button on the Files tab). The preparer picks the **return type**: Individual (the only one enabled) or Company / Trust, shown greyed out as "coming later". Then they drop in or choose files. Each file has a choice:
  - **Read for the return** (the default; PDF, CSV, XLSX, JSON). The file goes through `ingest_file`: read, redacted at once, classified, filed into its category folder, and its figures added unconfirmed. The result shows type, parse status, figures found, redaction counts, filed name and any notes. Duplicates are reported and skipped.
  - **Store only** (also Word, images and emails: PDF, DOCX, XLSX, CSV, JPG, PNG, EML, MSG). The file is filed unchanged into the folder the preparer picks, through the existing `file_document` path, named `<code>_FY<year>_OTHER_<date>.<ext>` and listed in the index. Its contents are never read, so nothing is extracted and nothing needs redacting.
- **Notes.** The preparer's own file notes about the client: free text, each stamped with the Windows user and time, newest first, with an optional income year. Notes can be edited and deleted. They are saved through the output guard, so a TFN or other identifier typed into a note is refused with the usual message. Beside them, an **Activity** list shows the client's actions from the audit log in plain words (documents read or stored, figures changed, workpapers prepared, reviews marked), as FYI does.
- **Figures.** One row per figure: label, description, amount, date, source document and page, method, **Confirmed** and **Substantiated** ticks, and notes. Pre-fill rows show "Leave unconfirmed if another document supports this (R4)". Selecting a row opens its source document beside the table. Labels are chosen from a list of valid keys; amounts are validated with `parse_amount`. **Add figure** creates a manual row. Every change is saved to `figures.csv` straight away through `write_figures`.
- **Prepare.** **Prepare return** runs `prepare_client`. The result shows the estimated refund or payable large, the calculation A and B components side by side with any difference highlighted, and every workpaper version (newest first) to download.
- **Review notes.** Notes from the latest workpaper grouped High, Medium, Low, each with its citation, a response box and a **Resolved** tick. **Mark reviewed** (asks for the reviewer's name) is enabled once every High note is resolved. Responses are carried into the Response column of the next workpaper version.

**Settings.** The AI reader switch (§8), FYI and Xero connection status, `TRA_HOME`, rates status, version.

## 7. Data and job status

### 7.0 Sensitive data, in plain words

When a document is imported to be read, its text is redacted the moment it is read (`redact_pages`, as today). From then on only the redacted text exists: classification, extraction, the figures, the logs, the workpaper and the AI reader (if ever switched on) all work from it, and the identifiers are never written into anything Sawnx or `tra` creates. The **stored original** is kept unchanged, because it is the firm's record of what the client provided (TASA record keeping, APP 12 access), exactly as FYI keeps it today. It is only reachable on the laptop, through Sawnx or the filing folder.

### 7.1 New files

`TRA_HOME\Work\<code>\client_notes.json` (one per client, all years): a list of `{"id", "text", "income_year" (or null), "by", "at", "edited_at"}`.

Preparer-made folders are directories under `TRA_HOME\Clients\<code>\FY<year>\` like the standard categories; a document's folder is its `category` in `index.csv`.

`TRA_HOME\Work\<code>\FY<year>\last_prepare.json`: the latest Prepare result (estimate, both calculations, notes) for the Prepare and Review tabs and the client list. `TRA_HOME\sawnx.json`: the AI reader switch, approver and date.

`TRA_HOME\Work\<code>\FY<year>\review.json`:

```json
{
  "responses": {"<note key>": {"text": "...", "resolved": true, "by": "<windows user>", "at": "<iso time>"}},
  "reviewed": {"by": "<name>", "at": "<iso time>", "workpaper": "<filename>"}
}
```

A note key is `check_id|label_key|figure_ids|doc_ids`, so a response stays attached to the same note when the return is prepared again. Responses whose note no longer appears are kept but shown as "No longer raised".

### 7.2 Job status

Worked out each time from the files (nothing stored except the reviewed mark):

| Status | When |
|---|---|
| New | No documents filed. |
| Docs in | Documents filed, and some figure other than an unconfirmed pre-fill row is still unconfirmed, or nothing is confirmed. |
| Figures confirmed | At least one figure confirmed, no non-pre-fill figure unconfirmed, and no workpaper newer than the last change to `figures.csv`, `state.json`, `cgt_events.csv` or `prior_year.csv`. |
| Prepared | The latest workpaper is newer than all of those files, and it hasn't been marked reviewed. |
| Reviewed | `review.json` marks the latest workpaper as reviewed. |

Changing a figure after preparing moves the job back to "Figures confirmed".

## 8. The AI reader

- An extractor in the existing plug-in point (`src/tra/ingest/extractors/`). It runs only when **all** of these are true: the setting is on; the document's text was readable; the built-in parser found no figures or only a partial read; and the API key is set as a Windows user environment variable.
- It is given the `RedactedText` object only. Before sending, the text is scanned again with `find_sensitive`; if anything is found, nothing is sent and a High note is raised.
- It uses the official `anthropic` Python library (an optional extra, `pip install -e ".[ai]"`) with Claude Opus 5.5 by default, structured JSON output, and the API's automatic fallback if a request is declined. The prompt asks for figures as JSON against the label keys in `config/labels.yaml`. Every figure it returns is added unconfirmed, with method `ai`, its document and page, and is validated like any other row.
- **Switching it on** in Settings asks for the approver's name and date, recorded in `TRA_HOME\sawnx.json` and the audit log, like the rates `verified_by`. Until then the switch is off and labelled "Needs privacy officer approval". Every workpaper raises a note when any figure came from the AI reader.
- Tested only against mocked responses. No live call is made in the tests or during the build.

## 9. Error handling

| Situation | What Sawnx does |
|---|---|
| `figures.csv` open in Excel | The change isn't saved: "figures.csv is open in Excel. Close it and try again." |
| Output guard blocks a write | Stops that action and shows the existing guard message, including "tell the privacy officer". |
| Unreadable, scanned or unknown document | Filed and listed with "Enter its figures by hand", as `tra ingest` does. |
| Unsupported file type | Refused before anything is saved, naming the supported types. |
| Rates file invalid | Prepare shows the `RatesError` message. |
| FYI unavailable | Files locally with the existing note; Settings shows FYI as unavailable. |
| Unexpected error | A plain error page with a short reference. The detail goes to the redacted log, never the page. |

## 10. Testing

Test-first, as for the rest of the tool. All test data is generated at runtime; nothing is committed that the repo-hygiene test would reject.

- **Security:** binds to 127.0.0.1 only; no cookie → 403; wrong `Host` → 403; cross-origin POST → 403; the key is removed from the address; documents only by `doc_id`; `no-store` headers.
- **Services:** an upload gives the same index, filed name and figures as `ingest_file`; a "Store only" file is filed unchanged into the chosen folder with no text read and no figures; Company and Trust return types are refused; a folder name with an identifier or a path character is refused; moving a document updates the index and the audit log; a note with a TFN is refused, and notes survive edits; ticking a figure changes `figures.csv` exactly as an Excel edit would; prepare through the service equals `tra prepare` (TEST01 refund $993.25); review keys survive a re-prepare; the guard refuses a TFN in a response.
- **Status:** every row of §7.2, including the move back after a figure changes.
- **AI reader:** off by default; never called when off; refuses unredacted text; the mocked response becomes unconfirmed `ai` figures; a bad response adds nothing and raises a note.
- **Pages:** each screen renders for an empty home, a new client, DEMO01 and TEST01.
- **By hand:** DEMO01, TEST01 and a client made from the preparer's own fake documents, start to finish in the built-in browser, at desktop and phone widths.

## 11. Delivery order

1. Mockup in Claude Design (fake data only), approved by the user.
2. Server, security and the client list.
3. Files tab, folders, import (read or store only) and the Notes tab.
4. Figures tab.
5. Prepare tab and workpaper downloads.
6. Review notes and job status.
7. Settings and the AI reader (off).
8. `Sawnx.cmd`, setup changes, README, CLAUDE.md, the Obsidian notes, and the privacy table (an LLM extractor now exists, off by default).

## 12. Additions (18 Oct 2026, after the first build)

**Client names.** Sawnx shows, sorts and searches clients by name, with the code beside it. New client asks for the
name; a blank code is suggested from the surname (Jane Citizen → CITI01). Names are stored only in
`TRA_HOME\clients.json` (through the output guard) and can be edited on the client page. Every file, folder, filename,
log, audit entry and workpaper still uses the code; the audit log records `client_named` with the code only.

**Document summaries and descriptions.** Each filed document gets an automatic one-line summary, built from the index
and figures.csv with no AI: type, issuer, date, and the figures it supports with their return items
(`tra/doc_summary.py`). Store-only and unreadable documents say so. The preparer can add a description per document
(`doc_notes.json`, through the output guard). Both show on the Files tab and in new Summary and Description columns of
the workpaper's Sources tab, as the evidence trail.

## 13. Open items

- Privacy officer approval before the AI reader is switched on (and the README privacy table updated when it is).
- The firm's IT confirms a local web server on 127.0.0.1 is acceptable on firm laptops.
- FYI document preview inside Sawnx, once the FYI API is confirmed.
- OCR, so the AI reader could help with scans.
- The privacy officer confirms that client names in `clients.json` (Sawnx screens only) are acceptable.
