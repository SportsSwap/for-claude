import copy
import datetime as dt
import json
import shutil
from pathlib import Path

import pytest

from lab import config, dials, news
from lab.config import P

ROOT = Path(__file__).resolve().parent.parent


def tiny_spec():
    """Dials an exclusion touches keep their named values plus one other;
    every other dial keeps two values only for direction and one elsewhere."""
    spec = copy.deepcopy(dials.build_spec())
    named = {(d, v) for r in spec["exclusions"] for d, vs in r["forbid"].items() for v in vs}
    touched = {d for d, _ in named}
    for d, info in spec["dials"].items():
        keep = [v for v in info["values"] if (d, v["value"]) in named]
        rest = [v for v in info["values"] if v not in keep]
        n = len(keep) + 1 if d in touched else (2 if d == "direction" else 1)
        info["values"] = (keep + rest)[:n]
    spec["setups"] = {k: spec["setups"][k] for k in ("flip_zone", "fair_value_gap", "trend_pullback")}
    return spec


def test_count_matches_brute_force():
    spec = tiny_spec()
    for setup in spec["setups"]:
        brute = sum(dials.is_valid(spec, v) for v in dials.iter_all(spec, setup))
        assert brute == dials.count(spec)["by_setup"][setup], setup


def test_decode_covers_every_version_once():
    spec = tiny_spec()
    s = "fair_value_gap"
    seen = set()
    for pi, (sc, tc) in enumerate(spec["chart_pairs"]):
        ctx = {"setup": s, "setup_chart": sc, "trigger_chart": tc}
        n = 1
        for d in dials.setup_dials(spec, s):
            n *= len(dials.valid_values(spec, ctx, d))
        for i in range(n):
            v = dials.decode(spec, s, pi, i)
            assert dials.is_valid(spec, v)
            seen.add(tuple(sorted(v.items(), key=lambda kv: kv[0])))
    assert len(seen) == dials.count(spec)["by_setup"][s]


def test_chart_pairs():
    pairs = dials.chart_pairs()
    assert ("daily", "1h") in pairs and ("daily", "daily") not in pairs
    assert ("1h", "5m") in pairs and ("1h", "1m") not in pairs and ("1m", "1m") in pairs
    assert len(pairs) == 13


def test_example_exclusion_flat_1600_on_4h():
    spec = dials.build_spec()
    ctx = {"setup": "breakout", "setup_chart": "4h", "trigger_chart": "1h"}
    assert "flat_1600" not in dials.valid_values(spec, ctx, "time_exit")


def test_spec_file_is_current_and_locked():
    on_disk = json.loads((ROOT / "rulebook_spec.json").read_text())
    spec = dials.build_spec()
    assert on_disk["count"] == dials.count(spec)
    assert {k: v for k, v in on_disk.items() if k != "count"} == json.loads(json.dumps(spec))
    config.verify_locks()


def test_rulebook_lists_every_dial_and_value():
    md = (ROOT / "rulebook.md").read_text()
    for d, info in dials.build_spec()["dials"].items():
        assert f"### `{d}`" in md
        for v in info["values"]:
            assert f"| `{v['value']}` | {v['meaning']} |" in md


def test_lock_catches_silent_threshold_change(tmp_path, monkeypatch):
    fake = tmp_path / "code"
    shutil.copytree(ROOT / "config", fake / "config")
    shutil.copy(ROOT / "rulebook_spec.json", fake / "rulebook_spec.json")
    monkeypatch.setattr(config, "code_root", lambda: fake)
    config.verify_locks()
    t = json.loads((fake / "config" / "thresholds.json").read_text())
    t["rolls"]["no_entry_minutes_before_roll"] = 30
    (fake / "config" / "thresholds.json").write_text(json.dumps(t))
    with pytest.raises(config.LockError):
        config.thresholds()


FED_SNIPPET = """
<h4><a id="1">2022 FOMC Meetings</a></h4>
<div class="fomc-meeting__month col"><strong>January</strong></div>
<div class="fomc-meeting__date col">25-26</div>
<div class="fomc-meeting__month col"><strong>March</strong></div>
<div class="fomc-meeting__date col">15-16*</div>
<div class="fomc-meeting__month col"><strong>May</strong></div>
<div class="fomc-meeting__date col">3-4</div>
<div class="fomc-meeting__month col"><strong>October</strong></div>
<div class="fomc-meeting__date col">14 (notation vote)</div>
<h4><a id="2">2023 FOMC Meetings</a></h4>
<div class="fomc-meeting__month col"><strong>Oct/Nov</strong></div>
<div class="fomc-meeting__date col">31-1</div>
"""


def test_parse_fomc():
    f = news.parse_fomc(FED_SNIPPET)
    assert f.date.tolist() == [dt.date(2022, 1, 26), dt.date(2022, 3, 16), dt.date(2022, 5, 4),
                               dt.date(2023, 11, 1)]
    assert f.verified.all() and "SEP" in f.notes.iat[1]


def test_parse_bls_archive():
    html = '<a href="/news.release/archives/cpi_01122022.htm">x</a><a href="/news.release/archives/cpi_02102022.htm">'
    assert news.parse_bls_archive(html, "CPI").date.tolist() == [dt.date(2022, 1, 12), dt.date(2022, 2, 10)]


def test_calendar_refuses_unverified_rows(lab_root, monkeypatch):
    monkeypatch.delenv("LAB_HTTP_CONTACT", raising=False)
    (P.news() / "sources").mkdir(parents=True)
    (P.news() / "sources" / "fomccalendars.htm").write_text(FED_SNIPPET)
    news.build(fetch=False)
    with pytest.raises(RuntimeError, match="unverified"):
        news.load_calendar()
    cal = news.load_calendar(require_verified=False)
    assert set(cal.event) == {"CPI", "NFP", "FOMC"}


def test_fomc_historical_pages_keep_scheduled_meetings_only():
    from lab.news import parse_fomc_historical
    html = """<h5 class="panel-heading panel-heading--shaded">January 28-29 Meeting - 2020</h5>
<h5 class="panel-heading">March 2 (unscheduled) Meeting - 2020</h5>
<h5>March 17-18 (cancelled) Meeting - 2020</h5>
<h5>March 19 (notation vote) - 2020</h5>
<h5>October 16 (unscheduled) - 2020</h5>
<h5>Jan/Feb 31-1 Meeting - 2020</h5>
<h5>April/May 30-1 Meeting - 2020</h5>
<h5>December 15-16 Meeting - 2020</h5>"""
    got = [str(d) for d in parse_fomc_historical(html, 2020)["date"]]
    assert got == ["2020-01-29", "2020-02-01", "2020-05-01", "2020-12-16"]
