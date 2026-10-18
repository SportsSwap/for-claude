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
- **Start it:** double-click the **Sawnx** shortcut on the desktop (setup makes it), or `Sawnx.cmd` in the tool folder, or type `.\tra web`. A black window opens and Sawnx opens in the browser. Close the black window to stop it.
- It runs **only on this laptop**. Other computers can't reach it and nothing goes on the internet.
- **Looks like FYI:** a dark top bar (Home, Clients, Documents, Settings), search, and the green **+** for a new client.
- **Home:** My Recent and My Starred documents. **Documents:** everything, sortable and filterable; tick several to star, download or move.
- **Clients:** every client by name and where their job is up to.
- **In Tray:** drop in documents for any client; Sawnx suggests who and where (client, cabinet, folder, year). Check it, then **File**.
- **Jobs:** every client has a tax return job each year; add your own (BAS, advice...) with due dates, tasks, comments and time. **Home** shows My Tasks, Delegated Tasks, My Time and Notifications.
- **Knowledge:** the firm's templates and policies (never client documents). **Settings → Filing rules** teach the In Tray where documents usually go.
- **Cabinets:** each client has *Tax return* (per year), *Permanent* and *Correspondence*, like FYI. Open a document to change its type, folder, date or status, or upload a newer version (older ones are kept).
- **Files:** folders, and **Import**: pick Individual, then for each file **Read for the return** or **Store only**.
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
