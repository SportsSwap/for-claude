import csv
import json

import pytest
from click.testing import CliRunner

from tra.cli import main
from tra.demo import build_demo_documents
from tra.privacy.redact import RedactionError
from tra.workspace import Workspace


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


@pytest.fixture
def run(home):
    runner = CliRunner()

    def invoke(*args):
        return runner.invoke(main, list(args), env={"TRA_HOME": str(home), "TRA_STORE": "local"},
                             catch_exceptions=False)

    return invoke


def _figure_rows(home, code="SMIT01"):
    path = Workspace(home, code, 2026).figures_csv
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _index_rows(home, code="SMIT01"):
    path = Workspace(home, code, 2026).index_csv
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_new_creates_workspace(run, home):
    result = run("new", "SMIT01", "--fy", "2026", "--help-debt")
    assert result.exit_code == 0, result.output
    ws = Workspace(home, "SMIT01", 2026)
    assert ws.load_state().help_debt is True
    assert ws.figures_csv.read_text(encoding="utf-8").startswith("figure_id,label_key")
    assert run("new", "SMIT01").exit_code == 1


def test_new_rejects_names(run):
    result = run("new", "Smith John")
    assert result.exit_code == 1
    assert "client code" in result.output.lower()


def test_ingest_requires_new(run, tmp_path):
    demo = build_demo_documents(tmp_path / "inbox")
    result = run("ingest", "SMIT01", str(demo.paths["prefill"]))
    assert result.exit_code == 1 and "tra new" in result.output


def test_ingest_demo_documents(run, home, tmp_path):
    demo = build_demo_documents(tmp_path / "inbox")
    run("new", "SMIT01")
    result = run("ingest", "SMIT01", *map(str, demo.paths.values()))
    assert result.exit_code == 0, result.output
    assert len(_index_rows(home)) == 8
    labels = {r["label_key"] for r in _figure_rows(home)}
    assert set(demo.expected) <= labels
    assert "redacted: TFN×1" in result.output
    audit = (home / "audit").glob("*.jsonl")
    actions = [json.loads(line)["action"] for f in audit for line in f.read_text().splitlines()]
    assert actions.count("document_ingested") == 8


def test_ingest_same_file_twice(run, home, tmp_path):
    demo = build_demo_documents(tmp_path / "inbox")
    run("new", "SMIT01")
    run("ingest", "SMIT01", str(demo.paths["dividend_bhp"]))
    before = (len(_index_rows(home)), len(_figure_rows(home)))
    result = run("ingest", "SMIT01", str(demo.paths["dividend_bhp"]))
    assert result.exit_code == 0
    assert "duplicate" in result.output.lower()
    assert (len(_index_rows(home)), len(_figure_rows(home))) == before


def test_ingest_redaction_failure_continues(run, home, tmp_path, monkeypatch):
    demo = build_demo_documents(tmp_path / "inbox")
    run("new", "SMIT01")
    import tra.ingest.readers as readers
    real = readers.redact_pages
    calls = {"n": 0}

    def flaky(pages):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RedactionError("redaction failed (ValueError)")
        return real(pages)

    monkeypatch.setattr(readers, "redact_pages", flaky)
    paths = [demo.paths["prefill"], demo.paths["income_statement"], demo.paths["dividend_bhp"]]
    result = run("ingest", "SMIT01", *map(str, paths))
    assert result.exit_code == 1
    assert len(_index_rows(home)) == 2
    audit_text = "".join(f.read_text() for f in (home / "audit").glob("*.jsonl"))
    assert "redaction_failed" in audit_text


def test_scan_reports_type_not_value(run, tmp_path, make_tfn):
    tfn = make_tfn()
    target = tmp_path / "notes.txt"
    target.write_text(f"line one\nclient tfn {tfn}\n", encoding="utf-8")
    result = run("scan", str(target))
    assert result.exit_code == 1
    assert "TFN" in result.output and ":2" in result.output
    assert tfn not in result.output
    clean = tmp_path / "clean.txt"
    clean.write_text("nothing here 412.35\n", encoding="utf-8")
    assert run("scan", str(clean)).exit_code == 0


def test_doctor_flags_unverified_rates(run):
    result = run("doctor")
    assert "FY2026" in result.output and "status: unverified" in result.output
    assert "XERO_CLIENT_ID" in result.output


def test_refuses_bad_tra_home(tmp_path):
    home = tmp_path / "OneDrive - Firm" / "Tax"
    home.mkdir(parents=True)
    result = CliRunner().invoke(main, ["new", "SMIT01"], env={"TRA_HOME": str(home)})
    assert result.exit_code == 1
    assert "cloud-synced" in result.output


def test_unhandled_area_note(run, home, make_pdf):
    path = make_pdf("ess.pdf", [["Income statement", "Gross payments 50,000.00", "Total tax withheld 9,000.00",
                                 "Employee share scheme discount 2,000.00"]])
    run("new", "SMIT01")
    assert run("ingest", "SMIT01", str(path)).exit_code == 0
    notes = json.loads(Workspace(home, "SMIT01", 2026).ingest_notes_json.read_text())
    assert any(n["check_id"] == "I6" and n["risk"] == "High" for n in notes)


def test_demo_auto_confirm(run, home):
    result = run("demo", "--auto-confirm")
    assert result.exit_code == 0, result.output
    rows = _figure_rows(home, "DEMO01")
    assert rows
    assert all(r["confirmed"] == ("N" if r["notes"] == "prefill" else "Y") for r in rows)
    assert "tra prepare DEMO01" in result.output
