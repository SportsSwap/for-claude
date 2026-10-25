---
name: teach-layouts
description: Use when the owner says "teach Sawnx the new layouts" (or asks to make Sawnx read documents it couldn't, add a reader for a bank/registry/receipt layout, or "learn" from unread documents). Writes a layout file and a made-up copy for each new layout so Sawnx reads it with its own rules, without the AI, then reads the waiting documents again.
---

# Teaching Sawnx new layouts

Every layout Sawnx learns is a document it reads for free, with no AI. Work through what's waiting, one layout at a
time, and prove each with a made-up copy. Design: `docs/specs/2026-10-25-layout-teaching-design.md`.

## Rules that are not negotiable

- **Only blanked-out text.** Read documents with `.\tra ai-text CODE --fy YEAR --doc D00N`. Never open the original
  file, the PDF, or anything under TRA_HOME\Clients.
- **Made-up clients only** until the privacy officer approves real ones (CLAUDE.md). If a document looks real, stop and
  ask the owner.
- **Layout files and made-up copies hold only the issuer's wording.** Never a client's name, address, or any number
  from the document (not even blanked markers like `[ACCOUNT REDACTED]`). Invent every name and amount in the copy:
  SAMPLE BANK, 123.45.
- **Never guess a return item.** If it's unclear which label a line belongs to (e.g. "interest" on a loan statement,
  "insurance" on a bank statement), leave it out of the layout and tell the owner; Things to check will show it.
- **Never add up amounts.** Use a total line the document prints, or `every: true` for one figure per line.
- Nothing is committed without the owner's OK.

## Steps

Run commands from the tool folder. If the samples live in another TRA_HOME, set `$env:TRA_HOME` for these commands.

1. **See what's waiting:** `.\tra layouts todo` (no text shown). It also lists layout files with mistakes: fix those first.
2. **Group by layout.** For each waiting document, read its blanked text with `.\tra ai-text`. Documents from the
   same issuer with the same wording are one layout: teach it once.
3. **Check the old readers first.** If an existing reader (`src/tra/ingest/extractors/`) nearly fits, a layout file is
   still the default; only change code when a layout can't be described by `line`/`contains` fields (e.g. a table
   whose columns move). Scanned pages (no text) can't be taught: say so.
4. **Write `config/layouts/<slug>.yaml`** (slug: issuer and kind, e.g. `cba-interest-summary`):

   ```yaml
   name: Commonwealth Bank interest summary
   doc_type: INTSTMT                # a type in config/doc_types.yaml
   match:
     all: ["commonwealth bank", "interest summary"]   # words every copy of this layout has; issuer wording only
     any: []                        # optional: at least one of these
   issuer: Commonwealth Bank        # starts each figure's description
   fields:
     - label: income.interest       # a figure label from config/labels.yaml (not info or computed ones)
       line: "Total interest earned"   # the line starts with these words; or contains: "words anywhere"
       amount: last                 # first or last amount after those words
       description: interest
       required: true               # missing -> Things to check says so
   added: "Claude, <date>, from a made-up sample"
   ```

   Make `match` specific enough that it can't catch other documents (two or three distinctive phrases).

   More field options:
   - `amount: 2` — the 2nd amount written with a `$` on the line (a table row); add `amounts: 2` to say how many
     amounts every row has, so a row where the scan lost a `$` is flagged instead of read one column off.
   - `dollars: true` — only amounts written with `$` count (default when `amount` is a number).
   - `also: ["30", "35"]` — one of these whole words must also be on the line (e.g. a benefit code).
   - `every: true` — one figure per matching line. Use it whenever a document can repeat the line (two employers,
     two rows for one period); without it, a second matching line only raises a doubt.
   - `suggested: true` — the label is only a suggestion (receipts): Things to check asks for a look.
   - `unread: true` (no label) — a line the layout doesn't read; a non-zero amount on it goes to Things to check
     (e.g. lump sums, allowances).
   Match words must be at least 4 characters and are whole words; `line` must start the line and end at a word.
   A misread amount ("$24s", "s1500", "$1,2O4.50") is never used: it becomes a doubt.
   **Numbers in made-up copies:** use short ones like 12345. Long runs of one digit repeated can pass the TFN check.
5. **Write the made-up copy `tests/layout_samples/<slug>.yaml`:** the same lines in the same order with invented
   names and numbers, `---page---` between pages if the layout spans pages, and the figures it must read:

   ```yaml
   text: |
     Commonwealth Bank
     Interest summary for 1 July 2025 to 30 June 2026
     Total interest earned $123.45
   figures:
     - {label: income.interest, amount: "123.45"}
   doubts: []
   ```

6. **Prove it:** `.venv\Scripts\python -m pytest tests/test_layout_samples.py -q` (every layout must read its copy, and
   only its copy).
7. **Try it on the real document:** `.\tra layouts try config\layouts\<slug>.yaml CODE D00N --fy YEAR`. It writes
   nothing. If it reads the wrong amount, fix the field, the copy, and step 6.
8. **Read the waiting documents again:** `.\tra reread CODE --waiting --fy YEAR` (confirmed and typed-in figures are
   never changed).
9. **Run everything:** the full suite in the background (`.venv\Scripts\python -m pytest`) and
   `.venv\Scripts\python -m pyflakes src tests`.
10. **Report to the owner, in plain words:** each new layout (what it recognises, which amounts it reads), what each
    document gave after reading again, anything left out and why (unclear item, scanned pages, odd table), and that
    every figure still needs confirming on the Figures tab. Then update the Obsidian notes (Known issues and ideas:
    layouts learned) in both copies.
