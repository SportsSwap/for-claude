"""One market's discovery data, ready for detectors and the engine.

Market.load("NQ") reads data/clean (warm-up + discovery only; the guard
blocks anything later) and builds, once, every chart with ATR plus the maps
the engine needs between a chart bar and the 1-minute bar it closes on.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import charts as ch
from . import io
from .atr import atr_prior
from .config import P, load_windows
from .rolls import add_roll_flags

SPEC = {"NQ": {"tick": 0.25, "point_value": 20.0}, "ES": {"tick": 0.25, "point_value": 50.0}}
COMMISSION_RT = 4.0


def instrument_spec(name: str) -> dict | None:
    """Per-lab override of tick, point value, commission and trade size:
    data/instrument_spec.json, e.g. {"NQ": {"tick": 0.01, "point_value": 1, "commission_rt": 0,
    "notional": 10000, "label": "TQQQ"}}. Absent: the futures defaults above."""
    path = P.data() / "instrument_spec.json"
    if not path.exists():
        return None
    return io.read_json(path).get(name)


@dataclass
class Chart:
    name: str
    df: pd.DataFrame
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    atr: np.ndarray
    avail_ns: np.ndarray      # int64 ns, bar usable from here
    open_ns: np.ndarray
    last_1m: np.ndarray       # index of the 1m bar whose close closes this bar
    session: np.ndarray       # session ordinal


@dataclass
class Market:
    name: str
    tick: float
    pv: float
    m1: pd.DataFrame
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    ts_ns: np.ndarray
    et_min: np.ndarray        # ET minute of day of the bar open
    sess: np.ndarray          # session ordinal per 1m bar
    sessions: np.ndarray      # session dates (ordinal -> date)
    tradable: np.ndarray      # per session: discovery (not warm-up)
    no_entry: np.ndarray      # roll blackout per 1m bar
    roll_exit_idx: np.ndarray  # sorted 1m indices of forced roll exits
    flat1600_idx: np.ndarray  # per session: last 1m bar opening before 16:00 ET (-1 if none)
    news: np.ndarray          # per session: news day
    era: np.ndarray           # per session: 1 / 2 / 0 (warm-up)
    charts: dict = field(default_factory=dict)
    commission_rt: float = COMMISSION_RT   # per unit of size, round trip
    notional: float = 0.0                  # >0: size each trade to this many dollars (ETFs)

    @property
    def n(self) -> int:
        return len(self.c)

    @staticmethod
    def from_frames(name: str, m1: pd.DataFrame, rolls: pd.DataFrame, news_days=frozenset(),
                    warmup_end: dt.date | None = None, era2_start: dt.date | None = None,
                    tick=None, pv=None) -> "Market":
        m1 = m1.sort_values("ts_event").reset_index(drop=True)
        m1["ts_event"] = pd.to_datetime(m1["ts_event"], utc=True)
        sess_dates = np.array(sorted(set(m1["session"])))
        sess_ord = {d: i for i, d in enumerate(sess_dates)}
        sess = m1["session"].map(sess_ord).to_numpy(np.int64)
        et = m1["ts_event"].dt.tz_convert("America/New_York")
        et_min = (et.dt.hour * 60 + et.dt.minute).to_numpy(np.int64)
        f = add_roll_flags(m1[["ts_event"]], rolls, 60) if len(rolls) else None
        no_entry = f["roll_no_entry"].to_numpy(bool) if f is not None else np.zeros(len(m1), bool)
        roll_exit = np.flatnonzero(f["roll_force_exit"].to_numpy()) if f is not None else np.zeros(0, np.int64)
        # last bar before 16:00 ET in each session
        before16 = (et_min < 16 * 60) | (et_min >= 18 * 60)  # evening bars come before 16:00 too
        idx = np.arange(len(m1))
        flat = np.full(len(sess_dates), -1, np.int64)
        s_b = pd.Series(idx[before16]).groupby(sess[before16]).max()
        flat[s_b.index.to_numpy()] = s_b.to_numpy()
        tradable = np.array([warmup_end is None or d > warmup_end for d in sess_dates])
        era = np.array([0 if not t else (2 if era2_start and d >= era2_start else 1)
                        for d, t in zip(sess_dates, tradable)])
        news = np.array([d in news_days for d in sess_dates])
        spec = instrument_spec(name) or SPEC.get(name, {"tick": 0.25, "point_value": 1.0})
        mk = Market(name, tick or spec["tick"], pv or spec["point_value"], m1,
                    m1["open"].to_numpy(float), m1["high"].to_numpy(float), m1["low"].to_numpy(float),
                    m1["close"].to_numpy(float), m1["ts_event"].dt.as_unit("ns").astype("int64").to_numpy(),
                    et_min, sess, sess_dates, tradable, no_entry, roll_exit, flat, news, era)
        mk.commission_rt = float(spec.get("commission_rt", COMMISSION_RT))
        mk.notional = float(spec.get("notional", 0.0))
        for name_ in ch.ORDER:
            mk.charts[name_] = mk._chart(name_)
        return mk

    def _chart(self, name: str) -> Chart:
        df = ch.build(self.m1, name)
        df["atr"] = atr_prior(df, 14).to_numpy()
        avail = df["ts_avail"].dt.as_unit("ns").astype("int64").to_numpy()
        opn = df["ts_open"].dt.as_unit("ns").astype("int64").to_numpy()
        last = np.searchsorted(self.ts_ns, avail, side="left") - 1
        sess_ord = {d: i for i, d in enumerate(self.sessions)}
        return Chart(name, df, df["open"].to_numpy(float), df["high"].to_numpy(float),
                     df["low"].to_numpy(float), df["close"].to_numpy(float), df["atr"].to_numpy(float),
                     avail, opn, last.astype(np.int64), df["session"].map(sess_ord).to_numpy(np.int64))

    @staticmethod
    def load(name: str) -> "Market":
        from .news import news_days
        w = load_windows()
        m1 = io.read_table(P.clean() / f"{name}_1m.parquet")
        m1 = m1[m1["session"] <= w.discovery[1]]
        rolls = io.read_table(P.clean() / f"{name}_rolls.parquet")
        try:
            nd = news_days()          # official dates only; unverified rows stop the lab
        except FileNotFoundError:
            nd = set()
        return Market.from_frames(name, m1, rolls, frozenset(nd), w.warmup[1], w.era2[0])

    def cut(self, n_1m: int) -> "Market":
        """The same market with only the first n_1m one-minute bars (for look-ahead tests)."""
        m1 = self.m1.iloc[:n_1m].copy()
        rolls = pd.DataFrame({"roll_time_utc": pd.to_datetime(
            self.ts_ns[np.r_[self.roll_exit_idx + 1][self.roll_exit_idx + 1 < self.n]], utc=True)})
        rolls = rolls.assign(old_contract="a", new_contract="b", spread=0.0)
        return Market.from_frames(self.name, m1, rolls, frozenset(self.sessions[self.news]),
                                  self.sessions[~self.tradable].max() if (~self.tradable).any() else None,
                                  self.sessions[self.era == 2].min() if (self.era == 2).any() else None,
                                  self.tick, self.pv)
