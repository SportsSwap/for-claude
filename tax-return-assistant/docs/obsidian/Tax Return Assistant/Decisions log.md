---
tags: [tax, decisions]
---

# Decisions log

Back to [[Tax Return Assistant]]

## Decided with Claude (14 Oct 2026)
| Question | Decision | Why |
|---|---|---|
| Python or something else? | **Python command-line tool** | Excel/VBA can't redact a PDF before reading it. Hubdoc and Dext receive documents unredacted. |
| How to read PDFs? | **Local only**, with room for an AI reader later | An AI reader would send client data offshore (APP 8) and needs firm approval |
| Tax software | **Xero Tax** | The tool works *around* Xero Tax: pre-fill, lodgment and the official estimate stay there |
| Workpaper layout | **Default layout for now** | All styling is in one file (`layout.py`), so it can be re-skinned to the firm template |
| Scans or digital? | **Mostly digital**, so no OCR yet | Scans get filed and flagged for manual entry |
| Computers | **Windows laptops** | PowerShell setup script |
| First version | **Stages 1–4 working; Xero and FYI built, but tested only with fake data** | No firm credentials available to test against |
| Confirm step | **Yes**: I confirm figures in Excel before the return is built | Catches extraction mistakes before the reviewer sees them |
| Original documents | **Filed unchanged** | FYI is the firm's record system; TASA record-keeping |
| Where the code lives | Its own folder, away from the PLS case study | My request |

## Things Claude decided during the build
- **Unknown hospital cover** is assumed covered, with a note to ask the client.
- **Two calculations** share no code, so a mistake in one shows up as a difference.
- **Rental and other tabs** subtotal each return label separately, and Rental shows net rent.
- **Running the demo twice** doesn't add the documents again.
- **Prior-year comparison** uses the tool's own output from last year automatically.
- **Personal super contributions (D12)** count in the HELP, surcharge and rebate income tests.

The full list, with what each costs if wrong, is in the build session: <https://claude.ai/code/session_01N2pEC5oyPFnAavBcEamEbT>

## Final review (15 Oct 2026)
A second Claude reviewed everything.
- **The tax maths and the Excel formulas were confirmed correct.**
- It found 1 serious bug: figures were lost if `figures.csv` was open in Excel during ingest.
- It found 12 important issues: redaction gaps, encoding, cloud folders, D12, residency, duplicates, Xero token size and others.
- **All of those were fixed**, each with a test.
- The smaller issues are listed in [[Known issues and ideas]].

## Windows test (17 Oct 2026)
- **Commands start with `.\tra`** (a small `tra.cmd` file) instead of activating the tool first. Windows blocks `Activate.ps1` by default, and firm laptops may not let me change that.
- **The tool finds `TRA_HOME` from my Windows account** when the PowerShell window doesn't have it, so it works straight after setup.

## Sawnx website (18 Oct 2026)
- **Sawnx**: an FYI-style website for the tool, with a black background. It runs **only on my laptop** (opens in the browser, not on the internet), so client documents stay in `C:\TaxAssistant` or FYI.
- First version: client list with job status (Docs in, Figures confirmed, Prepared, Reviewed), each client's files in folders (standard ones plus my own) and my own file notes, import where I pick the return type (Individual for now) and choose per file "Read for the return" or "Store only", confirm figures on screen, a Prepare button with the workpaper to download, and review notes with responses.
- **Sensitive numbers:** blanked out the moment a document is read, so nothing the tool makes ever holds them. The stored original stays unchanged as the firm's record, like FYI.
- **AI reader built in but switched off** until the privacy officer approves. It would only get blanked-out text, only for documents the tool can't read.
- Built as a small web server inside the tool (Flask), using the tool's existing code. No new database.
- **Borrowed from FYI** (its ideas from public pages, not its code or look): everything hangs off the client, folders work like FYI's cabinets, each year's return is a job with a status, file notes, and an Activity list drawn from the audit log.
- **Mockup** (Claude Design, made-up clients only): <https://claude.ai/artifact/KRWfmgQYTKTzCFPjA7kLmW>
- Design: `docs/specs/2026-10-18-sawnx-design.md`; build plan: `docs/plans/2026-10-18-sawnx.md`.
- **Built 18 Oct 2026** (402 tests pass, 3 skipped). Every step was test-first.
- **Found only by trying it in the browser**, both fixed with tests: (1) every save was refused, because a privacy setting made the browser hide where the form came from; (2) returns prepared with `.\tra prepare` didn't show in Sawnx. Lesson: always click through the real thing, not just the tests.
- **AI reader:** Claude Opus 5.5 through Anthropic's official library (installed only if switched on), automatic fallback if a request is declined, only blanked-out text, everything it finds unconfirmed. **Off** until the privacy officer approves.
- **Look:** the laptop's own fonts instead of the mockup's, because Sawnx fetches nothing from the internet.
- **Client names (18 Oct 2026):** Sawnx shows, sorts and searches by name; the code is suggested from the surname (Jane Citizen → CITI01). Files, logs and workpapers still use only the code, so a stray file never says who the client is. Names live in one file, `clients.json`.
- **Document summaries (18 Oct 2026):** every document gets an automatic summary (what it is, who issued it, the figures it supports) without any AI, plus a description box for my own notes. Both go into the workpaper's Sources tab as evidence.

Related: [[How it works]], [[Privacy rules]]
