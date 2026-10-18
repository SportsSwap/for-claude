# Tax Return Assistant: notes for Claude

The owner is an undergraduate accountant at a boutique Australian firm (Advisory, Accounting & Taxation). They are not a developer, so explain in plain language and give exact steps. They use **Windows laptops**, **Xero Tax** (lodgment) and **FYI Docs**. They keep project notes in an **Obsidian** vault on their computer. Copies of those notes are in `docs/obsidian/Tax Return Assistant/`; update them when the project changes, and send them the updated files.

## What this is
A local Python CLI (`tra`) that prepares **draft** individual returns: redact → file → extract → confirm in Excel → `tra prepare` (draft return, two independent tax calculations, self-checks, Excel workpaper). **It never lodges.** A registered agent signs off every return.

**Sawnx** (`src/tra/web/`, `tra web`, `Sawnx.cmd`) is the same tool as a local website: Flask on 127.0.0.1 only, a per-start session key, no CDN or external fonts. Routes are thin; behaviour is in `web/services/`, which call the existing code. The AI reader (`ingest/extractors/ai_reader.py`) is built but **off** until the privacy officer approves; it only takes `RedactedText` and its tests use a stand-in client.

- Design: `docs/specs/2026-10-14-tax-return-assistant-design.md` (binding) and `docs/specs/2026-10-18-sawnx-design.md`.
- Plans: `docs/plans/2026-10-14-tax-return-assistant.md`, `docs/plans/2026-10-18-sawnx.md`.
- User guide: `README.md`.

## Rules that are not negotiable
- TFN, Medicare, card, BSB, account, licence and passport numbers must never reach any file, log, filename or API. Redact first (`src/tra/privacy/`); every write goes through the output guard.
- Never commit client data, or a checksum-valid TFN, Medicare or card number, even as a test example. `tests/test_repo_hygiene.py` enforces this. Tests generate identifiers at runtime.
- Clients are identified by client code in every file, folder, filename, log, audit entry and workpaper. Names exist only in `TRA_HOME\clients.json`, for Sawnx's screens (`web/client_names.py`); the audit log records that a client was named, never the name. Client data lives under `TRA_HOME`, outside the repo and never in cloud-synced folders.
- Uncertain tax treatment is flagged with a citation, never guessed.

## Working on it
```
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest          # 464 tests; LibreOffice recalc tests run if soffice exists; 4 run only on Windows
.venv/bin/python -m pyflakes src tests
```
- On Windows the paths are `.venv\Scripts\...`. pyflakes isn't in the `dev` extras; `pip install pyflakes` into the venv.
- Users run the tool as `.\tra <command>` (`tra.cmd`), so they never need `Activate.ps1` or a script-policy change. Settings fall back to the values saved for the Windows account (`HKCU\Environment`), so a window opened before setup still works.
- Write the failing test first.
- Rates live in `config/rates/fyYYYY.yaml`, marked `status: unverified` until a registered agent checks them.

## Status (18 Oct 2026)
Built and reviewed; Sawnx built 18 Oct 2026. Not yet used on real clients. Before that:
- verify the rates (SAPTO FY2026 first), citations and label letters;
- privacy officer sign-off;
- a test on a firm laptop (setup, the demo and the tests passed on a personal Windows 10 PC on 17 Oct 2026);
- move to a private repo (`for-claude` is public).

- privacy officer approval before the AI reader is switched on, and the firm's IT confirming a local web server on 127.0.0.1 is OK.

Open ideas: company and trust returns, OCR for scans, FYI document preview in Sawnx. See `docs/obsidian/Tax Return Assistant/Known issues and ideas.md`.
