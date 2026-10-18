import pytest
from webctx import make_client, new_client

from tra.privacy.guard import SensitiveDataBlocked
from tra.web.client_notes import add_note, delete_note, edit_note, list_notes, notes_path


def test_add_edit_delete_note(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    home = settings.tra_home
    first = add_note(home, "TEST01", "Client called about the dividend statement.", "nicho", 2026)
    second = add_note(home, "TEST01", "Second note", "nicho")
    assert [n["id"] for n in list_notes(home, "TEST01")] == [second["id"], first["id"]]
    edited = edit_note(home, "TEST01", first["id"], "Client emailed instead.")
    assert edited["text"] == "Client emailed instead." and edited["edited_at"]
    delete_note(home, "TEST01", second["id"])
    assert [n["id"] for n in list_notes(home, "TEST01")] == [first["id"]]
    with pytest.raises(ValueError):
        add_note(home, "TEST01", "   ", "nicho")
    with pytest.raises(ValueError):
        edit_note(home, "TEST01", "nope", "x")


def test_note_with_tfn_refused(tmp_path, monkeypatch, make_tfn):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    add_note(settings.tra_home, "TEST01", "Safe note", "nicho")
    before = notes_path(settings.tra_home, "TEST01").read_bytes()
    with pytest.raises(SensitiveDataBlocked):
        add_note(settings.tra_home, "TEST01", f"TFN is {make_tfn()}", "nicho")
    assert notes_path(settings.tra_home, "TEST01").read_bytes() == before
    resp = client.post("/c/TEST01/notes", data={"text": f"tax file number {make_tfn()}", "fy": "2026"},
                       follow_redirects=True)
    assert "privacy officer" in resp.get_data(as_text=True)
    assert notes_path(settings.tra_home, "TEST01").read_bytes() == before


def test_notes_are_per_client_not_per_year(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings, fy=2026)
    new_client(settings, fy=2025)
    resp = client.post("/c/TEST01/notes", data={"text": "Engagement letter signed.", "fy": "2026"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/c/TEST01/2026/notes")
    assert notes_path(settings.tra_home, "TEST01") == settings.tra_home / "Work" / "TEST01" / "client_notes.json"
    for fy in (2026, 2025):
        assert "Engagement letter signed." in client.get(f"/c/TEST01/{fy}/notes").get_data(as_text=True)


def test_edit_and_delete_through_the_page(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings)
    note = add_note(settings.tra_home, "TEST01", "Old text", "nicho")
    client.post(f"/c/TEST01/notes/{note['id']}/edit", data={"text": "New text", "fy": "2026"})
    assert list_notes(settings.tra_home, "TEST01")[0]["text"] == "New text"
    client.post(f"/c/TEST01/notes/{note['id']}/delete", data={"fy": "2026"})
    assert list_notes(settings.tra_home, "TEST01") == []
    assert client.post("/c/nope/notes", data={"text": "x", "fy": "2026"}).status_code == 404
