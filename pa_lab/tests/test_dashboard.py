"""Dashboard: provenance refuses mismatches and unsourced digits, no em dashes,
the facecam corner stays empty, and the build reads nothing outside results/."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from dashboard import build as B
from dashboard import pages as pg
from dashboard.provenance import Provenance, ProvenanceError
from dashboard.render import Page


def _fixture(root: Path):
    r = root / "results"
    (r / "engine").mkdir(parents=True)
    (r / "behavior").mkdir()
    for name, nq, es in (("random_entries", -9.8, -12.5), ("cheat_peek60", 310.25, 120.0)):
        (r / "engine" / f"{name}.json").write_text(json.dumps({"results": {
            "NQ": {"per_trade_dollars": nq, "win_rate": 0.331}, "ES": {"per_trade_dollars": es, "win_rate": 0.32}}}))
    (r / "session_counts.csv").write_text(
        "market,window,start,end,sessions,weekdays\n"
        "NQ,warmup,2021-10-01,2021-12-31,66,66.0\nNQ,discovery,2022-01-03,2024-07-31,668,673.0\n"
        "NQ,final,2024-08-01,2026-10-16,572,577.0\n")
    (r / "behavior" / "verdicts.csv").write_text(
        "test,claim,metric,verdict,why\n"
        "levels_vs_random,Real levels hold more.,hold rate: A minus B,false,NQ pooled has an interval that includes zero.\n")
    rows = ["market,chart,point,lo,hi"]
    for m in ("NQ", "ES"):
        for c in ("5m", "15m", "1h", "4h", "daily", "pooled"):
            rows.append(f"{m},{c},0.0123,-0.004,0.021")
    (r / "behavior" / "levels_vs_random.csv").write_text("\n".join(rows) + "\n")
    return root


@pytest.fixture
def lab(tmp_path):
    return _fixture(tmp_path / "lab")


def test_build_ok_and_every_number_sourced(lab):
    res = B.build(lab)
    out = lab / "results" / "dashboard"
    prov = json.loads((out / "provenance.json").read_text())
    shown = {p["text"] for p in prov if p["shown"]}
    for page in json.loads((out / "pages.json").read_text()):
        assert set(page["numbers"]) <= shown
    assert res["pages"] >= 8 and any(p["page"] == "funnel_stages" for p in res["pending"])
    assert "—" not in (out / "deck.html").read_text()


def test_refuses_when_the_second_reader_differs(lab, monkeypatch):
    real = Provenance.reread
    def tampered(self, r):
        v = real(self, r)
        return v + 1 if isinstance(v, float) and r.file.endswith("random_entries.json") else v
    monkeypatch.setattr(Provenance, "reread", tampered)
    with pytest.raises(ProvenanceError, match="differ"):
        B.build(lab)
    assert not (lab / "results" / "dashboard" / "deck.html").exists()


def test_refuses_an_unsourced_digit(lab, monkeypatch):
    orig = pg.p_method
    def leaky(prov):
        p = orig(prov)
        p.subtitle = "Rules become dials across 7 charts"
        return p
    monkeypatch.setattr(pg, "p_method", leaky)
    with pytest.raises(B.BuildRefused, match="digits without a source"):
        B.build(lab)


def test_refuses_an_em_dash(lab, monkeypatch):
    orig = pg.p_random
    def dashed(prov):
        p = orig(prov)
        p.conclusion = "Random entries lose — as they should."
        return p
    monkeypatch.setattr(pg, "p_random", dashed)
    with pytest.raises(B.BuildRefused, match="dash"):
        B.build(lab)


def test_build_reads_only_results(lab, monkeypatch):
    seen = []
    real = Provenance.path
    def spy(self, rel):
        p = real(self, rel)
        seen.append(p)
        return p
    monkeypatch.setattr(Provenance, "path", spy)
    B.build(lab)
    assert seen and all((lab / "results") in p.parents for p in seen)
    prov = Provenance(lab / "results")
    for bad in ("../data/clean/NQ_1m.parquet", "../data/sealed/MANIFEST.json"):
        with pytest.raises(ProvenanceError):
            prov.path(bad)


def _node_ok():
    return shutil.which("node") and subprocess.run(["node", "-e", "require('playwright')"]).returncode == 0


@pytest.mark.skipif(not _node_ok(), reason="node playwright not available")
def test_layout_clean_and_facecam_empty(lab, monkeypatch):
    from dashboard import check_layout as L
    B.build(lab)
    rep = L.run(lab / "results" / "dashboard")
    assert rep["clean"], rep["sizes"]
    # a page that spills into the facecam corner and wraps its subtitle must be caught
    orig = pg.p_random
    def bad(prov):
        p = orig(prov)
        p.subtitle = "A subtitle that is far too long to fit on one line of the stage " * 3
        p.conclusion = "A conclusion long enough to run down into the corner kept free for the camera. " * 4
        return p
    monkeypatch.setattr(pg, "p_random", bad)
    B.build(lab)
    rep = L.run(lab / "results" / "dashboard")
    probs = " ".join(rep["sizes"]["1920x1080"]["problems"])
    assert not rep["clean"] and "facecam" in probs and ("overflows" in probs or "wraps" in probs)


def test_verdict_counts_ignore_case(lab):
    vf = lab / "results" / "behavior" / "verdicts.csv"
    vf.write_text(vf.read_text() + "bos_follow_20,x,20-bar move (ATR): A minus B,False,NQ pooled points the other way.\n")
    B.build(lab)
    prov = json.loads((lab / "results" / "dashboard" / "provenance.json").read_text())
    counts = {r["where"].get("verdict", "all"): r["text"] for r in prov if r["op"] == "count"}
    assert counts["false"] == "2" and counts["all"] == "2"
