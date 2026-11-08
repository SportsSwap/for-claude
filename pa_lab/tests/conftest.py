import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from lab.config import Windows  # noqa: E402

D = dt.date
SMALL_WINDOWS = Windows(
    warmup=(D(2021, 10, 1), D(2021, 10, 8)),
    discovery=(D(2021, 10, 11), D(2021, 11, 5)),
    era1=(D(2021, 10, 11), D(2021, 10, 22)),
    era2=(D(2021, 10, 25), D(2021, 11, 5)),
    final=(D(2021, 11, 8), D(2021, 12, 17)),
)


@pytest.fixture
def lab_root(tmp_path, monkeypatch):
    """A throwaway lab with the small windows; no unlock in the environment."""
    monkeypatch.setenv("LAB_ROOT", str(tmp_path))
    monkeypatch.delenv("LAB_UNLOCK", raising=False)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "windows.json").write_text(json.dumps(SMALL_WINDOWS.to_json()))
    return tmp_path


@pytest.fixture(scope="session")
def small_input(tmp_path_factory):
    """Synthetic files, Oct 1 - Dec 17 2021 (one roll, Dec 8), with defects, in the real input format."""
    import make_synthetic
    out = tmp_path_factory.mktemp("input")
    make_synthetic.main(["--out", str(out), "--start", "2021-10-01", "--end", "2021-12-17", "--defects"])
    return out


def minute_bars(start_utc: str, n: int, price=100.0, session=None):
    ts = pd.date_range(start_utc, periods=n, freq="1min", tz="UTC")
    df = pd.DataFrame({"ts_event": ts, "open": price, "high": price + 1, "low": price - 1,
                       "close": price, "volume": 10, "contract": "X"})
    return df
