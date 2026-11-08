"""Paths, master seed, frozen thresholds and the research windows.

Everything that can change a result lives in config/thresholds.json or
rulebook_spec.json. Both are locked by sha256 in config/amendments.json; the
lab refuses to load a file whose hash is not the latest amendment's hash.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

MASTER_SEED = 20220103  # first discovery session; every random draw derives from this
TZ = "America/New_York"


def root() -> Path:
    """Project root. LAB_ROOT lets the tests run the lab inside a temp folder."""
    return Path(os.environ.get("LAB_ROOT", Path(__file__).resolve().parent.parent))


def code_root() -> Path:
    return Path(__file__).resolve().parent.parent


class P:  # lazily resolved paths so LAB_ROOT can change in tests
    @staticmethod
    def data() -> Path: return root() / "data"
    @staticmethod
    def raw() -> Path: return root() / "data" / "raw"
    @staticmethod
    def clean() -> Path: return root() / "data" / "clean"
    @staticmethod
    def sealed() -> Path: return root() / "data" / "sealed"
    @staticmethod
    def news() -> Path: return root() / "data" / "news"
    @staticmethod
    def results() -> Path: return root() / "results"
    @staticmethod
    def windows_file() -> Path: return root() / "data" / "windows.json"
    @staticmethod
    def access_log() -> Path: return root() / "results" / "sealed_access_log.jsonl"
    @staticmethod
    def config() -> Path: return code_root() / "config"


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:  # guard-exempt: hashing only, used by ingest and amend
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


# --------------------------------------------------------------------------- locks
LOCKED_FILES = ("config/thresholds.json", "rulebook_spec.json")


class LockError(RuntimeError):
    pass


def _ledger() -> list[dict]:
    return json.loads((P.config() / "amendments.json").read_text())["amendments"]


def locked_hashes() -> dict[str, str]:
    return _ledger()[-1]["hashes"]


def verify_locks(files=LOCKED_FILES) -> None:
    want = locked_hashes()
    for rel in files:
        path = code_root() / rel
        if not path.exists():
            continue
        got = sha256_file(path)
        if want.get(rel) != got:
            raise LockError(
                f"{rel} changed (sha256 {got[:12]}) without a numbered amendment. "
                "Write the amendment first: python -m lab.amend \"<reason>\"")


def thresholds() -> dict:
    verify_locks(("config/thresholds.json",))
    return json.loads((P.config() / "thresholds.json").read_text())


def stamp() -> dict:
    """Provenance stamped into every result file."""
    return {"master_seed": MASTER_SEED, "amendment": _ledger()[-1]["n"],
            "locks": locked_hashes(),
            "written_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}


# --------------------------------------------------------------------------- windows
@dataclass(frozen=True)
class Windows:
    warmup: tuple[dt.date, dt.date]
    discovery: tuple[dt.date, dt.date]
    era1: tuple[dt.date, dt.date]
    era2: tuple[dt.date, dt.date]
    final: tuple[dt.date, dt.date]

    def label(self, d: dt.date) -> str:
        for name in ("warmup", "discovery", "final"):
            a, b = getattr(self, name)
            if a <= d <= b:
                return name
        return "outside"

    def era(self, d: dt.date) -> str | None:
        for name in ("era1", "era2"):
            a, b = getattr(self, name)
            if a <= d <= b:
                return name
        return None

    def to_json(self) -> dict:
        return {k: [a.isoformat(), b.isoformat()] for k, (a, b) in asdict(self).items()}

    @staticmethod
    def from_json(d: dict) -> "Windows":
        names = ("warmup", "discovery", "era1", "era2", "final")
        return Windows(**{k: (dt.date.fromisoformat(d[k][0]), dt.date.fromisoformat(d[k][1]))
                          for k in names})


D = dt.date
DEFAULT_WINDOWS = Windows(
    warmup=(D(2021, 10, 1), D(2021, 12, 31)),
    discovery=(D(2022, 1, 3), D(2024, 7, 31)),
    era1=(D(2022, 1, 3), D(2022, 12, 31)),
    era2=(D(2023, 1, 1), D(2024, 7, 31)),
    final=(D(2024, 8, 1), D(2026, 10, 16)),
)


def _add_months(d: dt.date, months: int) -> dt.date:
    y, m = divmod(d.month - 1 + months, 12)
    return D(d.year + y, m + 1, 1)


def derive_windows(first_session: dt.date, last_session: dt.date) -> Windows:
    """The stated windows when the data covers them; otherwise the same shape:
    3-month warm-up, ~2.5-year discovery split into two eras, last 2 years sealed."""
    week = dt.timedelta(days=7)
    if abs(first_session - DEFAULT_WINDOWS.warmup[0]) <= week \
            and last_session >= DEFAULT_WINDOWS.final[0]:
        w = DEFAULT_WINDOWS
        return Windows(w.warmup, w.discovery, w.era1, w.era2, (w.final[0], last_session))
    final_start = _add_months(D(last_session.year - 2, last_session.month, 1), 1)
    disc_start = _add_months(final_start, -30)
    warm_start = _add_months(disc_start, -3)
    if warm_start < first_session:
        raise ValueError(f"data from {first_session} is too short for a 3m warm-up, "
                         f"30m discovery and 2y sealed window ending {last_session}")
    era2_start = _add_months(disc_start, 12)
    day = dt.timedelta(days=1)
    return Windows((warm_start, disc_start - day), (disc_start, final_start - day),
                   (disc_start, era2_start - day), (era2_start, final_start - day),
                   (final_start, last_session))


def load_windows() -> Windows:
    f = P.windows_file()
    return Windows.from_json(json.loads(f.read_text())) if f.exists() else DEFAULT_WINDOWS
