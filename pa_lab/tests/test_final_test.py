"""Prompt 4: the final test on a tiny synthetic lab."""
import datetime as dt
import json
import os
import stat

import numpy as np
import pandas as pd
import pytest

from lab import final_test as ft
from lab import guard, ingest
from lab.config import P, sha256_file
from lab.market import Market
from lab.sessions import session_date

from conftest import SMALL_WINDOWS

BASE = dict(swing_strength=3, direction="both", confirmation="close_back", entry="close", stop_mode="hard",
            stop_ref="beyond_level", stop_buffer_atr=0.1, target="2R", management="hold", time_exit="bars_96",
            trend_filter="off", skip_choppy="off", skip_run="off", fresh_breakouts_only="off", news="trade",
            session="all", pullback_depth="any", gap_confluence="off", level_tol_atr=0.25, level_min_touches=2,
            level_shape="line")
VERSIONS = [
    {"id": "v1", "set": "common", **BASE, "setup": "level_bounce", "setup_chart": "15m", "trigger_chart": "15m"},
    {"id": "v2", "set": "common", **BASE, "setup": "breakout", "setup_chart": "1h", "trigger_chart": "15m"},
    {"id": "v3", "set": "named", **{**BASE, "stop_ref": "gap_middle", "fvg_min_gap_atr": 0.1, "fvg_max_age_bars": 24},
     "setup": "fair_value_gap", "setup_chart": "5m", "trigger_chart": "5m"},
]


def write_funnel(versions=VERSIONS):
    fd = P.results() / "funnel"
    fd.mkdir(parents=True, exist_ok=True)
    (fd / "versions.jsonl").write_text("".join(json.dumps(v) + "\n" for v in versions))
    (fd / "versions.sha256").write_text(sha256_file(fd / "versions.jsonl") + "  versions.jsonl\n")
    (fd / "stages.json").write_text(json.dumps({"min_trades": 30}))
    (fd / "candidates.json").write_text(json.dumps(["v1"]))
    (fd / "working_setups.json").write_text(json.dumps([{"setup": "level_bounce", "chart": "15m", "market": "NQ"}]))
    (fd / "named_versions.json").write_text(json.dumps([{"name": "The Gap Model", "id": "v3"}]))
    pd.DataFrame({"id": ["v1", "v2", "v3"], "net": [10.0, -5.0, 1.0], "sharpe": [0.6, -0.2, 0.1]}).to_parquet(
        fd / "metrics_NQ.parquet")
    man = {n: sha256_file(fd / n) for n in ft.SELECTION_FILES}
    (fd / "selection_manifest.json").write_text(json.dumps({"files": man}))


def log_events():
    if not P.access_log().exists():
        return []
    return [json.loads(x) for x in P.access_log().read_text().splitlines()]


def final_unlocks():
    return [e for e in log_events() if e["event"] == "unlock_open" and e["step"] == "final_test"]


@pytest.fixture
def lab(lab_root, small_input, monkeypatch):
    monkeypatch.setenv("LAB_UNLOCK", "ingest")
    assert ingest.run(small_input, windows_override=SMALL_WINDOWS) == 0
    monkeypatch.delenv("LAB_UNLOCK")
    write_funnel()
    return lab_root


def test_hash_mismatch_stops_before_unlock(lab, monkeypatch):
    (P.results() / "funnel" / "candidates.json").write_text(json.dumps(["v1", "v2"]))
    with pytest.raises(ft.PreflightError, match="candidates.json"):
        ft.run("rehearsal", workers=1, twin_sets=20)
    monkeypatch.setenv("LAB_UNLOCK", "final_test")
    with pytest.raises(ft.PreflightError):
        ft.run("final", workers=1, twin_sets=20)
    assert final_unlocks() == []


def test_rehearsal_runs_the_same_path_without_unlocking(lab):
    s = ft.run("rehearsal", workers=1, twin_sets=20)
    assert s["source"] == "rehearsal" and s["errors"] == 0
    assert s["price_shift_points"] == ft.REHEARSAL_SHIFT_POINTS
    assert s["window"] == ["2021-11-01", "2021-11-05"]
    od = P.results() / "final_rehearsal"
    assert (od / "REHEARSAL_OK.json").exists() and (od / "metrics_NQ.parquet").exists()
    assert final_unlocks() == []
    assert not (P.results() / "final").exists()


def test_final_needs_a_rehearsal(lab, monkeypatch):
    monkeypatch.setenv("LAB_UNLOCK", "final_test")
    with pytest.raises(ft.PreflightError, match="rehearsal"):
        ft.run("final", workers=1, twin_sets=20)
    assert final_unlocks() == []


def test_final_unlocks_once_and_refuses_to_run_twice(lab, monkeypatch):
    ft.run("rehearsal", workers=1, twin_sets=20)
    with pytest.raises(guard.SealedAccessError):          # no environment variable: no unlock
        ft.run("final", workers=1, twin_sets=20)
    assert final_unlocks() == []
    monkeypatch.setenv("LAB_UNLOCK", "final_test")
    s = ft.run("final", workers=1, twin_sets=20)
    assert s["window"] == [str(SMALL_WINDOWS.final[0]), str(SMALL_WINDOWS.final[1])]
    ev = [e["event"] for e in log_events() if e["step"] == "final_test"]
    assert ev.count("unlock_open") == 1 and ev.count("unlock_close") == 1
    assert "read_sealed_path" in ev
    od = P.results() / "final"
    for f in ("DONE.json", "metrics_NQ.parquet", "metrics_ES.parquet", "share_held.csv", "chart_made_money.csv",
              "setup_chart_year_NQ.csv", "working_vs_random.csv", "best_common_by_setup.csv",
              "named_versions.csv", "dials_held_in_common.csv"):
        assert (od / f).exists(), f
    with pytest.raises(ft.PreflightError, match="runs once"):
        ft.run("final", workers=1, twin_sets=20)
    # later analyses read the saved results only, without any unlock
    monkeypatch.delenv("LAB_UNLOCK")
    res = ft.load_final_results()
    assert set(res["metrics_NQ.parquet"]["id"]) == {"v1", "v2", "v3"}
    assert "session" not in res["daily/NQ/level_bounce.parquet"].columns
    assert len(final_unlocks()) == 1


def _bars(start_et, end_et):
    ts = pd.date_range(pd.Timestamp(start_et, tz="America/New_York"), pd.Timestamp(end_et, tz="America/New_York"),
                       freq="1min", inclusive="left").tz_convert("UTC")
    df = pd.DataFrame({"ts_event": ts, "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0,
                       "volume": 1, "contract": "X"})
    df["session"] = session_date(df["ts_event"])
    return df


def test_complete_sessions_and_dropped_session_as_roll():
    a = _bars("2022-01-03 18:00", "2022-01-04 17:00")      # complete
    b = _bars("2022-01-04 18:00", "2022-01-05 13:00")      # early close: dropped
    c = _bars("2022-01-05 18:00", "2022-01-06 16:00")      # last bar opens 15:59: complete
    m1 = pd.concat([a, b, c], ignore_index=True)
    kept, dropped = ft.complete_sessions(m1)
    assert set(kept.session) == {dt.date(2022, 1, 4), dt.date(2022, 1, 6)}
    assert dropped.session.tolist() == [dt.date(2022, 1, 5)]
    rolls = ft.dropped_as_rolls(dropped)
    assert rolls.roll_time_utc.iat[0] == b.ts_event.iat[0]
    mk = Market.from_frames("NQ", kept, rolls)
    last_a = len(a) - 1
    assert mk.roll_exit_idx.tolist() == [last_a]                 # positions close before the dropped session
    # the hour before the dropped session's 18:00 open is the 17:00 halt, so no bar falls in the blackout
    assert not mk.no_entry.any()
