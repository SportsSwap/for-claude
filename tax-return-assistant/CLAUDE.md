# Tax Return Assistant: notes for Claude

The owner is an undergraduate accountant at a boutique Australian firm (Advisory, Accounting & Taxation). They are not a developer, so explain in plain language and give exact steps. They use **Windows laptops**, **Xero Tax** (lodgment) and **FYI Docs**. They keep project notes in an **Obsidian** vault on their computer. Copies of those notes are in `docs/obsidian/Tax Return Assistant/`; update them when the project changes, and send them the updated files.

## What this is
A local Python CLI (`tra`) that prepares **draft** individual returns: redact → file → extract → confirm in Excel → `tra prepare` (draft return, two independent tax calculations, self-checks, Excel workpaper). **It never lodges.** A registered agent signs off every return.

**Sawnx** (`src/tra/web/`, `tra web`, `Sawnx.cmd`) is the same tool as a local website: Flask on 127.0.0.1 only, a per-start session key, no CDN or external fonts. Routes are thin; behaviour is in `web/services/`, which call the existing code. The AI reader (`ingest/extractors/ai_reader.py`, Claude Haiku 5.5) takes `RedactedText`, plus page images of scanned pages only when Settings' separate "Send page images" switch is on (its own privacy officer approval; pictures can't be blanked; never saved) and its tests use a stand-in client. **The privacy officer approved the AI reader for real clients (25 Oct 2026, as told by the owner)**: it's switched on in Sawnx Settings with the approver's name and date, and needs the firm's `ANTHROPIC_API_KEY` saved for the Windows account (the owner types it; never ask for it or put it in a chat or file). **Claude reading in chat is still made-up clients only:** when the owner asks you to read a client's documents, or to teach layouts, run `.\tra ai-text CODE` (blanked text of the documents the readers couldn't read), read it, and add figures with `.\tra ai-add CODE DOC_ID '<json>'` (unconfirmed, method ai) only for made-up clients or the owner's own papers with their OK. Never open the original files.

- Design: `docs/specs/2026-10-14-tax-return-assistant-design.md` (binding), `docs/specs/2026-10-18-sawnx-design.md` and `docs/specs/2026-10-25-sawnx-six-additions-design.md` (emails, client spreadsheets, Things to check, progress bar, recent searches, info request).
- Plans: `docs/plans/2026-10-14-tax-return-assistant.md`, `docs/plans/2026-10-18-sawnx.md`, `docs/plans/2026-10-25-sawnx-six-additions.md`.
- User guide: `README.md`.

## Rules that are not negotiable
- TFN, Medicare, card, BSB, account, licence and passport numbers must never reach any file, log, filename or API. Redact first (`src/tra/privacy/`); every write goes through the output guard.
- Never commit client data, or a checksum-valid TFN, Medicare or card number, even as a test example. `tests/test_repo_hygiene.py` enforces this. Tests generate identifiers at runtime.
- Clients are identified by client code in every file, folder, filename, log, audit entry and workpaper. Names exist only in `TRA_HOME\clients.json`, for Sawnx's screens (`web/client_names.py`); the audit log records that a client was named, never the name. Client data lives under `TRA_HOME`, outside the repo and never in cloud-synced folders.
- Uncertain tax treatment is flagged with a citation, never guessed.

## Working on it
```
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest          # 916 tests; LibreOffice recalc tests run if soffice exists; 4 run only on Windows
.venv/bin/python -m pyflakes src tests
```
- On Windows the paths are `.venv\Scripts\...`. pyflakes isn't in the `dev` extras; `pip install pyflakes` into the venv.
- Users run the tool as `.\tra <command>` (`tra.cmd`), so they never need `Activate.ps1` or a script-policy change. Settings fall back to the values saved for the Windows account (`HKCU\Environment`), so a window opened before setup still works.
- Write the failing test first.
- Rates live in `config/rates/fyYYYY.yaml`, marked `status: unverified` until a registered agent checks them.

## Status (18 Oct 2026)
Built and reviewed; Sawnx built 18 Oct 2026. On 25 Oct 2026 Sawnx gained email (.eml, .msg via olefile) and client-spreadsheet reading, Things to check, a progress bar, recent searches, Make info request (Word, from last year) and a Chrome app window; reviewed, not committed. Not yet used on real clients. Before that:
- verify the rates (SAPTO FY2026 first), citations and label letters;
- privacy officer sign-off;
- a test on a firm laptop (setup, the demo and the tests passed on a personal Windows 10 PC on 17 Oct 2026);
- move to a private repo (`for-claude` is public).

- AI reader: the privacy officer approved it for real clients (25 Oct 2026; a made-up demo on 19 Oct). Names and addresses aren't blanked before text is sent. Claude reading in chat (`ai-text`, teaching layouts) is still made-up only. Also the firm's IT confirming a local web server on 127.0.0.1 is OK.

**Teaching layouts:** when the owner says "teach Sawnx the new layouts", follow `.claude/skills/teach-layouts/SKILL.md` (design `docs/specs/2026-10-25-layout-teaching-design.md`): layout files in `config/layouts/`, each proved by a made-up copy in `tests/layout_samples/`. Filed documents are named `CODE YYYY-MM-DD Kind - Issuer.ext` since 25 Oct 2026 (`filing/naming.py`).

Open ideas: company and trust returns, OCR for scans, FYI document preview in Sawnx. See `docs/obsidian/Tax Return Assistant/Known issues and ideas.md`.
