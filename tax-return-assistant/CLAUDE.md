# Tax Return Assistant: notes for Claude

The owner is an undergraduate accountant at a boutique Australian firm (Advisory, Accounting & Taxation). They are not a developer, so explain in plain language and give exact steps. They use **Windows laptops**, **Xero Tax** (lodgment) and **FYI Docs**. They keep project notes in an **Obsidian** vault on their computer. Copies of those notes are in `docs/obsidian/Tax Return Assistant/`; update them when the project changes, and send them the updated files.

## What this is
A local Python CLI (`tra`) that prepares **draft** individual returns: redact → file → extract → confirm in Excel → `tra prepare` (draft return, two independent tax calculations, self-checks, Excel workpaper). **It never lodges.** A registered agent signs off every return.

- Design: `docs/specs/2026-10-14-tax-return-assistant-design.md` (binding).
- Plan: `docs/plans/2026-10-14-tax-return-assistant.md`.
- User guide: `README.md`.

## Rules that are not negotiable
- TFN, Medicare, card, BSB, account, licence and passport numbers must never reach any file, log, filename or API. Redact first (`src/tra/privacy/`); every write goes through the output guard.
- Never commit client data, or a checksum-valid TFN, Medicare or card number, even as a test example. `tests/test_repo_hygiene.py` enforces this. Tests generate identifiers at runtime.
- Clients are identified by client code only. Client data lives under `TRA_HOME`, outside the repo and never in cloud-synced folders.
- Uncertain tax treatment is flagged with a citation, never guessed.

## Working on it
```
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest          # 299 tests; LibreOffice recalc tests run if soffice exists
.venv/bin/python -m pyflakes src tests
```
- Write the failing test first.
- Rates live in `config/rates/fyYYYY.yaml`, marked `status: unverified` until a registered agent checks them.

## Status (17 Oct 2026)
Built and reviewed. Not yet used on real clients. Before that:
- verify the rates (SAPTO FY2026 first), citations and label letters;
- privacy officer sign-off;
- a Windows test of `setup.ps1`;
- move to a private repo (`for-claude` is public).

Open ideas: a double-click launcher, company and trust returns. See `docs/obsidian/Tax Return Assistant/Known issues and ideas.md`.
