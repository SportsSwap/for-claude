---
tags: [tax, how-to]
---

# How to run it

Back to [[Tax Return Assistant]]

It doesn't run inside Excel. It's a small program run from **PowerShell** (the blue Windows command window). It creates Excel files, and the checking happens in those.

## One-time setup (about 15 minutes)
1. **Install Python** from python.org/downloads. Tick **"Add python.exe to PATH"**. A work laptop may need IT.
2. **Download the code.**
   - On GitHub, switch the branch to `claude/tax-return-assistant-sstpuw`.
   - Click **Code → Download ZIP** and unzip it to `C:\Tools`.
   - Use the `tax-return-assistant` folder inside.
3. **Open PowerShell in that folder.** In File Explorer, click the address bar, type `powershell` and press Enter.
4. **Run the setup:** `powershell -ExecutionPolicy Bypass -File .\setup.ps1`. Accept `C:\TaxAssistant` for client data.
   - It worked on a Windows 10 PC on 17 Oct 2026. If it errors, give the message to Claude.

## Each time
- Open PowerShell in the folder and start each command with `.\tra`, for example `.\tra doctor`.
- Nothing to activate and no Windows settings to change. It works even in the window you ran setup in.
- `.\tra doctor` checks the setup.

## Sawnx: click instead of typing (built 18 Oct 2026)
- **Start it:** double-click the **Sawnx** shortcut on the desktop (setup makes it), or `Sawnx.cmd` in the tool folder, or type `.\tra web`. A black window opens and Sawnx opens in **its own Chrome window** (no tabs or address bar, like an app; Edge if there's no Chrome). Close the black window to stop it.
- **Bookmarks don't work:** each start makes a new secret key, so always start from the shortcut. `.	ra web --no-open` prints the address to paste into any browser instead.
- It runs **only on this laptop**. Other computers can't reach it and nothing goes on the internet.
- **Looks like FYI:** a dark top bar (Home, Clients, Documents, Settings), search, and the green **+** for a new client.
- **Home:** My Recent and My Starred documents. **Documents:** everything, sortable and filterable; tick several to star, download or move.
- **Clients:** every client by name and where their job is up to.
- **In Tray:** drop in documents for any client; Sawnx suggests who and where (client, cabinet, folder, year). Check it, then **File**.
- **Jobs:** every client has a tax return job each year; add your own (BAS, advice...) with due dates, tasks, comments and time. **Home** shows My Tasks, Delegated Tasks, My Time and Notifications.
- **Knowledge:** the firm's templates and policies (never client documents). **Settings → Filing rules** teach the In Tray where documents usually go.
- **Claude reads documents the rules can't:** import as usual, then in a Claude chat say "read TEST04's documents". Claude runs `.\tra ai-text TEST04` (sees only the blanked-out text) and `.\tra ai-add` (adds figures **unconfirmed**, marked "Claude:"). Check each on the Figures tab. Made-up clients only for now.
- **Delete:** open a document and click **Delete** (or tick several and click Delete). It goes to **Deleted items** at the bottom of the folder list, and its figures come out of the return. **Restore** puts it back; **Delete forever** is only for mistakes (duplicates, wrong client). Prepare again afterwards.
- **Cabinets:** each client has *Tax return* (per year), *Permanent* and *Correspondence*, like FYI. Open a document to change its type, folder, date or status, or upload a newer version (older ones are kept).
- **Files:** folders, and **Import**: pick Individual, then for each file **Read for the return** or **Store only**.
- **Emails (25 Oct 2026):** in Outlook drag the email onto the desktop (makes a `.msg`), then Import it with **Read for the return**. The email and each attachment become documents; lines like "Donations: $500" become unconfirmed figures with a suggested label. In the **In Tray** an email is suggested for Correspondence; choose *Tax return* and **Read for the return** to have it read.
  - **Once, on a laptop set up before 25 Oct 2026:** close Sawnx, then in PowerShell in the tool folder run `.\.venv\Scripts\pip install -e .` (adds `olefile`, needed for `.msg`). `.eml` works without it.
- **Client spreadsheets:** Import the `.xlsx` or `.csv` the same way. Rows with words Sawnx knows become figures with a suggested label; anything else is listed in Things to check.
- **Progress bar:** importing several files shows "Reading 3 of 8 · about 1 min left", then "Done". Click **Show the documents** afterwards.
- **Things to check:** open a document: the yellow box above **Open** lists what to look at before downloading it or confirming its figures. The Figures tab shows a line under each figure that needs a look.
- **Recent searches:** click in the search box at the top to see the last 5 clients I found by search.
- **Teach Sawnx new layouts:** anything not read is on **Settings → Layouts**. In a Claude chat say "teach Sawnx the new layouts"; Claude writes and proves a layout for each, reads them again, and tells me what it learned. Check the figures as usual.
- **Read again:** button on a document (or `.\tra reread SMIT01 --waiting`) after Sawnx has learned something new.
- **Make info request:** on the client's Files tab, click **Make info request**. It files a Word checklist in Correspondence > Letters and opens it; click **Open**, type the client's name in Word, and send it.
- **Figures:** tick Confirmed (and Substantiated for deductions) beside the source document. It saves straight away.
- **Prepare:** one button; shows the refund or payable and both calculations; download the workpaper.
- **Review notes:** a response and a Resolved tick for each note, then **Mark reviewed**.
- **Notes:** my file notes, plus an Activity list of everything done.
- The commands still work, and anything done one way shows up in the other.

## Try the fake client first
```
.\tra demo --auto-confirm
.\tra prepare DEMO01
```
Open `C:\TaxAssistant\Work\DEMO01\FY2026\Output\DEMO01_FY2026_Workpaper_DRAFT_v1.xlsx`.

## A real client (only after [[To do before real clients]])
| Step | Command | What happens |
|---|---|---|
| 1 | `.\tra new SMIT01` | Sets up the client, by client code (never a name). Options: `--help-debt`, `--hospital-days 365`, `--non-resident`, `--sapto single`, `--spouse`, `--dependants 2` |
| 2 | `.\tra ingest SMIT01 C:\Inbox\SMIT01` | Reads the PDFs, removes identifiers, files them, extracts figures |
| 3 | `.\tra figures SMIT01` | Opens the figures in **Excel**: check each against its document, mark `confirmed` = Y, save, close |
| 4 | `.\tra prepare SMIT01` | Writes the workpaper to `...\Work\SMIT01\FY2026\Output` |
| 5 | Excel and Xero Tax | Work through Review Notes, key it into Xero Tax, and the agent signs the Cover tab |

Tips:
- Leave rows marked `prefill` **unconfirmed** when a real document backs the same figure. Otherwise it's counted twice.
- Capital gains go in `cgt_events.csv`. Last year's figures go in `prior_year.csv`.

Related: [[How it works]], [[Self-checks]]
