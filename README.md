# PLS Group Limited (ASX: PLS) — FMAA x Shared Value Project 2026

Submission for the Shared Value Project x FMAA *Investing for the Future* case competition,
in the role of analysts in the shared value coverage team at FMAA Asset Management,
addressing the portfolio manager of an ASX 200 long-only fund.

## Recommendation

**BUY.** Twelve-month target **A$6.14** against a last close of A$5.48, or **+12.0%**, plus a
forecast FY27 dividend yield of 1.7%, for an expected total return of **13.6%** against a
benchmark that returned 5.90% in FY26. Bear A$2.30, base A$6.53, bull A$8.96.

The argument in one line: of the A$0.66 of upside, **A$0.43 — two thirds — comes from
ESG-linked operating decisions the market is not paying for.**

## Deliverables

| Path | What it is |
|---|---|
| `deck/PLS_Group_FMAA_2026.pptx` | The submission deck. 81 slides: 15 content slides (the case limit), a title, 3 dividers, and a 62-slide appendix. Speaker notes on every content slide. |
| `deck/PLS_Group_FMAA_2026.pdf` | The same deck as PDF, for Jotform upload. |
| `model/PLS_Valuation_Model_FMAA_2026.xlsx` | The valuation model. 19 sheets, 1,728 live formulas, zero evaluation errors. |
| `prep/QA_PREP.md` | Hostile Q&A prep for the live rounds, organised by how likely each question is. |
| `research/` | Four sourced research dossiers plus a verified core-facts file. |
| `deck/verify_numbers.py` | Checks every headline figure on the slides against the recalculated model. Exits non-zero on a mismatch. |

## Rebuilding

```bash
python3 model/build_model.py                                  # rebuild the workbook
python3 <xlsx-skill>/scripts/recalc.py model/*.xlsx 300       # recalculate and check for errors
node deck/build.js $(cat deck/.parts)                         # rebuild the deck
python3 deck/verify_numbers.py                                # confirm the slides tie to the model
```

`Assumptions!C7` in the workbook is a scenario switch. Set it to Bear, Base or Bull and the
whole model repoints: production by asset, price deck, cost deck, capital expenditure, all
three financial statements, the DCF and the target price.

## Three choices worth knowing about

**The terminal value is an annuity over the remaining ore base, not a growing perpetuity.**
An orebody is finite. On the base-case profile Pilgangoora consumes 104Mt of its 334.5Mt
mineable base by FY36 and exits at 14.3Mt of ore a year, leaving about 16 years. A growing
perpetuity would have valued the terminal period at A$19.0bn instead of A$9.9bn, on an asset
that runs out of rock.

**The three price scenarios converge on a common long-run level.** A trough forces supply out
and a spike pulls it in, so a perpetuity struck at either extreme is not a forecast. The
scenarios differ on the path and on volumes, not on where the cycle settles.

**The shared-value bridge is an attribution, not an addition.** The ore-sorting and power
benefits are already inside the A$569/t FY26 cost base the DCF discounts. The bridge
decomposes a valuation already struck; it does not inflate it.

## Known gaps

Company websites and the ASX announcements platform were unreachable from the environment
this was built in, so reported figures were corroborated across two or more independent
secondary reports of each announcement rather than read off the primary document. Headline
FY26 figures are consistent across sources. Appendix F4 is a register of every material gap,
with the valuation effect quantified where possible.

Two gaps closed late: total borrowings are A$853m at 30 June 2026, so the balance sheet now
ties to the reported A$6,258m of total assets; and FY26 safety and diversity metrics were
retrieved (TRIFR 2.77, down 11%; female participation 21.9%; Scope 1 and 2 down 5%).

One indicator turned against us and is reported rather than dropped: short interest bottomed
at 6.8% in May 2026 and has rebuilt to **10.09%** as at 4 August 2026, through the 10% level
our own risk register names as a warning signal. Appendix F2 sets out what we make of it.

## Disclaimer

Prepared as a university case-competition submission using publicly available information.
Not investment advice. Forecasts are the authors' estimates and will differ from outcomes.
