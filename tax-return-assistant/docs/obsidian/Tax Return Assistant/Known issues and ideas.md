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
- ~~No check that dates fall in the income year~~: **done 19 Oct 2026** (self-check R7, see [[Self-checks]]).
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
- **Fixed (19 Oct 2026):** a share registry dividend statement (amounts in a table under a heading row, as Link/MUFG and Computershare do) came in as "couldn't read". The reader now reads the table, and only uses it if unfranked + franked = total and the franking credit isn't too big. 'Withholding tax' on a statement comes in as TFN withheld with a note to confirm.
- **Ideas from the TEST02 trial:** ~~warn when a document is dated outside the income year~~ (the test statement was paid 28 March 2025, so it belongs in FY2025, not FY2026): **done 19 Oct 2026** as self-check R7; a "read again" button for a document that's already filed (importing the same file again is skipped as a duplicate). For now: Delete it, then import the same file again and it's read again.
- **Done 19 Oct 2026:** deleting documents in Sawnx (Deleted items, Restore, Delete forever).
- **Found 19 Oct 2026, not fixed:** an account number at the end of a line can swallow the first number of the next line when it's blanked ("Account 7012 3456" then "1 July 2025" became "[ACCOUNT REDACTED] July 2025"). Too much is blanked, never too little, but a date or amount can lose a digit.
- **Fixed 19 Oct 2026:** `tra ingest` could stop part-way when its output went to a window using an old text encoding (it printed a "→").
- **Fixed 19 Oct 2026:** about 1 time in 220, Sawnx refused to save a file note, comment, time entry, job, task, rule or In Tray document with "looks like a TFN". The cause was Sawnx's own random record ID, which sometimes held 8 digits that happen to pass the TFN check. IDs are now letters only, so they can never look like a TFN, Medicare, card or account number. The privacy check itself is unchanged.
- **What the date check (R7) can't see:**
  - documents with no date found (the I2 note already says so);
  - last year's annual statement that only shows an issue date early in this year (say 15 July 2025), because that date is inside FY2026;
  - a monthly rental statement for July, dated within 120 days after 30 June, which passes as if it were the year's summary;
  - a pre-fill report is allowed any date after 30 June, because it can be downloaded long after the year ends.

## Sawnx small issues (from the 18 Oct 2026 review, not fixed yet)
- A folder named like a Windows device (CON, NUL, COM1) gives an unclear error.
- If a filed document is moved outside Sawnx, its page says "Filed in FYI" instead of "file not found".
- The AI reader's on/off setting lives in the website part of the code; tidier in a shared place.
- The Activity list reads the whole audit log each time; fine now, slower after years.
- If Sawnx is killed in the middle of an import, the temporary copy can stay in the client's `_uploads` folder.

## From the six Sawnx additions (25 Oct 2026)
- **Forwarded emails:** the part of an email after "From:" or "On ... wrote:" isn't read for figures, so a forwarded bank email's amounts are listed in Things to check for me to enter.
- **An email attached inside an Outlook .msg** can't be read: save it from Outlook on its own and import it.
- **Client spreadsheets:** the word list is deliberately short; rows it doesn't know go to Things to check. A list of share sales isn't turned into CGT events yet.
- **Progress bar:** only on the client's Import panel, not In Tray's Add. The time left is an average, so it's rough for the first file or two.
- **Things to check** stays on a document after I've dealt with a document-level item (for example "Didn't find the franking credit"); only figure items drop off when confirmed. Idea: a "done" tick per item.
- **Info request** uses last year's confirmed figures in Sawnx. For a new client with only last year's notice of assessment, fill in `prior_year.csv` first, or it's the standard list.
- Still no OCR: scanned emails or photo attachments need manual entry.
- **My own sample documents (25 Oct 2026):** 6 of 7 came in as manual entry. The built-in readers are rules made for the demo layouts, so real wording ("Total incl. GST", interest month by month) doesn't match. Options: add readers for the layouts I see most (needs a fake-data copy of each), and use the AI (Claude in chat now; the AI reader with an API key once the privacy officer approves) for everything else. Scanned pages need OCR either way.
- **Bank statement exports** (with a balance, or debit and credit columns) aren't read as client lists: Things to check asks me to pick the rows.
- Small things left from the final review: the progress bar can repeat a warning once per file; In Tray's "filed" message doesn't mention an email's attachments; spreadsheets filed before 25 Oct count as one page; an email's Things to check drops a minus sign.
- **R7 and emails:** an email sent more than 120 days after 30 June raises the date note. Idea: don't date-check emails, since the sent date isn't the period the figures cover.

## From trying the AI reader (25 Oct 2026)
- Page images are only sent when Sawnx's own readers found no figures, so a scanned page inside a document that's partly readable isn't sent.
- Idea: let me pick the AI model in Settings (Sonnet 5.5 reads tables better than Haiku 5.5, still cheaply).

## Rental properties (26 Oct 2026)
- I showed Claude the firm's rental sheet (an M25 Rental tab for one property). Now: a **Rental** tab in Sawnx per client year (share %, private use, weeks, Apportion? ticks; more than one property; which property each document is; who paid each expense) and **one workpaper tab per property** in the firm's layout, rows A to X.
- **The return now uses the client's share.** Before this it claimed 100% of a jointly owned property.
- The share is read from a document when it says so ("Ownership share 50%"), by the rules or the AI, as a suggestion; Save on the Rental page to confirm it. Review note S18 until then.
- Why the rental sheet was missing from my test workpaper: none of its 11 rental figures were confirmed. Only confirmed figures go into the workpaper.
- **Independent review (26 Oct 2026):** the money matched (Python and the Excel formulas agree at 100%, 50% and 33.33% with private use). Fixed 9 things: an apostrophe in a property name (O'Brien St) broke the Summary's formulas; two names differing only in capitals read the wrong tab (now refused); "NaN" or a blank share (a blank saved 0%) are refused; a damaged rental.json now gives a plain message instead of crashing Prepare, the Rental page or an import; with two properties a document's share is never put on the wrong property, and a second, different suggestion only adds a note; text starting with "=" stays text in the workpaper (and the guard now checks it); Save columns only keeps real changes.
- Still to check on a laptop with Excel or LibreOffice: rounding at exactly half a cent with an odd share (Excel works in floating point).
- Not yet: acquisition and disposal details, the daily apportionment helper, prior-period amounts per row, reading weeks rented from documents.

## Rental expense categories (26 Oct 2026)
- Rental expenses used to all land in "Other rental deductions" (21 U). Now each goes to its ATO rental schedule category: advertising, body corporate, borrowing, cleaning, council rates, capital allowances, gardening and lawn mowing, insurance, land tax, legal, pest control, property agent fees, repairs and maintenance, stationery and phone, travel, water. Anything that doesn't fit (or fits two) stays as **Sundry**. The M25 tab shows each with a subtotal; the return still has one 21 U line.
- The words for each category are in `config/rental_words.yaml`: add words there when a statement's line goes to Sundry but shouldn't. I can change a figure's category on the Figures tab (the label list).
- New review notes: S15 rental travel, S16 borrowing expenses over $100, S17 depreciation on second-hand assets.
- Figures read before 26 Oct stay under Sundry until the document is read again or I change the label.

## From my tax agent's invoice (26 Oct 2026)
- The rules and the AI both read nothing, with no warning. Why: the PDF is a **scan with a typed-over text layer** (the scanner's OCR). The text looked ordinary enough ("A0ourt Due 495.00") that Sawnx didn't count it as garbled, so no picture was sent; Haiku got only the messy text and said "nothing here", and an empty answer left no note.
- **Fixed:** a page that is one big picture (80% of the page or more) now counts as a scan, so with page images on its picture is sent too. When the AI finds nothing, Things to check now says so. The built-in receipt reader also reads "Amount due", "Total (incl. GST)", "Invoice total" and "Total amount" lines (a nil "Amount due 0.00" is skipped).
- After that the AI read it right ($495.00 at D10), but Things to check still said "Didn't find a total." (the rules' note). **Fixed:** that note goes once the AI finds an amount. Other "Didn't find the ..." notes stay, because they name one amount the AI may have missed too. Figures still need confirming: a person checks every amount before it goes in a return.
- **New: the "matches" tick.** When the AI reads an amount, Sawnx looks for the same amount written as money ($, cents or commas) in the document's own text. Found: the Figures tab shows "✓ Same amount in the document's own text" (and the workpaper notes say so), so confirming is a glance. Not found: "look at this one closely". My $495.00 invoice figure has the tick. It still needs confirming.
- Known gap: changing an amount in Excel (figures.csv) doesn't remove the tick; the Figures tab does.
- **Read again** uses the free rules only, never the AI: to retry a document with the AI, delete it and import it again.

## From teaching layouts (25 Oct 2026)
- Scans with garbled text (my tax agent's invoice, AustralianSuper statement, property manager bundles) can't be taught: they need OCR or the AI.
- A layout doesn't fix a document's date when the scan garbles it (my income statement and Bupa samples got the import date).
- The Bupa layout doesn't read hospital cover days yet; the ATO income statement layout doesn't read allowances or lump sums.
- Idea: a "teach this one" button on a document that tells Claude which one to look at first.

## Ideas
- **Sawnx like FYI:** all five stages are built (18 Oct 2026). Ideas from here: sharing Sawnx across the firm (needs IT and the privacy officer), email capture into the In Tray (emails can now be dropped in and read, 25 Oct 2026; capturing straight from Outlook would be next), approvals.
- In Tray suggestions only offer the standard folders, not folders I've added for a client.
- **Double-click launcher**, so there's no typing in PowerShell. Claude offered to build it. (`.\tra` already removed the activate step.)
- **Sawnx**, a local FYI-style website instead of commands: **built 18 Oct 2026**. See [[How to run it]].
- Company and trust returns.
- **AI reader for documents the tool can't read** (talked about 18 Oct 2026). Only for documents its own readers can't handle (new layouts, scans). The laptop reads a scan into text, blanks out TFN, Medicare, account and other numbers as it does now, and sends only that cleaned-up text to the AI. The figures come back as unconfirmed rows in figures.csv, so a person still checks each one. **Needs the privacy officer's approval first** (and the partners'): client information would leave the laptop (APP 8), and the tool currently promises no AI or outside service. A separate FYI-style document store isn't needed: the tool already files into FYI once API access is set up.
- ~~Match the firm's own workpaper template~~: **done 18 Oct 2026** (B01 Summary hub, numbered tabs, same header, Transferred to links). Not copied: the vendor's buttons and macros (Refresh ATO pre-fill, roll-over) and the ITA, ICA, BAS and PAYG instalment tabs, which need data the tool doesn't have yet.

Related: [[To do before real clients]], [[Decisions log]]
