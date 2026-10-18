import io

import pytest
from webctx import make_client, new_client

from tra.demo import _write_pdf
from tra.privacy.audit import AuditLog
from tra.privacy.guard import SensitiveDataBlocked
from tra.web.intray import add_to_tray
from tra.web.knowledge import KNOWLEDGE_FOLDERS, knowledge_docs, knowledge_path, store_knowledge
from tra.web.rules import add_rule, delete_rule, load_rules


def _audit(tmp_path):
    return AuditLog(tmp_path / "a.jsonl")


def test_knowledge_store_keeps_a_readable_name(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    src = tmp_path / "up.docx"
    src.write_bytes(b"PK template")
    doc = store_knowledge(settings.tra_home, src, "Engagement letter template.docx", "Templates", "nicho",
                          _audit(tmp_path))
    assert KNOWLEDGE_FOLDERS == ("Templates", "Policies", "Procedures", "Other")
    assert doc.filed_name == "Engagement letter template.docx" and doc.category == "Templates"
    again = store_knowledge(settings.tra_home, tmp_path / "up.docx", "x.docx", "Other", "nicho", _audit(tmp_path))
    assert again.doc_id == doc.doc_id
    src2 = tmp_path / "up2.docx"
    src2.write_bytes(b"PK another")
    second = store_knowledge(settings.tra_home, src2, "Engagement letter template.docx", "Templates", "nicho",
                             _audit(tmp_path))
    assert second.filed_name == "Engagement letter template_02.docx"
    assert knowledge_path(settings.tra_home, doc.doc_id).read_bytes() == b"PK template"
    assert len(knowledge_docs(settings.tra_home)) == 2
    with pytest.raises(ValueError):
        store_knowledge(settings.tra_home, src2, "../../evil.docx", "Templates", "nicho", _audit(tmp_path))
    with pytest.raises(ValueError):
        store_knowledge(settings.tra_home, src2, "a.exe", "Templates", "nicho", _audit(tmp_path))


def test_knowledge_name_with_tfn_refused(tmp_path, monkeypatch, make_tfn):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    src = tmp_path / "up.pdf"
    src.write_bytes(b"%PDF policy")
    with pytest.raises(SensitiveDataBlocked):
        store_knowledge(settings.tra_home, src, f"TFN {make_tfn()}.pdf", "Policies", "nicho", _audit(tmp_path))


def test_rules_improve_in_tray_suggestions(tmp_path, monkeypatch):
    _app, _client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings, "SMIT01")
    rule = add_rule(settings.tra_home, "Harbour Accounting Trust", "SMIT01", "Permanent", "Trust deeds",
                    _audit(tmp_path))
    assert load_rules(settings.tra_home)[0]["phrase"] == "Harbour Accounting Trust"
    pdf = tmp_path / "deed.pdf"
    _write_pdf(pdf, ["Deed of variation", "HARBOUR ACCOUNTING TRUST", "Dated 1 March 2026"])
    item = add_to_tray(settings.tra_home, pdf, "nicho", _audit(tmp_path))
    s = item.suggestion
    assert (s["code"], s["cabinet"], s["folder"], s["mode"]) == ("SMIT01", "Permanent", "Trust deeds", "store")
    delete_rule(settings.tra_home, rule["id"], _audit(tmp_path))
    assert load_rules(settings.tra_home) == []
    with pytest.raises(ValueError):
        add_rule(settings.tra_home, "ab", "SMIT01", "Permanent", "Trust deeds", _audit(tmp_path))
    with pytest.raises(ValueError):
        add_rule(settings.tra_home, "Something", "NOPE01", "Permanent", "Trust deeds", _audit(tmp_path))


def test_pages(tmp_path, monkeypatch):
    _app, client, settings = make_client(tmp_path, monkeypatch)
    new_client(settings, "SMIT01")
    resp = client.post("/knowledge", content_type="multipart/form-data",
                       data={"folder": "Policies", "files": [(io.BytesIO(b"%PDF privacy policy"), "Privacy policy.pdf")]})
    assert resp.status_code == 302
    page = client.get("/knowledge").get_data(as_text=True)
    assert "Privacy policy.pdf" in page and "not client documents" in page
    [doc] = knowledge_docs(settings.tra_home)
    assert client.get(f"/knowledge/{doc.doc_id}").data.startswith(b"%PDF")
    assert client.get("/knowledge/D999").status_code == 404
    client.post("/settings/rules", data={"phrase": "Harbour Trust", "code": "SMIT01", "cabinet": "Permanent",
                                         "folder": "Trust deeds"})
    assert "Harbour Trust" in client.get("/settings").get_data(as_text=True)
