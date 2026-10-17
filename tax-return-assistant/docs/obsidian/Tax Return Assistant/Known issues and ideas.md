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

## Ideas
- **Double-click launcher**, so there's no typing in PowerShell. Claude offered to build it.
- Simple local web page instead of commands.
- Company and trust returns.
- An AI reader for messy documents, on redacted text, once the firm approves.
- Match the firm's own workpaper template (edit `layout.py`).

Related: [[To do before real clients]], [[Decisions log]]
