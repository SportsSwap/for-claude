# Teaching Sawnx new layouts (design)

Date: 25 Oct 2026. Status: agreed with the owner in chat. Builds on `2026-10-25-sawnx-six-additions-design.md`.

## Why

The built-in readers are rules written for the demo layouts, so most real documents come in as "manual entry"
(the owner's 7 sample PDFs: 6 unread). The owner wants Sawnx to read as much as possible with its own rules, with no
AI and no cost, so that the AI (added later) only handles what's left, and less of it over time.

## Decisions (owner, 25 Oct 2026)

| Question | Decision |
|---|---|
| How the cycle starts | The owner asks in a Claude chat ("teach Sawnx the new layouts"). No API key, no schedule. |
| Where a learned layout lives | One settings file per layout, read by one shared reader. Code only for layouts too odd for a file. |
| Documents already filed | Re-read at the end of each teaching session, plus a **Read again** button on any document. |

## 1. Layout files

`config/layouts/<slug>.yaml`, one per layout:

```yaml
name: SAMPLE BANK interest summary
doc_type: INTSTMT                    # must be in config/doc_types.yaml; its category is the folder
match:                               # on the blanked text, any case
  all: ["sample bank", "interest summary"]
  any: []                            # optional: at least one of these
issuer: SAMPLE BANK                  # the start of every figure's description
fields:
  - label: income.interest           # a label a figure may have (labels.yaml)
    line: "Interest paid this financial year"   # the line starts with these words (spaces and case ignored)
    amount: last                     # first | last amount on that line (default last)
    description: interest
    required: true                   # missing -> a Things to check doubt
  - label: income.interest
    line: "Interest"
    every: true                      # one figure per matching line (never added up)
added: "Claude, 25 Oct 2026, from a made-up sample"
```

- `line` matches the start of a line; `contains` (instead of `line`) matches anywhere in it. Exactly one of the two.
- Never a client's name, address or identifier: only the issuer's own wording.
- A field is never guessed: a line whose return item is unclear isn't put in the file; Things to check lists it.

`src/tra/ingest/layouts.py`: `load_layouts(dir=None) -> (list[Layout], list[str] problems)`. A file with a mistake
(unknown doc type or label, no `line`/`contains`, bad YAML) is skipped and reported, never crashes an import.
`match_layout(rt, layouts)` picks the matching layout with the most `match` words (ties by name).
`read_with_layout(rt, layout, doc_id) -> ExtractResult`: unconfirmed figures, method `parser`, description
`"<issuer> – <description>"`, page of the line; `doubts` for each required field not found;
`parse_status` parsed / partial / manual_needed like the other readers.

## 2. Where it runs

`ingest_file` (and so `tra ingest`, Sawnx Import, In Tray filing, email attachments): with no forced type, a matching
layout comes first and sets the document type; otherwise the existing classifier and readers run unchanged. The
reading-notes entry records `"layout": "<slug>"` so the Layouts page can count what each layout read.

## 3. Read again

`src/tra/reread.py`: `reread_document(ws, doc_id, audit) -> RereadResult(added, removed, status)`.
- Loads the filed original (local store only), redacts, and reads it the same way as an import (shared helper
  `read_document(loaded, doc_types, doc_id, override_type)` taken out of `ingest_file`).
- Figures from that document that are **confirmed**, or typed in (`manual`), are never touched. Unconfirmed `parser`
  figures are replaced. Unconfirmed `ai` figures are replaced only when the new read finds figures.
- The index gets the new parse status (and the new type if a layout recognised it; the folder stays). Its reading
  notes are replaced (keeping `from_email`); its I1 note is dropped when it no longer needs manual entry.
- Pre-fill reports aren't re-read (their lines would double); stored-only and FYI documents can't be.
- Audited as `document_reread` with counts. `.\tra reread CODE D007`, `.\tra reread CODE --waiting` (every
  manual-entry or partly-read document), and a **Read again** button on the document panel.

## 4. The teaching cycle

- **Not read yet:** `.\tra layouts todo [CODE]` and Sawnx *Settings → Layouts* list documents that are
  `manual_needed` or `partial` (client code, year, document number, type, pages; no text), plus every learned layout
  with how many documents it has read, and any layout file with a mistake.
- **Dry run:** `.\tra layouts try config\layouts\x.yaml CODE D007` shows what a layout would read from that
  document's blanked text (labels, amounts, pages, missing required fields). Writes nothing; audited like ai-text.
- **Proof:** every layout file has a made-up copy at `tests/layout_samples/<slug>.yaml` (`text:` with invented
  names and numbers in the same wording and order, `figures:` the expected label and amount). One test reads every
  layout against its copy; a layout without a copy fails. The repo hygiene test scans the copies.
- **The steps Claude follows** are written once in a project skill (`.claude/skills/teach-layouts/SKILL.md`) and
  pointed to from CLAUDE.md: todo → ai-text one document per layout → layout file → made-up copy → try → re-read the
  waiting documents → full suite → show the owner every new layout and what it read. Nothing is committed without
  the owner's OK.

## File names (owner, 25 Oct 2026)

New imports, cabinet documents and documents read again are named `CODE YYYY-MM-DD Kind - Issuer.ext`
(`filing/naming.py`; the kind is `short` in `config/doc_types.yaml`). The issuer comes from what was read; it's
dropped when unknown, when it's the client's own name (clients.json), or when it holds a blanked marker, and digits
and characters Windows refuses are removed. Names stay led by the client code (a project rule) and pass the guard.
Documents filed before keep their names until they're read again.

## Privacy

Same as `tra ai-text`: Claude sees only blanked-out text, scanned again first; made-up clients only until the privacy
officer approves real ones. The todo list and Layouts page show no document text. Layout files and copies hold the
issuer's wording only.

## Not in scope

OCR for scanned pages, tables whose columns move between documents (code, or the AI), learning without Claude (the
AI reader), a schedule.

## Testing

Test-first: the engine (matching, first/last amount, every, required, bad files), pipeline order (layout before the
classifier, forced type still wins), Read again (confirmed and typed figures kept, replaced counts, notes, audit),
the CLI commands, the Layouts page and button. All data made up at runtime or in the made-up copies.
