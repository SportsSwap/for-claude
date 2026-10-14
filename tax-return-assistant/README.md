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
4. **Each time you use the tool**, open PowerShell in the folder and run:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
   If Windows refuses, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

`TRA_HOME` must be on the laptop itself. The tool refuses to run if it is inside OneDrive, Dropbox, Google Drive or iCloud (that would send client data offshore), or inside a git repository.

`tra doctor` checks the setup at any time.

---

## Try it with invented data first

```powershell
tra demo --auto-confirm
tra prepare DEMO01
```

This creates a fake client, **DEMO01**, from eight invented documents: a pre-fill report, an income statement, a bank statement, a dividend statement, a rental statement, a private health statement and two receipts. It runs them through the whole process. The documents contain made-up TFN, Medicare, card, BSB, account and licence numbers, so you can see redaction working. Open the workpaper path that `prepare` prints.

The demo gives an estimated payable of $5,697.11 and these review notes:

| Risk | Note |
|---|---|
| High S4 | Work-related claims over $300, and the union receipt has no date, so it isn't substantiated |
| High C2 | Rates file not yet verified |
| Medium S13 | A $1,499 laptop claimed outright; it's a depreciating asset |
| Medium S9 | Income is over the MLS threshold and hospital cover wasn't recorded, so it was assumed |
| Low I2 | The union receipt had no date, so the filename uses the ingest date |

---

## Preparing a real client

Clients are identified **only by their client code** (e.g. `SMIT01`), never by name.

### 1. Set up the client

```powershell
tra new SMIT01 --fy 2026
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
tra ingest SMIT01 C:\Inbox\SMIT01\*.pdf
tra ingest SMIT01 C:\Inbox\SMIT01            # a whole folder
tra ingest SMIT01 scan.pdf --type DIVSTMT     # force the document type
```

For each file the tool:

1. **Reads the text and redacts it straight away.** TFNs, Medicare numbers, card numbers, BSBs, account numbers, driver licence and passport numbers are replaced with `[TFN REDACTED]` and so on. Nothing else ever sees the original text.
2. **Works out the document type** (see `config/doc_types.yaml`).
3. **Extracts the figures it understands** into `figures.csv`, each marked *unconfirmed* with its source document and page.
4. **Files the original, unchanged**, as `TRA_HOME\Clients\SMIT01\FY2026\<Category>\SMIT01_FY2026_<DocType>_<date>.pdf`, and lists it in `index.csv`. The original filename is never recorded, since filenames often contain names.

Ingesting the same file twice is detected and skipped. If a document can't be read (a scan, a password-protected or damaged PDF, or a layout the tool doesn't know), it is still filed and a note asks you to enter its figures by hand. Excel lock files (`~$...`) and hidden files in a folder are ignored.

**Documents it reads today:**

- the ATO pre-fill report;
- income statements;
- bank and interest statements;
- dividend statements;
- property manager statements;
- private health insurance statements;
- receipts;
- Xero P&L exports (CSV or XLSX).

Real layouts vary by bank and registry. When one isn't read correctly, enter the figures by hand, and send a **blank or fake-data** copy of the layout to whoever maintains the tool so a reader can be added. Never send a real one.

### 3. Check and confirm the figures

```powershell
tra figures SMIT01
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
tra prepare SMIT01
```

This:

1. builds the draft return from confirmed figures;
2. runs both tax calculations and every self-check;
3. writes `TRA_HOME\Work\SMIT01\FY2026\Output\SMIT01_FY2026_Workpaper_DRAFT_v1.xlsx`.

Running it again writes `_v2`; earlier versions are never overwritten. It prints the estimated refund or payable and the High notes.

### 5. Review and key in

Work through the **Review Notes** tab. Key the return into Xero Tax, using the Summary tab in ATO item order. Then compare Xero Tax's estimate with the Tax Calc tab. The registered agent reviews the workpaper and signs the Cover tab.

---

## What's in the workpaper

| Tab | Contents |
|---|---|
| **Cover** | DRAFT – NOT FOR LODGMENT banner, client code, year, preparer, rates status, estimated result, sign-off boxes |
| **Summary** | Lead schedule: every return label in ATO order. Columns: this year (formula), pre-fill, difference, prior year, movement %, review note count. |
| **One tab per category** | Salary & Wages, Interest, Dividends, Rental, D1–D15, Private Health and so on. Each row has its source document (a link to the filed file) and page, with a subtotal per return label. The Rental tab also shows net rent. |
| **Capital Gains** | Only when there are CGT events. The event schedule and the s102-5 method statement, as formulas. |
| **Tax Calc** | Taxable income through to refund or payable, all as formulas. Beside them, the tool's independent calculation and a difference column that turns red if they disagree. |
| **Rates** | The year's rates copied in, so the file stands alone, with their verification status |
| **Sources** | Every filed document: type, date, pages, what was redacted |
| **Review Notes** | Every flag, assumption and client question, ranked by risk, then by dollar impact, with citations and a response column |

Typed-in numbers (figures and rates) are **blue**. Everything else is a formula, so the working can be followed in Excel.

## The self-checks

| ID | Checks |
|---|---|
| R1–R5 | Every figure has a filed source; label totals add up; unconfirmed figures listed; pre-fill and source document not both counted; the same document not ingested twice (same type, label and amount from two documents) |
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
| Client codes only | Names never appear in filenames, logs or the audit log |
| Local only | No client data is sent anywhere except FYI and Xero, and only when you run those commands. There is no AI or other external service. `TRA_HOME` may not be in a cloud-synced folder (OneDrive, SharePoint/Teams libraries, Dropbox, Google Drive, iCloud). |
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

Copy `config/rates/fy2026.yaml` to `fy2027.yaml`, change `income_year`, and update every figure from the ATO pages. Set `status: unverified` until checked, then run `tra doctor`.

The loader rejects a file whose bracket base amounts don't match its rates, whose Medicare thresholds don't line up, or whose SAPTO figures don't agree with the taper. A typo is caught before it reaches a return. Run the tests (below) after editing.

## Xero setup (sole trader clients)

1. Someone with access to the firm's Xero developer account creates an app at <https://developer.xero.com>:
   - type: **mobile or desktop app (PKCE)**;
   - redirect URI: `http://localhost:8765/callback`.
2. Check the scope names in `config/xero_mapping.yaml` against Xero's current granular scopes and correct them. Apps created after 2 March 2026 must use granular scopes.
3. Set the app's client ID as the Windows user environment variable `XERO_CLIENT_ID`. There is no client secret.
4. Run `tra xero connect` once. It opens Xero in the browser and lists the organisations.
5. Run `tra xero pull SMIT01 --tenant <id>`. The tenant ID is remembered for that client after the first time.

`pull` files the P&L, balance sheet, bank transactions and chart of accounts as documents (pulling again with unchanged data adds nothing). Only the Xero refresh token is stored, in Windows Credential Manager. It adds the P&L lines as unconfirmed business income and expense figures. Complete the detailed business schedule (P8) in Xero Tax. The Xero client has been tested against mocked responses only; do a trial run on a test organisation first.

## FYI setup

1. Ask FYI for API access. Their external API uses an access ID, an access secret and an application ID.
2. Confirm the header names and endpoint paths in `config/fyi.yaml` with FYI. They are **unconfirmed**.
3. Set `FYI_BASE_URL`, `FYI_ACCESS_ID`, `FYI_ACCESS_SECRET`, `FYI_APP_ID` and `TRA_STORE=fyi` as user environment variables.

With FYI set, `ingest` files into FYI. If FYI is unavailable it files locally and raises a note; `tra fyi push SMIT01` sends those later. The FYI client has been tested against mocked responses only.

## Changing the workpaper layout

All fonts, colours, widths and number formats are in `src/tra/workpaper/layout.py`. To match the firm's template, change that file. `build.py` decides what goes where; `layout.py` decides how it looks.

---

## For developers

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
```

There are 299 tests, all on invented data generated while the tests run.

- **Tax maths:** the two calculations are tested on hand-worked bracket-edge cases and on 5,000 random returns, where they must agree to the cent.
- **Redaction:** every identifier type, plus traps such as amounts, phone numbers, ABNs and dates.
- **End to end:** an end-to-end test plants identifiers in fake documents, runs the whole flow, and scans every file the tool wrote.
- **Workpaper formulas:** if LibreOffice is installed, the workbook is recalculated and checked against Python.

```
config/         rates per year, labels, document types, checks, citations, Xero/FYI settings
src/tra/
  privacy/      validators, detectors, redaction, output guard, audit log, log filter
  ingest/       readers, classifier, extractors, pipeline
  filing/       naming, local store, FYI store, index
  return_/      draft return, CGT
  taxcalc/      rates loader, calculation A, calculation B
  checks/       reconciliation, pre-fill, sanity, prior year, ranking
  workpaper/    build.py (content), layout.py (styling)
  xero/         OAuth (PKCE), API client, figures
  cli.py        the `tra` command
tests/
```

An LLM-based extractor could be added later in `src/tra/ingest/extractors/`. It would work on redacted text only, and only after the firm approves sending data to it (Privacy Act APP 8). None exists today.

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
- **Untested on Windows.** `setup.ps1` was written for Windows but could not be run where the tool was built. Try it on one laptop first.
