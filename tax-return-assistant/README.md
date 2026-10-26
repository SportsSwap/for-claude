# Tax Return Assistant

An internal tool for preparing **draft** Australian individual tax returns. You give it a client's source documents. It:

- removes identifiers from the text before anything else reads it;
- files the originals under the firm's naming convention;
- pulls out the tax figures, each tied to its source document and page;
- produces an Excel workpaper that shows all the working;
- produces a ranked list of review notes.

It also estimates the tax two independent ways so the Xero Tax figure can be cross-checked.

**It never lodges anything.** Returns are prepared and lodged in Xero Tax, and every return is reviewed and signed off by a registered tax agent at the firm. The tool's job is everything before and around keying the return in.

Design: [`docs/specs/2026-10-14-tax-return-assistant-design.md`](docs/specs/2026-10-14-tax-return-assistant-design.md)
Build plan: [`docs/plans/2026-10-14-tax-return-assistant.md`](docs/plans/2026-10-14-tax-return-assistant.md)

---

## Before it is used on a real client

These steps need people at the firm. The tool reminds you on every workpaper until they are done.

1. **Verify the rates.** Open `config/rates/fy2026.yaml` (and `fy2025.yaml` for late returns). A registered tax agent checks every figure against the ATO page listed under `sources:`. Then set:
   ```yaml
   status: verified
   verified_by: <name>
   verified_on: 2026-10-20
   ```
   Until then every workpaper carries the High note **C2 "rates not yet verified"**. The figures were gathered through web-search summaries of the ATO and Department of Health pages, because those sites couldn't be reached when the tool was built.
2. **Verify the citations** in `config/citations.yaml` (set `verified: true` on each). Unverified ones print as "(citation to be confirmed by reviewer)".
3. **Check the ATO label letters** in `config/labels.yaml` against the 2026 return forms and set `letter_verified: true`. Item numbers and descriptions are reliable; the letters were not checked.
4. **Privacy sign-off.** Ask the firm's privacy officer to read [Privacy and compliance](#privacy-and-compliance) below and confirm the controls. Make sure the drive holding the client data folder is encrypted with BitLocker.
5. **Move the code to a firm-owned repository.** It currently sits in a personal repository next to an unrelated case study.

---

## Setting up a Windows laptop (once, about 15 minutes)

1. **Install Python 3.11 or later** from <https://www.python.org/downloads/>. Tick **"Add python.exe to PATH"**. Firm laptops often need IT to do this.
2. **Get the code.** On GitHub, use *Code → Download ZIP* on this branch and unzip it, for example to `C:\Tools\tax-return-assistant`.
3. **Run the setup script.** Open PowerShell in that folder and run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\setup.ps1
   ```
   It creates a private Python environment (`.venv`) and installs the tool. It then asks where client data should live (default `C:\TaxAssistant`), saves that as `TRA_HOME`, and runs `tra doctor`.
4. **Each time you use the tool**, open PowerShell in the folder and start each command with `.\tra`, for example:
   ```powershell
   .\tra doctor
   ```
   `.\tra` runs the copy of the tool that setup installed, so there is nothing to activate and no Windows setting to change. It works straight away, even in the window you ran setup in. (If you activate `.venv` with `.\.venv\Scripts\Activate.ps1`, plain `tra` works too, but Windows blocks that script until `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` has been run.)

`TRA_HOME` must be on the laptop itself. The tool refuses to run if it is inside OneDrive, Dropbox, Google Drive or iCloud (that would send client data offshore), or inside a git repository.

`.\tra doctor` checks the setup at any time.

**Already set up before 25 October 2026?** Reading Outlook `.msg` emails needs one small extra library, `olefile`
(free, widely used, nothing else comes with it). Close Sawnx, then in PowerShell in the tool's folder run
`.\.venv\Scripts\pip install -e .` once (or run `setup.ps1` again). Until then a `.msg` import says what to run, and
`.eml` emails work anyway. For firm IT: the tool's only new dependency is `olefile>=0.46`.

---

## Try it with invented data first

```powershell
.\tra demo --auto-confirm
.\tra prepare DEMO01
```

This creates a fake client, **DEMO01**, from eight invented documents: a pre-fill report, an income statement, a bank statement, a dividend statement, a rental statement, a private health statement and two receipts. It runs them through the whole process. The documents contain made-up TFN, Medicare, card, BSB, account and licence numbers, so you can see redaction working. Open the workpaper path that `prepare` prints.

The demo gives an estimated payable of $5,697.11 and these review notes:

| Risk | Note |
|---|---|
| High S4 | Work-related claims over $300, and the union receipt has no date, so it isn't substantiated |
| High C2 | Rates file not yet verified |
| Medium S13 | A $1,499 laptop claimed outright; it's a depreciating asset |
| Medium S9 | Income is over the MLS threshold and hospital cover wasn't recorded, so it was assumed |
| Low S14 | Residency was assumed, so confirm the client was an Australian resident all year |
| Low I2 | The union receipt had no date, so the filename uses the ingest date |

---

## Sawnx: the tool as a website

Sawnx does everything below by clicking instead of typing commands. It opens in your browser but runs **only on this laptop**: no other computer can reach it, and nothing goes on the internet. The commands keep working, and anything done in one shows up in the other.

**Start it:** double-click the **Sawnx** shortcut on the desktop (setup makes it), or `Sawnx.cmd` in this folder, or run `.\tra web`. A black window opens and Sawnx opens in **its own Chrome window** (no tabs or address bar, like an app). Without Chrome it uses an Edge window, and without either your usual browser. Close the black window to stop it. Each start makes a new secret key, so a bookmark won't open Sawnx: always start it from the shortcut. `.\tra web --no-open` prints the address instead, to paste into any browser.

| Screen | What it does |
|---|---|
| Top bar | Home, Clients, Documents, Settings; a search box for clients or documents (click in it to see your **recent searches**); the green **+** for New client; **?** for help. Laid out like FYI, in Sawnx's own colours. |
| In Tray | Drop in documents for any client. Sawnx reads each one (identifiers blanked first) and suggests the client (by finding a client's name in it), cabinet, folder, type and year; you check, change and **File**, or **Discard**. Nothing is filed without you. |
| Home | **My Recent**, **My Tasks**, **Delegated Tasks**, **My Starred**, **My Time** (this week) and **Notifications** (tasks and jobs due, the In Tray, colleagues' comments). |
| Jobs | Every client's "Individual tax return FY…" job (its status follows the return) plus jobs you add (BAS, advice...), with due dates, who it's assigned to, notes, tasks, comments and time recorded against it. |
| Knowledge | The firm's templates, policies and procedures, in folders. Firm documents only, never client documents. |
| Documents | Every document across all clients and years. Click a heading to sort; filter by client, year, folder or type; tick several to star, download or move them. |
| Clients | Every client by **name** (with its code), sorted by name, with where each job is up to (New, Docs in, Figures confirmed, Prepared, Reviewed), the estimate and the High notes. Search by name or code. **New client** asks for the name and suggests a code from the surname (Jane Citizen → CITI01). |
| Files | The client's documents in folders (the standard ones plus any you add). **Import** asks for the return type (Individual; company and trust are coming later) and, per file, **Read for the return** or **Store only** (for letters, ID, emails). Files that are read have identifiers blanked out the moment they're read, exactly as `tra ingest` does. Each document shows a **summary** of what it is, who issued it and the figures it supports, and a box for **your own description**; both go into the workpaper's Sources tab as the evidence trail. **Cabinets** like FYI: *Tax return* (per year, as above), *Permanent* and *Correspondence* (per client, stored only, never read). Open a document to edit its **properties** (type, folder, date, status) and to **upload a new version**; older copies stay listed. **Delete** (on the open document, or for ticked documents) moves a document to **Deleted items** with everything read from it, so its figures come out of the return; **Restore** puts it all back, and **Delete forever** removes it for good. Deleting a document also lets you import the same file again, to have it read again. Emails (`.eml`, `.msg`) and clients' own spreadsheets are read too, a **progress bar** shows while files are read, each document shows **Things to check**, and **Make info request** writes this year's checklist from last year's return (see below). |
| Figures | **Confirm all** (on a document, or per document on this tab) confirms every figure from it after you've checked them (pre-fill rows excepted). Tick each figure once you've checked it against its source, which shows beside the table. Fix a label or amount, or add a figure by hand. Changes save to `figures.csv` straight away. A line under a figure says what to check first (a suggested label, read by the AI reader or Claude, no page). |
| Prepare | Prepares the return (as `tra prepare`), shows the estimate and both calculations side by side, and lists every workpaper to download. |
| Review notes | Each note with a response box and a Resolved tick. Responses go into the Response column of the next workpaper. **Mark reviewed** once every High note is resolved. |
| Notes | Your own file notes about the client, and an activity list from the audit log. |
| Settings | The AI reader switch (off), the client data folder, rates status, FYI and Xero, **Layouts** (what Sawnx has learned to read, and what's waiting), and **filing rules** ("if a document mentions X, suggest client Y, cabinet Z, folder W"; suggestions only). |

### How to: emails, client spreadsheets, Things to check, progress, recent searches, info requests

**Read an email from a client.** In Outlook, drag the email onto the desktop (that saves a `.msg` file), or use
*File → Save As*. In Sawnx open the client, **Files → Import documents**, choose the file, leave it on **Read for the
return**, and click **Import**. Sawnx files the email itself as *Email from the client* in **Other**, and reads its
subject, date and text (the sender and recipients aren't kept). A line such as "Donations to Red Cross: $500" becomes an
unconfirmed figure with a *suggested label*. Lines it can't put a label on are listed in Things to check. Each attachment
is filed and read as its own document, exactly as if you'd imported it, and its Things to check says which email it
came in. PDFs, spreadsheets, CSV and JSON are read; Word files and photos are stored in **Other**; anything else (a
`.zip`) isn't filed and the email's Things to check says so. Signature logos are skipped, and quoted replies ("On ...
wrote:") aren't read, so an amount the client repeats isn't counted twice. Importing the same email again files nothing.
In the **In Tray**, an email is suggested for *Correspondence → Emails*; to have it read, choose *Tax return*, the year
and **Read for the return** before **File**. Emails from the command line work too: `.\tra ingest SMIT01 mail.msg`.

**Read a client's own spreadsheet.** Import the `.xlsx` or `.csv` the same way. If it isn't a Xero export or another
known layout, Sawnx reads it as the client's list: on each sheet it finds the description and amount columns (and a
date or category column), skips totals and blank rows, and turns each row whose words it knows (donation, union fees,
phone, uniform, course, tax agent, rent received...) into an unconfirmed figure with a suggested label, described as
"Sheet 1 row 4: Red Cross donation". A row it can't label, or whose words could mean two things ("interest" could be
bank interest or loan interest), isn't added; it's listed in Things to check with its row and amount, for you to enter
by hand. A sheet that looks like share sales gives no figures and asks you to enter CGT events. The word list is
`config/sheet_words.yaml`; anyone can add words there (keep out a word that could mean two labels).

**Things to check.** Open a document (click its name on the Files tab). A yellow **Things to check** box at the top of
the panel, above **Open**, lists what the reader wasn't sure about: amounts it didn't find, rows it couldn't label,
pages with no text, no date found, an area the tool doesn't handle, and each unconfirmed figure with a suggested
label or read by the AI reader or Claude. The document list shows how many each document has ("2 to check"), the import
results list them under each file, and the **Figures** tab shows a line under each figure that needs a look. Confirming
a figure removes its item. There are no "70% sure" scores: the built-in readers either find a line or don't, so each
item says what was found, guessed or missed.

**Progress bar.** When you import several files, Sawnx reads them one at a time and shows "Reading 3 of 8 · about
1 min left", then "Done: 8 files in 1 min 12 s". Results appear as each file finishes. Click **Show the documents** to
see them in the list. The time left is the average so far, so it settles after the first file or two, and it includes
the AI reader's time when that's switched on.

**Recent searches.** Click in the search box at the top: your last 5 clients found by search are listed (a client you
opened from the search results, or a search that found just one client). Click one to open it. Sawnx keeps only client
codes for this (never what you typed), one list per Windows user, in `TRA_HOME\sawnx_recent.json`.

**Make info request.** On a client's **Files** tab (Tax return cabinet), click **Make info request**. Sawnx builds a Word
checklist for this year from last year's return: who paid what last year (employers, banks, share registries, health
fund), shares sold, a rental property, and one line for each kind of deduction claimed, plus "Anything new this year?".
It never includes amounts or the client's name: the letter starts "Dear [client's name]," for you to fill in. It's filed
in **Correspondence → Letters** as `SMIT01 <date> Information request.docx` and opened in the panel: click **Open** to edit it in
Word, then attach it to your email. Last year means the previous year's confirmed figures in Sawnx (or
`prior_year.csv`); with nothing from last year it's the standard checklist, and says so. The wording is in
`config/info_request.yaml`.

### How to: teach Sawnx new layouts, and Read again

Sawnx's own readers are rules. When a document comes in as "manual entry needed", Sawnx can usually be **taught its
layout**, so it reads every document like it from then on, with no AI and no cost. The more layouts it knows, the
less the AI is needed.

1. Import documents as usual. Anything not read goes on **Settings → Layouts → Not read yet** (also
   `.\tra layouts todo`).
2. In a Claude chat, say **"teach Sawnx the new layouts"**. Claude follows fixed steps (`.claude/skills/teach-layouts`):
   it reads only the blanked-out text (`.\tra ai-text`), writes a small layout file in `config/layouts/` (which words
   recognise the layout, which line holds which amount), writes a made-up copy of the layout in
   `tests/layout_samples/` with invented names and numbers, and proves it with the tests. It checks the layout on the
   real document with `.\tra layouts try` (writes nothing), then reads the waiting documents again.
3. Claude tells you what each new layout reads. Check the figures on the Figures tab as usual; nothing is committed
   without your OK.

**Read again** (a button on any document, or `.\tra reread SMIT01 D007`, or `--waiting` for everything not read)
reads a filed document with today's rules. Figures you've confirmed or typed in are never changed; unconfirmed ones
the readers added are replaced, and the document gets its readable name.

What a layout can't fix: **scanned pages** (no text, or text so garbled that amounts can't be trusted) need OCR or
the AI. An amount that looks misread ("$24s") is never used: Things to check asks you to look at it. A layout is never
asked to guess a return item: if a line could be two things, it's left for you.

Layouts learned so far: the ATO income statement (myGov), Bupa's private health statement, and NSW government school
receipts (labels suggested only).

**The AI reader is built in but switched off.** It uses **Claude Haiku 5.5** (shown on the Settings page). When it reads a document it also says what kind it is (a rental statement, say), so a document Sawnx's word-matching filed under the wrong type goes to the right folder; Things to check says "Type set by the AI reader" so you can change it. **Send page images for scans** (Settings, off by default, needs its own privacy officer approval) also sends pictures of scanned pages (no usable text, or a page that is one big picture even when the scanner typed a text layer over it), PDFs only, at most 20 pages (and 20 MB) a document, as small greyscale pictures. Numbers in a picture can't be blanked, so those pages go to Anthropic as they are; each use is in the audit log (`ai_page_images_sent`) and no picture is saved. Switching the AI reader off switches page images off too, so they need approving again. If it finds nothing, Things to check says so. If the AI can't answer, the document is still filed, with a note to enter it by hand; it never stops an import. It may not call a document an ATO pre-fill, prior-year return or Xero export, and any account number it copies into a description is blanked. The privacy officer approved it for real clients on 25 October 2026. If the privacy officer approves it, switching it on in Settings (with the approver's name and date, recorded in the audit log) lets Claude read documents the built-in readers can't. It only ever receives the blanked-out text, and everything it finds arrives unconfirmed for you to check (R6 flags it on the workpaper). It needs `.\.venv\Scripts\pip install -e ".[ai]"` (close Sawnx first) and an API key from the firm's Anthropic Console account, saved for the Windows account by typing this in PowerShell yourself (never paste a key into a chat): `[Environment]::SetEnvironmentVariable('ANTHROPIC_API_KEY', 'your-key', 'User')`. Sawnx finds a key saved this way even if it was already running; switched on without a key, an import says so. **What leaves the laptop:** the document's text with identifier numbers blanked out. Names, addresses and amounts are not blanked, so the privacy officer's approval covers those.

**Without an API key: Claude reads it in a chat.** The firm has no Anthropic API account, so instead you can ask
Claude (Claude Code, in a chat on this laptop) to read the documents the built-in readers couldn't:

```powershell
.\tra ai-text TEST04                 # shows Claude only the blanked-out text of the unread documents
.\tra ai-add TEST04 D002 "<answer>"  # adds what Claude read, as unconfirmed figures
```

You just say "read TEST04's documents" and Claude runs both. `ai-text` scans the text again and shows nothing if an
identifier is left in it; `ai-add` checks every label, amount and page and refuses the whole answer if any part is
wrong, won't read the same document twice, and records each step in the audit log by document number. The figures
arrive unconfirmed, marked "Claude:", for you to check against the document (R6 flags them on the workpaper).
Same privacy as the AI reader: names, addresses and amounts go to Claude under your Claude account's terms, so the
privacy officer has approved it for **made-up clients only** (19 Oct 2026).

---

## Preparing a real client

Clients are identified **only by their client code** (e.g. `SMIT01`), never by name.

### 1. Set up the client

```powershell
.\tra new SMIT01 --fy 2026
```

The options change the calculation, so set those that apply:

| Option | Meaning |
|---|---|
| `--help-debt` | The client has a HELP or other study loan |
| `--hospital-days 365` | Days covered by private hospital insurance. Leave it out if unknown: the tool takes it from the private health statement if that shows it, otherwise assumes cover and raises a note. |
| `--age-band 65to69` / `70plus` | For the private health rebate |
| `--sapto single` | Eligible for the seniors and pensioners tax offset (`couple`, `illness_separated`) |
| `--spouse`, `--dependants 2` | Raises a note: the family Medicare and MLS thresholds need family income |
| `--sole-trader` | For Xero clients |
| `--non-resident` | Not an Australian resident for tax. The estimate assumes residency, so this raises a High note to prepare the return in Xero Tax. |

These are saved in `TRA_HOME\Work\SMIT01\FY2026\state.json`. Edit that file to change them later.

### 2. Ingest the documents

```powershell
.\tra ingest SMIT01 C:\Inbox\SMIT01\*.pdf
.\tra ingest SMIT01 C:\Inbox\SMIT01            # a whole folder
.\tra ingest SMIT01 scan.pdf --type DIVSTMT     # force the document type
```

For each file the tool:

1. **Reads the text and redacts it straight away.** TFNs, Medicare numbers, card numbers, BSBs, account numbers, driver licence and passport numbers are replaced with `[TFN REDACTED]` and so on. Nothing else ever sees the original text.
2. **Works out the document type** (see `config/doc_types.yaml`).
3. **Extracts the figures it understands** into `figures.csv`, each marked *unconfirmed* with its source document and page.
4. **Files the original, unchanged**, as `TRA_HOME\Clients\SMIT01\FY2026\<Category>\SMIT01 2026-03-24 Dividend statement - SAMPLE MINING LTD.pdf` (client code, the document's date, what it is, and who issued it when the tool read that; never the client's name), and lists it in `index.csv`. Documents filed before 25 October 2026 keep their old names (`SMIT01_FY2026_DIVSTMT_2026-03-24.pdf`) until they're read again. The original filename is never recorded, since filenames often contain names.

Ingesting the same file twice is detected and skipped. If a document can't be read (a scan, a password-protected or damaged PDF, or a layout the tool doesn't know), it is still filed and a note asks you to enter its figures by hand. Excel lock files (`~$...`) and hidden files in a folder are ignored.

**Documents it reads today:**

- the ATO pre-fill report;
- income statements;
- bank and interest statements;
- dividend statements, either one amount per line or the share registries' table (Link/MUFG, Computershare). A table is used only if it adds up; otherwise it's left for you to enter;
- property manager statements;
- private health insurance statements;
- receipts;
- Xero P&L exports (CSV or XLSX);
- clients' own spreadsheets (XLSX or CSV): rows with words it knows become figures with a suggested label;
- emails (`.eml`, or `.msg` from Outlook): lines with an amount become figures with a suggested label, and each
  attachment is filed and read as its own document.

Real layouts vary by bank and registry. When one isn't read correctly, enter the figures by hand, and send a **blank or fake-data** copy of the layout to whoever maintains the tool so a reader can be added. Never send a real one.

### 3. Check and confirm the figures

```powershell
.\tra figures SMIT01
```

This checks `figures.csv` and opens it in Excel. For every row:

- **check it against the source** and set `confirmed` to `Y`. Only confirmed figures go into the return;
- set `substantiated` to `Y` for work-related claims with proper written evidence;
- fix the `label_key` if the suggestion is wrong. Receipts are always suggested as `ded.d5`. The valid keys are in `config/labels.yaml`;
- **add manual figures** as new rows. Leave `figure_id` blank, set `method` to `manual`, and put the document's `doc_id` (from `index.csv`) and page if it has one. A figure with no source is allowed but raises a High note.

Rows marked `notes = prefill` come from the pre-fill report. Leave them **unconfirmed** when a source document supports the same figure, or the amount is counted twice (the tool flags this as R4). Confirm one only when it's the only support for that figure.

Also fill in, as needed:

- **Capital gains:** `cgt_events.csv` in the same folder. One row per sale: acquired and disposed dates, proceeds and cost base. Prior-year capital losses go in `figures.csv` as `cgt.prior_losses`.
- **Prior year:** `prior_year.csv` (`label_key,amount`) from last year's return. After the first year, the tool uses its own previous output automatically.

Save (keep the "CSV UTF-8" format Excel opens it in) and close Excel before the next step. If the file is still open, the tool says so and changes nothing; close it and run the command again.

### 4. Prepare the draft

```powershell
.\tra prepare SMIT01
```

This:

1. builds the draft return from confirmed figures;
2. runs both tax calculations and every self-check;
3. writes `TRA_HOME\Work\SMIT01\FY2026\Output\SMIT01_FY2026_Workpaper_DRAFT_v1.xlsx`.

Running it again writes `_v2`; earlier versions are never overwritten. It prints the estimated refund or payable and the High notes.

### 5. Review and key in

Work through the **Review Notes** tab. Key the return into Xero Tax, using the B01 Summary tab in ATO item order. Then compare Xero Tax's estimate with the Tax Calc tab. The registered agent reviews the workpaper and signs the Cover tab.

---

## What's in the workpaper

| Tab | Contents |
|---|---|
| **Cover** | DRAFT – NOT FOR LODGMENT banner, client code, year, partner, manager, reviewer and preparer, rates status, estimated result, sign-off boxes, and a link to start at B01 Summary |
| **B01 Summary** | The hub, like the firm's B01. A tax summary box (total income, deductions, taxable income, tax, payable or refundable), then every return item the client has, in ATO order: item, code, a **Go to** link to its tab, amount, tax credits, pre-fill, difference, prior year, movement %, review notes. |
| **Item tabs** | Named and numbered like the firm's workpapers: 01 Salaries and Wages, 10 Interest Received, 11 Dividends Received, 15 Business Professional, 24 Other Income, C15 Losses, M03 Capital Gains, M25 Rental Property, D01 MV Expenses … D10 Cost Managing Tax, D07 Int Div Deductions (D7 and D8), D15 D11 - D15 Deductions (D12 and D15), PHI Private Health. **Only the tabs the client needs appear.** Each has the same header (client code, year ended, workpaper, prepared by, reviewed by), a "↩ B01 Summary" link and a blue "i  The purpose of this worksheet is…" line. Each return item has its own section: **ATO pre-fill** and **Client documents and adjustments** separately, each figure linked to its source document and page, a total, and **Transferred to: Item 10 L**, a link to that line of B01 Summary. The rental tab also shows net rent; M03 has the CGT events and the s102-5 method statement. |
| **Tax Calc** | Taxable income through to refund or payable, all as formulas. Beside them, the tool's independent calculation and a difference column that turns red if they disagree. |
| **Rates** | The year's rates copied in, so the file stands alone, with their verification status |
| **Sources** | Every filed document: type, date, pages, what was redacted |
| **Review Notes** | Every flag, assumption and client question, ranked by risk, then by dollar impact, with citations and a response column |

The look follows the firm's workpapers: Calibri 10, dark grey text, no gridlines, light-blue link boxes and the accounting number format. Typed-in numbers (figures and rates) are **blue**. Everything else is a formula, so the working can be followed in Excel. Headers show the client **code**, not the name (the privacy rule).

## The self-checks

| ID | Checks |
|---|---|
| R1–R5 | Every figure has a filed source; label totals add up; unconfirmed figures listed; pre-fill and source document not both counted; the same document not ingested twice (same type, label and amount from two documents) |
| R7 | A document used in the return is dated outside the income year, so its figures may belong to another year. Allowed: 30 June dates; annual statements (income statement, interest summary, managed fund, health insurance, rental) dated up to 120 days after 30 June; the ATO pre-fill report dated after 30 June. A pre-fill dated earlier in the year is flagged as probably last year's. Undated documents are skipped (I2 covers them) |
| P1–P4 | Return vs ATO pre-fill (differences over $1, items on pre-fill but missing, no pre-fill ingested, HELP mismatch) |
| C1–C2 | The two tax calculations agree to the cent; the rates file is verified |
| S1 | Deductions high relative to income |
| S2 | Income with no supporting statement |
| S3 | Rental income without expenses, or the reverse |
| S4 | Work-related claims over $300 without substantiation (s900-35) |
| S5 | Car claim over the cents-per-km cap (s28-25) |
| S6 | Conventional clothing (TR 97/12) |
| S7 | Rental repairs that look capital (TR 97/23) |
| S8 | CGT dates and cost base; discount on assets held only just over 12 months (s115-25) |
| S9 | Medicare levy surcharge exposure |
| S10 | Redraw or line-of-credit interest (TR 2000/2) |
| S11 | Gifts under $2 or not confirmed as a DGR |
| S12 | Areas the tool doesn't prepare (managed funds, family thresholds, business P8 detail, non-residents, net financial investment losses) |
| S13 | Equipment over $300 claimed outright (s40-80) |
| S14 | Residency assumed (a reminder to confirm it) |
| Y1–Y2 | Movements over 20% (and $100) against last year; items that disappeared |
| I1–I7 | Raised at ingest: manual entry needed, no document date, FYI unavailable, duplicate file, unmapped Xero section, an unhandled area mentioned in a document (employee share schemes, foreign income or tax, PSI, trust or partnership distributions, Medicare levy exemption), hospital cover days taken from the health statement |

Thresholds are in `config/checks.yaml`. Where the treatment is uncertain, the note says so and cites the provision or ruling. It never changes the return.

---

## Privacy and compliance

The tool is built so that sensitive identifiers can't end up in anything it creates.

| Control | How |
|---|---|
| Redact before processing | Text is redacted as it is read, before classification, extraction or logging. TFNs are detected by check digit *and* by the words "TFN" / "tax file number" (so a mistyped TFN is still caught). Medicare by check digit and keyword, cards by Luhn, BSB, account, licence and passport by format and keyword. The rest of the code accepts only redacted text. |
| Output guard | Every file the tool writes (CSV, JSON, the workpaper, the index, logs, filenames) is scanned before writing. If anything looks like an identifier, the write is refused and a `guard_blocked` entry (place and type, never the value) goes in the audit log. |
| No values in logs | Log lines are redacted. The audit log records who did what and when, by client code and document ID, with redaction *counts*, never values or original filenames. |
| Client codes in files | Every file, folder, filename, log, audit entry and workpaper uses the client code. Names appear only on Sawnx's screens and in `TRA_HOME\clients.json`, written through the output guard (for the privacy officer to confirm). |
| Local only | No client data is sent anywhere except FYI and Xero, and only when you run those commands. The AI reader is built in but **switched off**; it can only be switched on in Sawnx Settings with the approver's name and date, and then sends only redacted text to Anthropic's Claude service (APP 8 applies). `TRA_HOME` may not be in a cloud-synced folder (OneDrive, SharePoint/Teams libraries, Dropbox, Google Drive, iCloud). |
| Sawnx website | Listens on 127.0.0.1 only. Every request needs the random key made each time it starts; requests from other sites or host names are refused; pages are never cached. Uploads are saved under a random name, used and deleted; original filenames are never recorded. |
| Emails and spreadsheets | An email's subject, date and text are redacted like any document; its sender, recipients and attachment file names are never kept. Attachments are saved under a random name, read or stored, and deleted. Names and addresses in an email or a client's spreadsheet aren't blanked (as with PDFs). Things to check, recent searches and the info request are written through the output guard; recent searches keep client codes only, and the info request never contains amounts or the client's name. |
| Secrets | Xero and FYI credentials live in Windows user environment variables. The Xero token is kept in Windows Credential Manager. Nothing secret is in the code, config or repository (see `.env.example` for the names). |
| Nothing in git | `.gitignore` blocks PDFs, spreadsheets and CSVs. A test fails if any committed file contains a valid TFN, Medicare or card number. |
| Originals | Filed unchanged in the firm's system of record, as the firm keeps them today |

**Mapping** (for the privacy officer to confirm; this is not legal advice):

- **APP 1 (open and transparent management):** this README and the audit log document how client information is handled.
- **APP 6 (use and disclosure):** information is used only to prepare the client's return; nothing is disclosed except to FYI and Xero, the firm's existing service providers.
- **APP 8 (cross-border disclosure):** no client data leaves the laptop except via FYI and Xero. Cloud-synced folders are refused.
- **APP 11 (security):** redaction before processing, the output guard, local storage, credential store, BitLocker recommended.
- **APP 12 (access):** originals are filed unchanged, so the client's documents can be produced on request.
- **TASA 2009 s30-10 (Code of Professional Conduct):** confidentiality (the controls above); reasonable care (sourced figures, dual calculation, self-checks, agent sign-off); the tool never lodges.
- **Notifiable Data Breaches scheme:** if the output guard ever blocks a write (`guard_blocked` in the audit log), stop and tell the privacy officer. It means an identifier reached a place it shouldn't, and the cause needs finding before the tool is used again.

---

## Updating rates for a new year

Copy `config/rates/fy2026.yaml` to `fy2027.yaml`, change `income_year`, and update every figure from the ATO pages. Set `status: unverified` until checked, then run `.\tra doctor`.

The loader rejects a file whose bracket base amounts don't match its rates, whose Medicare thresholds don't line up, or whose SAPTO figures don't agree with the taper. A typo is caught before it reaches a return. Run the tests (below) after editing.

## Xero setup (sole trader clients)

1. Someone with access to the firm's Xero developer account creates an app at <https://developer.xero.com>:
   - type: **mobile or desktop app (PKCE)**;
   - redirect URI: `http://localhost:8765/callback`.
2. Check the scope names in `config/xero_mapping.yaml` against Xero's current granular scopes and correct them. Apps created after 2 March 2026 must use granular scopes.
3. Set the app's client ID as the Windows user environment variable `XERO_CLIENT_ID`. There is no client secret.
4. Run `.\tra xero connect` once. It opens Xero in the browser and lists the organisations.
5. Run `.\tra xero pull SMIT01 --tenant <id>`. The tenant ID is remembered for that client after the first time.

`pull` files the P&L, balance sheet, bank transactions and chart of accounts as documents (pulling again with unchanged data adds nothing). Only the Xero refresh token is stored, in Windows Credential Manager. It adds the P&L lines as unconfirmed business income and expense figures. Complete the detailed business schedule (P8) in Xero Tax. The Xero client has been tested against mocked responses only; do a trial run on a test organisation first.

## FYI setup

1. Ask FYI for API access. Their external API uses an access ID, an access secret and an application ID.
2. Confirm the header names and endpoint paths in `config/fyi.yaml` with FYI. They are **unconfirmed**.
3. Set `FYI_BASE_URL`, `FYI_ACCESS_ID`, `FYI_ACCESS_SECRET`, `FYI_APP_ID` and `TRA_STORE=fyi` as user environment variables.

With FYI set, `ingest` files into FYI. If FYI is unavailable it files locally and raises a note; `.\tra fyi push SMIT01` sends those later. The FYI client has been tested against mocked responses only.

## Changing the workpaper layout

The workpaper follows the firm's individual tax workpapers (B01 Summary as the hub, numbered item tabs, the same header on every tab). All fonts, colours, widths and number formats are in `src/tra/workpaper/layout.py`; tab names are the `tab:` entries in `config/labels.yaml`. `build.py` decides what goes where; `layout.py` decides how it looks.

---

## For developers

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
```

There are 891 tests, all on invented data generated while the tests run. Four run only on Windows (the `tra.cmd` and `Sawnx.cmd` launchers and reading the settings saved for the Windows account). The Sawnx tests use a test browser client; none open a real browser or call the internet.

- **Tax maths:** the two calculations are tested on hand-worked bracket-edge cases and on 5,000 random returns, where they must agree to the cent.
- **Redaction:** every identifier type, plus traps such as amounts, phone numbers, ABNs and dates.
- **End to end:** an end-to-end test plants identifiers in fake documents, runs the whole flow, and scans every file the tool wrote.
- **Workpaper formulas:** if LibreOffice is installed, the workbook is recalculated and checked against Python.

```
config/         rates per year, labels, document types, checks, citations, Xero/FYI settings
src/tra/
  privacy/      validators, detectors, redaction, output guard, audit log, log filter
  ingest/       readers, emails (.eml, .msg), classifier, extractors (incl. client sheets, email text), pipeline
  filing/       naming, local store, FYI store, index
  return_/      draft return, CGT
  taxcalc/      rates loader, calculation A, calculation B
  checks/       reconciliation, pre-fill, sanity, prior year, ranking
  workpaper/    build.py (content), layout.py (styling)
  xero/         OAuth (PKCE), API client, figures
  web/          Sawnx: security, services, routes, templates, static
  cli.py        the `tra` command
tests/
```

The AI reader (`src/tra/ingest/extractors/ai_reader.py`) works on redacted text only and is off unless switched on in Sawnx Settings after the firm approves sending data to it (Privacy Act APP 8). Its tests use a stand-in client and never call the network. Sawnx's design: [`docs/specs/2026-10-18-sawnx-design.md`](docs/specs/2026-10-18-sawnx-design.md); emails, client spreadsheets, Things to check, the progress bar, recent searches and the info request: [`docs/specs/2026-10-25-sawnx-six-additions-design.md`](docs/specs/2026-10-25-sawnx-six-additions-design.md). The `.msg` tests build Outlook files with a small writer in `tests/msgfile.py`, so no real email is ever needed.

## Known limitations

- **Individuals only.** Company and trust returns are not built.
- **Flagged, not calculated:** these are detected and raised for the reviewer:
  - the family Medicare levy reduction and family income tests;
  - non-resident returns;
  - foreign income;
  - employee share schemes;
  - personal services income;
  - trust and partnership distributions;
  - managed fund (AMIT) components;
  - net financial investment losses in the income tests;
  - the detailed business schedule (P8).
- **Medicare levy exemptions (M1)** are only flagged when a document mentions a Medicare entitlement statement or a Medicare levy exemption. Otherwise the reviewer must consider them.
- **Pensions and annuities** (items 5–7) have no labels yet; enter them under item 24 and adjust in Xero Tax.
- **No OCR.** Scanned documents are filed and flagged for manual entry.
- **Layouts.** Readers cover the ATO pre-fill report and the layouts the tool was built with. New layouts will need adding as they come up.
- **Unverified reference data.** The rates, citations, label letters, Xero scope names and FYI endpoints are unverified until checked (see the top of this file).
- **Windows testing so far.** `setup.ps1`, the demo and the tests have been run on one personal Windows 10 PC (17 October 2026). Try it on one firm laptop before using it more widely, because IT-managed Python installs and Group Policy may behave differently.
