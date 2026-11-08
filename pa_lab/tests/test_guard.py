"""The seal on the final window."""
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from lab import guard, io
from lab.config import P

from conftest import minute_bars


def test_read_of_sealed_path_raises(lab_root):
    p = lab_root / "data" / "sealed" / "x.parquet"
    p.parent.mkdir(parents=True)
    minute_bars("2021-10-04 15:00", 3).to_parquet(p)
    with pytest.raises(guard.SealedAccessError):
        io.read_table(p)
    with pytest.raises(guard.SealedAccessError):
        io.read_bytes(p)


def test_read_of_final_window_session_anywhere_raises(lab_root):
    p = lab_root / "data" / "clean" / "leak.parquet"
    p.parent.mkdir(parents=True)
    df = pd.concat([minute_bars("2021-10-04 15:00", 3), minute_bars("2021-11-09 15:00", 3)])
    df.to_parquet(p)
    with pytest.raises(guard.SealedAccessError, match="final window"):
        io.read_table(p)
    # also by an explicit session column, and in CSV
    c = lab_root / "data" / "clean" / "leak.csv"
    pd.DataFrame({"session": ["2021-11-08"], "x": [1]}).to_csv(c, index=False)
    with pytest.raises(guard.SealedAccessError):
        io.read_table(c)


def test_open_window_reads_fine(lab_root):
    p = lab_root / "data" / "clean" / "ok.parquet"
    p.parent.mkdir(parents=True)
    minute_bars("2021-10-04 15:00", 3).to_parquet(p)
    assert len(io.read_table(p)) == 3


def test_unlock_needs_name_and_env(lab_root, monkeypatch):
    with pytest.raises(guard.SealedAccessError, match="environment"):
        with guard.unlock("final_test"):
            pass
    monkeypatch.setenv("LAB_UNLOCK", "ingest")
    with pytest.raises(guard.SealedAccessError):
        with guard.unlock("final_test"):
            pass
    monkeypatch.setenv("LAB_UNLOCK", "peek")
    with pytest.raises(guard.SealedAccessError, match="not an unlock step"):
        with guard.unlock("peek"):
            pass


def test_unlock_allows_and_logs_every_read(lab_root, monkeypatch):
    p = lab_root / "data" / "sealed" / "x.parquet"
    p.parent.mkdir(parents=True)
    minute_bars("2021-11-09 15:00", 3).to_parquet(p)
    monkeypatch.setenv("LAB_UNLOCK", "final_test")
    with guard.unlock("final_test"):
        assert len(io.read_table(p)) == 3
    with pytest.raises(guard.SealedAccessError):   # the unlock ends with the block
        io.read_table(p)
    events = [json.loads(line)["event"] for line in P.access_log().read_text().splitlines()]
    assert events[:4] == ["unlock_open", "read_sealed_path", "read_final_window_rows", "unlock_close"]


def test_only_ingest_writes_sealed_and_only_once(lab_root, monkeypatch):
    p = lab_root / "data" / "sealed" / "y.json"
    with pytest.raises(guard.SealedAccessError):
        io.write_json({}, p)
    monkeypatch.setenv("LAB_UNLOCK", "final_test")
    with guard.unlock("final_test"), pytest.raises(guard.SealedAccessError):
        io.write_json({}, p)
    monkeypatch.setenv("LAB_UNLOCK", "ingest")
    with guard.unlock("ingest"):
        io.write_json({}, p)
        with pytest.raises(guard.SealedAccessError, match="written once"):
            io.write_json({}, p)


def test_no_unguarded_readers():
    """Every data read in lab/ must go through lab/io.py."""
    pat = re.compile(r"pd\.read_|read_parquet|read_csv|pyarrow|np\.load\(|open\([^)]*['\"]r")
    lab = Path(__file__).resolve().parent.parent / "lab"
    offenders = [f"{f.name}:{i}" for f in lab.glob("*.py") if f.name != "io.py"
                 for i, line in enumerate(f.read_text().splitlines(), 1)
                 if pat.search(line) and "guard-exempt" not in line]
    assert offenders == []
