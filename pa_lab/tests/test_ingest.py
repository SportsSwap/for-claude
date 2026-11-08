"""End to end on two months of synthetic data with injected defects."""
import json
import os
import stat

import pandas as pd
import pytest

from lab import guard, ingest, io
from lab.config import P, sha256_file

from conftest import SMALL_WINDOWS


@pytest.fixture
def ingested(lab_root, small_input, monkeypatch):
    monkeypatch.setenv("LAB_UNLOCK", "ingest")
    rc = ingest.run(small_input, windows_override=SMALL_WINDOWS)
    monkeypatch.delenv("LAB_UNLOCK")
    return rc, small_input


def test_ingest_passes_and_seals(ingested):
    rc, src = ingested
    assert rc == 0
    verdict = json.loads((P.results() / "audit" / "audit_pass.json").read_text())
    assert verdict["pass"]
    # raw copies are byte-identical and recorded
    raw = json.loads((P.raw() / "MANIFEST.json").read_text())["files"]
    for name, rec in raw.items():
        assert rec["sha256"] == sha256_file(src / name) == sha256_file(P.raw() / name)
    # sealed manifest matches the sealed files, which are read-only
    man = json.loads((P.sealed() / "MANIFEST.json").read_text())
    for name, rec in man["files"].items():
        f = P.sealed() / name
        assert sha256_file(f) == rec["sha256"]
        assert not (f.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def test_clean_files_hold_no_final_sessions_and_no_halt_bars(ingested):
    for m in ("NQ", "ES"):
        df = io.read_table(P.clean() / f"{m}_1m.parquet")   # the guard itself would raise on a leak
        assert max(df.session) < SMALL_WINDOWS.final[0]
        assert min(df.session) >= SMALL_WINDOWS.warmup[0]
        et = pd.to_datetime(df.ts_event, utc=True).dt.tz_convert("America/New_York")
        assert (et.dt.hour != 17).all()
        assert df.ts_event.is_monotonic_increasing and not df.ts_event.duplicated().any()


def test_session_counts_per_window(ingested):
    c = pd.read_csv(P.results() / "session_counts.csv")
    got = c[c.market == "NQ"].set_index("window")["sessions"].to_dict()
    assert got["warmup"] == 6 and got["discovery"] == 20 and got["final"] == 30
    assert got["era1"] + got["era2"] == got["discovery"]


def test_ingest_runs_once(ingested, small_input, monkeypatch):
    monkeypatch.setenv("LAB_UNLOCK", "ingest")
    with pytest.raises(SystemExit, match="runs once"):
        ingest.run(small_input, windows_override=SMALL_WINDOWS)


def test_ingest_needs_its_unlock(lab_root, small_input):
    with pytest.raises(guard.SealedAccessError):
        ingest.run(small_input, windows_override=SMALL_WINDOWS)


def test_audit_fails_on_conflicting_duplicates(lab_root, small_input, tmp_path, monkeypatch):
    src = tmp_path / "bad"
    src.mkdir()
    for f in small_input.iterdir():
        (src / f.name).write_bytes(f.read_bytes())
    p = src / "NQ_1m_backadjusted.parquet"
    df = pd.read_parquet(p)
    df = pd.concat([df, df.iloc[[100]].assign(close=df.close.iat[100] + 5, high=df.high.iat[100] + 5)])
    df.to_parquet(p, index=False)
    u = src / "NQ_1m_unadjusted.parquet"
    du = pd.read_parquet(u)
    pd.concat([du, du.iloc[[100]]]).to_parquet(u, index=False)
    monkeypatch.setenv("LAB_UNLOCK", "ingest")
    assert ingest.run(src, windows_override=SMALL_WINDOWS) == 1
    v = json.loads((P.results() / "audit" / "audit_pass.json").read_text())
    assert v["markets"]["NQ"]["conflicting_duplicates"] is False and v["pass"] is False
