---
tags: [tax, design]
---

# How it works

Back to [[Tax Return Assistant]]

## What happens to a document
1. **Read:** PDF, CSV, Excel or Xero export.
2. **Redact straight away.** TFN, Medicare, card, BSB, account, licence and passport numbers become `[TFN REDACTED]` and so on before anything else sees the text. See [[Privacy rules]].
3. **Classify:** pre-fill report, income statement, bank statement, dividend statement, rental statement, private health statement, receipt, Xero report…
4. **Extract figures** into `figures.csv`, each tagged with its source document and page, and marked *unconfirmed*.
5. **File the original unchanged** as `SMIT01_FY2026_DIVSTMT_2026-03-24.pdf`, under `C:\TaxAssistant\Clients\SMIT01\FY2026\<Category>\`, and list it in `index.csv`. FYI Docs is supported once the firm sets it up.
6. **I confirm the figures** in Excel. Only confirmed figures go into the return.
7. **Prepare:**
   - builds the draft return in ATO item order (matches Xero Tax);
   - runs **two separate tax calculations** that must agree to the cent;
   - runs the [[Self-checks]];
   - writes the workpaper.

Documents it can't read (scans, password-protected files, unknown layouts) are still filed, and a note asks for manual entry.

## The workpaper (Excel)
| Tab | What's on it |
|---|---|
| Cover | DRAFT – NOT FOR LODGMENT, estimated result, sign-off boxes |
| Summary | Every return label: this year, pre-fill, difference, prior year, movement % |
| One tab per category | Each figure with a link to its source document and page; a subtotal per label |
| Capital Gains | CGT events and the net capital gain working (when there are any) |
| Tax Calc | Taxable income through to refund or payable, all live Excel formulas, with the second calculation beside it |
| Rates | That year's rates, copied in |
| Sources | Every filed document |
| Review Notes | Every flag, ranked High / Medium / Low, with citations and a response column |

Blue numbers are typed-in inputs; everything else is a formula.

## Tax years and rates
- **Rates files:** `config/rates/fy2026.yaml` and `fy2025.yaml`. Each new year, copy the file and update the figures.
- **Verification:** the files are marked *unverified* until a registered agent checks them. See [[To do before real clients]].

## Other parts
- **Xero:** pulls the P&L, balance sheet, bank transactions and chart of accounts for sole traders. Read-only; tested with fake data only.
- **FYI Docs:** files documents there and falls back to local folders if FYI is down. Tested with fake data only.

Related: [[Decisions log]], [[Tax terms]]
