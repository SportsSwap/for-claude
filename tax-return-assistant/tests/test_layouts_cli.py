"""The teaching commands: `tra layouts todo` (what's waiting) and `tra layouts try` (a dry run). Made-up data."""

import pytest
from click.testing import CliRunner

from tra.cli import main
from tra.demo import _write_pdf
from tra.filing.local_store import LocalStore
from tra.ingest.classify import load_doc_types
from tra.ingest.pipeline import ingest_file
from tra.privacy.audit import AuditLog

from webctx import new_client

LAYOUT = """
name: SAMPLE BANK interest summary
doc_type: INTSTMT
match:
  all: ["sample bank", "yearly interest"]
issuer: SAMPLE BANK
fields:
  - label: income.interest
    line: "Interest paid this financial year"
    description: interest
    required: true
  - label: income.interest_tfn_withheld
    line: "TFN withholding"
    description: TFN withheld
    required: true
"""


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from tra.settings import Settings

    monkeypatch.setenv("TRA_HOME", str(tmp_path / "home"))
    monkeypatch.setattr("tra.ingest.layouts.LAYOUTS_DIR", tmp_path / "layouts")
    ws = new_client(Settings.from_env())
    path = tmp_path / "a.pdf"
    _write_pdf(path, ["SAMPLE BANK", "Yearly interest", "Interest paid this financial year 321.00"])
    doc = ingest_file(path, ws, LocalStore(ws.tra_home), load_doc_types(), AuditLog(ws.audit_path)).doc
    return ws, doc, tmp_path


def _run(ws, *args):
    return CliRunner().invoke(main, list(args), env={"TRA_HOME": str(ws.tra_home), "TRA_STORE": "local"})


def test_todo_lists_waiting_documents_without_text(setup):
    ws, doc, tmp_path = setup
    (tmp_path / "layouts").mkdir()
    (tmp_path / "layouts" / "broken.yaml").write_text("name: [unclosed", encoding="utf-8")
    result = _run(ws, "layouts", "todo")
    assert result.exit_code == 0, result.output
    assert f"TEST01 FY2026 {doc.doc_id}" in result.output and "manual_needed" in result.output
    assert "broken.yaml" in result.output
    assert "Interest paid" not in result.output and "SAMPLE BANK" not in result.output


def test_todo_shows_learned_layouts(setup):
    ws, _doc, tmp_path = setup
    (tmp_path / "layouts").mkdir()
    (tmp_path / "layouts" / "sample-bank-yearly.yaml").write_text(LAYOUT, encoding="utf-8")
    assert "sample-bank-yearly" in _run(ws, "layouts", "todo").output


def test_try_is_a_dry_run(setup):
    ws, doc, tmp_path = setup
    layout = tmp_path / "candidate.yaml"
    layout.write_text(LAYOUT, encoding="utf-8")
    before = ws.figures_csv.read_text(encoding="utf-8")
    result = _run(ws, "layouts", "try", str(layout), "TEST01", doc.doc_id)
    assert result.exit_code == 0, result.output
    assert "Recognised: yes" in result.output
    assert "income.interest $321.00 (page 1) SAMPLE BANK – interest" in result.output
    assert "Didn't find the TFN withheld." in result.output
    assert ws.figures_csv.read_text(encoding="utf-8") == before
    assert '"layout_tried"' in ws.audit_path.read_text(encoding="utf-8")


def test_try_reports_a_mistake_in_the_file(setup):
    ws, doc, tmp_path = setup
    layout = tmp_path / "bad.yaml"
    layout.write_text(LAYOUT.replace("doc_type: INTSTMT", "doc_type: NOPE"), encoding="utf-8")
    result = _run(ws, "layouts", "try", str(layout), "TEST01", doc.doc_id)
    assert result.exit_code == 1 and "doc_type NOPE" in result.output


def test_reread_says_when_a_file_kept_its_name(setup, monkeypatch):
    from pathlib import Path

    ws, doc, tmp_path = setup
    (tmp_path / "layouts").mkdir()
    (tmp_path / "layouts" / "sample-bank-yearly.yaml").write_text(LAYOUT, encoding="utf-8")

    def locked(self, target):
        raise PermissionError(32, "in use")

    monkeypatch.setattr(Path, "rename", locked)
    result = _run(ws, "reread", "TEST01", doc.doc_id)
    assert result.exit_code == 0 and "keeps its old name" in result.output
