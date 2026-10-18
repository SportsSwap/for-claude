import openpyxl
import pytest
from webctx import build_test01, make_client

from tra.privacy.audit import AuditLog
from tra.privacy.guard import SensitiveDataBlocked
from tra.review_store import load_review, mark_reviewed, note_key, responses_by_key, review_path, save_response
from tra.web.services.prepare import load_summary, run_prepare
from tra.web.status import job_status


def _prepared(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    audit = AuditLog(ws.audit_path)
    summary = run_prepare(ws, audit, "tester")
    return client, settings, ws, audit, summary


def _key(summary, check_id):
    return note_key(next(n for n in summary.notes if n.check_id == check_id))


def test_note_key_stable_across_prepares(tmp_path, monkeypatch):
    _client, _settings, ws, audit, first = _prepared(tmp_path, monkeypatch)
    second = run_prepare(ws, audit, "tester")
    assert [note_key(n) for n in first.notes] == [note_key(n) for n in second.notes]
    assert _key(first, "C2").startswith("C2|")


def test_response_carried_into_next_workpaper(tmp_path, monkeypatch):
    _client, _settings, ws, audit, summary = _prepared(tmp_path, monkeypatch)
    save_response(ws, _key(summary, "C2"), "Rates check booked with the registered agent", True, "tester")
    assert responses_by_key(ws) == {_key(summary, "C2"): "Rates check booked with the registered agent"}
    again = run_prepare(ws, audit, "tester")
    sheet = openpyxl.load_workbook(ws.output_dir / again.workpaper)["Review Notes"]
    rows = [r for r in sheet.iter_rows(values_only=True) if r and r[2] and str(r[2]).startswith("C2")]
    assert rows and rows[0][9] == "Rates check booked with the registered agent"


def test_response_with_tfn_refused(tmp_path, monkeypatch, make_tfn):
    _client, _settings, ws, _audit, summary = _prepared(tmp_path, monkeypatch)
    with pytest.raises(SensitiveDataBlocked):
        save_response(ws, _key(summary, "S14"), f"TFN {make_tfn()} checked", False, "tester")
    assert not review_path(ws).exists()


def test_mark_reviewed_needs_high_resolved_and_name(tmp_path, monkeypatch):
    _client, _settings, ws, audit, summary = _prepared(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Resolve every High note first"):
        mark_reviewed(ws, "A Reviewer", summary.workpaper, summary.notes, audit)
    for n in summary.notes:
        if n.risk == "High":
            save_response(ws, note_key(n), "Dealt with", True, "tester")
    with pytest.raises(ValueError, match="reviewer's name"):
        mark_reviewed(ws, "  ", summary.workpaper, summary.notes, audit)
    mark_reviewed(ws, "A Reviewer", summary.workpaper, summary.notes, audit)
    assert load_review(ws).reviewed["by"] == "A Reviewer"
    assert job_status(ws) == "Reviewed"


def test_status_reviewed_then_back_after_new_prepare(tmp_path, monkeypatch):
    _client, _settings, ws, audit, summary = _prepared(tmp_path, monkeypatch)
    for n in summary.notes:
        save_response(ws, note_key(n), "ok", True, "tester")
    mark_reviewed(ws, "A Reviewer", summary.workpaper, summary.notes, audit)
    assert job_status(ws) == "Reviewed"
    run_prepare(ws, audit, "tester")
    assert job_status(ws) == "Prepared"
    assert load_summary(ws).workpaper.endswith("_v2.xlsx")
