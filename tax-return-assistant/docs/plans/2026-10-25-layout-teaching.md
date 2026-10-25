# Teaching Sawnx new layouts: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Layout files read by one shared reader, Read again, and the commands and skill for a chat-driven teaching cycle.
**Architecture:** `ingest/layouts.py` (load, match, read) runs before the classifier inside `ingest_file`;
`reread.py` re-runs the same read on a filed document; CLI and a Sawnx page expose the queue.
**Spec:** `docs/specs/2026-10-25-layout-teaching-design.md`

## Global Constraints
- Claude only sees blanked text (`tra ai-text`, `tra layouts try`); made-up clients only. Never open originals.
- Every write through the guard. Client codes only. Figures unconfirmed. Never guess a label.
- Confirmed and manual figures are never changed by Read again.
- Do not commit. Windows: `.venv\Scripts\python -m pytest`.

## Review Focus
1. A broken layout file must never stop an import or a page.
2. Read again must not duplicate figures, and must keep confirmed/typed ones.
3. A layout file or made-up copy must not hold a client name or identifier (hygiene test covers identifiers).

### Task 1: Layout engine — `src/tra/ingest/layouts.py`, `tests/test_layouts.py`
Produces `Layout`, `load_layouts(path=None) -> tuple[list[Layout], list[str]]`, `match_layout(rt, layouts)`,
`read_with_layout(rt, layout, doc_id) -> ExtractResult`. Tests: match all/any and most-specific wins; line vs
contains; first/last amount; every; required -> doubt "Didn't find the <description>."; bad files reported and
skipped (unknown doc type, unknown label, neither line nor contains, YAML error); no layouts dir -> empty.

### Task 2: Pipeline + shared read — `pipeline.py`
Produces `read_document(loaded, doc_types, doc_id, override_type=None, ai_reader=None) -> tuple[str, ExtractResult,
str | None]` (doc type, result, layout slug). Tests: a matching layout sets the type and figures; forced type wins;
no match -> unchanged behaviour; reading notes record the layout.

### Task 3: Layout proofs — `tests/test_layout_samples.py`, `tests/layout_samples/`
Every `config/layouts/*.yaml` has `tests/layout_samples/<slug>.yaml` and reads it to exactly its `figures`.

### Task 4: Read again — `src/tra/reread.py`, `cli.py` (`tra reread`), `tests/test_reread.py`
Tests: replaces unconfirmed parser figures; keeps confirmed and manual; ai replaced only when new figures; index
status/type updated, folder unchanged; reading notes replaced keeping from_email; I1 dropped; prefill/stored/FYI
refused with a plain message; audit `document_reread`; `--waiting` does all manual/partial documents.

### Task 5: Teaching commands — `cli.py` (`tra layouts todo`, `tra layouts try`), tests in `tests/test_layouts_cli.py`
todo lists waiting documents (no text) and layout problems; try prints labels/amounts/pages/missing fields and
writes nothing but the audit line.

### Task 6: Sawnx — Layouts page and Read again button; `tests/test_web_layouts.py`
`GET /layouts` (linked from Settings): learned layouts with counts, problems, waiting documents with links.
`POST /c/<code>/<fy>/doc/<doc_id>/reread` -> flash result, back to the document.

### Task 7: The skill and docs
`.claude/skills/teach-layouts/SKILL.md`, CLAUDE.md pointer, README how-to, Obsidian notes (both copies), test count.

### Task 8: First teaching session
Teach the owner's made-up samples (scratch TRA_HOME, TEST01), re-read them, full suite, final review, report.
