---
tags: [project, tax, work]
status: built, not yet used on real clients
started: 2026-10-14
updated: 2026-10-17
---

# Tax Return Assistant

A tool I had Claude build for the firm. You give it a client's documents and it prepares a **draft** Australian individual tax return. It produces an Excel workpaper that shows all the working, plus a list of things to check.

It **never lodges anything.** The return is still done in Xero Tax and signed off by a registered tax agent.

## Where things are
- **Code:** GitHub `SportsSwap/for-claude`, branch `claude/tax-return-assistant-sstpuw`, folder `tax-return-assistant`
- **Client data when it runs:** `C:\TaxAssistant` on the laptop. Never in OneDrive, never in GitHub.
- **Built in:** Claude Code session <https://claude.ai/code/session_01N2pEC5oyPFnAavBcEamEbT>

## Status (17 Oct 2026)
- All six stages built, with 299 automated tests passing
- The demo client works end to end: estimated payable $5,697.11
- **Not ready for real clients yet.** See [[To do before real clients]].

## Notes
- [[How to run it]]: setup on a Windows laptop, and the steps for each client
- [[How it works]]: what happens to a document, what's in the workpaper
- [[Self-checks]]: the review notes it raises and why
- [[Privacy rules]]: the non-negotiables and how the tool enforces them
- [[Decisions log]]: what was decided and why
- [[To do before real clients]]: checklist
- [[Known issues and ideas]]: limitations and things to improve
- [[Tax terms]]: glossary
