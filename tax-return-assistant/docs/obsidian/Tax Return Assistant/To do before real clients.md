---
tags: [tax, todo]
---

# To do before real clients

Back to [[Tax Return Assistant]]

## Needs a registered tax agent
- [ ] Check every figure in `config/rates/fy2026.yaml` (and `fy2025.yaml`) against ato.gov.au, then set `status: verified`, `verified_by` and `verified_on`.
  - **Check the SAPTO thresholds first.** The file has single 34,919 / 52,759. The reviewer thinks they're still 32,279 / 50,119.
  - Claude couldn't reach the ATO site and used search summaries.
- [ ] Check the citations in `config/citations.yaml` and set `verified: true`.
- [ ] Check the ATO label letters in `config/labels.yaml` (e.g. 10 L, 21 P) and set `letter_verified: true`.

## Needs the firm
- [ ] Privacy officer reads [[Privacy rules]] and the README's privacy section, and signs off.
- [ ] BitLocker on for the laptop drive holding `C:\TaxAssistant`.
- [ ] Move the code to a **private, firm-owned** GitHub repo. `for-claude` is public.
- [ ] Show the supervising agent the demo workpaper.

## Needs testing on a real Windows laptop
- [x] Run `setup.ps1`. Done 17 Oct 2026 on my personal Windows 10 PC with no errors. Two first-run problems were found and fixed (see [[Known issues and ideas]]).
- [x] Run `.\tra demo --auto-confirm`, then `.\tra prepare DEMO01`, and open the workpaper in Excel. Done 17 Oct 2026: payable $5,697.11, and it looked right in Excel.
- [ ] Check `.\tra figures` opens Excel, and saving keeps the file working.
  - Excel opens it, and the tool won't change the file while it's open. Still to check: save it in Excel, close it, then run `.\tra prepare` again.
- [ ] Repeat on a firm laptop. IT may install Python differently, and the firm may lock down PowerShell.

## Optional (later)
- [ ] **Xero:** register the firm's app at developer.xero.com, set `XERO_CLIENT_ID`, confirm the scope names, then try it on a test organisation.
- [ ] **FYI:** get API access from FYI, confirm `config/fyi.yaml`, set the `FYI_*` variables.
- [ ] Send Claude **blank or fake-data** copies of real bank and registry statement layouts, so readers can be added. Never real ones.

Related: [[How to run it]], [[Known issues and ideas]]
