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
   - It has never been run on a real Windows machine. If it errors, give the message to Claude.

## Each time
- Open PowerShell in the folder, then run `.\.venv\Scripts\Activate.ps1`.
- If scripts are blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- `tra doctor` checks the setup.

## Try the fake client first
```
tra demo --auto-confirm
tra prepare DEMO01
```
Open `C:\TaxAssistant\Work\DEMO01\FY2026\Output\DEMO01_FY2026_Workpaper_DRAFT_v1.xlsx`.

## A real client (only after [[To do before real clients]])
| Step | Command | What happens |
|---|---|---|
| 1 | `tra new SMIT01` | Sets up the client, by client code (never a name). Options: `--help-debt`, `--hospital-days 365`, `--non-resident`, `--sapto single`, `--spouse`, `--dependants 2` |
| 2 | `tra ingest SMIT01 C:\Inbox\SMIT01` | Reads the PDFs, removes identifiers, files them, extracts figures |
| 3 | `tra figures SMIT01` | Opens the figures in **Excel**: check each against its document, mark `confirmed` = Y, save, close |
| 4 | `tra prepare SMIT01` | Writes the workpaper to `...\Work\SMIT01\FY2026\Output` |
| 5 | Excel and Xero Tax | Work through Review Notes, key it into Xero Tax, and the agent signs the Cover tab |

Tips:
- Leave rows marked `prefill` **unconfirmed** when a real document backs the same figure. Otherwise it's counted twice.
- Capital gains go in `cgt_events.csv`. Last year's figures go in `prior_year.csv`.

Related: [[How it works]], [[Self-checks]]
