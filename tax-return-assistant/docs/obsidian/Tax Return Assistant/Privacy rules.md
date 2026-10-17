---
tags: [tax, privacy, compliance]
---

# Privacy rules

Back to [[Tax Return Assistant]]

## The non-negotiables (my brief)
- Never store, log or write TFNs, Medicare numbers, driver licence or passport numbers, bank account or BSB numbers, or card numbers. That covers the workpaper, filenames, logs and anything sent to an API.
- Redact them **before** any processing.
- Identify clients only by **client code**, never by name.
- Credentials go in environment variables, never in code.
- Client data stays local and never goes into git. There's an audit log, with no sensitive values in it.
- Comply with the **Privacy Act 1988** (APPs) and the **Tax Agent Services Act 2009 / TPB Code**.
- **Drafts only.** It never lodges. A registered agent signs off every return.

## How the tool enforces them
- **Redaction first:** TFNs are caught by check digit *and* by the word "TFN" nearby, so a typo'd TFN still counts. Medicare and cards are checked by check digit too. The other identifier types are found by format and keyword.
- **Output guard:** every file the tool writes is scanned first. If something looks like an identifier, it refuses and logs `guard_blocked`.
- **Audit log:** who, what and when, by client code and document ID only.
- **No cloud folders:** it refuses to run if client data would be in OneDrive, Dropbox, Google Drive or SharePoint (APP 8).
- **Originals are filed unchanged**, as the firm keeps them now.
- **No AI service gets client data.** An AI reader could be added later, but only on redacted text and only with firm approval.

## Watch out
- If `guard_blocked` ever shows in the audit log, stop and tell the privacy officer (Notifiable Data Breaches scheme).
- The GitHub repo `for-claude` is **public**. That's fine for the code (no client data, and a test checks), but the tool should move to a private, firm-owned repo.
- Turn on BitLocker for the drive that holds `C:\TaxAssistant`.

Related: [[To do before real clients]], [[Decisions log]]
