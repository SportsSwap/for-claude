"""The seal on the final window.

Nothing may read data/sealed/ or any bar from a session dated in the final
window unless an explicit unlock is on. An unlock needs BOTH:
  1. a named step in code:   with unlock("final_test"): ...
  2. the same name in the environment:  LAB_UNLOCK=final_test
Every unlock and every guarded read made under it is appended to
results/sealed_access_log.jsonl.

Only the ingest step may write into data/sealed/, and only once.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import sys
import threading
from pathlib import Path

from .config import P, load_windows

ALLOWED_STEPS = ("ingest", "final_test")
ENV_VAR = "LAB_UNLOCK"
_state = threading.local()


class SealedAccessError(PermissionError):
    pass


def active_step() -> str | None:
    return getattr(_state, "step", None)


def _log(event: str, **kw) -> None:
    P.access_log().parent.mkdir(parents=True, exist_ok=True)
    rec = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "event": event, "step": active_step(), "pid": os.getpid(),
           "argv": sys.argv, **kw}
    with open(P.access_log(), "a") as f:
        f.write(json.dumps(rec, default=str) + "\n")


@contextlib.contextmanager
def unlock(step: str):
    if step not in ALLOWED_STEPS:
        raise SealedAccessError(f"'{step}' is not an unlock step; allowed: {ALLOWED_STEPS}")
    if os.environ.get(ENV_VAR) != step:
        _log("unlock_refused", requested=step, env=os.environ.get(ENV_VAR))
        raise SealedAccessError(
            f"unlock('{step}') also needs the environment variable {ENV_VAR}={step}")
    if active_step() is not None:
        raise SealedAccessError(f"already unlocked for '{active_step()}'")
    _state.step = step
    _log("unlock_open")
    try:
        yield
    finally:
        _log("unlock_close")
        _state.step = None


def _is_sealed_path(path: Path) -> bool:
    try:
        Path(path).resolve().relative_to(P.sealed().resolve())
        return True
    except ValueError:
        return False


def check_path(path: Path, mode: str = "read") -> None:
    """Called by every reader (mode='read') and writer (mode='write')."""
    if not _is_sealed_path(path):
        return
    step = active_step()
    if mode == "read":
        if step is None:
            raise SealedAccessError(f"read of sealed path {path} without an unlock")
        _log("read_sealed_path", path=str(path))
    else:
        if step != "ingest":
            raise SealedAccessError(f"only the ingest step writes data/sealed/ ({path})")
        if Path(path).exists():
            raise SealedAccessError(f"{path} already exists; the final window is written once")
        _log("write_sealed_path", path=str(path))


def check_sessions(sessions, source: str = "frame") -> None:
    """Raise if any session date falls on or after the final window start."""
    import pandas as pd
    if sessions is None or len(sessions) == 0:
        return
    final_start = load_windows().final[0]
    s = pd.to_datetime(pd.Series(sessions)).dt.date
    n = int((s >= final_start).sum())
    if n == 0:
        return
    if active_step() is None:
        raise SealedAccessError(
            f"{source}: {n} rows dated in the final window (>= {final_start}) without an unlock")
    _log("read_final_window_rows", source=str(source), rows=n)
