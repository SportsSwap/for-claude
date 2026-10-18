---
tags: [tax, backlog]
---

# Known issues and ideas

Back to [[Tax Return Assistant]]

## What it doesn't do (by design)
- **Company and trust returns.** Individuals only for now.
- **Flagged, not calculated:**
  - family Medicare and surcharge thresholds;
  - non-residents;
  - foreign income;
  - employee share schemes;
  - PSI;
  - trust and partnership distributions;
  - managed fund statements;
  - net financial investment losses;
  - business schedule (P8) detail.
- **Medicare levy exemptions (M1)** are only flagged if a document mentions them.
- **No labels for pensions and annuities** (items 5–7).
- **No OCR**: scans need manual entry.
- **Layouts:** it only reads the layouts it was built with, plus the ATO pre-fill report. Real bank and registry layouts need adding.

## Small issues left from the review
- A cell starting with "=" in a document becomes a live Excel formula.
- Ingesting a second pre-fill report doubles the pre-fill totals.
- HELP note (P4) shows when no pre-fill was ingested and the client has a HELP debt.
- The $300 check counts car claims, which s900-35 excludes.
- Keyword checks over-fire ("phone bill", "suitcase", "newsletter").
- No check that dates fall in the income year.
- Copied Excel rows can create duplicate figure IDs.
- `tra scan` prints file paths.
- Some symbols break when Windows output is redirected to a file.
- Three small `setup.ps1` gaps.
- An odd partial-TFN case.
- No command to remove a document ingested by mistake.

## Found in the Windows test (17 Oct 2026)
- **Fixed:** Windows blocked `Activate.ps1` on a fresh PC. Commands now start with `.\tra`, which needs no activating and no change to Windows settings.
- **Fixed:** in the window setup ran in, the tool said `TRA_HOME is not set`. It now finds the folder setup saved.
- **Fixed:** the README's list of demo review notes was missing the residency note (S14).
- **Fixed (17 Oct 2026):** after Excel saved figures.csv, review notes lost their cents ("$2,019" instead of "$2,019.00"). Every dollar amount in the notes now shows two decimals. The tax figures were never affected.
- **Accuracy test client TEST01** (18 Oct 2026): four made-up documents in `C:\TaxAssistant\Inbox\TEST01` (salary, interest, a franked dividend, a membership receipt). Claude's trial run matched a hand calculation to the cent. Still to do: run it myself and compare with my own calculation.
- Not yet tried on a firm laptop.

## Sawnx small issues (from the 18 Oct 2026 review, not fixed yet)
- A folder named like a Windows device (CON, NUL, COM1) gives an unclear error.
- If a filed document is moved outside Sawnx, its page says "Filed in FYI" instead of "file not found".
- The AI reader's on/off setting lives in the website part of the code; tidier in a shared place.
- The Activity list reads the whole audit log each time; fine now, slower after years.
- If Sawnx is killed in the middle of an import, the temporary copy can stay in the client's `_uploads` folder.

## Ideas
- **Sawnx like FYI, stages 3-5:** jobs and tasks; comments, notifications and time; knowledge and filing rules. Stages 1 (the look, Home, the document list) and 2 (In Tray, cabinets, properties, versions) are built.
- In Tray suggestions only offer the standard folders, not folders I've added for a client.
- **Double-click launcher**, so there's no typing in PowerShell. Claude offered to build it. (`.\tra` already removed the activate step.)
- **Sawnx**, a local FYI-style website instead of commands: **built 18 Oct 2026**. See [[How to run it]].
- Company and trust returns.
- **AI reader for documents the tool can't read** (talked about 18 Oct 2026). Only for documents its own readers can't handle (new layouts, scans). The laptop reads a scan into text, blanks out TFN, Medicare, account and other numbers as it does now, and sends only that cleaned-up text to the AI. The figures come back as unconfirmed rows in figures.csv, so a person still checks each one. **Needs the privacy officer's approval first** (and the partners'): client information would leave the laptop (APP 8), and the tool currently promises no AI or outside service. A separate FYI-style document store isn't needed: the tool already files into FYI once API access is set up.
- Match the firm's own workpaper template (edit `layout.py`).

Related: [[To do before real clients]], [[Decisions log]]
