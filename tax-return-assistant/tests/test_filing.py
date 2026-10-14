from datetime import date, datetime
from pathlib import Path

import pytest

from tra.filing.index import DocumentIndex
from tra.filing.local_store import LocalStore
from tra.filing.naming import filed_name
from tra.filing.store import FallbackStore, FiledRef, FilingRequest
from tra.models import Document
from tra.privacy.guard import SensitiveDataBlocked


def _doc(doc_id="D001", sha="a" * 64, **kw):
    base = dict(doc_id=doc_id, doc_type="DIVSTMT", category="Investments",
                filed_name=f"SMIT01_FY2026_DIVSTMT_2026-03-24{'' if doc_id == 'D001' else '_02'}.pdf",
                filed_location="C:/x", doc_date=date(2026, 3, 24), date_detected=True, pages=1, sha256=sha,
                ingested_at=datetime(2026, 10, 14, 9, 30).astimezone(), redaction_counts={"TFN": 1},
                parse_status="parsed", store="local")
    base.update(kw)
    return Document(**base)


def test_filed_name():
    assert filed_name("SMIT01", 2026, "DIVSTMT", date(2026, 3, 24), ".pdf", set()) == \
        "SMIT01_FY2026_DIVSTMT_2026-03-24.pdf"
    existing = {"SMIT01_FY2026_DIVSTMT_2026-03-24.pdf"}
    assert filed_name("SMIT01", 2026, "DIVSTMT", date(2026, 3, 24), ".PDF", existing) == \
        "SMIT01_FY2026_DIVSTMT_2026-03-24_02.pdf"
    existing.add("SMIT01_FY2026_DIVSTMT_2026-03-24_02.pdf")
    assert filed_name("SMIT01", 2026, "DIVSTMT", date(2026, 3, 24), ".pdf", existing).endswith("_03.pdf")


def test_local_store_copies_unchanged(tmp_path):
    source = tmp_path / "inbox" / "anything.pdf"
    source.parent.mkdir()
    source.write_bytes(b"%PDF original bytes")
    store = LocalStore(tmp_path / "home")
    req = FilingRequest("SMIT01", 2026, "Investments", "SMIT01_FY2026_DIVSTMT_2026-03-24.pdf", "DIVSTMT",
                        date(2026, 3, 24))
    ref = store.file(source, req)
    target = tmp_path / "home" / "Clients" / "SMIT01" / "FY2026" / "Investments" / req.filed_name
    assert ref == FiledRef(location=str(target), store="local")
    assert target.read_bytes() == b"%PDF original bytes"


def test_index_roundtrip_and_ids(tmp_path):
    index = DocumentIndex(tmp_path / "index.csv")
    assert index.next_doc_id() == "D001"
    index.append(_doc("D001", "a" * 64))
    index.append(_doc("D002", "b" * 64, date_detected=False, redaction_counts={}))
    assert index.next_doc_id() == "D003"
    loaded = index.load()
    assert loaded[0] == _doc("D001", "a" * 64)
    assert loaded[1].redaction_counts == {} and loaded[1].date_detected is False
    assert index.find_by_sha("b" * 64).doc_id == "D002"
    assert index.find_by_sha("c" * 64) is None
    assert index.names() == {d.filed_name for d in loaded}


def test_index_update(tmp_path):
    index = DocumentIndex(tmp_path / "index.csv")
    index.append(_doc())
    index.update(_doc(store="fyi", filed_location="https://fyi.example/doc/1"))
    assert index.load()[0].store == "fyi"


def test_index_has_no_original_filename(tmp_path):
    source = tmp_path / "John Smith TFN.pdf"
    source.write_bytes(b"%PDF")
    store = LocalStore(tmp_path / "home")
    name = filed_name("SMIT01", 2026, "INCSTMT", date(2026, 6, 30), source.suffix, set())
    ref = store.file(source, FilingRequest("SMIT01", 2026, "Income", name, "INCSTMT", date(2026, 6, 30)))
    index = DocumentIndex(tmp_path / "home" / "Clients" / "SMIT01" / "FY2026" / "index.csv")
    index.append(_doc(filed_name=name, filed_location=ref.location, doc_type="INCSTMT", category="Income"))
    text = index.path.read_text(encoding="utf-8")
    for word in ("John", "Smith", "John Smith TFN.pdf"):
        assert word not in text
        assert word not in name


def test_filed_name_guarded():
    with pytest.raises(SensitiveDataBlocked):
        filed_name("SMIT01", 2026, "OTHER 4111111111111111", date(2026, 1, 1), ".pdf", set())


class _Broken:
    name = "fyi"

    def file(self, source, req):
        raise ConnectionError("FYI down: secret detail")


def test_fallback_store(tmp_path):
    source = tmp_path / "a.pdf"
    source.write_bytes(b"%PDF")
    store = FallbackStore(_Broken(), LocalStore(tmp_path / "home"))
    ref = store.file(source, FilingRequest("SMIT01", 2026, "Other", "SMIT01_FY2026_OTHER_2026-01-01.pdf", "OTHER",
                                           date(2026, 1, 1)))
    assert ref.store == "local" and ref.fell_back is True
    assert Path(ref.location).exists()
