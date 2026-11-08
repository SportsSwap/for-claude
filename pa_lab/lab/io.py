"""The only file readers and writers in the lab. Each one goes through the guard.

A test (tests/test_guard.py::test_no_unguarded_readers) fails if any other
module in lab/ calls a pandas/pyarrow reader directly.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import guard
from .sessions import session_date


def _guard_frame(df: pd.DataFrame, source) -> pd.DataFrame:
    if "session" in df.columns:
        guard.check_sessions(df["session"], source)
    elif "ts_event" in df.columns:
        guard.check_sessions(session_date(pd.to_datetime(df["ts_event"], utc=True)), source)
    return df


def read_table(path: Path | str, **kw) -> pd.DataFrame:
    path = Path(path)
    guard.check_path(path, "read")
    suf = path.suffix.lower()
    if suf == ".parquet":
        df = pd.read_parquet(path, **kw)
    elif suf in (".csv", ".gz"):
        df = pd.read_csv(path, **kw)
    else:
        raise ValueError(f"unsupported table format: {path}")
    return _guard_frame(df, path)


def read_json(path: Path | str):
    path = Path(path)
    guard.check_path(path, "read")
    return json.loads(path.read_text())


def read_bytes(path: Path | str) -> bytes:
    path = Path(path)
    guard.check_path(path, "read")
    return path.read_bytes()


def write_table(df: pd.DataFrame, path: Path | str) -> Path:
    path = Path(path)
    guard.check_path(path, "write")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)
    return path


def write_json(obj, path: Path | str) -> Path:
    path = Path(path)
    guard.check_path(path, "write")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    return path
