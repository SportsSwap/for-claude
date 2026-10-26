---
tags: [tax, design]
---

# How it works

Back to [[Tax Return Assistant]]

## What happens to a document
1. **Read:** PDF, CSV, Excel, Xero export, a client's own spreadsheet, or an email (.eml or .msg) with its attachments.
2. **Redact straight away.** TFN, Medicare, card, BSB, account, licence and passport numbers become `[TFN REDACTED]` and so on before anything else sees the text. See [[Privacy rules]].
3. **Classify:** pre-fill report, income statement, bank statement, dividend statement, rental statement, private health statement, receipt, Xero report…
4. **Extract figures** into `figures.csv`, each tagged with its source document and page, and marked *unconfirmed*.
5. **File the original unchanged** as `SMIT01 2026-03-24 Dividend statement - SAMPLE MINING LTD.pdf` (readable names since 25 Oct 2026; older files keep `SMIT01_FY2026_DIVSTMT_2026-03-24.pdf` until read again), under `C:\TaxAssistant\Clients\SMIT01\FY2026\<Category>\`, and list it in `index.csv`. FYI Docs is supported once the firm sets it up.
6. **I confirm the figures** in Excel. Only confirmed figures go into the return.
7. **Prepare:**
   - builds the draft return in ATO item order (matches Xero Tax);
   - runs **two separate tax calculations** that must agree to the cent;
   - runs the [[Self-checks]];
   - writes the workpaper.

Documents it can't read (scans, password-protected files, unknown layouts) are still filed, and a note asks for manual entry.

## Teaching Sawnx layouts (25 Oct 2026)
- The readers are rules. A document Sawnx can't read can usually be **taught**: Claude, in a chat, reads its blanked-out text, writes a small layout file (`config/layouts/`: which words recognise it, which line holds which amount) and a made-up copy that proves it in the tests. From then on Sawnx reads that layout itself, no AI.
- **Read again** reads a filed document with today's rules; confirmed and typed-in figures are never changed.
- Learned so far: ATO income statement (myGov), Bupa health statement, NSW school receipts (suggested labels).
- Can't be taught: scans with no text or garbled text. A misread amount ("$24s") is flagged, never used.

## Emails, client spreadsheets and Things to check (25 Oct 2026)
- **Emails:** the email itself is filed in Other as *Email from the client*. Its subject, date and text are blanked out like any document; the sender and recipients aren't kept. A line like "Donations to Red Cross: $500" becomes an unconfirmed figure with a *suggested label*. Reading stops at a quoted reply ("On ... wrote:"), so amounts the client repeats aren't counted twice.
- **Attachments:** each one is filed and read as its own document, as if I'd imported it. Word files and photos are stored only; a .zip or other unusable file isn't filed, and the email says so. Signature logos are skipped. Attachment names are never kept.
- **Client spreadsheets (.xlsx, .csv):** if it isn't a Xero export or another known layout, Sawnx finds the description and amount columns and turns each row with words it knows into a figure with a suggested label ("Sheet 1 row 4: Red Cross donation"). The word list is `config/sheet_words.yaml`. A row it can't label, or that could be two things ("interest"), isn't added: it goes in Things to check. A list of share sales gives no figures (enter them as CGT events).
- **Things to check:** each document's list of what the reader wasn't sure about: amounts not found, rows not labelled, no date, scanned pages, areas the tool doesn't handle, and unconfirmed figures that are suggested or AI-read. Shown above **Open** on the document, in the import results, under figures on the Figures tab, and as a count in the document list. No made-up confidence scores: the readers find a line or they don't.
- **Make info request:** a Word checklist for this year's papers from last year's confirmed figures (who paid what, shares sold, rental, deductions claimed). No amounts, no client name ("Dear [client's name],"). Filed in Correspondence > Letters. Wording in `config/info_request.yaml`.

## The workpaper (Excel)
| Tab | What's on it |
|---|---|
| Cover | DRAFT – NOT FOR LODGMENT, estimated result, partner / manager / reviewer / preparer, sign-off boxes |
| B01 Summary | The hub, like the firm's: tax summary box, then each return item with a **Go to** link, amount, tax credits, pre-fill, difference, prior year, movement % |
| Item tabs (only the ones needed) | Named like the firm's: 01 Salaries and Wages, 10 Interest Received, D05 Other Work Deductions, M25 Rental <property> (one per property, in the firm's rental layout), PHI Private Health… Same header on each; ATO pre-fill and client documents shown separately; each figure links to its document and page; **Transferred to: Item 10 L** links back to the Summary line |
| M03 Capital Gains | CGT events and the net capital gain working (when there are any) |
| Tax Calc | Taxable income through to refund or payable, all live Excel formulas, with the second calculation beside it |
| Rates | That year's rates, copied in |
| Sources | Every filed document |
| Review Notes | Every flag, ranked High / Medium / Low, with citations and a response column |

It looks like the firm's workpapers (Calibri 10, no gridlines, light-blue link boxes). Blue numbers are typed-in inputs; everything else is a formula. Headers show the client code, never the name.

## Tax years and rates
- **Rates files:** `config/rates/fy2026.yaml` and `fy2025.yaml`. Each new year, copy the file and update the figures.
- **Verification:** the files are marked *unverified* until a registered agent checks them. See [[To do before real clients]].

## Other parts
- **Xero:** pulls the P&L, balance sheet, bank transactions and chart of accounts for sole traders. Read-only; tested with fake data only.
- **FYI Docs:** files documents there and falls back to local folders if FYI is down. Tested with fake data only.

Related: [[Decisions log]], [[Tax terms]]
