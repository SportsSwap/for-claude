"""Noise-band strategy: the lab's decisions, one 1-minute bar at a time. No broker code here.

The same rules as scripts/noise_band_search.py (decisions.md D64-D71), written so a live bot can
call it bar by bar. scripts/bot_replay_check.py proves it takes exactly the lab's trades.

Minute index k: 0 = the bar opening 09:30 New York, 389 = the bar opening 15:59.
A decision on bar k is made at that bar's close (k + 1 minutes after 09:30).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

RTH = 390          # regular-hours minute bars, 09:30 .. 15:59
OR_END = 15        # bars 0..14 make the opening range (09:30-09:45)
LAST_CHECK = 269   # the bar that closes at 14:00
EXIT_BAR = 374     # the bar that closes at 15:45
MIN_BARS = 370     # a day with fewer real bars is not kept as history (as the lab)
HISTORY_DAYS = 21  # kept days needed before trading (20 for the band, 21 as the lab's warm-up)

VERSIONS = {
    # picked on 2013-Sep 2021 only; held on 2022-Jul 2024 and Aug 2024-Nov 2026 (D66-D71)
    "best": dict(band_mult=1.25, band_days=20, or_offset_atr=0.15, vwap_filter=False, interval=30,
                 exit_on_vwap=True, stop_atr=0.5, trail_trigger_atr=None, giveback=0.5),
    # the post's rules as written (the 4 ATR / 10 ATR exits practically never trigger)
    "as_written": dict(band_mult=1.25, band_days=20, or_offset_atr=0.3, vwap_filter=True, interval=10,
                       exit_on_vwap=False, stop_atr=10.0, trail_trigger_atr=4.0, giveback=0.5),
}


@dataclass
class Position:
    side: int            # +1 long, -1 short
    entry_k: int
    entry_ref: float     # the signal bar's close (the lab measures moves from here)
    atr: float
    best: float = 0.0    # best favourable move so far, in points


@dataclass
class KeptDay:
    dist: list           # |close / open - 1| for every minute, forward-filled
    high: float
    low: float
    close: float


class NoiseBand:
    def __init__(self, version: str = "best"):
        if version not in VERSIONS:
            raise ValueError(f"version must be one of {list(VERSIONS)}")
        self.version = version
        self.p = VERSIONS[version]
        self.checks = set(range(29, LAST_CHECK + 1, self.p["interval"]))
        self.hist: deque[KeptDay] = deque(maxlen=self.p["band_days"])
        self.trs: deque[float] = deque(maxlen=5)
        self.n_kept = 0
        self.prev_close: float | None = None
        self.day = None
        self._new_day_state()

    # ------------------------------------------------------------------ day bookkeeping
    def _new_day_state(self):
        self.day_open = None
        self.last_k = -1
        self.real_bars = 0
        self.real_k = set()
        self.ok_start = False
        self.C = [None] * RTH
        self.dist = [None] * RTH
        self.vwap = [None] * RTH
        self.hi = self.lo = None
        self.orh = self.orl = None
        self.cum_pv = self.cum_v = self.cum_tp = 0.0
        self.traded = False
        self.pos: Position | None = None
        self.blocked = False          # set by the caller to stop new entries today

    def start_day(self, day):
        """Call before the first bar of a new trading day (closes the previous day first)."""
        if self.day is not None:
            self.finish_day()
        self.day = day
        self._new_day_state()

    def finish_day(self):
        """Keep the finished day as history when it is complete enough (same test as the lab)."""
        if self.day is None:
            return
        keep = self.ok_start and self.real_bars >= MIN_BARS and EXIT_BAR in self.real_k
        if keep:
            last = self.C[self.last_k]
            for k in range(self.last_k + 1, RTH):          # trailing minutes keep the last close
                self._fill(k, last)
            tr = (self.hi - self.lo) if self.prev_close is None else \
                max(self.hi, self.prev_close) - min(self.lo, self.prev_close)
            self.trs.append(tr)
            self.hist.append(KeptDay(list(self.dist), self.hi, self.lo, self.C[RTH - 1]))
            self.prev_close = self.C[RTH - 1]
            self.n_kept += 1
        self.day = None

    def _fill(self, k, c):
        self.C[k] = c
        self.dist[k] = abs(c / self.day_open - 1)

    # ------------------------------------------------------------------ features for today
    def atr(self):
        return sum(self.trs) / 5 if len(self.trs) == 5 else None

    def sigma(self, k):
        n = self.p["band_days"]
        if len(self.hist) < n:
            return None
        return sum(d.dist[k] for d in self.hist) / n

    def ready(self):
        return (self.ok_start and self.n_kept >= HISTORY_DAYS and self.atr() is not None
                and self.prev_close is not None)

    # ------------------------------------------------------------------ the bar handler
    def on_bar(self, k: int, o: float, h: float, l: float, c: float, v: float) -> list[dict]:
        """Feed one completed 1-minute bar of today. Returns actions:
        {"type": "enter", "side": +1/-1, "k": k, "price": close, ...} or
        {"type": "exit", "reason": ..., "k": k, "price": close}."""
        if k < 0 or k >= RTH or k <= self.last_k:
            return []
        actions = []
        if self.day_open is None:
            self.ok_start = (k == 0)
            self.day_open = o
        # minutes with no bar: the lab forward-fills the last close (no volume)
        if self.last_k >= 0:
            lc = self.C[self.last_k]
            for kk in range(self.last_k + 1, k):
                actions += self._process(kk, lc, lc, lc, lc, 0.0)
        actions += self._process(k, o, h, l, c, v)
        self.real_bars += 1
        self.real_k.add(k)
        return actions

    def _process(self, k, o, h, l, c, v):
        self.last_k = k
        self._fill(k, c)
        self.hi = h if self.hi is None else max(self.hi, h)
        self.lo = l if self.lo is None else min(self.lo, l)
        if k < OR_END:
            self.orh = h if self.orh is None else max(self.orh, h)
            self.orl = l if self.orl is None else min(self.orl, l)
        tp = (h + l + c) / 3
        self.cum_pv += tp * v
        self.cum_v += v
        self.cum_tp += tp
        self.vwap[k] = self.cum_pv / self.cum_v if self.cum_v > 0 else self.cum_tp / (k + 1)
        if self.pos is not None:
            return self._exit_check(k, c)
        if (not self.traded and not self.blocked and k in self.checks and self.ready()):
            return self._entry_check(k, c)
        return []

    def _entry_check(self, k, c):
        p, atr, s = self.p, self.atr(), self.sigma(k) * self.p["band_mult"]
        up = max(self.day_open, self.prev_close) * (1 + s)
        dn = min(self.day_open, self.prev_close) * (1 - s)
        long_ = c > self.orh + p["or_offset_atr"] * atr and c > up
        short = c < self.orl - p["or_offset_atr"] * atr and c < dn
        if p["vwap_filter"]:
            long_ = long_ and c > self.vwap[k]
            short = short and c < self.vwap[k]
        if not (long_ or short):
            return []
        side = 1 if long_ else -1
        self.traded = True
        self.pos = Position(side, k, c, atr)
        return [{"type": "enter", "side": side, "k": k, "price": c, "atr": atr, "upper": up, "lower": dn,
                 "vwap": self.vwap[k], "orh": self.orh, "orl": self.orl}]

    def _exit_check(self, k, c):
        p, pos = self.p, self.pos
        move = pos.side * (c - pos.entry_ref)
        pos.best = max(pos.best, move)
        reason = None
        if p["exit_on_vwap"] and pos.side * (c - self.vwap[k]) < 0:
            reason = "crossed VWAP"
        if p["stop_atr"] is not None and move <= -p["stop_atr"] * pos.atr:
            reason = reason or "stop"
        if (p["trail_trigger_atr"] is not None and pos.best >= p["trail_trigger_atr"] * pos.atr
                and move <= (1 - p["giveback"]) * pos.best):
            reason = reason or "gave back half"
        if reason is None and k >= EXIT_BAR:
            reason = "15:45"
        if reason is None:
            return []
        self.pos = None
        return [{"type": "exit", "reason": reason, "k": k, "price": c}]

    # ------------------------------------------------------------------ restart support
    def drop_position(self):
        """Forget any position the strategy thinks it has (used after catching up on missed bars)."""
        self.pos = None
        self.traded = True

    def restore_position(self, side, entry_k, entry_ref, atr):
        """After a restart mid-trade: rebuild the position and replay its exit rules over the bars
        already seen today. Returns an exit action if the exit was missed while offline."""
        self.traded = True
        self.pos = Position(side, entry_k, entry_ref, atr)
        for k in range(entry_k + 1, self.last_k + 1):
            out = self._exit_check(k, self.C[k])
            if out:
                out[0]["reason"] = "missed while offline: " + out[0]["reason"]
                return out
        return []
