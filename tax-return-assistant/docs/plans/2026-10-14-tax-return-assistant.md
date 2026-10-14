# Tax Return Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local Windows-friendly Python CLI (`tra`) that ingests and redacts client tax documents, files them, builds a draft individual return with a fully sourced Excel workpaper, runs two independent tax calculations plus self-checks, and raises ranked review notes. Xero and FYI clients are included and mock-tested.

**Architecture:** A `src/tra` package of small modules, each with one job: `privacy` → `ingest` → `filing` → `return_` → `taxcalc` → `checks` → `workpaper`, with `xero` and `fyi` adapters. Client data lives under `TRA_HOME`, outside the repo. Only `RedactedText` crosses from reading into processing, and every write passes an output guard.

**Tech Stack:** Python ≥ 3.11, click, pdfplumber, openpyxl, PyYAML, requests, keyring, reportlab (demo/fake documents), pytest.

**Spec:** `tax-return-assistant/docs/specs/2026-10-14-tax-return-assistant-design.md` (read it alongside this plan; § references below point into it).

## Global Constraints

- Everything lives under `tax-return-assistant/`. Nothing outside that folder is modified except the root `.gitignore` (not needed; the folder has its own).
- All commands below run from `tax-return-assistant/`.
- Python ≥ 3.11 syntax only (no `type` statements). Use `pathlib` everywhere; no hard-coded `/` separators.
- Money: `decimal.Decimal` only, never float. Rounding helpers live in `tra/money.py`.
- Sensitive values (TFN, Medicare, card, BSB, account, licence, passport) must never appear in any file, log line, exception message, or audit entry the tool writes.
- The original source filename is never recorded or logged (§5).
- Clients are identified only by client code, pattern default `^[A-Z0-9]{2,12}$`.
- Income year label format: `FY2026` = 1 July 2025 – 30 June 2026.
- Filed name format: `[ClientCode]_[FY]_[DocType]_[YYYY-MM-DD].ext`.
- Redaction placeholders, verbatim: `[TFN REDACTED]`, `[MEDICARE REDACTED]`, `[CARD REDACTED]`, `[BSB REDACTED]`, `[ACCOUNT REDACTED]`, `[LICENCE REDACTED]`, `[PASSPORT REDACTED]`.
- Workpaper banner text, verbatim: `DRAFT – NOT FOR LODGMENT`.
- Env var names: `TRA_HOME`, `TRA_STORE` (`local`|`fyi`, default `local`), `TRA_CLIENT_CODE_PATTERN`, `XERO_CLIENT_ID`, `FYI_BASE_URL`, `FYI_ACCESS_ID`, `FYI_ACCESS_SECRET`, `FYI_APP_ID`.
- No test or committed file may contain a checksum-valid TFN or Medicare number. Tests build valid ones at runtime. The only allowed checksum-valid card in source is the public test number `4111 1111 1111 1111`.
- Commit messages end with the session's attribution lines.

## Review Focus

1. **`figures.csv` after an Excel round trip.** Excel saves with a UTF-8 BOM, rewrites dates as `dd/mm/yyyy`, shows amounts as `1234.5` or `$1,234.50`, and users type `y`/`yes`/`Yes`. All of these must load without error (test in Task 8).
2. **A file open in Excel is locked on Windows.** Writing `figures.csv` or the workpaper then raises `PermissionError`. The tool must say "close <file> in Excel and re-run" and must never leave a half-written file; writes go to a temp file followed by `os.replace` (test in Task 8).
3. **Cloud-synced or odd `TRA_HOME` paths:** `C:\Users\x\OneDrive - Firm Pty Ltd\Tax`, paths with spaces, and lowercase `onedrive`. These must be detected and refused (test in Task 4).
4. **Identifiers split by PDF extraction.** For example, `123 456\n782` or `2123 45670\n1` across a line break must still be redacted (test in Task 2).
5. **Re-running commands.** Ingesting the same file twice must not file or extract twice. Running `prepare` twice must write `_v2`, never overwrite `_v1` (tests in Tasks 10 and 19).

---

## Stage 1: ingest and redaction

### Task 1: Scaffold and check-digit validators

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/tra/__init__.py`, `src/tra/privacy/__init__.py`, `src/tra/privacy/validators.py`, `tests/conftest.py`, `tests/test_validators.py`

**Interfaces:**
- Produces:
  - `tfn_valid(digits: str) -> bool`, `medicare_valid(digits: str) -> bool`, `luhn_valid(digits: str) -> bool`, `abn_valid(digits: str) -> bool`. All take a digits-only string; wrong length returns False.
  - `tra.__version__ = "0.1.0"`.
  - `conftest.py` fixtures: `make_tfn(length=9)`, `make_medicare()`, `make_card()`. Each builds a checksum-valid random value with test-local helpers written from the spec weights, *not* by importing `validators`.

- [ ] **Step 1: Write `pyproject.toml`.** Use setuptools with src layout, `[project.scripts] tra = "tra.cli:main"`, runtime deps `click, pdfplumber, openpyxl, pyyaml, requests, keyring, reportlab`, and optional `[dev]` with `pytest`. Write `.gitignore` blocking `*.pdf *.xlsx *.xls *.csv *.jsonl .env .venv/ __pycache__/ *.egg-info/ build/ dist/`, with `!tests/**` and `!config/**` re-includes. Run `pip install -e ".[dev]"`; expected: succeeds.
- [ ] **Step 2: Write failing tests** in `tests/test_validators.py`:
  - `test_tfn_valid_generated_9_and_8_digit`: 200 values from `make_tfn(9)` and `make_tfn(8)` are all True.
  - `test_tfn_invalid`: `tfn_valid("123456789") is False`, `tfn_valid("12345678") is False`, `tfn_valid("1234567") is False`.
  - `test_tfn_single_digit_change_invalidates`: changing any one digit of a generated valid TFN gives False in ≥ 90% of cases.
  - `test_medicare_valid_and_first_digit`: generated values are True; the same value with first digit `1` or `7` is False; a 10-digit value with a wrong 9th digit is False; an 11-digit value (with IRN) is True.
  - `test_luhn`: `luhn_valid("4111111111111111")` is True; `"4111111111111112"` is False.
  - `test_abn`: `abn_valid("51824753556")` (the ATO's published example ABN) is True; `"51824753557"` is False.
- [ ] **Step 3: Run** `python -m pytest tests/test_validators.py -v`. Expected: FAIL (import error).
- [ ] **Step 4: Implement `validators.py`.**
  - TFN: 9-digit weights 1,4,3,7,5,8,6,9,10; 8-digit weights 10,7,8,4,6,3,5,1; valid when the sum is divisible by 11.
  - Medicare: first digit 2–6; the 9th digit equals (1,3,7,9,1,3,7,9 · digits 1–8) mod 10; 10 or 11 digits.
  - ABN: subtract 1 from the first digit, weights 10,1,3,5,7,9,11,13,15,17,19, valid when the sum is divisible by 89.
- [ ] **Step 5: Run the tests.** Expected: PASS.
- [ ] **Step 6: Commit** `feat(tra): scaffold package and check-digit validators`.

### Task 2: Detectors and redaction

**Files:**
- Create: `src/tra/privacy/detectors.py`, `src/tra/privacy/redact.py`, `tests/test_redact.py`

**Interfaces:**
- Consumes: Task 1 validators.
- Produces:
  - `Match(type: str, start: int, end: int)`: frozen dataclass. `type` is one of `TFN MEDICARE CARD BSB ACCOUNT LICENCE PASSPORT`.
  - `find_sensitive(text: str, *, context: bool = True) -> list[Match]`. Matches are non-overlapping and sorted. `context=False` returns only checksum-validated matches (TFN, Medicare, card); it is used by the repo hygiene test.
  - `RedactedText`: frozen dataclass with `pages: tuple[str, ...]`, `counts: Mapping[str, int]`, and property `text` (pages joined with `"\n\f\n"`). The constructor requires the keyword `_key=redact._KEY`; any other value raises `TypeError`.
  - `redact_pages(pages: list[str]) -> RedactedText` and `redact_text(text: str) -> str`.
  - `RedactionError(Exception)`. Any internal exception is wrapped in it, and the message never includes text.
  - `PLACEHOLDER: dict[str, str]`, with the values from Global Constraints.

- [ ] **Step 1: Write failing tests** (use the conftest generators):
  - `test_tfn_checksum_spaced_and_hyphenated`: `f"TFN: {t[:3]} {t[3:6]} {t[6:]}"` and the hyphenated form both become `"TFN: [TFN REDACTED]"`, and `counts["TFN"] == 1`.
  - `test_tfn_checksum_without_context`: a valid TFN mid-sentence with no keyword is redacted.
  - `test_tfn_context_bad_checksum`: `"Tax file number 123 456 789"` is redacted.
  - `test_tfn_split_across_line`: `f"TFN {t[:3]} {t[3:6]}\n{t[6:]}"` is redacted (Review Focus 4).
  - `test_medicare_with_irn_and_line_break`: the generated Medicare number written as `"2xxx xxxxx\n1"` after `"Medicare card"` is redacted.
  - `test_card_luhn`: `"Card 4111 1111 1111 1111"` is redacted. `"XXXX XXXX XXXX 1234"` is unchanged.
  - `test_bsb_and_account`: `"BSB 062-000 Account number 1234 5678"` gives `"BSB [BSB REDACTED] Account number [ACCOUNT REDACTED]"`.
  - `test_licence_and_passport`: `"Driver licence no. 12345678"` → `[LICENCE REDACTED]`; `"Passport PA1234567"` → `[PASSPORT REDACTED]`.
  - `test_not_redacted`: each of `"$123,456.78"`, `"Total 85,000.00"`, `"Phone 02 9876 5432"`, `"Mobile 0412 345 678"`, `"24/03/2026"`, `"ABN 51 824 753 556"`, `"Invoice INV-2026-0042"` is unchanged.
  - `test_redacted_text_cannot_be_built_directly`: `RedactedText(pages=("x",), counts={})` raises `TypeError`.
  - `test_detector_exception_fails_closed`: monkeypatch a detector to raise; `redact_pages` raises `RedactionError`, and `str(err)` contains none of the input text.
- [ ] **Step 2: Run** `python -m pytest tests/test_redact.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement the detectors** per spec §7.2.
  - Digit groups may be separated by `[ \t-]` or a single `\n`.
  - Amount guard: skip any candidate immediately preceded by `$` or containing `,` or `.`.
  - ABN guard: an 11-digit run that passes `abn_valid`, or that follows `ABN`, is excluded before the TFN scan.
  - Context windows: 40 characters for TFN, 30 for the others, case-insensitive.
  - `redact_pages` replaces matches right to left so offsets stay valid.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): redact identifiers before processing`.

### Task 3: Output guard, audit log, logging filter

**Files:**
- Create: `src/tra/privacy/guard.py`, `src/tra/privacy/audit.py`, `src/tra/privacy/logging_filter.py`, `tests/test_guard_audit.py`

**Interfaces:**
- Consumes: `find_sensitive`, `redact_text`.
- Produces:
  - `SensitiveDataBlocked(Exception)`, built as `SensitiveDataBlocked(location: str, detector_type: str)`. Its message is `f"Refused to write {location}: looks like a {detector_type}"`.
  - `check_text(value: str, location: str) -> None`.
  - `check_rows(rows: Iterable[Iterable[object]], location: str) -> None`. Scans strings, and ints with 8–19 digits.
  - `check_workbook(wb: openpyxl.Workbook, location: str) -> None`. Skips cells whose value starts with `=`.
  - `atomic_write_text(path: Path, text: str, location: str) -> None`: guard, write to `path.with_suffix(path.suffix + ".tmp")`, then `os.replace`.
  - `FileLockedError(Exception)`: raised when `PermissionError` occurs on replace. Its message is `f"{path.name} is open in another program (probably Excel). Close it and re-run."`.
  - `AuditLog(path: Path)` with `.record(action: str, client: str | None = None, **fields: object) -> None`. Each entry is one JSON line `{"ts", "user", "action", "client", ...fields}`. Fields are guard-checked; on a block, the entry is recorded as `{"action": "guard_blocked", "blocked_action": action, "detector": type}`.
  - `RedactingFilter(logging.Filter)`: rewrites `record.msg` with `redact_text(record.getMessage())` and clears `record.args`. `configure_logging(log_path: Path) -> None` attaches it to a file handler.

- [ ] **Step 1: Write failing tests:**
  - `test_check_text_blocks_each_type`: one generated sample per detector type raises `SensitiveDataBlocked`, and `str(err)` never contains the sample.
  - `test_check_rows_blocks_int_tfn`: a row containing `int(make_tfn())` raises.
  - `test_check_workbook_blocks_cell`: Sheet `Interest`, cell B7 holds a TFN string; the error message contains `Interest!B7`.
  - `test_atomic_write_permission_error`: monkeypatch `os.replace` to raise `PermissionError`; `FileLockedError` is raised, the original file is unchanged and no `.tmp` is left (Review Focus 2).
  - `test_audit_records_and_blocks`: a normal record is appended with `user` and `ts`; a record with `note=<tfn>` writes a `guard_blocked` line, and the TFN is not in the file.
  - `test_logging_filter_redacts`: logging `"client TFN %s"` with a TFN writes `[TFN REDACTED]` to the log file.
- [ ] **Step 2: Run** `python -m pytest tests/test_guard_audit.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** per the interfaces. `user` is `getpass.getuser()`; `ts` is ISO-8601 local time with offset.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): guard every write, audit log without values`.

### Task 4: Settings, models, workspace, money and date utilities

**Files:**
- Create: `src/tra/settings.py`, `src/tra/models.py`, `src/tra/workspace.py`, `src/tra/money.py`, `src/tra/dates.py`, `tests/test_settings_workspace.py`, `tests/test_money_dates.py`

**Interfaces:**
- Produces:
  - **`money.py`**
    - `parse_amount(s: str) -> Decimal`: accepts `1,234.56`, `$1,234.56`, `1234.5`, `(1,234.56)` (negative), and `-1234.56`; anything else raises `ValueError`.
    - `round_cents(d: Decimal) -> Decimal`: ROUND_HALF_UP to 0.01.
    - `truncate_dollars(d: Decimal) -> Decimal`: towards zero, to 1.
  - **`dates.py`**
    - `parse_date(s: str) -> date | None`: accepts `YYYY-MM-DD`, `dd/mm/yyyy`, `d/m/yy`, `d Month yyyy` and `d Mon yyyy`.
    - `find_doc_date(text: str) -> date | None`. Priority: a date after `Statement date|Payment date|Date paid|Issue date`, else the end date of `... to <date>` / `Period ending <date>`, else None.
    - `fy_label(year: int) -> str` (`"FY2026"`).
    - `fy_bounds(year: int) -> tuple[date, date]`.
    - `days_in_fy(year: int) -> int`.
  - **`models.py`** (dataclasses per spec §5)
    - `Document`: fields `doc_id, doc_type, category, filed_name, filed_location, doc_date, date_detected: bool, pages: int, sha256, ingested_at: datetime, redaction_counts: dict[str, int], parse_status: str, store: str`.
    - `Figure`: fields `figure_id, label_key, description, amount: Decimal, date: date | None, doc_id: str | None, page: int | None, method: str, confirmed: bool, substantiated: bool | None, notes: str`.
    - `PrefillLine(label_key, payer, amount: Decimal, doc_id, page)`.
    - `ReviewNote`: fields `risk, check_id, message, dollar_impact: Decimal | None, audience, action, label_key: str | None = None, citation_id: str | None = None, figure_ids: tuple = (), doc_ids: tuple = ()`.
    - `ClientState`: fields `client_code, income_year, resident=True, age_band="under65", sapto_status="none", has_spouse=False, dependants=0, help_debt=False, hospital_cover_days: int | None = None, sole_trader=False, xero_tenant_id: str | None = None`. Allowed `age_band` values: `under65 | 65to69 | 70plus`; allowed `sapto_status` values: `none | single | couple | illness_separated`.
  - **`settings.py`**
    - `Settings(tra_home: Path, store: str, client_code_pattern: str)` with `Settings.from_env(env: Mapping[str, str] = os.environ) -> Settings`. Raises `ConfigError("TRA_HOME is not set")`.
    - `check_tra_home(path: Path) -> list[str]`. It returns human-readable problems for: path missing; a `.git` folder in the path or any parent; any path part matching `(?i)^(onedrive.*|dropbox|google drive|googledrive|icloud ?drive)$`.
    - `validate_client_code(code: str, pattern: str) -> None`: raises `ValueError`.
  - **`workspace.py`**
    - `Workspace(tra_home: Path, client_code: str, income_year: int)` with properties:
      - `clients_dir` = `tra_home/Clients/<code>/FY<year>`
      - `work_dir` = `tra_home/Work/<code>/FY<year>`
      - `index_csv` = `clients_dir/index.csv`
      - files in `work_dir`: `figures_csv`, `cgt_csv` (`cgt_events.csv`), `prefill_json`, `prior_year_csv`, `ingest_notes_json`, `state_json`
      - `output_dir` = `work_dir/Output`
      - `audit_path` = `tra_home/audit/audit-<calendar year>.jsonl`
    - Methods: `create(categories: list[str]) -> None`, `exists() -> bool`, `load_state() -> ClientState`, `save_state(state) -> None` (atomic, guarded).

- [ ] **Step 1: Write failing tests:**
  - `test_parse_amount_variants`: each format above, plus `parse_amount("abc")` raises.
  - `test_round_and_truncate`: `round_cents(Decimal("2.345")) == Decimal("2.35")`; `truncate_dollars(Decimal("45000.99")) == 45000`.
  - `test_parse_date_variants`: each format; `find_doc_date("Statement date: 24/03/2026") == date(2026, 3, 24)`; `find_doc_date("Period 1 July 2025 to 30 June 2026") == date(2026, 6, 30)`.
  - `test_fy`: `fy_label(2026) == "FY2026"`; `fy_bounds(2026) == (date(2025, 7, 1), date(2026, 6, 30))`; `days_in_fy(2026) == 365`; `days_in_fy(2024) == 366`.
  - `test_check_tra_home_cloud_paths` (Review Focus 3): a path containing the part `OneDrive - Firm Pty Ltd`, and one containing `onedrive`, each return a problem; `tmp_path / "Tax Assistant"` (with a space) returns no problems.
  - `test_check_tra_home_inside_git`: `tmp_path` with a `.git` folder and `TRA_HOME` beneath it returns a problem.
  - `test_client_code`: `SMIT01` passes; `"Smith John"` and `"SMIT 01"` raise.
  - `test_workspace_create_and_state_roundtrip`: `create()` makes every category folder plus `Output`; saving then loading `ClientState` round-trips.
- [ ] **Step 2: Run** `python -m pytest tests/test_settings_workspace.py tests/test_money_dates.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** per the interfaces. Workspace categories come from the caller (Task 5's doc-type config) so there is a single source of truth.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): settings, models, workspace and money/date helpers`.

### Task 5: Readers, doc types, classifier

**Files:**
- Create: `config/doc_types.yaml`, `src/tra/ingest/__init__.py`, `src/tra/ingest/readers.py`, `src/tra/ingest/classify.py`, `tests/test_readers_classify.py`

**Interfaces:**
- Consumes: `redact_pages`, `RedactedText`.
- Produces:
  - `LoadedDocument(redacted: RedactedText, sha256: str, page_count: int, image_only_pages: tuple[int, ...], suffix: str)`.
  - `load(path: Path) -> LoadedDocument`. Supported suffixes are `.pdf .csv .xlsx .json`; anything else raises `UnsupportedFile(suffix)`. Raw text exists only inside this function and goes straight to `redact_pages`. For CSV, XLSX and JSON, a page is the whole file rendered as lines.
  - `DocType(code, category, description, all: tuple[str, ...], any: tuple[str, ...])`.
  - `load_doc_types(path: Path | None = None) -> dict[str, DocType]`, in file order, defaulting to `config/doc_types.yaml` located relative to the package (`Path(__file__).parents[2] / "config"`).
  - `CATEGORIES = ("ATO", "Income", "Investments", "Rental", "Deductions", "Business", "Health", "Other")`.
  - `classify(rt: RedactedText, doc_types) -> str`: the first type whose `all` keywords are all present and whose `any` list is empty or has one present (case-insensitive). Default `OTHER`.

- [ ] **Step 1: Write `config/doc_types.yaml`** with these codes and categories, in this order:

  | Code | Category | Keywords |
  |---|---|---|
  | `PREFILL` | ATO | all `["pre-fill report"]` |
  | `PRIOR` | ATO | all `["tax return for individuals"]`, any `["notice of assessment", "return summary"]` |
  | `INCSTMT` | Income | any `["income statement", "payg payment summary"]` |
  | `DIVSTMT` | Investments | all `["dividend"]`, any `["franking credit", "franked amount"]` |
  | `MFUND` | Investments | any `["amit member annual statement", "annual tax statement"]` |
  | `INTSTMT` | Investments | any `["interest summary", "interest statement"]` |
  | `BANKSTMT` | Investments | all `["statement"]`, any `["opening balance", "closing balance"]` |
  | `CGT` | Investments | any `["capital gains report", "contract note"]` |
  | `RENTSTMT` | Rental | any `["rental statement", "property manager", "owner statement"]` |
  | `PHI` | Health | all `["private health insurance statement"]` |
  | `XEROPL` | Business | all `["profit and loss"]`, any `["xero", "account code"]` |
  | `XEROBS` | Business | all `["balance sheet"]`, any `["xero", "account code"]` |
  | `XEROBANK` | Business | all `["bank transactions"]` |
  | `XEROCOA` | Business | all `["chart of accounts"]` |
  | `RECEIPT` | Deductions | any `["tax invoice", "receipt"]` |
  | `OTHER` | Other | (no keywords) |

  `MFUND` sits before `INTSTMT` and `BANKSTMT` because fund statements mention interest.
- [ ] **Step 2: Write failing tests:**
  - `test_load_pdf_redacts_before_return`: build a one-page PDF with reportlab containing `"TFN 123 456 789"`; `load()` gives `redacted.text` containing `[TFN REDACTED]` and `counts["TFN"] == 1`.
  - `test_load_image_only_page`: a PDF page with only a drawn rectangle gives `image_only_pages == (1,)`.
  - `test_load_csv_and_unsupported`: a CSV loads as one page; `.docx` raises `UnsupportedFile`.
  - `test_classify_examples`: one short text per code returns that code, including a fund statement that also mentions "interest" (→ `MFUND`). Unknown text → `OTHER`.
  - `test_sha256_stable`: loading the same file twice gives the same `sha256`.
- [ ] **Step 3: Run** `python -m pytest tests/test_readers_classify.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement.** A PDF page whose extracted text is empty after `.strip()` counts as image-only.
- [ ] **Step 5: Run the tests.** Expected: PASS.
- [ ] **Step 6: Commit** `feat(tra): read, redact and classify documents`.

### Task 6: Demo documents and first extractors

**Files:**
- Create: `src/tra/demo.py`, `src/tra/ingest/extractors/__init__.py`, `src/tra/ingest/extractors/base.py`, `prefill.py`, `income_statement.py`, `interest.py`, `dividends.py` (all under `extractors/`), `tests/test_extractors_income.py`

**Interfaces:**
- Consumes: `RedactedText`, `Figure`, `PrefillLine`, `parse_amount`, `find_doc_date`.
- Produces:
  - `ExtractResult(figures: list[Figure], prefill: list[PrefillLine], doc_date: date | None, parse_status: str)`. `parse_status` is `parsed` when every expected field was found, `partial` when some were, `manual_needed` when none were.
  - Protocol `Extractor` with `doc_types: frozenset[str]` and `extract(rt: RedactedText, doc_id: str) -> ExtractResult`. It raises `TypeError` unless `isinstance(rt, RedactedText)`. Figures are returned with `figure_id=""`, `method="parser"` and `confirmed=False`.
  - `get_extractor(doc_type: str) -> Extractor | None`.
  - `demo.DemoIdentifiers(tfn: str, medicare: str, card: str, bsb: str, account: str, licence: str)`.
    - `demo.SAFE_IDENTIFIERS` holds values that are caught only by context rules, so no checksum-valid TFN or Medicare number is ever written by the demo: `tfn="123 456 789"`, `medicare="1234 56789 0"`, `card="4111 1111 1111 1111"`, `bsb="062-000"`, `account="1234 5678"`, `licence="12345678"`.
  - `demo.build_demo_documents(target: Path, ids: DemoIdentifiers = SAFE_IDENTIFIERS) -> DemoClient`.
    - `DemoClient` has `paths: dict[str, Path]` keyed by doc type and `expected: dict[str, Decimal]`, the label_key totals the extractors should find.
    - Documents and contents:

      | Doc | Contents |
      |---|---|
      | `prefill.pdf` | TFN; salary $85,000.00 / withheld $19,000.00 from ACME PTY LTD; interest $412.35 from COMMONWEALTH BANK; dividends franked $1,200.00, franking credit $514.29 from BHP GROUP LTD; PHI premiums |
      | `income_statement.pdf` | TFN; gross $85,000.00, tax withheld $19,000.00, RFB $0.00, RESC $0.00, allowances $1,200.00 |
      | `bank_interest.pdf` | BSB, account, interest $412.35, period 1 July 2025 to 30 June 2026 |
      | `dividend_bhp.pdf` | Franked $1,200.00, unfranked $0.00, franking credit $514.29, payment date 24 March 2026 |
      | `rental.pdf` | Gross rent $26,000.00, management fees $1,820.00, repairs $640.00, council rates $2,100.00, water $780.00 |
      | `phi.pdf` | Premiums 1 Jul–31 Mar $1,800.00, rebate $437.18; premiums 1 Apr–30 Jun $600.00, rebate $144.71; benefit code 30; Medicare number |
      | `receipt_laptop.pdf` | Tax invoice, OFFICEWORKS, 12 August 2025, total $1,499.00, card |
      | `receipt_union.pdf` | Receipt, union fees, $520.00, deliberately undated so it is not marked substantiated |

    - Each line is drawn with `canvas.drawString` so pdfplumber yields one line per string.
  - Line grammars the extractors parse (also what `demo.py` writes):
    - **PREFILL** (zero amounts are skipped; the demo writes `HELP ... No`):
      - `Salary or wages  <PAYER>  Gross payments <amt>  Tax withheld <amt>`
      - `Interest  <PAYER>  Gross interest <amt>  TFN amounts withheld <amt>`
      - `Dividends  <PAYER>  Unfranked <amt>  Franked <amt>  Franking credit <amt>`
      - `Private health insurance  <PAYER>  Premiums eligible <amt>  Rebate received <amt>`
      - `HELP  Debt balance indicator  Yes|No`
    - **INCSTMT:** `Gross payments <amt>`, `Total tax withheld <amt>`, `Allowances <amt>`, `Reportable fringe benefits amount <amt>`, `Reportable employer superannuation contributions <amt>`, `Payer: <name>`.
    - **INTSTMT/BANKSTMT:** `Interest earned <amt>` or `Total interest <amt>`, and `TFN withholding <amt>`.
    - **DIVSTMT:** `Unfranked amount <amt>`, `Franked amount <amt>`, `Franking credit <amt>`, `Payment date <date>`.
  - Label keys produced: `income.salary`, `income.salary_tax_withheld`, `income.allowances`, `it.rfb`, `it.resc`, `income.interest`, `income.interest_tfn_withheld`, `income.div_unfranked`, `income.div_franked`, `income.franking_credit`, `income.div_tfn_withheld`.
  - PREFILL also emits `PrefillLine`s for the `info`-role keys `phi.premiums_total`, `phi.rebate_total` and `help.indicator` (1 when Yes; skipped when No). It emits unconfirmed `notes="prefill"` figures for every pre-fill line *except* `info`-role keys.

- [ ] **Step 1: Write failing tests** (build the demo into `tmp_path`, then `load()` each document):
  - `test_prefill_extracts_lines`: `{line.label_key: line.amount}` equals `{income.salary: 85000.00, income.salary_tax_withheld: 19000.00, income.interest: 412.35, income.div_franked: 1200.00, income.franking_credit: 514.29, phi.premiums_total: 2400.00, phi.rebate_total: 581.89}`. Unconfirmed `notes="prefill"` figures exist for the five non-info keys only.
  - `test_income_statement`: `income.salary == 85000.00`, `income.salary_tax_withheld == 19000.00`, `income.allowances == 1200.00`, `parse_status == "parsed"`, `page == 1`.
  - `test_interest_and_doc_date`: `income.interest == 412.35`, `doc_date == date(2026, 6, 30)`.
  - `test_dividends`: franked 1200.00, franking credit 514.29, `doc_date == date(2026, 3, 24)`.
  - `test_extractor_rejects_raw_str`: `get_extractor("DIVSTMT").extract("raw", "D001")` raises `TypeError`.
  - `test_unparseable_is_manual_needed`: a DIVSTMT with no recognisable lines gives `parse_status == "manual_needed"` and no figures.
- [ ] **Step 2: Run** `python -m pytest tests/test_extractors_income.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the extractors with per-line regexes over `rt.pages`, recording the page number per match.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): demo documents and income extractors`.

### Task 7: Remaining extractors

**Files:**
- Create: `src/tra/ingest/extractors/rental.py`, `phi.py`, `receipt.py`, `xero_csv.py`, `config/xero_mapping.yaml`, `tests/test_extractors_other.py`

**Interfaces:**
- Consumes: the Task 6 `Extractor` protocol and the demo builder.
- Produces:
  - **RENTSTMT:** `Total rent received <amt>` → `rent.gross`. Expense lines go to `rent.other`, one figure per line, with the description as the line text. A line containing `interest` goes to `rent.interest`.
  - **PHI:**
    - `Premiums eligible for rebate 1 July - 31 March <amt>` → `phi.premiums_p1`
    - `Rebate received 1 July - 31 March <amt>` → `phi.rebate_p1`
    - the same lines for `1 April - 30 June` → `phi.premiums_p2`, `phi.rebate_p2`
    - `Benefit code <nn>` → the notes of the PHI figures.
    - The membership number is never extracted.
  - **RECEIPT / OTHER:** `Total <amt>` or `Amount paid <amt>` → one figure with `label_key="ded.d5"` (suggested) and `substantiated=True` when both a date and a supplier line (`Tax invoice` + the first non-empty line) are present. `parse_status="partial"` always (the label is a suggestion).
  - **XEROPL / XEROBS / XEROBANK (CSV exports):** rows of `Account, Amount` under section headings. Headings are mapped via `config/xero_mapping.yaml`: `pl_sections: {"Income": income.business_income, "Trading Income": income.business_income, "Less Cost of Sales": income.business_expenses, "Less Operating Expenses": income.business_expenses, "Operating Expenses": income.business_expenses}`. Balance sheet and bank transaction exports produce no figures; their `parse_status` is `parsed` and they are filed for reference.

- [ ] **Step 1: Write failing tests:**
  - `test_rental`: gross 26000.00; four `rent.other` figures summing to 5340.00.
  - `test_phi_periods`: four figures with the demo amounts; `"Medicare"` is absent from all figure descriptions.
  - `test_receipt_substantiated`: amount 1499.00, `ded.d5`, `substantiated is True`, `date == date(2025, 8, 12)`.
  - `test_xero_pl_csv`: a 6-row CSV gives income and expense figures mapped by section; an unknown section gives a `partial` status.
- [ ] **Step 2: Run** `python -m pytest tests/test_extractors_other.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** Extend `demo.py` with the rental, PHI and receipt grammars above.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): rental, health, receipt and Xero export extractors`.

### Task 8: Figures, CGT events and pre-fill files

**Files:**
- Create: `config/labels.yaml`, `src/tra/labels.py`, `src/tra/figures.py`, `tests/test_figures.py`

**Interfaces:**
- Consumes: `Figure`, `PrefillLine`, `parse_amount`, `parse_date`, `atomic_write_text`, `FileLockedError`, `check_rows`.
- Produces:
  - **`labels.yaml`**: one entry per label key with `item`, `label`, `letter_verified: false`, `description`, `role`, `tab`, `order`.
    - `role` ∈ `income | deduction | rental_income | rental_deduction | business_income | business_deduction | loss | withheld | franking | phi | it | info`.
    - Keys:
      - from Tasks 6–7: `income.business_income`, `income.business_expenses`, `income.other`;
      - deductions: `ded.d1`…`ded.d10`, `ded.d12`, `ded.d15`;
      - `loss.l1`, `cgt.prior_losses`;
      - computed labels `cgt.total_gains` (18 H) and `cgt.net_gain` (18 A), both `computed: true`;
      - `rent.gross` (21 P), `rent.interest` (21 Q), `rent.capital_works` (21 F), `rent.other` (21 U);
      - `phi.premiums_p1`, `phi.premiums_p2`, `phi.rebate_p1`, `phi.rebate_p2`;
      - `info`-role keys `phi.premiums_total`, `phi.rebate_total`, `help.indicator`;
      - `it.rfb`, `it.resc`.
    - Letters as in spec §8.2: 1 C, 2 K, 10 L/M, 11 S/T/U/V, D1 A, D2 B, D3 C, D4 D, D5 E, D6 K, D7 I, D8 H, D9 J, D10 M.
  - `LabelDef` dataclass and `load_labels(path=None) -> dict[str, LabelDef]`, ordered by `order`.
  - `FIGURE_COLUMNS = ["figure_id", "label_key", "description", "amount", "date", "doc_id", "page", "method", "confirmed", "substantiated", "notes"]`.
  - `read_figures(path: Path, labels) -> tuple[list[Figure], list[str]]`: returns the figures and errors like `"row 7: unknown label_key 'income.salry'"`. Reads with `utf-8-sig`. `confirmed` accepts `Y/y/yes/Yes/TRUE/1` and `N/n/no/No/FALSE/0/blank`.
  - `write_figures(path: Path, figures: list[Figure]) -> None`: atomic and guarded.
  - `append_figures(path: Path, new: list[Figure]) -> list[Figure]`: assigns the next ids `F0001…` and returns them with ids.
  - `CgtEvent(event_id, asset, acquired: date, disposed: date, proceeds: Decimal, cost_base: Decimal, doc_id, page, confirmed: bool)`. `CGT_COLUMNS` are those fields in that order. `read_cgt(path) -> tuple[list[CgtEvent], list[str]]`; a missing file returns `([], [])`.
  - `read_prefill(path) -> list[PrefillLine]` and `append_prefill(path, lines) -> None` (JSON).
  - `read_prior_year(path: Path) -> dict[str, Decimal]`: columns `label_key, amount`; a missing file returns `{}`.
  - `write_header_files(ws: Workspace) -> None`: writes empty `figures.csv` and `cgt_events.csv` with headers.
  - Bulk manual entry happens directly in `figures.csv`, which covers the spec §7.5 "CSV template" row, so no separate template extractor is built.
  - Every CSV and JSON write in this task, and `DocumentIndex` in Task 9, goes through `atomic_write_text`, so it is guarded.

- [ ] **Step 1: Write failing tests:**
  - `test_roundtrip`: write 3 figures, read them back, and they are equal.
  - `test_excel_roundtrip_formats` (Review Focus 1): a file with a BOM, date `24/03/2026`, amounts `1234.5` and `$1,234.50`, and confirmed `yes`/`y` loads with no errors and the values parsed correctly.
  - `test_errors_listed`: rows with an unknown label, amount `abc`, page `x`, and confirmed `maybe` each produce an error naming the row number; valid rows still load.
  - `test_append_assigns_ids`: two appends give `F0001..F0003` with no duplicates.
  - `test_write_locked_file` (Review Focus 2): monkeypatch `os.replace` to raise `PermissionError`; `FileLockedError` is raised and the previous contents are intact.
  - `test_cgt_and_prior_year_missing_ok`: both readers return empty on missing files.
  - `test_labels_cover_extractor_keys`: every label key emitted by the Task 6–7 extractors exists in `load_labels()`.
- [ ] **Step 2: Run** `python -m pytest tests/test_figures.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): figures.csv, CGT events and pre-fill storage`.

## Stage 2: filing

### Task 9: Naming, local store, index, fallback

**Files:**
- Create: `src/tra/filing/__init__.py`, `naming.py`, `store.py`, `local_store.py`, `index.py` (all under `filing/`), `tests/test_filing.py`

**Interfaces:**
- Consumes: `Workspace`, `Document`, `check_text`, `atomic_write_text`, `fy_label`.
- Produces:
  - `filed_name(client_code: str, income_year: int, doc_type: str, doc_date: date, suffix: str, existing: set[str]) -> str`. On collision it appends `_02`, `_03`, …, and the result passes `check_text`.
  - `FilingRequest(client_code, income_year, category, filed_name, doc_type, doc_date)`.
  - `FiledRef(location: str, store: str, fell_back: bool = False)`.
  - Protocol `DocumentStore` with `name: str` and `file(source: Path, req: FilingRequest) -> FiledRef`.
  - `LocalStore(tra_home: Path)`: copies the original unchanged (`shutil.copy2`) to `Clients/<code>/FY<year>/<category>/<filed_name>`.
  - `FallbackStore(primary: DocumentStore, fallback: DocumentStore)`: on any exception from the primary, it files with the fallback and returns `fell_back=True`. The exception message is not logged; only its type is.
  - `INDEX_COLUMNS = ["filed_name", "doc_id", "doc_type", "category", "doc_date", "date_detected", "pages", "sha256", "ingested_at", "parse_status", "store", "filed_location", "redaction_counts"]`.
  - `DocumentIndex(path: Path)` with `load() -> list[Document]`, `append(doc) -> None`, `update(doc) -> None`, `next_doc_id() -> str` (`D001`…), `find_by_sha(sha) -> Document | None`, `names() -> set[str]`.

- [ ] **Step 1: Write failing tests:**
  - `test_filed_name`: `filed_name("SMIT01", 2026, "DIVSTMT", date(2026, 3, 24), ".pdf", set()) == "SMIT01_FY2026_DIVSTMT_2026-03-24.pdf"`; with that name already existing, the result ends `_02.pdf`.
  - `test_local_store_copies_unchanged`: the filed file's bytes equal the source's bytes, and it sits under the `Investments` folder.
  - `test_index_roundtrip_and_ids`: append two docs → `next_doc_id() == "D003"`; `find_by_sha` works; `redaction_counts` round-trips as a dict.
  - `test_index_has_no_original_filename`: after filing `John Smith TFN.pdf`, neither `index.csv` nor the filed name contains `John`, `Smith` or `TFN`.
  - `test_fallback_store`: a primary that raises gives `FiledRef.store == "local"` and `fell_back is True`.
- [ ] **Step 2: Run** `python -m pytest tests/test_filing.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): file originals under the naming convention with an index`.

### Task 10: Ingest pipeline and CLI (`new`, `ingest`, `figures`, `scan`, `doctor`, `demo`)

**Files:**
- Create: `src/tra/ingest/pipeline.py`, `src/tra/cli.py`, `src/tra/notes_store.py`, `tests/test_pipeline_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 2–9.
- Produces:
  - `notes_store.read_notes(path) -> list[ReviewNote]` and `append_notes(path, notes) -> None` (JSON; `Decimal` stored as string).
  - `IngestReport(doc: Document | None, figures_added: int, notes: list[ReviewNote], duplicate: bool)`.
  - `file_document(source: Path, ws: Workspace, store: DocumentStore, *, doc_type: str, category: str, doc_date: date | None, sha256: str, pages: int, redaction_counts: dict, parse_status: str, audit: AuditLog) -> tuple[Document, list[ReviewNote]]`. This shared filing step is reused by Xero in Task 20.
    - It raises a Low note `I2 "date not detected; ingest date used"` when `doc_date` is None.
    - It raises a Medium note `I3 "filed locally; FYI unavailable — run tra fyi push"` when the store fell back.
  - `ingest_file(path: Path, ws: Workspace, store: DocumentStore, doc_types, audit: AuditLog, override_type: str | None = None) -> IngestReport`. In order:
    1. `load`.
    2. If the hash is already in the index: Low note `I4` and a duplicate report; nothing filed.
    3. Classify, or use the override.
    4. Extract.
    5. `file_document`.
    6. Append figures with `doc_id` set, and append the pre-fill lines.
    7. Append notes: Medium `I1 "manual entry needed"` when `manual_needed`, or when the document is image-only.
    8. Audit `document_ingested` with `doc_id, doc_type, filed_name, redaction_counts, parse_status`.
    9. Scan the redacted text for `employee share scheme`, `foreign income`, `foreign tax`, `personal services income`. Each hit raises a High reviewer note `I6 "area not handled by the tool: <phrase>"`, which feeds spec check S12.

    On `RedactionError`, it audits `redaction_failed` (with no doc fields beyond the sha256) and raises `IngestError("redaction failed; document not processed")`.
  - CLI (`click` group `main`):
    - `tra new CODE --fy 2026 [--sole-trader] [--help-debt] [--age-band ...]`
    - `tra ingest CODE FILES... [--fy] [--type CODE]`: continues past per-file errors and exits 1 if any failed. It prints one line per file: `D003 DIVSTMT parsed 3 figures (redacted: TFN×1)`.
    - `tra figures CODE [--fy]`: validates, prints errors, then opens the file with `os.startfile` on Windows or prints the path elsewhere.
    - `tra scan PATH`: prints `path:line type` for each match (never the value) and exits 1 if anything is found.
    - `tra doctor`: prints `OK`/`PROBLEM` lines for Python, `TRA_HOME` checks, rates files and their `status`, env vars present (names only), and `TRA_STORE`.
    - `tra demo [--auto-confirm]`: creates `DEMO01` FY2026, builds the demo documents into `TRA_HOME/Inbox/DEMO01`, and ingests them. With `--auto-confirm` it marks every figure confirmed. It then prints the next steps.
  - `--fy` defaults to 2026 throughout. `FileLockedError`, `ConfigError`, `SensitiveDataBlocked` and `IngestError` become `click.ClickException` with their messages.
  - Every command except `doctor` and `scan` runs `check_tra_home` first and exits 1 listing the problems (spec §6). Every command calls `configure_logging(TRA_HOME/logs/tra.log)`.

- [ ] **Step 1: Write failing tests** (use `click.testing.CliRunner` with `env={"TRA_HOME": str(tmp_path / "home")}` and the home folder created):
  - `test_new_creates_workspace`: exit 0; `state.json` and the headed `figures.csv` exist.
  - `test_ingest_demo_documents`: ingesting all demo files (exit 0) gives 8 index rows and figures for every expected label.
  - `test_ingest_same_file_twice` (Review Focus 5): the second run reports a duplicate; index rows and figure count are unchanged.
  - `test_ingest_redaction_failure_continues`: monkeypatch `redact_pages` to raise for one file; the other files are ingested; exit code 1; the audit has `redaction_failed`.
  - `test_scan_reports_type_not_value`: scanning a text file containing a generated TFN prints `TFN` and not the digits; exit 1.
  - `test_doctor_flags_unverified_rates`: the output contains `status: unverified` for FY2026.
  - `test_refuses_bad_tra_home`: `TRA_HOME` inside a folder named `OneDrive - Firm` makes `tra new` exit 1 with the problem shown.
  - `test_unhandled_area_note`: ingesting a document containing "employee share scheme" stores an I6 note.
  - `test_demo_auto_confirm`: all figure rows have `confirmed == "Y"`.
- [ ] **Step 2: Run** `python -m pytest tests/test_pipeline_cli.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.** The rates file check in `doctor` reads only the `status` key (the full loader arrives in Task 12; create minimal `config/rates/fy2026.yaml` and `fy2025.yaml` stubs containing `income_year` and `status: unverified` now; Task 12 fills them).
- [ ] **Step 4: Run** `python -m pytest -v`. Expected: all PASS.
- [ ] **Step 5: Commit** `feat(tra): ingest pipeline and CLI for stages 1-2`.

## Stage 3/4: return, tax calculation, checks, workpaper

### Task 11: Draft return and CGT

**Files:**
- Create: `src/tra/return_/__init__.py`, `src/tra/return_/prepare.py`, `src/tra/return_/cgt.py`, `tests/test_return_cgt.py`

**Interfaces:**
- Consumes: `Figure`, `CgtEvent`, `LabelDef`, `round_cents`.
- Produces:
  - `CgtSummary(total_current_gains: Decimal, net_capital_gain: Decimal, losses_carried_forward: Decimal, discount_events: tuple[str, ...], events_used: tuple[str, ...])`.
  - `discount_eligible(acquired: date, disposed: date) -> bool`: True only when `disposed` is strictly after the 12-month anniversary of `acquired`. A 29 February acquisition has its anniversary on 1 March.
  - `compute_cgt(events: list[CgtEvent], prior_losses: Decimal, resident: bool = True) -> CgtSummary`. Uses confirmed events only. Losses (current first, then prior) are applied to non-discount gains first, then to discount gains. The remaining discount gains are halved if `resident`. Unused losses are carried forward.
  - `LabelLine(label_key: str, amount: Decimal, figure_ids: tuple[str, ...])`.
  - `DraftReturn(client_code, income_year, lines: dict[str, LabelLine], cgt: CgtSummary)` with `.amount(key) -> Decimal` (0 if absent).
  - `build_draft(client_code: str, income_year: int, figures: list[Figure], cgt_events: list[CgtEvent], labels: dict[str, LabelDef]) -> DraftReturn`.
    - Confirmed figures only.
    - `cgt.total_gains` and `cgt.net_gain` lines come from `compute_cgt`, using `prior_losses` = the confirmed `cgt.prior_losses` total.
    - The figure ids of CGT lines are the event ids.

- [ ] **Step 1: Write failing tests:**
  - `test_discount_eligibility`: acquired 2024-07-01 and disposed 2025-07-01 → False; disposed 2025-07-02 → True; acquired 2024-02-29 and disposed 2025-03-01 → False, 2025-03-02 → True.
  - `test_cgt_loss_ordering`: a discount gain of 10,000, a non-discount gain of 4,000 and a current loss of 5,000 give: 4,000 absorbed, 1,000 off the discount gain, net = 9,000 × 50% = 4,500; total gains 14,000.
  - `test_cgt_prior_losses_carried_forward`: a gain of 2,000 with prior losses of 5,000 gives net 0 and 3,000 carried forward.
  - `test_build_draft_confirmed_only`: an unconfirmed figure is excluded; two confirmed `income.interest` figures sum to one line and keep both figure ids.
- [ ] **Step 2: Run** `python -m pytest tests/test_return_cgt.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): draft return builder and CGT method statement`.

### Task 12: Rates config and loader

**Files:**
- Modify: `config/rates/fy2026.yaml`, `config/rates/fy2025.yaml` (replace the Task 10 stubs)
- Create: `src/tra/taxcalc/__init__.py`, `src/tra/taxcalc/rates.py`, `tests/test_rates.py`

**Interfaces:**
- Produces:
  - `Rates` dataclass mirroring the YAML: `income_year, status, verified_by, verified_on, sources: dict, brackets: list[Bracket(from_: int, rate: Decimal, base: Decimal)], lito: Lito, medicare: Medicare, mls: Mls, phi_rebate: list[PhiPeriod], help: Help, sapto: dict[str, Sapto], car_cents_per_km: CarRate, wfh_rate: Decimal`.
  - `load_rates(income_year: int, path: Path | None = None) -> Rates`. A missing file raises `RatesError(f"No rates file for FY{year}: expected config/rates/fy{year}.yaml")`.
  - `validate_rates(r: Rates) -> None`: raises `RatesError(<rule>)` when:
    - brackets are not ascending;
    - `base[i] != base[i-1] + rate[i-1] * (from[i] - from[i-1])`;
    - any rate is outside [0, 1];
    - Medicare `upper != floor(lower * 1.25)` (single and SAPTO single);
    - SAPTO `|max - taper * (cut_out - shade_out)| > 1`;
    - LITO is not continuous at `taper1_to` (`max - taper1_rate * (taper1_to - full_to) != taper2_base`);
    - HELP marginal bases are not consistent.
  - YAML shape. "from" means income *over* this amount; HELP `percent_of_income` rows use RI ≥ from:
    ```yaml
    income_year: 2026
    status: unverified
    verified_by: null
    verified_on: null
    sources: {brackets: <url>, lito: <url>, medicare: <url>, mls: <url>, phi: <url>, help: <url>, sapto: <url>, car: <url>, wfh: <url>}
    resident_brackets: [{from: 0, rate: 0, base: 0}, …]
    lito: {max: 700, full_to: 37500, taper1_rate: 0.05, taper1_to: 45000, taper2_base: 325, taper2_rate: 0.015}
    medicare: {rate: 0.02, shade_in: 0.10, single: {lower, upper}, sapto_single: {lower, upper}, family: {lower, per_child}, sapto_family: {lower, per_child}}
    mls: {single: [{from: 0, rate: 0}, …], family: [...], family_per_child_after_first: 1500}
    phi_rebate: [{from: 2025-07-01, to: 2026-03-31, under65: [b, t1, t2, t3], 65to69: [...], 70plus: [...]}, …]
    help: {method: marginal, bands: [{from, base, rate}], flat_from: 179286, flat_rate: 0.10}   # FY2025: method: percent_of_income, rows: [{from, rate}]
    sapto: {single: {max, shade_out, cut_out}, couple: {...}, illness_separated: {...}, taper: 0.125}
    car_cents_per_km: {rate: 0.88, km_cap: 5000}
    wfh_rate: 0.70
    ```

- [ ] **Step 1: Fill `fy2026.yaml`** with every value in spec §8.1's FY2026 table. Source URLs are the ATO pages for each section; the PHI source is the health.gov.au PHI circular.
- [ ] **Step 2: Fill `fy2025.yaml`.**
  - Same brackets and LITO.
  - Medicare: single 27222/34027, SAPTO single 43020/53775, family 45907 + 4216, SAPTO family 59886 + 4216.
  - MLS: single 97000/113000/151000; family 194000/226000/302000.
  - PHI: 2024-07-01–2025-03-31: under65 [0.24608, 0.16405, 0.08202, 0], 65to69 [0.28710, 0.20507, 0.12303, 0], 70plus [0.32812, 0.24608, 0.16405, 0]. 2025-04-01–2025-06-30: under65 [0.24288, 0.16192, 0.08095, 0], 65to69 [0.28337, 0.20240, 0.12143, 0], 70plus [0.32385, 0.24288, 0.16192, 0].
  - HELP `percent_of_income` rows, `from` → rate: 54435 → .01, 62851 → .02, 66621 → .025, 70619 → .03, 74856 → .035, 79347 → .04, 84108 → .045, 89155 → .05, 94504 → .055, 100175 → .06, 106186 → .065, 112557 → .07, 119310 → .075, 126468 → .08, 134057 → .085, 142101 → .09, 150627 → .095, 159664 → .10.
  - SAPTO: single 2230/32279/50119; couple 1602/28974/41790; illness_separated 2040/31279/47599.
  - Car 0.88 / 5000; WFH 0.70.
- [ ] **Step 3: Write failing tests:**
  - `test_load_both_years_valid`: both load and validate; `status == "unverified"`.
  - `test_missing_year`: `load_rates(2019)` raises a `RatesError` that mentions `fy2019.yaml`.
  - `test_validation_catches_typos`: each rule fails when one value is altered (e.g. base 4288 → 4388, Medicare upper +1, SAPTO cut_out +100).
- [ ] **Step 4: Run** `python -m pytest tests/test_rates.py -v`. Expected: FAIL, then implement `rates.py`.
- [ ] **Step 5: Run the tests.** Expected: PASS.
- [ ] **Step 6: Commit** `feat(tra): FY2025 and FY2026 rates with validation (unverified)`.

### Task 13: Calculation A

**Files:**
- Create: `src/tra/taxcalc/result.py`, `src/tra/taxcalc/calc_a.py`, `tests/test_calc_a.py`

**Interfaces:**
- Consumes: `DraftReturn`, `ClientState`, `Rates`, `round_cents`, `truncate_dollars`, `days_in_fy`.
- Produces:
  - `TaxResult` (frozen) with fields `total_income, deductions, taxable_income, basic_tax, lito, sapto, offsets_used, medicare_levy, mls_income, mls, repayment_income, help, phi_adjustment, franking_credits, payg_withheld, tfn_withheld, net_result`. `net_result` is positive for payable and negative for a refund. `phi_adjustment` is positive when rebate was over-received. `.components() -> dict[str, Decimal]`.
  - `calculate_a(draft: DraftReturn, state: ClientState, rates: Rates) -> TaxResult`. It uses explicit `draft.amount(key)` references, never `labels.yaml` roles:
    - `total_income` = salary + allowances + interest + div_unfranked + div_franked + franking_credit + (rent.gross − rent.interest − rent.capital_works − rent.other) + cgt.net_gain + (business_income − business_expenses) + income.other
    - `deductions` = Σ `ded.*`
    - `taxable_income` = `max(0, truncate_dollars(total_income − deductions − loss.l1))`
    - `basic_tax`: Σ over brackets of `rate × slice`
    - LITO: `min/max` piecewise formula
    - SAPTO: per `state.sapto_status`, using rebate income = TI + rfb + resc + rental loss
    - `offsets_used` = `min(basic_tax, lito + sapto)`
    - Medicare: `min(rate × TI, shade_in × (TI − lower))` when TI > lower, using the SAPTO-single thresholds if SAPTO applies
    - `mls_income` = TI + rfb + resc + max(0, −net_rent); `mls` = tier rate × (TI + rfb) × uncovered_days / days_in_fy. Family tiers apply when `has_spouse or dependants`. `hospital_cover_days is None` means fully covered.
    - HELP: on `repayment_income` (= `mls_income`) only if `state.help_debt`
    - PHI: Σ over periods of `rebate_received − round_cents(premiums × rate[age_band][tier])`, with tier from `mls_income` against the MLS tiers
    - `net_result` = `basic_tax − offsets_used + medicare + mls + help + phi_adjustment − franking − payg − tfn_withheld`, where `tfn_withheld` = interest + dividend TFN withholding
    - Every component is `round_cents`.

- [ ] **Step 1: Write failing tests** with hand-worked FY2026 values (single, under 65, no HELP, covered unless stated):
  - `test_bracket_edges`: TI 18,200 → tax 0; 18,201 → 0.16; 45,000 → 4,288.00; 45,001 → 4,288.30; 135,000 → 31,288.00; 190,000 → 51,638.00; 200,000 → 56,138.00.
  - `test_lito`: TI 37,500 → 700.00; 40,000 → 575.00; 45,000 → 325.00; 50,000 → 250.00; 66,667 → 0.00.
  - `test_medicare_shade_in`: TI 28,011 → 0.00; 30,000 → 198.90; 35,013 → 700.20; 35,014 → 700.28; 85,000 → 1,700.00.
  - `test_help_fy2026`: RI 67,000 → 0; 80,000 → 1,950.00; 125,000 → 8,700.00; 150,000 → 12,950.00; 179,286 → 17,928.60.
  - `test_help_fy2025_percent`: RI 54,434 → 0; 54,435 → 544.35; 100,000 → 5,500.00.
  - `test_mls`: TI 120,000, no cover all year → 1,500.00 (1.25%); with `hospital_cover_days=365` → 0.
  - `test_phi_adjustment_base_tier`: a standalone draft with salary 85,000 (base tier); entitled 1,800 × 24.288% = 437.18 and 600 × 24.118% = 144.71; received matches, so the adjustment is 0.00.
  - `test_demo_client_net_result`: salary 85,000, allowances 1,200, withheld 19,000, interest 412.35, franked 1,200, credit 514.29, rent 26,000 less 5,340, D5 2,019 gives TI = 106,967 and basic tax 22,878.10; Medicare 2,139.34; LITO 0. PHI is Tier 1 (MLS income 106,967): entitled 291.46 + 96.47, received 581.89, so the adjustment is 193.96. Net payable 5,697.11. Show the working in the test docstring.
- [ ] **Step 2: Run** `python -m pytest tests/test_calc_a.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): tax calculation A`.

### Task 14: Calculation B and the dual-calc checks

**Files:**
- Create: `src/tra/taxcalc/calc_b.py`, `src/tra/checks/__init__.py`, `src/tra/checks/context.py`, `src/tra/checks/dual_calc.py`, `tests/test_calc_b_dual.py`

**Interfaces:**
- Consumes: `TaxResult`, `Rates`, `LabelDef` (roles), `DraftReturn`.
- Produces:
  - `calculate_b(draft: DraftReturn, state: ClientState, rates: Rates, labels: dict[str, LabelDef]) -> TaxResult`. It shares nothing with `calc_a` except `money`/`dates`:
    - `total_income`: iterates labels by `role` (`income`, `rental_income` − `rental_deduction`, `business_income` − `business_deduction`, `franking`)
    - tax: the base amount of the bracket containing TI + rate × (TI − from)
    - LITO: three-row table `(from, base, rate)`
    - Medicare: explicit three-band rule
    - MLS and PHI tiers: found by `bisect`
    - HELP: cumulative slices (marginal), or `bisect` (percent)
    - SAPTO: explicit three-band rule
    - `net_result`: summed from a component list.
  - `CheckContext` (in `checks/context.py`): fields `figures: list[Figure]` (all), `documents: list[Document]`, `draft, prefill: list[PrefillLine], prior_year: dict[str, Decimal], rates, state, calc_a, calc_b, labels, cfg: dict, citations: dict`.
  - `check_dual_calc(ctx) -> list[ReviewNote]`: a High `C1` note per differing component (`|a − b| ≥ 0.01`), naming the component.
  - `check_rates_status(ctx) -> list[ReviewNote]`: a High `C2` note when `rates.status != "verified"`, with the message `f"FY{year} rates not yet verified against ato.gov.au by a registered agent"`.

- [ ] **Step 1: Write failing tests:**
  - `test_b_matches_a_across_range`: for 5,000 TIs from a seeded RNG, from 0 to 500,000, built as salary-only drafts, with HELP on and off, every age band and `sapto_status`, and both FY2025 and FY2026, `calculate_b(...).components() == calculate_a(...).components()`.
  - `test_b_matches_a_demo`: the Task 13 demo draft matches exactly.
  - `test_dual_calc_flags_difference`: monkeypatch `calc_b` to add 0.01 to `medicare_levy`; there is exactly one C1 note and it mentions `medicare_levy`.
  - `test_rates_status_note`: unverified → one High C2; verified → none.
- [ ] **Step 2: Run** `python -m pytest tests/test_calc_b_dual.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): independent tax calculation B and dual-calc check`.

### Task 15: Reconciliation and pre-fill checks

**Files:**
- Create: `config/checks.yaml`, `src/tra/checks/reconcile.py`, `src/tra/checks/prefill.py`, `tests/test_checks_reconcile_prefill.py`

**Interfaces:**
- Consumes: `CheckContext`.
- Produces:
  - `checks.yaml` keys:
    - `prefill_tolerance: 1.00`, `double_count_tolerance: 1.00`
    - `deductions_to_income_max: 0.30`, `work_related_to_salary_max: 0.15`
    - `substantiation_threshold: 300`
    - `prior_year_pct: 0.20`, `prior_year_floor: 100`
    - `clothing_keywords: [shirt, pants, shoes, suit, jeans, jacket, dress]`
    - `capital_keywords: [replace, renovat, new, install]`
    - `interest_purpose_keywords: [redraw, line of credit]`
    - `asset_keywords: [laptop, computer, phone, tablet, monitor, desk, chair, printer]`
  - `check_reconcile(ctx) -> list[ReviewNote]`:
    - **R1:** High, per confirmed figure with no `doc_id`, or with a `doc_id` not in `ctx.documents`.
    - **R2:** High, per label where `draft.amount` ≠ the sum of confirmed figures.
    - **R3:** Medium, one note listing the count and figure ids of unconfirmed figures.
    - **R4:** High, per pair of confirmed figures on the same label within tolerance where one has `notes == "prefill"` and the other doesn't.
  - `check_prefill(ctx) -> list[ReviewNote]`:
    - **P1:** High, label total differs from the pre-fill total by more than the tolerance; `dollar_impact` = the difference.
    - **P2:** High, a pre-fill line whose label has no confirmed figure.
    - **P3:** Medium, no `PREFILL` document in `ctx.documents`.
    - **P4:** High, `help.indicator` is in the pre-fill but `state.help_debt` is False, or the reverse.
    - `phi.premiums_total` and `phi.rebate_total` compare against `phi.premiums_p1 + p2` and `phi.rebate_p1 + p2` under P1/P2 rules.
    - Other `info` keys are never compared.

- [ ] **Step 1: Write failing tests:** one triggering and one non-triggering case per check id (R1, R2, R3, R4, P1, P2, P3, P4, plus the PHI total comparison), each built from small hand-made contexts via a `make_ctx(**overrides)` helper in the test module.
- [ ] **Step 2: Run** `python -m pytest tests/test_checks_reconcile_prefill.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): reconciliation and pre-fill checks`.

### Task 16: Sanity checks and citations

**Files:**
- Create: `config/citations.yaml`, `src/tra/checks/sanity.py`, `tests/test_checks_sanity.py`

**Interfaces:**
- Consumes: `CheckContext`, `checks.yaml`.
- Produces:
  - `citations.yaml`: ids → `{ref, description, verified: false}`. The ids are `itaa97_s8_1, itaa97_s25_5, itaa97_s26_31, itaa97_s28_25, itaa97_s40_27, itaa97_s40_80, itaa97_s102_5, itaa97_s115_25, itaa97_s900_35, itaa97_div30, itaa97_div43, itaa97_div207, tr97_12, tr97_23, tr2000_2, tr2024_3, pcg2023_1, mla1986, hesa2003, tasa2009_s30_10`.
  - `load_citations(path=None) -> dict[str, dict]` (in `checks/__init__.py`).
  - `check_sanity(ctx) -> list[ReviewNote]`, implementing S1–S13 as in the spec §8.4 table, with these citation ids:

    | Check | Citation |
    |---|---|
    | S4 | `itaa97_s900_35` |
    | S5 | `itaa97_s28_25` |
    | S6 | `tr97_12` |
    | S7 | `tr97_23` |
    | S8 | `itaa97_s115_25` |
    | S9 | `mla1986` |
    | S10 | `tr2000_2` |
    | S11 | `itaa97_div30` |
    | S13 | `itaa97_s40_80` |

    - **S5:** fires when the D1 total exceeds `car.rate × km_cap` (4,400.00 for FY2026) and no D1 figure's notes contain `logbook`.
    - **S9:** `audience="client"`, `action="question"`; also fires as an assumption note when `hospital_cover_days is None` and `mls_income` is over the base threshold.
    - **S12:** fires when there is any `MFUND` document, `state.has_spouse or dependants` (family Medicare/MLS), `income.business_income` (P8 detail), or a `CGT` document with no CGT events.

- [ ] **Step 1: Write failing tests:** one triggering and one non-triggering case per S1–S13. `test_s4_substantiation`: a D5 total of 520 with one figure `substantiated=None` triggers S4 with citation `itaa97_s900_35`; a total of 280 does not.
- [ ] **Step 2: Run** `python -m pytest tests/test_checks_sanity.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): sanity checks with citations`.

### Task 17: Prior-year checks, ranking, running all checks

**Files:**
- Create: `src/tra/checks/prior_year.py`, `src/tra/checks/notes.py`, `tests/test_checks_prior_notes.py`
- Modify: `src/tra/checks/__init__.py`

**Interfaces:**
- Consumes: `CheckContext`, `read_prior_year`.
- Produces:
  - `check_prior_year(ctx) -> list[ReviewNote]`:
    - **Y1:** Medium, `|this − prior| > prior_year_pct × |prior|` **and** `|this − prior| > prior_year_floor`.
    - **Y2:** Medium client question, a label present in the prior year and absent now.
    - An empty `prior_year` gives no notes.
  - `load_prior_year(ws: Workspace) -> dict[str, Decimal]`: uses `prior_year.csv` if present, otherwise `Work/<code>/FY<year-1>/last_return.json`, otherwise `{}`.
  - `rank_notes(notes: list[ReviewNote]) -> list[ReviewNote]`: de-duplicates on `(check_id, label_key, doc_ids)`, keeping the first; sorts High→Medium→Low, then `|dollar_impact|` descending, with None last.
  - `run_all_checks(ctx) -> list[ReviewNote]`: concatenates dual_calc, rates_status, reconcile, prefill, sanity and prior_year, then `rank_notes`.

- [ ] **Step 1: Write failing tests:**
  - `test_y1_pct_and_floor`: 1,000 → 1,300 triggers; 10 → 15 does not (under the floor); 1,000 → 1,150 does not.
  - `test_y2_disappeared`.
  - `test_prior_from_last_return`: no CSV, but FY2025's `last_return.json` exists, so its values are used.
  - `test_rank_order_and_dedupe`: a mixed list sorts High (larger $) before High (smaller $) before High (None) before Medium; exact duplicates collapse to one.
- [ ] **Step 2: Run** `python -m pytest tests/test_checks_prior_notes.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): prior-year checks and review-note ranking`.

### Task 18: Workpaper builder

**Files:**
- Create: `src/tra/workpaper/__init__.py`, `src/tra/workpaper/layout.py`, `src/tra/workpaper/build.py`, `tests/test_workpaper.py`

**Interfaces:**
- Consumes: `DraftReturn`, `TaxResult`, `Rates`, `ReviewNote`, `Document`, `Figure`, `LabelDef`, `PrefillLine`, `check_workbook`, `FileLockedError`.
- Produces:
  - `WorkpaperContext(client_code, income_year, state, documents, figures (confirmed), draft, rates, calc_a, calc_b, notes, prefill: dict[str, Decimal], prior_year: dict[str, Decimal], labels, prepared_by: str, tool_version: str)`.
  - `WorkpaperMap(total_cells: list[str], summary_cells: dict[str, str], taxcalc_cells: dict[str, str])`. Cell refs look like `"Interest!J9"`.
  - `build_workpaper(path: Path, ctx: WorkpaperContext) -> WorkpaperMap`. It runs `check_workbook` before saving, saves to `.tmp` then `os.replace`, and maps `PermissionError` to `FileLockedError`.
  - `layout.py` holds every colour, font, fill, column width and number format (`'#,##0.00;(#,##0.00);"-"'`) plus a `style_*` helper per element. `build.py` contains no styling literals.
  - Tabs and columns follow spec §9:
    - **Category tabs:** one per distinct `LabelDef.tab` with confirmed figures. The Source document cell is a hyperlink to `Document.filed_location`. The total row is `=SUM(J<first>:J<last>)`.
    - **Summary:** "This year" is `='<Tab>'!J<totalrow>` filtered by label (`=SUMIFS('<Tab>'!J:J,'<Tab>'!K:K,"<label_key>")`, where hidden column K holds the label_key). Computed CGT labels reference the Capital Gains tab. Pre-fill and Prior are literal inputs; Difference and Movement % are formulas.
    - **Rates:** written from `Rates` in fixed blocks.
    - **Tax Calc:** each `TaxResult` component is an Excel formula off Summary and Rates, as in spec §8.3:
      - LOOKUP for brackets;
      - nested `IF` for LITO, Medicare and SAPTO;
      - `LOOKUP` for MLS, PHI and HELP tiers;
      - `ROUND(…, 2)` and `ROUNDDOWN` matching `money.py`.

      A "Python calc B" column holds literal values, and a Difference column with conditional formatting sits beside it.
    - **Cover:** the red banner `DRAFT – NOT FOR LODGMENT` in merged cells A1:H2.
    - **Review Notes:** in the order given (already ranked); risk cell fill comes from `layout`.

- [ ] **Step 1: Write failing tests** (build from the demo context assembled with Tasks 11–17):
  - `test_tabs_present`: Cover, Summary, Salary & Wages, Interest, Dividends, Rental, D5 Other work-related, Tax Calc, Rates, Sources, Review Notes.
  - `test_totals_are_formulas`: every ref in `total_cells`, `summary_cells` and `taxcalc_cells` holds a string starting with `=`.
  - `test_every_figure_row_has_source`: every data row on category tabs has a non-empty Source document and Page.
  - `test_banner_and_rates_status`: the Cover banner text matches verbatim, and the Rates sheet shows `unverified`.
  - `test_guard_blocks_leak`: putting a generated TFN in a figure description makes `build_workpaper` raise `SensitiveDataBlocked` and leaves no file.
  - `test_recalc_matches_calc_a` (skip if `shutil.which("soffice")` is None): convert with `soffice --headless --convert-to xlsx` into a temp dir, load with `data_only=True`, and every `taxcalc_cells` value is within 0.01 of `calc_a.components()`. The 1c tolerance covers floating-point half-cent cases in spreadsheet engines; A vs B stays exact.
- [ ] **Step 2: Run** `python -m pytest tests/test_workpaper.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS (or the recalc test skipped where LibreOffice is absent).
- [ ] **Step 5: Commit** `feat(tra): sourced Excel workpaper with live formulas`.

### Task 19: `tra prepare` and the end-to-end leak test

**Files:**
- Create: `src/tra/run.py`, `tests/test_end_to_end.py`
- Modify: `src/tra/cli.py`

**Interfaces:**
- Consumes: everything from Tasks 8–18.
- Produces:
  - `PrepareResult(workpaper: Path, notes: list[ReviewNote], calc_a: TaxResult)`.
  - `prepare_client(ws: Workspace, audit: AuditLog, prepared_by: str) -> PrepareResult`. In order:
    1. Load the state, labels, rates (`ws.income_year`), index, figures (any errors → `PrepareError` listing them), CGT events, pre-fill, prior year and ingest notes.
    2. Build the draft and run both calculations.
    3. Run the checks, plus the ingest notes.
    4. Rank the notes.
    5. Build the workpaper at the next free `Output/<code>_FY<year>_Workpaper_DRAFT_v<n>.xlsx`.
    6. Write `last_return.json` (label → amount, atomic, guarded).
    7. Audit `workpaper_generated` with `file`, `figures`, and `notes_high/medium/low`.
  - CLI `tra prepare CODE [--fy]`: prints the workpaper path, `Estimated refund $X` / `Estimated payable $X`, and note counts by risk, with a reminder line: `Draft only — review and sign-off by a registered tax agent required. Nothing has been lodged.`

- [ ] **Step 1: Write failing tests:**
  - `test_end_to_end_no_leaks`:
    1. Generate a `DemoIdentifiers` set with checksum-valid values from the conftest generators.
    2. Build the demo documents with them into `tmp_path/inbox`.
    3. Through `CliRunner`: `new` → `ingest` all → confirm all figures by rewriting `figures.csv`, but leave the pre-fill duplicates unconfirmed → `prepare`.
    4. Assert exit 0, a workpaper exists, and the audit has `workpaper_generated`.
    5. Walk every file under `TRA_HOME` *except* the `Clients/` originals and `Inbox/`. That covers `Work/`, `audit/`, the `index.csv` files and the xlsx (read every cell via openpyxl). Assert that none contains any identifier, compared with whitespace and hyphens stripped.
  - `test_prepare_twice_versions` (Review Focus 5): two runs give `_v1` and `_v2`, and `_v1` is unchanged (same sha256).
  - `test_prepare_reports_figure_errors`: a bad row in `figures.csv` gives exit 1 with the row number in the output, and no workpaper.
  - `test_demo_expected_notes`: the notes include C2 (rates unverified), S4 (the union receipt is undated) and S13 (laptop $1,499 in D5). They do *not* include C1, R1 or R4.
- [ ] **Step 2: Run** `python -m pytest tests/test_end_to_end.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `python -m pytest -v`. Expected: all PASS.
- [ ] **Step 5: Commit** `feat(tra): prepare command, end-to-end run with leak scan`.

## Stages 5–6: Xero and FYI

### Task 20: Xero client and `tra xero connect/pull`

**Files:**
- Create: `src/tra/xero/__init__.py`, `auth.py`, `client.py`, `to_figures.py` (all under `xero/`), `tests/test_xero.py`
- Modify: `config/xero_mapping.yaml`, `src/tra/cli.py`

**Interfaces:**
- Consumes: `file_document`, `append_figures`, `redact_text`, `TokenStore`, `AuditLog`.
- Produces:
  - Constants:
    - `AUTHORIZE_URL = "https://login.xero.com/identity/connect/authorize"`
    - `TOKEN_URL = "https://identity.xero.com/connect/token"`
    - `CONNECTIONS_URL = "https://api.xero.com/connections"`
    - `API_BASE = "https://api.xero.com/api.xro/2.0"`
  - `pkce_pair() -> tuple[str, str]`: the verifier, and its S256 challenge (base64url, no padding).
  - `authorize_url(client_id, redirect_uri, scopes: list[str], state, challenge) -> str`.
  - `Tokens(access_token, refresh_token, expires_at: datetime)`.
  - `exchange_code(session, client_id, code, verifier, redirect_uri) -> Tokens` and `refresh_tokens(session, client_id, refresh_token) -> Tokens`.
  - `TokenStore(service="tra-xero")` with `get() -> Tokens | None` and `set(tokens) -> None`, backed by `keyring`.
  - `XeroClient(session, access_token, tenant_id)` with:
    - `profit_and_loss(from_date, to_date) -> dict`
    - `balance_sheet(as_at) -> dict`
    - `bank_transactions(from_date, to_date) -> list[dict]`: pages `page=1..` until fewer than 100 results
    - `accounts() -> list[dict]`
    - Every response goes through `strip_sensitive`.
  - Errors:
    - `XeroPermissionError`: HTTP 401 with `insufficient_scope` in the body. Its message is `"Xero needs extra permissions: run 'tra xero connect' and approve again."`
    - `XeroAuthError`: other 401s.
    - 429: retried up to 3 times, sleeping `Retry-After` seconds (injectable `sleep`).
  - `SENSITIVE_KEYS = {"BankAccountNumber", "AccountNumber", "BSB", "TaxNumber"}`.
  - `strip_sensitive(obj)`: drops those keys recursively, then runs `redact_text` over every string.
  - `pl_to_figures(report: dict, mapping: dict, doc_id: str) -> list[Figure]`: walks `Reports[0].Rows`. Section titles are mapped via `pl_sections`; each `Row` gives one figure (description = the first cell, amount = the last cell, `method="xero"`); unknown sections are skipped and returned in a list for an `I5` note.
  - `config/xero_mapping.yaml` adds `scopes: [openid, offline_access, accounting.reports.profitandloss.read, accounting.reports.balancesheet.read, accounting.banktransactions.read, accounting.settings.read]`, with a comment: "granular scope names unconfirmed — check developer.xero.com when registering the app".
  - CLI:
    - `tra xero connect`: PKCE flow with a localhost redirect `http://localhost:8765/callback` (one-shot `http.server`); tokens go to `TokenStore`; it lists connections so the user can pick a tenant.
    - `tra xero pull CODE [--fy]`: writes four JSON snapshots (P&L and balance sheet for the income year, bank transactions, chart of accounts) to temp files. It files them via `file_document` as `XEROPL`, `XEROBS`, `XEROBANK` and `XEROCOA`, appends figures from the P&L only, saves `xero_tenant_id` to state, and audits `xero_pull` with endpoint names only.
    - `XeroAuthError` message: `"Xero sign-in has expired: run 'tra xero connect'."`

- [ ] **Step 1: Write failing tests** with a fake `requests.Session` (a class recording calls and returning queued responses):
  - `test_pkce_challenge`: the challenge equals base64url(sha256(verifier)) with no `=`.
  - `test_authorize_url_params`: it contains `code_challenge_method=S256`, the scopes space-joined, and no client secret.
  - `test_refresh`: posts `grant_type=refresh_token`; `Tokens` is parsed.
  - `test_bank_transactions_paging`: pages of 100 and 37 give 137 rows over 2 calls, with the `xero-tenant-id` header on each.
  - `test_429_retry_then_ok` and `test_401_insufficient_scope`.
  - `test_strip_sensitive`: `BankAccountNumber` is removed; a description with a card number becomes `[CARD REDACTED]`.
  - `test_pl_to_figures`: a sample report with Income (2 rows) and Operating Expenses (3 rows) gives 5 figures mapped correctly.
  - `test_pull_files_snapshots`: running `pull` with a fake client adds four index rows (`XEROPL`, `XEROBS`, `XEROBANK`, `XEROCOA`), and every figure carries the `XEROPL` doc_id.
- [ ] **Step 2: Run** `python -m pytest tests/test_xero.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): Xero client with PKCE auth (mock-tested)`.

### Task 21: FYI store and `tra fyi push`

**Files:**
- Create: `src/tra/filing/fyi_store.py`, `config/fyi.yaml`, `tests/test_fyi.py`
- Modify: `src/tra/cli.py` (commands use `make_store`)

**Interfaces:**
- Consumes: `DocumentStore`, `FiledRef`, `FilingRequest`, `DocumentIndex`, `FallbackStore`, `LocalStore`.
- Produces:
  - `config/fyi.yaml`, with the comment "UNCONFIRMED — check with FYI developer docs/support before first use":
    ```yaml
    headers: {access_id: X-Access-Id, access_secret: X-Access-Secret, app_id: X-App-Id}
    endpoints: {find_client: /clients?code={code}, upload: /documents}
    cabinet_map: {ATO: Tax, Income: Tax, Investments: Tax, Rental: Tax, Deductions: Tax, Business: Accounting, Health: Tax, Other: Tax}
    ```
  - `FyiError(Exception)`.
  - `FyiStore(session, base_url, access_id, access_secret, app_id, cfg: dict)` with `name = "fyi"`. `file()` makes a GET to find the client by code (one result required; zero or more than one raises `FyiError`), then a multipart POST of the file with fields `client_id, cabinet, filename, year`, and returns `FiledRef(location=<returned url or id>, store="fyi")`. Any HTTP error or non-JSON response raises `FyiError(status)`, with no response body in the message.
  - `make_store(settings: Settings, session=None) -> DocumentStore`: `TRA_STORE=fyi` with all env vars present gives `FallbackStore(FyiStore, LocalStore)`; missing env vars give `LocalStore` plus a printed warning; `local` gives `LocalStore`.
  - CLI `tra fyi push CODE [--fy]`: for each index row with `store == "local"`, files via `FyiStore` and updates the index row's `store` and `filed_location`. It reports counts pushed and failed, and audits `fyi_push` with doc_ids.

- [ ] **Step 1: Write failing tests:**
  - `test_fyi_headers_and_upload`: the fake session sees all three headers on both calls and the multipart field `filename` equal to the filed name.
  - `test_fyi_client_not_found`: zero matches raises `FyiError`.
  - `test_make_store_selection`: the three cases above.
  - `test_ingest_falls_back_when_fyi_down`: a store whose FYI part raises gives a local filing and an `I3` note.
  - `test_fyi_push_updates_index`: two local rows become `store == "fyi"`.
- [ ] **Step 2: Run** `python -m pytest tests/test_fyi.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tra): FYI store with local fallback (mock-tested)`.

### Task 22: README, Windows setup, repo hygiene

**Files:**
- Create: `README.md`, `setup.ps1`, `.env.example`, `tests/test_repo_hygiene.py`

**Interfaces:**
- Consumes: `find_sensitive(text, context=False)`.

- [ ] **Step 1: Write the failing test** `test_no_identifiers_committed`:
  - List the files under `tax-return-assistant/` with `git ls-files`, falling back to walking the folder minus ignored paths.
  - Run `find_sensitive(content, context=False)` over each text file.
  - Assert no matches other than the allowlisted `4111111111111111`.
- [ ] **Step 2: Run** `python -m pytest tests/test_repo_hygiene.py -v`. Expected: PASS if Tasks 1–21 complied, otherwise fix the offending file. A FAIL here is a real defect, not a test bug.
- [ ] **Step 3: Write `setup.ps1`:**
  - Require `py -3` ≥ 3.11 (clear message and a python.org link if missing).
  - Create `.venv`; run `.venv\Scripts\python -m pip install -e .`.
  - Prompt for the `TRA_HOME` folder (default `C:\TaxAssistant`), create it, and set it as a *User* env var via `[Environment]::SetEnvironmentVariable`.
  - Run `.venv\Scripts\tra doctor`.
  - Print how to activate (`.venv\Scripts\Activate.ps1`) and the `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` hint.
- [ ] **Step 4: Write `.env.example`** with the env var names from Global Constraints and empty values, plus a comment that real secrets go in Windows user env vars, never in this file.
- [ ] **Step 5: Write `README.md`** with these sections:
  1. What it is and isn't: drafts only, never lodges, agent sign-off.
  2. Setup on Windows.
  3. Try it with `tra demo`.
  4. Workflow for a real client: `new` → `ingest` → `figures` → `prepare` → key into Xero Tax.
  5. Before first real use: verify `config/rates/*.yaml`, `config/citations.yaml` and the `labels.yaml` letters, then set `status: verified`, `verified_by` and `verified_on`; get privacy officer sign-off.
  6. Privacy controls, each mapped to APP 1/6/8/11/12, TASA s30-10 and the NDB scheme.
  7. Updating rates each year: copy `fy2026.yaml` to `fy2027.yaml`, edit, and run `tra doctor`.
  8. Xero setup.
  9. FYI setup.
  10. Re-skinning the workpaper (`layout.py`).
  11. Running tests.
  12. Known limitations (spec §3 and §14).
- [ ] **Step 6: Run** `python -m pytest -v`. Expected: all PASS.
- [ ] **Step 7: Commit** `docs(tra): README, Windows setup script, repo hygiene test`.
