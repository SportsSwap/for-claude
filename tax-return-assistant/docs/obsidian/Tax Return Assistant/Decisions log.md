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
| Workpaper layout | **The firm's layout (18 Oct 2026)** | Copied from the firm's individual tax workpaper: B01 Summary hub, numbered item tabs, same header, "Transferred to" links. Only the layout was read, by a script on the laptop; no client details reached Claude |
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
- **AI reader:** Claude Opus 5.5 at first, **Claude Haiku 5.5 from 25 Oct 2026** (my choice: much cheaper, and suits reading figures; it has no automatic fallback, so a declined document just needs entering by hand), through Anthropic's official library (installed only if switched on), automatic fallback if a request is declined, only blanked-out text, everything it finds unconfirmed. **Off** until the privacy officer approves.
- **Look:** the laptop's own fonts instead of the mockup's, because Sawnx fetches nothing from the internet.
- **Client names (18 Oct 2026):** Sawnx shows, sorts and searches by name; the code is suggested from the surname (Jane Citizen → CITI01). Files, logs and workpapers still use only the code, so a stray file never says who the client is. Names live in one file, `clients.json`.
- **FYI look, stage 1 (18 Oct 2026):** light pages with a dark top bar, Home (My Recent, My Starred), a Documents page, and one FYI-style document list (sort, filter, star, bulk download and move). FYI's layout and features, not its logo or colours. Next stages, one at a time: (2) FYI-style cabinets, document properties and an In Tray where the AI suggests where each document goes; (3) jobs and tasks; (4) comments, notifications and time; (5) knowledge and filing rules. Jobs, comments and approvals only really make sense if several people share Sawnx, which would be a bigger privacy and IT decision.
- **No API account, so Claude reads in chat (19 Oct 2026):** the firm won't pay for an Anthropic API account yet. Instead Claude, in a chat, reads documents the rules couldn't, through two commands: `tra ai-text` (blanked-out text only, scanned again) and `tra ai-add` (figures added unconfirmed, checked strictly, audit logged). Same privacy as the AI reader; the privacy officer approved it for made-up clients only.
- **AI reader demo (19 Oct 2026):** the privacy officer approved switching the AI reader on to see it, with made-up clients only. The API key is saved for the Windows account (never typed into a chat); Sawnx now finds it even if it was already running, and says so if it's on without a key.
- **Deleting documents (19 Oct 2026):** like the Recycle Bin. Delete moves a document to Deleted items with its figures, pre-fill and CGT lines and notes, so the return stops counting it; Restore puts everything back; Delete forever is a second step that also removes its older versions, description, star and comments. A deleted document's number is never reused. FYI documents are deleted in FYI. Every step is in the audit log by document number. Firms keep tax records for years, so Delete forever is for mistakes only.
- **FYI look, stages 3-5 (18 Oct 2026):** jobs (one tax return job per client per year, plus my own jobs), tasks (My Tasks, Delegated Tasks), comments on documents and jobs, time recorded against jobs (My Time), notifications, a Knowledge area for firm templates and policies, and filing rules for the In Tray. Built for one laptop: assignees are just names; sharing Sawnx across the firm would be a separate privacy and IT decision.
- **FYI look, stage 2 (18 Oct 2026):** an **In Tray** (drop in documents; Sawnx suggests client, cabinet, folder and year without AI; I confirm), **cabinets** (Tax return, Permanent, Correspondence), **document properties** (type, folder, date, status) and **versions** (older copies kept). Next: stage 3, jobs and tasks.
- **Document summaries (18 Oct 2026):** every document gets an automatic summary (what it is, who issued it, the figures it supports) without any AI, plus a description box for my own notes. Both go into the workpaper's Sources tab as evidence.

## Wrong-year documents (19 Oct 2026)
- **New self-check R7**, after the TEST02 trial, where a dividend paid 28 March 2025 went into the FY2026 return with no warning. It raises a Medium note for any document used in the return whose own date is outside 1 July to 30 June, and asks me to confirm which year it belongs to. It cites nothing, because the date alone doesn't settle the treatment.
- **Allowed:** documents dated 30 June (the period end); annual statements (income statement, interest summary, managed fund, health insurance, rental) dated up to 120 days after 30 June, because they're issued after the year ends; the ATO pre-fill report dated any time after 30 June.
- **A pre-fill dated during the year** (before 30 June) is flagged: the year's report normally comes out after 30 June, so it's probably last year's.
- The 120 days and the list of annual statement types are in `config/checks.yaml`, so the firm can change them.

## Six Sawnx additions (25 Oct 2026)
What I decided when Claude asked:
- **Info request wording:** a template filled in from last year's data, not AI. Works for real clients today and nothing leaves the laptop.
- **Info request format:** a Word document filed in the client's Correspondence cabinet (Letters), to edit and attach to an email.
- **No amounts in the request:** names only (who paid what). Less client money detail sitting in an email.
- **Emails with attachments:** the email is one document (its text read) and each attachment is filed and read as its own document.
- **Outlook .msg files:** read them, which needed one small library (`olefile`).
- **Spreadsheet rows with no label:** not added as figures; listed in Things to check. Never guessed.
- **Recent searches:** a client counts when I open them from the search results, or a search finds only them. Opening from the Clients list doesn't count.
- **Order:** Things to check, spreadsheets, emails, progress bar, recent searches, info request.

Claude's calls along the way (worth knowing):
- The client's name is never written into the info request: it says "Dear [client's name]," for me to fill in, because names only live in `clients.json`.
- In Tray still suggests Correspondence for emails (most are just correspondence); to read one, file it in the Tax return with **Read for the return**.
- An email isn't read past a quoted reply or forwarded part. If that part has amounts, Things to check says to look at it, so nothing is counted twice or lost silently.
- Words that suggest something private (gym, fine, personal, holiday...) stop a label being suggested at all.
- Emails and client spreadsheets are allowed dates up to 120 days after 30 June in R7, like annual statements.
- The progress bar sends files one at a time, so nothing has to run in the background. Without its script, Import works the old way.
- Found only by trying it in the browser: the empty progress box showed before any import (a layout rule overrode "hidden"). Fixed with one CSS rule and a test.
- **Sawnx opens in its own Chrome window (25 Oct 2026)**, as I asked: Chrome's app mode (`--app`), no tabs or address bar. Edge's app window if Chrome isn't installed, otherwise the usual browser.
- Design: `docs/specs/2026-10-25-sawnx-six-additions-design.md`; plan: `docs/plans/2026-10-25-sawnx-six-additions.md`.

## After trying the AI reader (25 Oct 2026)
- My test: the AI read 81 figures from 11 documents, but none were in the workpaper, because only **confirmed** figures go in (on purpose). Added **Confirm all** per document (pre-fill rows excepted).
- Rental papers were filed under the wrong type (interest, bank, receipt, dividend) by word-matching. Now **the AI reader also says what the document is**, and its answer wins unless I forced a type, a learned layout read it, or it's an email, client spreadsheet, pre-fill or prior-year return. Things to check says so.
- Why Claude in Excel does better: it sees the pages and is a bigger model; Sawnx's AI reader gets blanked text only. Added **Send page images for scans**: off until the privacy officer approves it separately; only pages with no usable text (scans, or text where under half the words look like words), PDFs only, at most 20 pages, 110 dpi; numbers in pictures aren't blanked; never saved; audited.

## Review fixes before page images go to the privacy officer (25 Oct 2026)
- Switching the AI reader off now switches page images off too (and both need approving again), so pictures can't quietly come back.
- Pictures are small greyscale JPEGs, at most 2000 px and 20 MB per document; pages left out get a Things to check line.
- If the AI or a picture fails, the document is still filed with a note; an import never stops because of the AI. Requests time out after 2 minutes.
- The AI may not label a document an ATO pre-fill, prior-year return or Xero export (they have special checks). Account numbers it copies into a description are blanked.
- Readable bank statements (01JUL25, 1,234.56CR) and accented names aren't mistaken for scans.
- Confirm all confirms only the figures that were on screen; any that arrived since are left for me to check.

## AI reader approved for real clients (25 Oct 2026)
- The privacy officer signed off on Sawnx's **AI reader** for real clients: the blanked-out text of documents the rules can't read goes to Anthropic, and every figure comes back unconfirmed.
- **Not** covered: Claude reading in a chat (`ai-text`) and teaching layouts stay made-up clients (or my own papers) only.
- Set up 25 Oct 2026: AI library installed, API key saved for my Windows account (on my personal Anthropic account for now; expires 24 Nov 2026). A key pasted into a chat was deleted and replaced: keys are never typed into chats or files.

## Teaching Sawnx layouts (25 Oct 2026)
- **Goal:** read as much as possible with Sawnx's own rules, so the AI (later) only handles what's left, and less of it over time.
- **How it starts:** I ask in a Claude chat ("teach Sawnx the new layouts"). No API key, no schedule.
- **Where layouts live:** one small settings file each (`config/layouts/`), read by one shared reader; every layout proved by a made-up copy in the tests. Code only for layouts too odd for a file.
- **Documents already filed:** read again at the end of each teaching session, plus a **Read again** button.
- **My samples (25 Oct 2026):** real papers, used with my OK to learn the layouts only (files and tests hold invented details), then deleted. 3 of 7 now read without AI: ATO income statement, Bupa health statement, NSW school receipts. The tax agent's invoice, the super statement and the two property manager bundles are scans too garbled for rules: they need OCR or the AI.
- **A misread amount is never used:** the Bupa scan showed "$24s" for $245; Sawnx flags it instead of taking $24.
- **File names:** readable, still led by the client code: `TEST01 2026-03-31 Receipt - SAMPLE SHOP.pdf`. New imports and documents read again; older ones keep their names.
- **Scans with a text layer (26 Oct 2026):** a page that is one big picture is a scan even when the scanner typed text over it, so with page images on its picture goes to the AI reader as well as the blanked text. Covered by the page-images approval (it is a scanned page).
- **"Matches the document's text" (26 Oct 2026):** an AI figure is ticked when its amount is also printed in the document's text. It speeds up checking; it never confirms a figure.

Related: [[How it works]], [[Privacy rules]]
