---
tags: [tax, review]
---

# Self-checks

Back to [[Tax Return Assistant]]. These run on every return and appear on the Review Notes tab, ranked by risk, then dollar impact. They never change the return; they only flag.

| Code | Checks for |
|---|---|
| R1–R5 | A figure with no source document; label totals not adding up; unconfirmed figures; pre-fill *and* the source document both counted; the same document ingested twice |
| P1–P4 | Differences from the ATO pre-fill (over $1); pre-fill items missing from the return; no pre-fill ingested; HELP debt mismatch |
| C1 | The two tax calculations disagree |
| C2 | Rates file not yet verified (shows until a registered agent checks it) |
| S1 | Deductions high relative to income |
| S2 | Income with no statement behind it |
| S3 | Rental income with no expenses, or the reverse |
| S4 | Work claims over $300 without written evidence (s900-35) |
| S5 | Car claim over the cents-per-km cap (5,000 km × 88c) |
| S6 | Ordinary clothing claimed (TR 97/12) |
| S7 | A rental "repair" that looks like an improvement (TR 97/23) |
| S8 | CGT dates and cost base; discount on assets held only just over 12 months |
| S9 | Medicare levy surcharge risk when hospital cover is missing or unknown |
| S10 | Interest on a redraw or line of credit (TR 2000/2) |
| S11 | Gifts under $2, or not confirmed as going to a DGR |
| S12 | Things the tool doesn't prepare: family thresholds, non-residents, managed funds, business P8 detail, net investment losses |
| S13 | Equipment over $300 claimed outright (it's depreciating, s40-80) |
| S14 | Residency assumed |
| Y1–Y2 | Over 20% (and $100) movement from last year; items that disappeared |
| I1–I7 | From ingest: manual entry needed, no document date, FYI down, duplicate file, unmapped Xero section, an area it doesn't handle (ESS, foreign income, trusts…), hospital cover days read from the health statement |

The thresholds are in `config/checks.yaml`; the citations are in `config/citations.yaml` (not yet verified).

Related: [[How it works]], [[Tax terms]]
