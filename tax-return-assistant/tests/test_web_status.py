import os

from checkctx import doc, fig

from tra.clients import create_client
from tra.figures import write_figures
from tra.filing.index import DocumentIndex
from tra.privacy.audit import AuditLog
from tra.web.status import STATUSES, job_status, latest_workpaper


def _client(tmp_path, code="TEST01"):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return create_client(home, code, 2026, {}, AuditLog(home / "audit" / "audit.jsonl"))


def _workpaper(ws, n=1, when=None):
    path = ws.output_dir / f"{ws.client_code}_FY2026_Workpaper_DRAFT_v{n}.xlsx"
    path.write_bytes(b"x")
    if when is not None:
        os.utime(path, (when, when))
    return path


def _age(path, when):
    os.utime(path, (when, when))


def test_statuses_in_order():
    assert STATUSES == ("New", "Docs in", "Figures confirmed", "Prepared", "Reviewed")


def test_new(tmp_path):
    assert job_status(_client(tmp_path)) == "New"


def test_docs_in_when_unconfirmed(tmp_path):
    ws = _client(tmp_path)
    DocumentIndex(ws.index_csv).append(doc("D001"))
    assert job_status(ws) == "Docs in"  # nothing confirmed yet
    write_figures(ws.figures_csv, [fig("F0001", "income.salary", 100), fig("F0002", "income.interest", 5, confirmed=False)])
    assert job_status(ws) == "Docs in"


def test_prefill_rows_do_not_block_confirmed(tmp_path):
    ws = _client(tmp_path)
    DocumentIndex(ws.index_csv).append(doc("D001"))
    write_figures(ws.figures_csv, [fig("F0001", "income.salary", 100),
                                   fig("F0002", "income.salary", 100, confirmed=False, notes="prefill")])
    assert job_status(ws) == "Figures confirmed"


def test_figures_confirmed(tmp_path):
    ws = _client(tmp_path)
    DocumentIndex(ws.index_csv).append(doc("D001"))
    write_figures(ws.figures_csv, [fig("F0001", "income.salary", 100)])
    assert job_status(ws) == "Figures confirmed"
    assert latest_workpaper(ws) is None


def test_prepared_when_workpaper_newer(tmp_path):
    ws = _client(tmp_path)
    DocumentIndex(ws.index_csv).append(doc("D001"))
    write_figures(ws.figures_csv, [fig("F0001", "income.salary", 100)])
    for p in (ws.figures_csv, ws.state_json, ws.cgt_csv):
        _age(p, 1_700_000_000)
    _workpaper(ws, 1, 1_700_000_100)
    newest = _workpaper(ws, 2, 1_700_000_200)
    assert latest_workpaper(ws) == newest
    assert job_status(ws) == "Prepared"


def test_latest_workpaper_by_version_not_name(tmp_path):
    ws = _client(tmp_path)
    _workpaper(ws, 9)
    ten = _workpaper(ws, 10)
    assert latest_workpaper(ws) == ten


def test_back_to_confirmed_after_figure_change(tmp_path):
    ws = _client(tmp_path)
    DocumentIndex(ws.index_csv).append(doc("D001"))
    write_figures(ws.figures_csv, [fig("F0001", "income.salary", 100)])
    for p in (ws.figures_csv, ws.state_json, ws.cgt_csv):
        _age(p, 1_700_000_000)
    _workpaper(ws, 1, 1_700_000_100)
    assert job_status(ws) == "Prepared"
    _age(ws.figures_csv, 1_700_000_500)
    assert job_status(ws) == "Figures confirmed"
