# PLS Group Limited (ASX: PLS) — FMAA x Shared Value Project 2026

Submission for the FMAA / Shared Value Project *Investing for the Future* case competition.
Recommendation to the Portfolio Manager of the FMAA Asset Management ASX 200 long-only fund.

## Recommendation

**BUY** — 12-month target **A$6.12** against a last close of A$5.48 (+11.7%), plus a
forecast FY27 dividend yield of 1.7%, for an expected total return of **13.4%** against
a benchmark that returned 5.90% in FY26.

## Contents

| Path | What it is |
|---|---|
| `model/PLS_Valuation_Model_FMAA_2026.xlsx` | The valuation model. 18 sheets, 1,700 live formulas, zero errors. |
| `model/params.py` | Every input, provenance-tagged. |
| `model/build_model.py` | Rebuilds the workbook from the parameters. |
| `deck/` | The submission deck: 15 main slides plus appendix. |
| `research/` | Sourced research dossiers underpinning every figure. |

## Rebuilding

```bash
python3 model/build_model.py
python3 <xlsx-skill>/scripts/recalc.py model/PLS_Valuation_Model_FMAA_2026.xlsx 300
```

`Assumptions!C7` is a scenario switch. Set it to Bear, Base or Bull and the whole model
repoints — production, prices, costs, capex, the three statements, the DCF and the target price.

## Two modelling choices worth knowing about

**The terminal value is an annuity over the remaining ore base, not a growing perpetuity.**
An orebody is finite. On the base-case production profile Pilgangoora mines 104Mt of the
334Mt mineable base by FY36, leaving about 16 years. A growing perpetuity would have valued
the terminal period at A$18.9bn instead of A$9.9bn — nearly double, for an asset that runs out.

**The three price scenarios converge on a common long-run level.** In a commodity, a trough
forces supply out and a spike pulls it in, so a perpetuity struck at either extreme is not a
forecast. The scenarios differ on the path and on volumes, not on where the cycle settles.
