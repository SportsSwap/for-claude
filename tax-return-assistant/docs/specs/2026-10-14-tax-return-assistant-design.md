# Tax Return Assistant — Design Spec

**Date:** 14 October 2026
**Status:** Draft for review
**Scope of this spec:** individual returns, first delivery (stages 1–4 working end to end, stages 5–6 built and mock-tested)

---

## 1. Purpose

An internal tool for the Advisory, Accounting & Taxation team. It turns a client's source documents into a **draft** Australian individual tax return, a fully sourced Excel workpaper, and a ranked list of review notes. A registered tax agent at the firm reviews and signs off every return. The tool never lodges anything with the ATO.

It sits *around* Xero Tax rather than replacing it. Xero Tax remains where returns are prepared, pre-fill is pulled, and lodgment happens. Xero Tax has no public API to push a return into, so the tool's job is everything before and around keying-in:

- ingest, redact and file the documents;
- extract figures, each with its source;
- build the workpaper, with working shown in live formulas;
- run self-checks and raise review notes;
- produce a draft label list in Xero Tax item order;
- estimate tax independently, as a cross-check on the Xero Tax estimate.

### Success criteria for the first delivery

1. `tra` runs end to end on a generated fake client (pre-fill report, income statement, bank interest, dividend statements, rental agent statement, receipts, private health statement) and produces:
   - filed documents and an index;
   - `figures.csv`;
   - a workpaper with every tab described in §9;
   - review notes.
2. **No sensitive identifier appears in any output.** A test injects known fake identifiers into the source documents, then scans every file the tool wrote and fails if any identifier appears.
3. Tax calculation A, calculation B, and the workpaper's own Excel formulas (recalculated) agree to the cent on every test case.
4. The full test suite passes.

## 2. Decisions made during brainstorming

| Question | Decision |
|---|---|
| Extraction approach | Local only. Purpose-built parsers for structured documents; everything else goes to manual entry. An extractor plug-in interface exists so an LLM extractor *on redacted text* can be added later, after firm sign-off. It is off by default and no LLM extractor is built now. |
| Tax software | Xero Tax. The draft return follows ATO item order. Pre-fill input is the ATO pre-fill report (PDF or CSV) from Online Services for Agents. |
| Workpaper layout | Sensible default now (§9). All styling lives in one module so it can be re-skinned to the firm template later. |
| Scans and photos | Mostly digital, so no OCR in the first delivery. Image-only PDFs are filed and flagged for manual entry. |
| Machines | Windows laptops. PowerShell setup; `pathlib` everywhere. |
| First delivery | Stages 1–4 working end to end. Stages 5–6 (Xero, FYI) built against published APIs and tested with mocks. |
| Approach | Local Python CLI. Extracted figures go into a CSV that the preparer confirms; the workpaper is built only from confirmed figures. |
| Originals | The original document is filed **unchanged** (FYI is the firm's access-controlled system of record; TASA record keeping). The tool never copies sensitive values into anything it creates. |
| Location | `tax-return-assistant/` in this repo, self-contained, away from the PLS case-study files. |

## 3. Non-goals for the first delivery

- Lodgment of any kind (permanent non-goal).
- Company and trust returns. The data model leaves room for them; nothing is built.
- OCR, an LLM extractor, and a UI.
- Medicare levy family-income reduction, exemptions (M1), foreign income, employee share schemes, PSI, and AMIT component calculations for managed funds. Each is **detected and flagged** for the reviewer, not calculated.
- A full business schedule (P8). Xero P&L totals map to Item 15 and are flagged to complete the detailed labels in Xero Tax.

## 4. Architecture

### 4.1 Layout

```
tax-return-assistant/
  pyproject.toml            # package "tra", console script `tra`, Python >= 3.11
  README.md                 # setup, workflow, privacy controls, compliance mapping
  .gitignore                # blocks client data (see §10.6)
  .env.example              # names of env vars only, no values
  setup.ps1                 # Windows one-command setup
  config/
    rates/fy2025.yaml       # one file per income year (§8.1)
    rates/fy2026.yaml
    doc_types.yaml          # doc type codes → filing category, filename code
    labels.yaml             # internal label keys → ATO item / label / description
    citations.yaml          # citation registry (§8.5)
    checks.yaml             # thresholds for sanity checks (ratios, floors)
    xero_mapping.yaml       # Xero account types → label keys
  src/tra/
    cli.py                  # click commands (§6)
    settings.py             # TRA_HOME, client-code pattern, store selection
    models.py               # Document, Figure, ReviewNote, ClientState dataclasses
    privacy/
      validators.py         # TFN, Medicare, Luhn, ABN check digits
      detectors.py          # pattern + context detectors → Match(type, span)
      redact.py             # redact(text) -> RedactedText ; counts by type
      guard.py              # output guard: scan before any write
      audit.py              # append-only JSONL audit log
      logging_filter.py     # redacts every log record
    ingest/
      readers.py            # PDF (pdfplumber), CSV, XLSX → pages of raw text, in memory
      classify.py           # RedactedText → doc type code
      extractors/           # one module per doc type; registry; Extractor protocol
      pipeline.py           # read → redact → classify → extract → file → figures.csv
    filing/
      naming.py             # [ClientCode]_[FY]_[DocType]_[Date].ext
      store.py              # DocumentStore protocol
      local_store.py        # \Clients\[ClientCode]\[FY]\[Category]\ + index.csv
      fyi_store.py          # FYI adapter (stage 6)
    figures.py              # read/write/validate figures.csv
    return_/
      prepare.py            # confirmed figures → DraftReturn (label → amount + figure ids)
      cgt.py                # CGT event schedule → net capital gain
    taxcalc/
      rates.py              # load + validate a rates YAML
      calc_a.py             # bracket-slice method
      calc_b.py             # published-base-amount method, written separately
      result.py             # TaxResult dataclass
    checks/
      reconcile.py
      prefill.py
      sanity.py
      prior_year.py
      dual_calc.py
      notes.py              # ranking and de-duplication
    workpaper/
      build.py              # openpyxl builder, formulas only
      layout.py             # all styling, column widths, colours, fonts
    xero/
      auth.py               # OAuth2 auth code + PKCE, tokens in Windows Credential Manager
      client.py             # P&L, balance sheet, bank transactions, chart of accounts
      to_figures.py         # Xero data → figures (unconfirmed)
  tests/
    fakes.py                # fake-identifier generators and fake document builders
    ...                     # see §12
  docs/specs/               # this file
```

### 4.2 Boundaries

Each unit has one job and a small interface:

- **`privacy`** depends on nothing else in `tra`. Everything else depends on it.
- **`ingest`** turns files into `Document` records and unconfirmed `Figure` rows. It only accepts `RedactedText` from `privacy.redact`. Extractors are typed to accept `RedactedText`, so passing raw text is a type error, and a runtime check rejects it too.
- **`filing`** knows nothing about tax. It takes the original file plus metadata and returns a filed reference (name, location, link).
- **`return_`** turns *confirmed* figures into a `DraftReturn`.
- **`taxcalc`** is pure functions: `DraftReturn` plus a rates file gives a `TaxResult`. No I/O.
- **`checks`** are pure functions: inputs give a list of `ReviewNote`.
- **`workpaper`** renders everything. It computes nothing that is not also a formula in the sheet.
- **`xero`** produces unconfirmed figures, the same as an extractor.

## 5. Data model

**Document**
- `doc_id`: e.g. `D007`.
- `doc_type`: code from `doc_types.yaml`.
- `category`.
- `filed_name`.
- `filed_location`: local path or FYI link.
- `doc_date`: the date found in the document, otherwise the ingest date, with a review note.
- `pages`.
- `sha256` of the original.
- `ingested_at`.
- `redaction_counts`, e.g. `{"TFN": 1, "BSB": 1}`.
- `parse_status`: `parsed` | `partial` | `manual_needed`.

The **original filename is never recorded** anywhere, because filenames often contain client names or TFNs. The SHA-256 hash ties a filed document back to its source.

**Figure** (one row in `figures.csv`)
- `figure_id`.
- `label_key`, e.g. `income.interest`, `ded.d5`, `rent.gross` (see `labels.yaml`).
- `description`.
- `amount`: Decimal, 2 dp.
- `date`.
- `doc_id` and `page`: required unless `method=manual_no_source`.
- `method`: `parser` | `manual` | `xero`.
- `confirmed`: `Y`/`N`.
- `substantiated`: `Y`/`N`/blank. Used for work-related deductions.
- `notes`.

Rules: only rows with `confirmed=Y` reach the return. A confirmed row with no `doc_id` is allowed but always raises a High review note.

**ReviewNote**
- `risk`: `High` | `Medium` | `Low`.
- `check_id`.
- `message`.
- `dollar_impact`: an estimate, possibly blank.
- `audience`: `client` | `reviewer` | `preparer`.
- `action`: question / confirm / assumption.
- `citation_id`: optional.
- `figure_ids` and `doc_ids`.

**ClientState** (`state.json` per client and year)
- client code, income year, residency (default resident, assumption noted);
- date of birth year *band* only, used for the PHI rebate age bracket and SAPTO eligibility (no full DOB stored);
- spouse and dependants (yes/no plus count);
- HELP debt (yes/no);
- private hospital cover days;
- whether the client is a sole trader;
- the Xero tenant id, if linked.

## 6. Workflow and CLI

All client data lives under `TRA_HOME` (e.g. `C:\TaxAssistant\`). The tool refuses to run if `TRA_HOME` is unset, is inside a git working tree, or is inside a OneDrive, Dropbox or Google Drive synced folder. Cloud sync would move client data offshore, which raises APP 8.

```
TRA_HOME\
  Clients\SMIT01\FY2026\{ATO,Income,Investments,Rental,Deductions,Business,Health,Other}\
  Clients\SMIT01\FY2026\index.csv
  Work\SMIT01\FY2026\state.json, figures.csv, prior_year.csv, Output\
  Inbox\                       # optional drop folder
  audit\audit-2026.jsonl
```

| Command | What it does |
|---|---|
| `tra doctor` | Checks Python, `TRA_HOME`, rates files (and whether each is verified), which env vars are *present* (never prints values), and FYI/Xero configuration. |
| `tra new SMIT01 --fy 2026` | Validates the client code against the pattern (default `^[A-Z0-9]{2,12}$`) and creates folders and `state.json`. |
| `tra ingest SMIT01 <files...> [--fy 2026]` | Runs the stage 1 + 2 pipeline per file and appends unconfirmed rows to `figures.csv`. Prints a summary per document: type, figures found, redaction counts, parse status. |
| `tra figures SMIT01` | Validates `figures.csv` (types, required sources, label keys) and opens it in Excel. |
| `tra prepare SMIT01` | Uses confirmed figures to build the draft return, run both calcs and all checks, and write `Output\SMIT01_FY2026_Workpaper_DRAFT_v{n}.xlsx`. Existing versions are never overwritten. |
| `tra scan <path>` | Runs the privacy detectors over any file or folder and reports matches by type and location, never the values. Useful before sharing anything. |
| `tra xero connect` / `tra xero pull SMIT01` | Stage 5. |
| `tra fyi push SMIT01` | Stage 6. Files are pushed to FYI; local remains the fallback. |

## 7. Stages 1–2: ingest, redaction, filing

### 7.1 Reading

- **PDF:** `pdfplumber`, page by page, in memory. A page with no text layer (image-only) marks the document `manual_needed`.
- **CSV and XLSX:** read as text rows.
- Raw text never leaves `readers.py` except by passing straight to `redact()`.

### 7.2 Redaction

Redaction runs immediately after reading, before classification, extraction or logging. Each match is replaced with `[TFN REDACTED]`, `[MEDICARE REDACTED]`, `[CARD REDACTED]`, `[BSB REDACTED]`, `[ACCOUNT REDACTED]`, `[LICENCE REDACTED]` or `[PASSPORT REDACTED]`. The result is a `RedactedText` object holding the redacted pages and `counts` by type.

| Type | Detection |
|---|---|
| TFN | (a) 8 or 9 digits, optionally separated by spaces or hyphens, that pass the ATO check digit. Weights for 9 digits are 1,4,3,7,5,8,6,9,10; for 8 digits 10,7,8,4,6,3,5,1. The weighted sum must be divisible by 11. (b) **Any** 8–9 digit sequence within 40 characters after "TFN", "tax file number" or "tax file no", *even if the check digit fails*. |
| Medicare | 10 digits (optionally an 11th, the IRN). The first digit is 2–6, and the 9th digit equals (1,3,7,9,1,3,7,9 · first 8 digits) mod 10. Also any 10–11 digit sequence after "Medicare". |
| Card | 13–19 digits (spaces or hyphens allowed) passing Luhn. Already-masked numbers (e.g. `XXXX XXXX XXXX 1234`) are left as they are. |
| BSB | `NNN-NNN` anywhere, and `NNNNNN` or `NNN NNN` after "BSB". |
| Account no. | 5–10 digit sequence (spaces or hyphens allowed) within 30 characters after "account", "acct", "acc no" or "a/c". |
| Driver licence | Alphanumeric token of 4–10 characters with at least 4 digits, within 30 characters after "licence", "license", "DL no" or "driver". |
| Passport | `[A-Z]{1,2}\d{7}` within 30 characters after "passport". |

Rules:
- Bias is towards **over-redaction**. A redacted invoice number costs nothing; a leaked TFN is a breach.
- **Never redacted:** money amounts (anything with `$`, a decimal point, or thousands commas), dates, and ABNs/ACNs. An 11-digit number passing the ABN checksum is ABN-shaped, which prevents a partial TFN match inside it.
- A detector exception aborts that document (fail closed). The audit log records `redaction_failed` with the doc_id only.
- Names and addresses are not in the redaction list. They are never logged, never written to filenames, and extracted text is never persisted, so they don't leak through the tool's own outputs.

### 7.3 Output guard

Every write goes through `guard.check(...)` first: CSV rows, every workpaper cell (strings, and integer numbers of 8–19 digits), `index.csv`, `state.json`, filenames, and log records. If any detector fires, the guard refuses the write, raises `SensitiveDataBlocked(location, detector_type)` (no value), and writes an audit entry.

### 7.4 Classification

The classifier uses keyword rules over the redacted text, configured per doc type in `doc_types.yaml`. Examples: "Individual pre-fill report" → `PREFILL`; "Income statement" or "PAYG payment summary" → `INCSTMT`; "Dividend statement" with "franking credit" → `DIVSTMT`; "rental statement" or "property manager" → `RENTSTMT`; "Private health insurance statement" → `PHI`.

Anything that doesn't match is classified `OTHER` and flagged for manual entry. The preparer can override the type with `tra ingest --type DIVSTMT`.

### 7.5 Extractors (first delivery)

| Doc type | Extracts |
|---|---|
| `PREFILL` | Every pre-fill line: salary and withholding per payer, interest, dividends, PHI, HELP indicator. Stored as *pre-fill* data for comparison, not as figures. Each line is also offered as an unconfirmed figure (`method=parser`, note `prefill`), so a label with no other source can still be sourced to the pre-fill. Check R4 catches the case where the pre-fill line and the source document are both confirmed. |
| `INCSTMT` | Gross payments, tax withheld, allowances, reportable fringe benefits, reportable employer super contributions. |
| `INTSTMT` / `BANKSTMT` | Interest earned for the year and TFN amounts withheld. |
| `DIVSTMT` | Unfranked amount, franked amount, franking credit, payment date. |
| `RENTSTMT` | Gross rent, agent fees, and other expense lines (each line its own figure). |
| `PHI` | Premiums eligible for rebate, rebate received, benefit code, days covered. The membership number is not extracted. |
| `XEROPL` / `XEROBS` / `XEROBANK` (CSV exports) | Account totals mapped via `xero_mapping.yaml`. |
| `RECEIPT` / `OTHER` | Date and total if found, *suggested* label key, and substantiated=`Y` when a dated receipt with a supplier is detected. |
| CSV template | Manual figures in `figures.csv` format, for bulk entry. |

Every extractor returns figures with `doc_id` and `page`. Anything it can't read becomes a `manual_needed` review note, not a guess.

The plug-in interface is `Extractor.supports(doc_type) -> bool` plus `Extractor.extract(RedactedText, Document) -> list[Figure]`.

### 7.6 Filing

- **Name:** `[ClientCode]_[FY]_[DocType]_[Date].ext`, e.g. `SMIT01_FY2026_DIVSTMT_2026-03-24.pdf`.
  - The date is the document date; if none is found, the ingest date is used and a review note raised.
  - A collision adds `_02`, `_03`, and so on.
- **Local store:** `TRA_HOME\Clients\[ClientCode]\[FY]\[Category]\`. The original is copied unchanged.
- **`index.csv` columns:** filed_name, doc_id, doc_type, category, doc_date, pages, sha256, ingested_at, parse_status, store.
  - The same hash ingested twice is recognised as a duplicate: it isn't filed twice and a Low note is raised.
- **Store selection:** `TRA_STORE=local|fyi`. If `fyi` is selected but fails (no credentials, network error, HTTP error), the document is filed locally, a Medium note "filed locally, push to FYI later" is raised, and `tra fyi push` retries later.

## 8. Stage 4: tax calculation and self-checks

### 8.1 Rates config

Each `config/rates/fyYYYY.yaml` contains:

- `income_year`, `period` (1 Jul – 30 Jun);
- `status: unverified | verified`, `verified_by`, `verified_on`, plus `source` URLs per section;
- `resident_brackets`: threshold, marginal rate, **and** the published base amount for each bracket;
- `lito`, `medicare_levy` (rate, low-income thresholds, shade-in rate), `mls` (tiers), `phi_rebate` (tiers × age bands × sub-periods), `help` (repayment schedule), `sapto`, `car_cents_per_km` (rate and km cap), `wfh_fixed_rate`.

`rates.py` validates the file on load:
- brackets are ascending and contiguous;
- each published base amount equals the tax on the previous brackets;
- all percentages are between 0 and 1.

A file with `status: unverified` raises a **High** review note on every return: "FY2026 rates not yet verified against ato.gov.au by a registered agent".

**Verification status of the first-delivery figures.** The ATO, Department of Health and legislation websites are blocked from the environment where this was built. Every figure below was gathered through web-search summaries that cite those sites. Both files therefore ship as `status: unverified` until someone at the firm checks each figure against the primary source.

| FY2026 (2025–26) | Figure |
|---|---|
| Resident brackets | 0–18,200 nil · 18,201–45,000 16c over 18,200 · 45,001–135,000 $4,288 + 30c over 45,000 · 135,001–190,000 $31,288 + 37c over 135,000 · 190,001+ $51,638 + 45c over 190,000 |
| LITO | $700 up to $37,500; less 5c per $1 to $45,000 ($325); less 1.5c per $1 to $66,667 (nil) |
| Medicare levy | 2%. Single low-income threshold $28,011, phase-in to $35,013 (10c per $1 over). SAPTO single $44,268 / $55,335. Family $47,238 + $4,338 per child (family reduction flagged only, §3). |
| MLS | Singles ≤ $101,000 nil · ≤ $118,000 1% · ≤ $158,000 1.25% · above 1.5%. Families $202,000 / $236,000 / $316,000, + $1,500 per child after the first. |
| PHI rebate, 1 Jul 2025 – 31 Mar 2026 | Under 65: 24.288 / 16.192 / 8.095 / 0%. 65–69: 28.337 / 20.240 / 12.143 / 0%. 70+: 32.385 / 24.288 / 16.192 / 0%. |
| PHI rebate, 1 Apr – 30 Jun 2026 | Under 65: 24.118 / 16.079 / 8.038 / 0%. 65–69: 28.139 / 20.098 / 12.058 / 0%. 70+: 32.158 / 24.118 / 16.079 / 0%. |
| HELP (new marginal system) | ≤ $67,000 nil · $67,001–$125,000 15c per $1 over $67,000 · $125,001–$179,285 $8,700 + 17c over $125,000 · ≥ $179,286 10% of total repayment income |
| SAPTO | Single $2,230, shade-out $34,919, cut-out $52,759. Couple (each) $1,602 / $30,994 / $43,810. Illness-separated $2,040 / $33,732 / $50,052. Taper 12.5c. |
| Car | 88c per km, 5,000 km cap |
| WFH fixed rate | 70c per hour |

FY2025 (2024–25) is included for late and prior-year returns. It uses the same brackets and LITO. The figures that differ:
- Medicare single $27,222 / $34,027; SAPTO single $43,020 / $53,775; family $45,907 + $4,216 per child.
- MLS $97,000 / $113,000 / $151,000; families $194,000 / $226,000 / $302,000.
- HELP: the 19-row percentage-of-total-income schedule, starting at $54,435 (1%) and reaching 10% at $159,664.
- SAPTO single shade-out $32,279, cut-out $50,119.
- PHI rebate for both FY2025 sub-periods.
- 88c per km; WFH 70c per hour.

The exact rows go into `fy2025.yaml` with sources, also marked unverified.

### 8.2 Draft return

`prepare.py` sums confirmed figures by `label_key` and maps each to its ATO item and label using `labels.yaml`. Each label keeps the list of figure ids behind it, which is how every number traces back to a source.

`labels.yaml` covers:
- Items 1, 2, 10, 11, 12 (flag only), 13 (flag only), 15, 18, 20 (flag only), 21 and 24;
- D1–D10, plus D12 and D15;
- L1;
- the offsets;
- M1 (flag only) and M2;
- private health insurance details;
- the income test items IT1–IT8 needed for MLS, HELP and PHI income.

Label **letters** come from the 2026 individual and supplementary return instructions but couldn't be confirmed from here. Every entry carries `letter_verified: false` until checked; item numbers and descriptions are the reliable reference.

CGT (`cgt.py`): one row per CGT event (asset description, acquired, disposed, proceeds, cost base, held ≥ 12 months).
- The net capital gain follows the s102-5 method statement: losses are applied to non-discount gains first, then to discount gains; the 50% discount applies to the remaining discount gains for residents (s115-25 12-month rule).
- Prior-year net capital losses come from the pre-fill or are entered manually.
- Any CGT event raises a Medium "confirm cost base and dates" note.

### 8.3 Two independent calculations

Both calculations take the same `DraftReturn` and rates. They live in separate modules and share no helper functions apart from the Decimal rounding utilities.

| Step | Calc A | Calc B |
|---|---|---|
| Taxable income | Sum of income items minus deductions minus L1, cents truncated, floored at 0 | Same inputs, computed by iterating labels.yaml categories (independent summation code) |
| Tax on TI | Σ over brackets of rate × the slice of TI inside each bracket | Published base amount of the bracket containing TI, plus marginal rate × (TI − threshold) |
| LITO | `min(700, max(0, …))` piecewise formula | Lookup over a three-row table of (from, base, taper) |
| Medicare levy | `min(2% × TI, 10% × (TI − lower))` when TI > lower | Explicit three-band rule: ≤ lower → 0; lower–upper → shade-in; > upper → 2% |
| MLS | Rate for the tier containing MLS income × MLS income × days uncovered / days in year | Tier search done separately, same formula |
| HELP | Marginal schedule (FY2026) or %-of-income schedule (FY2025) | Same schedules, evaluated by a different lookup path |
| PHI adjustment | Σ sub-periods (premium share × entitled % − rebate received) | Computed per sub-period from day counts |
| Result | Tax − non-refundable offsets (limited to tax) + levy + MLS + HELP − PHI adjustment − franking credits − PAYG and TFN withholding | Same composition, its own code |

Rounding follows ATO conventions:
- cents are dropped from taxable income;
- tax, levies and offsets are calculated and rounded to the cent (round half up);
- Decimal is used throughout, never floats.

`dual_calc` compares every component. Any difference of 1c or more is a High note naming the component.

The workpaper's Tax Calc sheet computes the same steps with Excel formulas off its own Rates sheet. A test recalculates the workbook (LibreOffice headless, skipped if LibreOffice isn't installed) and asserts it matches calc A.

### 8.4 Self-checks

Each check returns `ReviewNote`s. Thresholds live in `checks.yaml`.

| Check | Rule | Default risk |
|---|---|---|
| R1 Unsourced figure | Confirmed figure with no doc_id/page, or with a doc_id that is not in `index.csv` | High |
| R2 Label totals | Each return label equals the sum of its figures (Python), and the Summary formula references every category total (structural check on the built workbook) | High |
| R3 Unconfirmed figures | Rows still `confirmed=N` at prepare time are listed and excluded | Medium |
| R4 Possible double count | Two confirmed figures on the same label with the same amount (within $1), one from PREFILL and one from another document | High |
| P1 Pre-fill mismatch | Label differs from pre-fill by more than $1 | High |
| P2 Pre-fill item missing | Pre-fill line has no matching figure (e.g. a second bank account's interest) | High |
| P3 No pre-fill | No PREFILL document ingested | Medium |
| C1 Calc mismatch | Calc A ≠ calc B on any component | High |
| C2 Rates unverified | Rates file `status: unverified` | High |
| S1 Deductions vs income | Total deductions over 30% of total income, or D1–D5 over 15% of salary | Medium |
| S2 Missing expected document | Interest with no INTSTMT/BANKSTMT; dividends with no DIVSTMT; salary with no INCSTMT or pre-fill | Medium |
| S3 Rental one-sided | Rental income with no rental expenses, or the reverse | Medium |
| S4 Substantiation | D1–D5 total over $300 and any D1–D5 figure with `substantiated≠Y` (ITAA 1997 s900-35) | High |
| S5 Car cap | Cents-per-km claim over 5,000 km × rate (s28-25) | High |
| S6 Clothing | D3 description suggests conventional clothing (TR 97/12) | Medium |
| S7 Capital vs repair | Rental expense description contains "replace", "renovat", "new", "install" (TR 97/23, Div 40/43) | Medium |
| S8 CGT discount | Discount applied to an asset held under 12 months (s115-25) | High |
| S9 MLS exposure | MLS income over threshold and hospital cover days < days in year | Medium (client question) |
| S10 Interest purpose | Rental interest with "redraw" or "line of credit" in the description (TR 2000/2) | Medium |
| S11 Gifts | D9 gift under $2, or recipient not noted as a DGR (Div 30) | Low |
| S12 Unhandled area | ESS, PSI, foreign income, managed fund AMIT, family Medicare reduction, M1 exemption detected | High (reviewer) |
| Y1 Prior-year movement | Label moved more than 20% **and** more than $100 against `prior_year.csv` | Medium |
| Y2 Prior-year item gone | Label present last year, absent this year (e.g. rental stopped) | Medium (client question) |

**Ranking** (`notes.py`): High, then Medium, then Low; within each, by absolute dollar impact descending. Duplicates are merged by (check_id, label, doc).

**Prior year input:** `prior_year.csv` (label_key, amount), filled from last year's Xero Tax return, or created automatically from the tool's own previous `prepare` output.

### 8.5 Citations

`citations.yaml` maps citation ids to a reference and a one-line description:

- ITAA 1997 s8-1, s25-5, s26-31, s28-25, s40-27, s102-5, s115-25, s900-35, Div 30, Div 43, Div 207;
- TR 97/12, TR 97/23, TR 2000/2, TR 2024/3, PCG 2023/1;
- Medicare Levy Act 1986, HESA 2003, TASA 2009 s30-10.

Each entry has `verified: true|false`. Unverified citations show "(citation to be confirmed by reviewer)" in the workpaper. All ship unverified for the same reason as the rates. Where no citation is known, a note says "reviewer to confirm treatment" rather than citing something uncertain.

## 9. Stage 3: workpaper (default layout)

File: `[ClientCode]_FY2026_Workpaper_DRAFT_v{n}.xlsx`. All styling lives in `workpaper/layout.py`.

| Tab | Contents |
|---|---|
| Cover | Client code, income year, prepared by, date, reviewer, sign-off cells, tool version, rates file status. A red **DRAFT – NOT FOR LODGMENT** banner. |
| Summary | Lead schedule: every label in ATO item order (including zero labels). Columns: Item, Label, Description, This year (formula to the category tab total), Pre-fill, Difference (formula), Prior year, Movement % (formula), Review flag. |
| One tab per category with figures | E.g. Salary & Wages, Interest, Dividends, Rental, Capital Gains, Other Income, D1 Car, D2 Travel, … D10. Columns: Figure ID, Date, Description, Source document, Page, Method, Confirmed, Substantiated, Amount, Notes. A **SUM** total row. Source document cells link to the filed document. |
| Tax Calc | Taxable income through to refund or payable, entirely as formulas off Summary and Rates. A "Python check (calc B)" column and a difference column with conditional formatting. |
| Rates | The rates file copied in, so the workbook stands alone, with its verification status shown. |
| Sources | The document index: doc ID, filed name, type, date, pages, link. |
| Review Notes | Every note, ranked. Columns: #, Risk, Area, Note, $ impact, For (client/reviewer/preparer), Action, Citation, Figure/doc refs, Response (blank for the reviewer). |

Rules:
- No total, subtotal or calculated cell is a hardcoded number. A test walks every total cell and asserts it holds a formula.
- Inputs (figure amounts, rates) are the only literal numbers, and every input row carries a source reference.

## 10. Privacy and compliance controls

1. **Redact first** (§7.2), and the type system enforces it.
2. **Output guard** on every write (§7.3).
3. **Logging:** all records pass through `logging_filter`. Log lines identify clients only by client code. Raw document text is never logged at any level.
4. **Audit log:** `TRA_HOME\audit\audit-YYYY.jsonl`, append-only. Each entry has timestamp, Windows username, action, client code, and doc_id or filed name. It covers redaction counts, files written, Xero and FYI calls (endpoint name only) and guard blocks. **No values, no original filenames.**
5. **Secrets:** env vars `XERO_CLIENT_ID`, `FYI_ACCESS_ID`, `FYI_ACCESS_SECRET`, `FYI_APP_ID` (names in `.env.example`). The Xero refresh token is stored in Windows Credential Manager via `keyring`. Nothing secret goes in code, config or the repo.
6. **No client data in git:** `tax-return-assistant/.gitignore` blocks `*.pdf`, `*.xlsx`, `*.csv`, `*.jsonl` and `.env` outside `tests/` and `config/`. `TRA_HOME` must sit outside any git working tree, which `tra doctor` enforces. Test identifiers are generated in memory at test time and never committed; a test scans the repo's committed files for checksum-valid TFNs, Medicare numbers and card numbers.
7. **No external calls with client data** in the first delivery. The only outbound calls are Xero and FYI, both explicitly invoked, and no LLM calls exist. Xero responses go through field-level stripping (e.g. `BankAccountNumber`) and then the redactor.
8. **README compliance section** maps the controls to:
   - APP 1 (open and transparent management), APP 6 (use and disclosure), APP 8 (cross-border disclosure), APP 11 (security), APP 12 (access);
   - TASA 2009 s30-10 Code items: confidentiality, reasonable care, competence;
   - the NDB scheme: what to do if the guard ever blocks a leak.

   It recommends BitLocker on the drive holding `TRA_HOME` and notes that the firm's privacy officer should confirm the controls.

## 11. Stages 5–6: Xero and FYI

**Xero (stage 5)**
- **Auth:** OAuth2 authorisation code with PKCE (public client, so no client secret on laptops), via a localhost redirect. Tokens are stored in Windows Credential Manager.
- **Scopes:** Xero granular scopes are mandatory for apps created on or after 2 March 2026. The exact scope names are configured in `xero_mapping.yaml` and must be confirmed in the Xero developer portal when the firm registers the app.
- **Calls:** connections (tenant selection), Reports/ProfitAndLoss and Reports/BalanceSheet (for the income year), BankTransactions (paged), Accounts.
- **Errors:** 401 `insufficient_scope` gives a clear "update permissions" message. 429 is retried with backoff.
- **Output:** unconfirmed figures with `method=xero` and the Xero report as the source, saved as a JSON snapshot in the client's Business folder and indexed like a document.
- **Tests:** mocked HTTP responses built from Xero's documented response shapes.

**FYI (stage 6)**
- **Auth:** FYI's external API uses header credentials (an access ID, an access secret, and an application identifier issued by FYI). The base URL and endpoint paths for "find client by code" and "upload document to cabinet" couldn't be confirmed from the developer docs here, so they are **config values** in `settings`, documented as "confirm with FYI before first use".
- **Adapter:** `FyiStore` implements the `DocumentStore` protocol, setting the filename, client code, cabinet from the category map, and year.
- **Tests:** contract tests against mocks.
- **Fallback:** local store (§7.6).

## 12. Testing

Tests use pytest. All data is fake and generated at test time (reportlab for PDFs).

| Area | Tests |
|---|---|
| Validators | TFN 8- and 9-digit check digits, both valid and invalid (generated). Medicare check digit and first digit. Luhn. ABN. |
| Redaction | Spaced, hyphenated and line-split numbers. Context-only TFN with a bad check digit. False-positive traps: `$123,456.78`, phone numbers, dates, ABNs, invoice numbers. Counts by type. A detector exception fails closed. |
| Output guard | Blocks CSV, XLSX cell, filename and log writes containing each identifier type. Error messages never contain the value. |
| Tax calc | Hand-worked cases at and either side of every bracket, LITO, Medicare, MLS tier and HELP boundary. Calc A == calc B on 5,000 generated incomes from $0 to $500k. Rates validation rejects a broken file. |
| CGT | Losses applied to non-discount gains first. Discount only at 12 months or more. Prior-year losses. |
| Checks | Each check id has a test that triggers it and one that doesn't. Ranking order. |
| Reconciliation | An unsourced figure is flagged. Label sums equal figure sums. |
| Workpaper | Every total cell is a formula. Every figure row has a source. Required tabs exist. The DRAFT banner is present. LibreOffice recalculation matches calc A (skipped if unavailable). |
| Filing | Naming, collisions, duplicate hash, index columns, FYI-failure fallback. |
| Xero / FYI | Mocked auth, paging, 401/429 handling, field stripping, mapping to figures. |
| End to end | A fake client through `new → ingest → (auto-confirm in test) → prepare`. Then **every** output file and the audit log are scanned for the injected fake identifiers. |
| Repo hygiene | No committed file contains a checksum-valid TFN, Medicare number or card number. |

## 13. Error handling

| Situation | Behaviour |
|---|---|
| Unreadable or image-only document | Filed; `manual_needed` note raised |
| Unknown document type | `OTHER`; filed under Other; note raised |
| Redaction error | That document stops; nothing written; audit entry |
| Output guard trips | Write refused; command exits non-zero with location and type |
| Rates file missing for the year | Hard error naming the expected file |
| Rates file invalid | Hard error naming the failed rule |
| `figures.csv` malformed | `tra figures` / `prepare` lists each bad row and stops |
| FYI unavailable | Local fallback plus note |
| Xero token expired or revoked | Clear message to run `tra xero connect` |

## 14. Risks and open items

1. **Rates and citations are unverified** (§8.1, §8.5). Someone at the firm has to verify both files against the primary sources before the tool is used on a real return. The tool enforces this with a High note on every return until the files are marked verified.
2. **ATO label letters are unverified** (§8.2).
3. **FYI endpoints are unconfirmed** (§11). They need FYI developer documentation or support.
4. **Xero app registration** (client id, granular scope names) must be done by the firm.
5. **Parser coverage:** layouts differ by bank, registry and agent. The first delivery parses the fake layouts plus the pre-fill report; real-world layouts get added one at a time as they're met. The manual-entry path covers the gap.
6. **Repository:** this is a firm tool living in a personal repo next to an unrelated case study. It's worth moving to a firm-owned private repo before anyone else at the firm uses it.
