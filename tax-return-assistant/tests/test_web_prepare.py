from decimal import Decimal

from webctx import build_test01, make_client

from tra.privacy.audit import AuditLog
from tra.run import prepare_client
from tra.web.services.prepare import load_summary, workpapers


def _prepared(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    resp = client.post("/c/TEST01/2026/prepare")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/c/TEST01/2026/prepare")
    return client, settings, ws


def test_test01_refund_matches_cli(tmp_path, monkeypatch):
    client, settings, ws = _prepared(tmp_path, monkeypatch)
    summary = load_summary(ws)
    assert summary.net == Decimal("-993.25")
    page = client.get("/c/TEST01/2026/prepare").get_data(as_text=True)
    assert "Estimated refund" in page and "$993.25" in page and "Nothing has been lodged" in page
    twin = build_test01(settings, "TEST02")
    cli = prepare_client(twin, AuditLog(twin.audit_path), "tester")
    assert cli.calc_a.net_result == summary.net
    assert [(n.risk, n.check_id) for n in cli.notes] == [(n.risk, n.check_id) for n in summary.notes]


def test_calcs_side_by_side_and_differences_zero(tmp_path, monkeypatch):
    client, _settings, ws = _prepared(tmp_path, monkeypatch)
    summary = load_summary(ws)
    assert summary.a == summary.b and summary.a["taxable_income"] == Decimal("61250")
    assert summary.a["medicare_levy"] == Decimal("1225.00") and summary.a["lito"] == Decimal("81.25")
    assert "agree to the cent" in client.get("/c/TEST01/2026/prepare").get_data(as_text=True)


def test_download_only_listed_workpapers(tmp_path, monkeypatch):
    client, _settings, ws = _prepared(tmp_path, monkeypatch)
    [path] = workpapers(ws)
    resp = client.get(f"/c/TEST01/2026/workpaper/{path.name}")
    assert resp.status_code == 200 and resp.data[:2] == b"PK" and "attachment" in resp.headers["Content-Disposition"]
    assert client.get("/c/TEST01/2026/workpaper/TEST01_FY2026_Workpaper_DRAFT_v9.xlsx").status_code == 404
    assert client.get("/c/TEST01/2026/workpaper/..%2Fstate.json").status_code == 404
    assert client.get("/c/TEST01/2026/workpaper/state.json").status_code == 404


def test_prepare_error_shown(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    text = ws.figures_csv.read_text(encoding="utf-8-sig")
    ws.figures_csv.write_text(text + "F0099,income.interest,Bad,abc,,,,manual,Y,,\r\n", encoding="utf-8-sig")
    resp = client.post("/c/TEST01/2026/prepare", follow_redirects=True)
    assert "Fix these rows" in resp.get_data(as_text=True)
    assert workpapers(ws) == [] and load_summary(ws) is None


def test_client_list_shows_estimate_and_high_notes(tmp_path, monkeypatch):
    client, _settings, _ws = _prepared(tmp_path, monkeypatch)
    page = client.get("/clients").get_data(as_text=True)
    assert "Refund $993.25" in page and "Prepared" in page


def test_cli_prepare_shows_in_sawnx(tmp_path, monkeypatch):
    """Work done with `tra prepare` shows up in Sawnx (spec §4.2), found by hand on 18 Oct 2026."""
    _app, client, settings = make_client(tmp_path, monkeypatch)
    ws = build_test01(settings)
    prepare_client(ws, AuditLog(ws.audit_path), "tester")
    assert load_summary(ws).net == Decimal("-993.25")
    page = client.get("/clients").get_data(as_text=True)
    assert "Refund $993.25" in page
    assert "$993.25" in client.get("/c/TEST01/2026/prepare").get_data(as_text=True)
