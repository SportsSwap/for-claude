"""Sawnx's Rental page: each property's share, private use and ticks, which property each document is, and which
column each figure is in. Made-up data only (the demo rental statement)."""

import json
from decimal import Decimal

from webctx import ingest_demo, make_client, new_client

from tra.rental import load_rental


def _setup(tmp_path, monkeypatch, *stems):
    _app, web, settings = make_client(tmp_path, monkeypatch)
    ws = new_client(settings)
    reports = ingest_demo(settings, ws, *(stems or ("rental",)))
    return web, ws, reports


def _page(web, path="/c/TEST01/2026/rental"):
    return web.get(path).get_data(as_text=True).replace("&#39;", "'")


def test_the_tab_shows_only_for_a_year_with_rentals(tmp_path, monkeypatch):
    web, _ws, _ = _setup(tmp_path, monkeypatch, "income_statement")
    assert 'href="/c/TEST01/2026/rental"' not in _page(web, "/c/TEST01/2026/figures")
    (tmp_path / "b").mkdir()
    web, _ws, _ = _setup(tmp_path / "b", monkeypatch)
    assert 'href="/c/TEST01/2026/rental"' in _page(web, "/c/TEST01/2026/figures")


def test_the_page_shows_the_assumed_property_and_its_rows(tmp_path, monkeypatch):
    web, _ws, _ = _setup(tmp_path, monkeypatch)
    page = _page(web)
    assert "Property 1" in page and "Assumed 100%" in page
    for heading in ("Rental Income", "Council Rates", "Agent Fees", "Repairs and Maintenance", "Net Income / (Loss)"):
        assert heading in page
    assert "26,000.00" in page  # the demo's rent, all of it while the share is 100%


def test_saving_a_property_sets_the_share(tmp_path, monkeypatch):
    web, ws, _ = _setup(tmp_path, monkeypatch)
    resp = web.post("/c/TEST01/2026/rental/P1", data={"name": "Sample St", "share": "50", "private_use": "0",
                                                       "weeks_rented": "52", "weeks_available": "52",
                                                       "first_income": "", "apportion": ["rent.insurance"]},
                    follow_redirects=True)
    assert resp.status_code == 200
    [p] = load_rental(ws).properties
    assert (p.name, p.share, p.share_source) == ("Sample St", Decimal("50"), "person")
    assert p.apportioned("rent.insurance") and not p.apportioned("rent.council_rates")  # unticked on the form
    page = resp.get_data(as_text=True).replace("&#39;", "'")
    assert "Set by you" in page and "13,000.00" in page
    entries = [json.loads(line) for line in ws.audit_path.read_text(encoding="utf-8").splitlines()]
    assert entries[-1]["action"] == "rental_changed" and "Sample St" not in json.dumps(entries[-1])


def test_a_bad_share_is_refused(tmp_path, monkeypatch):
    web, ws, _ = _setup(tmp_path, monkeypatch)
    resp = web.post("/c/TEST01/2026/rental/P1", data={"name": "Sample St", "share": "150", "private_use": "0",
                                                       "weeks_rented": "52", "weeks_available": "52"},
                    follow_redirects=True)
    assert "between 0 and 100" in resp.get_data(as_text=True)
    assert load_rental(ws).properties[0].share_source == "default"


def test_a_suggested_share_says_where_it_came_from(tmp_path, monkeypatch):
    from tra.privacy.audit import AuditLog
    from tra.rental import suggest_share
    web, ws, reports = _setup(tmp_path, monkeypatch)
    doc_id = reports[0].doc.doc_id
    suggest_share(ws, doc_id, Decimal("50"), AuditLog(ws.audit_path))
    page = _page(web)
    assert f"Suggested 50% from {doc_id}" in page


def test_a_second_property_and_assigning_documents(tmp_path, monkeypatch):
    web, ws, reports = _setup(tmp_path, monkeypatch)
    doc_id = reports[0].doc.doc_id
    web.post("/c/TEST01/2026/rental/add", data={"name": "Example Rd"})
    setup = load_rental(ws)
    assert [p.name for p in setup.properties] == ["Property 1", "Example Rd"]
    page = _page(web)
    assert f'name="doc-{doc_id}"' in page  # with two properties, each rental document gets a choice
    web.post("/c/TEST01/2026/rental/documents", data={f"doc-{doc_id}": "P2"})
    assert load_rental(ws).documents == {doc_id: "P2"}
    resp = web.post("/c/TEST01/2026/rental/P2/remove", follow_redirects=True)
    assert "still has documents" in resp.get_data(as_text=True)
    assert len(load_rental(ws).properties) == 2
    web.post("/c/TEST01/2026/rental/documents", data={f"doc-{doc_id}": "P1"})
    web.post("/c/TEST01/2026/rental/P2/remove")
    assert [p.id for p in load_rental(ws).properties] == ["P1"]


def test_moving_a_figure_to_this_taxpayer_only(tmp_path, monkeypatch):
    from tra.web.services.figures import figure_rows
    web, ws, _ = _setup(tmp_path, monkeypatch)
    rates = next(f for f in figure_rows(ws) if f.label_key == "rent.council_rates")
    page = _page(web)
    assert f'name="col-{rates.figure_id}"' in page
    web.post("/c/TEST01/2026/rental/columns", data={f"col-{rates.figure_id}": "taxpayer"})
    assert load_rental(ws).columns == {rates.figure_id: "taxpayer"}
    web.post("/c/TEST01/2026/rental/columns", data={f"col-{rates.figure_id}": "nonsense"})
    assert load_rental(ws).columns == {rates.figure_id: "taxpayer"}  # an unknown column changes nothing


def test_posts_need_the_same_origin(tmp_path, monkeypatch):
    web, ws, _ = _setup(tmp_path, monkeypatch)
    resp = web.post("/c/TEST01/2026/rental/P1", data={"name": "X", "share": "50"},
                    headers={"Origin": "http://evil.example"})
    assert resp.status_code in (400, 403) and not ws.rental_json.exists()
