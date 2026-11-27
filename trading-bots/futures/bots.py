"""Futures bots for NQ/MNQ and ES/MES, on 1-minute bars of the regular session
(09:30-16:00 New York) unless stated. Each returns a Result via engine.to_result.

Sources for each rule are in the docstrings. Signals use only bars that have
closed; entries are at the next bar's open or at a resting stop/limit price.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from engine import data as Y
from . import mdata as D
from .engine import to_result, walk

T0 = pd.Timedelta(hours=9, minutes=30)
START = "2011-01-01"


@lru_cache(maxsize=4)
def session(sym):
    """Matrices (days x 390) for the regular session, NYSE days only."""
    nyse = set(Y.load("^GSPC").index)
    o = D.day_matrix(sym, "open"); h = D.day_matrix(sym, "high")
    l = D.day_matrix(sym, "low"); c = D.day_matrix(sym, "close")
    keep = [d for d in c.index if d in nyse and d >= pd.Timestamp(START) - pd.Timedelta(days=400)]
    o, h, l, c = (x.loc[keep] for x in (o, h, l, c))
    o = o.fillna(c.shift(1, axis=1)).bfill(axis=1)
    h = h.fillna(o); l = l.fillna(o); c = c.fillna(o)
    days = c.index
    daily = pd.DataFrame({"open": o[0], "high": h.max(axis=1), "low": l.min(axis=1), "close": c[389]}, index=days)
    return {"O": o.values, "H": h.values, "L": l.values, "C": c.values, "days": days, "daily": daily}


def _atr(daily, n=14):
    pc = daily["close"].shift(1)
    tr = pd.concat([daily["high"] - daily["low"], (daily["high"] - pc).abs(), (daily["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _t(day, m):  # time of the close of bar m
    return day + T0 + pd.Timedelta(minutes=int(m) + 1)


def _finish(rows, sym, s, cm):
    cols = ["entry_time", "exit_time", "side", "entry", "exit", "slipped"]
    t = pd.DataFrame(rows, columns=cols)
    days = s["days"][s["days"] >= pd.Timestamp(START)]
    return to_result(t, sym, days, cm)


# ------------------------------------------------------------- F01 noise band
def noise_band(p, cm=1.0, sym="NQ"):
    """Zarattini, Aziz & Barbon (2024) 'Beat the Market' intraday momentum.
    sigma(m) = mean over the last N days of |close(m)/open - 1|. Upper band =
    max(open, prev close) x (1 + k sigma), lower = min(open, prev close) x
    (1 - k sigma). Every `check` minutes from 10:00: long above the upper band,
    short below the lower; a long exits when price falls below max(upper band,
    VWAP) at a check (mirror for shorts); everything is flat at 16:00.
    HistData has no volume, so VWAP is the session's running mean of typical price."""
    s = session(sym)
    O, H, L, C, days = s["O"], s["H"], s["L"], s["C"], s["days"]
    mv = np.abs(C / O[:, [0]] - 1)
    sigma = pd.DataFrame(mv).rolling(p["lookback"]).mean().shift(1).values
    pc = np.r_[np.nan, C[:-1, 389]]
    up = np.maximum(O[:, 0], pc)[:, None] * (1 + p["k"] * sigma)
    dn = np.minimum(O[:, 0], pc)[:, None] * (1 - p["k"] * sigma)
    tp = (H + L + C) / 3
    vwap = np.cumsum(tp, axis=1) / np.arange(1, 391)
    checks = [m for m in range(29, 390) if (m + 1) % p["check"] == 0 and m < 389]
    rows = []
    for d in range(len(days)):
        if days[d] < pd.Timestamp(START) or np.isnan(sigma[d, 0]) or np.isnan(pc[d]):
            continue
        pos, ent, em = 0, 0.0, 0
        for m in checks:
            px = C[d, m]
            if pos == 1 and px < max(up[d, m], vwap[d, m]):
                rows.append((_t(days[d], em), _t(days[d], m), 1, ent, px, 2)); pos = 0
            elif pos == -1 and px > min(dn[d, m], vwap[d, m]):
                rows.append((_t(days[d], em), _t(days[d], m), -1, ent, px, 2)); pos = 0
            if pos == 0:
                if px > up[d, m] and (p["side"] != "short"):
                    pos, ent, em = 1, px, m
                elif px < dn[d, m] and (p["side"] != "long"):
                    pos, ent, em = -1, px, m
        if pos != 0:
            rows.append((_t(days[d], em), _t(days[d], 389), pos, ent, C[d, 389], 2))
    return _finish(rows, sym, s, cm)


# ------------------------------------------------------- F02 opening range breakout
def orb(p, cm=1.0, sym="NQ"):
    """Zarattini, Barbon & Aziz (2023) 'Can Day Trading Really Be Profitable?':
    trade in the direction of the first N-minute candle (skip a doji), enter at
    the next bar's open, stop at the opening range's other side (or 10% of the
    14-day ATR), target R x risk, else out at 16:00."""
    s = session(sym)
    O, H, L, C, days = s["O"], s["H"], s["L"], s["C"], s["days"]
    atr = _atr(s["daily"]).shift(1).values
    n = p["minutes"]
    rows = []
    for d in range(len(days)):
        if days[d] < pd.Timestamp(START) or np.isnan(atr[d]):
            continue
        o0, cn = O[d, 0], C[d, n - 1]
        if cn == o0:
            continue
        side = 1 if cn > o0 else -1
        if p["side"] == "long" and side < 0:
            continue
        ent = O[d, n]
        if p["stop"] == "range":
            stop = L[d, :n].min() if side > 0 else H[d, :n].max()
        else:
            stop = ent - side * 0.1 * atr[d]
        risk = abs(ent - stop)
        if risk <= 0:
            continue
        tgt = ent + side * p["R"] * risk if p["R"] > 0 else None
        i, px, why = walk(H[d], L[d], C[d], n, 389, side, stop, tgt)
        rows.append((_t(days[d], n - 1), _t(days[d], i), side, ent, px, 1 + (why != "target")))
    return _finish(rows, sym, s, cm)


# --------------------------------------------------------- F03 intraday momentum
def intraday_momentum(p, cm=1.0, sym="NQ"):
    """Gao, Han, Li & Zhou (2018, JFE) 'Market intraday momentum': the return
    from yesterday's close to 10:00 predicts the last half hour. Baltussen,
    Da, Lammers & Martens (2021, JFE): the rest-of-day return (yesterday's close
    to 15:30) is the stronger signal. Modes:
      first30        enter 15:30 in the direction of prev close -> 10:00
      first30_agree  same, and the 15:00-15:30 return must agree (known at 15:30)
      first30_1500   enter 15:00 in the direction of prev close -> 10:00
      restofday      enter 15:30 in the direction of prev close -> 15:30
    Out at 16:00. Optional minimum signal size in percent."""
    s = session(sym)
    O, C, days = s["O"], s["C"], s["days"]
    pc = np.r_[np.nan, C[:-1, 389]]
    mode = p["signal"]
    e = 330 if mode == "first30_1500" else 360
    rows = []
    for d in range(len(days)):
        if days[d] < pd.Timestamp(START) or np.isnan(pc[d]):
            continue
        r = (C[d, 359] / pc[d] - 1) if mode == "restofday" else (C[d, 29] / pc[d] - 1)
        if abs(r) < p["min_move"] / 100 or r == 0:
            continue
        side = 1 if r > 0 else -1
        if mode == "first30_agree" and np.sign(C[d, 359] - C[d, 329]) != side:
            continue
        rows.append((_t(days[d], e - 1), _t(days[d], 389), side, O[d, e], C[d, 389], 2))
    return _finish(rows, sym, s, cm)


# ------------------------------------------------------------ F04 overnight drift
def overnight(p, cm=1.0, sym="NQ"):
    """Buy at the 16:00 close, sell next morning (03:00 European-open drift per
    Boyarchenko, Larsen & Whelan 2023, or the 09:30 open). Optional filters:
    only after a down day, only above the 200-day average."""
    s = session(sym)
    O, C, days = s["O"], s["C"], s["days"]
    daily = s["daily"]
    sma = daily["close"].rolling(200).mean().values
    pc = np.r_[np.nan, C[:-1, 389]]
    mins = D.minutes(sym)["open"]
    rows = []
    for d in range(len(days) - 1):
        if days[d] < pd.Timestamp(START):
            continue
        c = C[d, 389]
        if p["down"] and not c < pc[d]:
            continue
        if p["trend"] and not c > sma[d]:
            continue
        nxt = days[d + 1]
        if p["exit"] == "09:30":
            xt, xp = nxt + T0, O[d + 1, 0]
        else:
            xt = nxt + pd.Timedelta(hours=3)
            j = mins.index.searchsorted(xt)
            if j >= len(mins) or mins.index[j] > xt + pd.Timedelta(minutes=30):
                continue
            xp = mins.iloc[j]
        rows.append((_t(days[d], 389), xt, 1, c, xp, 2))
    return _finish(rows, sym, s, cm)


# ------------------------------------------------------------ F05 daily FVG
NEWS = {pd.Timestamp(x) for x in (Path(__file__).with_name("news_days.txt").read_text().split())}


def daily_fvg(p, cm=1.0, sym="NQ"):
    """The earlier PA Lab survivor C-fair_value_gap-00364 (your daily FVG bot):
    at each futures daily close (17:00 ET) a 3-day fair value gap (low of the
    last day above the high of 3 days ago, or the mirror) of at least
    `min_gap` x daily ATR(14) gets a resting limit at the gap's near edge. Stop
    beyond the far edge plus 0.1 ATR, target R x risk. The order lives, and a
    filled trade is closed after, `hours` hours. One trade or order at a time.
    Gaps formed on CPI, jobs-report or FOMC days are skipped (from 2013)."""
    g = D.daily_globex(sym)
    g = g[g.index >= pd.Timestamp(START) - pd.Timedelta(days=60)]
    atr = _atr(g).shift(1)
    m = D.minutes(sym)
    mt, mh, ml, mc = m.index.values, m["high"].values, m["low"].values, m["close"].values
    tick = 0.25
    rows = []
    busy_until = pd.Timestamp("1900-01-01")
    for k in range(3, len(g)):
        day = g.index[k - 1]  # the day that just closed
        if day < pd.Timestamp(START):
            continue
        dec = day + pd.Timedelta(hours=18)  # after every bar of that futures day
        if dec < busy_until:
            continue
        if p["skip_news"] and day in NEWS:
            continue
        a = atr.iloc[k - 1]
        hi1, lo1, cl1 = g["high"].iloc[k - 1], g["low"].iloc[k - 1], g["close"].iloc[k - 1]
        hi3, lo3 = g["high"].iloc[k - 3], g["low"].iloc[k - 3]
        if np.isnan(a):
            continue
        if lo1 > hi3 and lo1 - hi3 >= p["min_gap"] * a and cl1 > lo1:
            side, near, stop = 1, lo1, hi3 - 0.1 * a
        elif hi1 < lo3 and lo3 - hi1 >= p["min_gap"] * a and cl1 < hi1:
            side, near, stop = -1, hi1, lo3 + 0.1 * a
        else:
            continue
        risk = abs(near - stop)
        tgt = near + side * p["R"] * risk
        end = dec + pd.Timedelta(hours=p["hours"])
        i0 = mt.searchsorted(np.datetime64(dec))
        i1 = mt.searchsorted(np.datetime64(end)) - 1
        if i1 <= i0:
            continue
        # wait for the limit: needs a trade 1 tick through
        lim = (ml[i0:i1 + 1] <= near - tick) if side > 0 else (mh[i0:i1 + 1] >= near + tick)
        hit = np.flatnonzero(lim)
        if len(hit) == 0:
            busy_until = end
            continue
        f = i0 + hit[0]
        i, px, why = walk(mh, ml, mc, f, i1, side, stop, tgt)
        rows.append((pd.Timestamp(mt[f]), pd.Timestamp(mt[i]), side, near, px, 0 + (why != "target")))
        busy_until = pd.Timestamp(mt[i])
    s = session(sym)
    return _finish(rows, sym, s, cm)


# ----------------------------------------------------- F06 IBS on futures (daily)
def _state(entry, exit_):
    st = np.zeros(len(entry)); prev = 0
    for i in range(len(entry)):
        st[i] = 1 if (prev == 0 and entry[i]) else (0 if (prev == 1 and exit_[i]) else prev)
        prev = st[i]
    return st


def _daily_trades(s, st, sym, cm, price="close"):
    daily = s["daily"]
    rows = []
    days = daily.index
    c = daily["close"].values
    i = 0
    while i < len(st):
        if st[i] == 1 and (i == 0 or st[i - 1] == 0):
            j = i
            while j + 1 < len(st) and st[j + 1] == 1:
                j += 1
            x = min(j + 1, len(st) - 1)
            rows.append((_t(days[i], 389), _t(days[x], 389), 1, c[i], c[x], 2))
            i = x + 1
        else:
            i += 1
    rows = [r for r in rows if r[0] >= pd.Timestamp(START)]
    return _finish(rows, sym, s, cm)


def ibs(p, cm=1.0, sym="NQ"):
    """Bot 07 from the systematic set, in contracts: buy at the 16:00 close when
    IBS = (close-low)/(high-low) < X, sell at a close above yesterday's high or
    IBS > 0.8. Futures hold overnight, so the gap counts."""
    s = session(sym)
    d = s["daily"]
    x = ((d["close"] - d["low"]) / (d["high"] - d["low"]).replace(0, np.nan)).fillna(0.5)
    entry = (x < p["thr"]).values.copy()
    if p["trend"]:
        entry &= (d["close"] > d["close"].rolling(200).mean()).values
    ex = ((d["close"] > d["high"].shift(1)) | (x > 0.8)).values
    return _daily_trades(s, _state(entry, ex), sym, cm)


def lower_band(p, cm=1.0, sym="NQ"):
    """Bot 12 in contracts (Quantitativo): close < (N-day high - k x 25-day mean
    range) and IBS < 0.3 -> buy the close; sell a close above yesterday's high."""
    s = session(sym)
    d = s["daily"]
    rng = (d["high"] - d["low"]).rolling(25).mean()
    band = d["high"].rolling(p["n"]).max() - p["k"] * rng
    x = ((d["close"] - d["low"]) / (d["high"] - d["low"]).replace(0, np.nan)).fillna(0.5)
    entry = ((d["close"] < band) & (x < 0.3)).values
    ex = (d["close"] > d["high"].shift(1)).values
    return _daily_trades(s, _state(entry, ex), sym, cm)


# ------------------------------------------------------------- F08 opening gap
def gap(p, cm=1.0, sym="NQ"):
    """Opening gap vs yesterday's 16:00 close, at least k x ATR(14). 'fade':
    trade back toward yesterday's close (target = that close, stop = the same
    distance the other way). 'go': trade with the gap, stop at yesterday's
    close. Out at 16:00 either way."""
    s = session(sym)
    O, H, L, C, days = s["O"], s["H"], s["L"], s["C"], s["days"]
    atr = _atr(s["daily"]).shift(1).values
    pc = np.r_[np.nan, C[:-1, 389]]
    rows = []
    for d in range(len(days)):
        if days[d] < pd.Timestamp(START) or np.isnan(atr[d]) or np.isnan(pc[d]):
            continue
        g = O[d, 0] - pc[d]
        if abs(g) < p["k"] * atr[d]:
            continue
        ent = O[d, 0]
        if p["mode"] == "fade":
            side = -int(np.sign(g)); tgt = pc[d]; stop = ent - side * abs(g)
        else:
            side = int(np.sign(g)); tgt = None; stop = pc[d]
        i, px, why = walk(H[d], L[d], C[d], 0, 389, side, stop, tgt)
        rows.append((days[d] + T0, _t(days[d], i), side, ent, px, 1 + (why != "target")))
    return _finish(rows, sym, s, cm)


# --------------------------------------------------------- F09 turn of the month
def turn_of_month(p, cm=1.0, sym="NQ"):
    """Bot 09 in contracts: long from the 16:00 close N trading days before
    month end to the close of trading day M of the new month."""
    s = session(sym)
    idx = s["daily"].index
    ym = idx.year * 100 + idx.month
    df = pd.DataFrame({"ym": ym}, index=idx)
    fwd = df.groupby("ym").cumcount() + 1
    bwd = -(df.groupby("ym").cumcount(ascending=False) + 1)
    st = ((bwd >= -p["before"]) | (fwd < p["after"])).astype(float).values
    return _daily_trades(s, st, sym, cm)


# ------------------------------------------------ F10 volatility breakout (Williams)
def vol_breakout(p, cm=1.0, sym="NQ"):
    """Larry Williams' volatility breakout: buy stop at open + k x yesterday's
    range, sell stop at open - k x range; the first one hit is the trade, out at
    16:00. Optional stop at the open."""
    s = session(sym)
    O, H, L, C, days = s["O"], s["H"], s["L"], s["C"], s["days"]
    d = s["daily"]
    rng = (d["high"] - d["low"]).shift(1).values
    rows = []
    for k in range(len(days)):
        if days[k] < pd.Timestamp(START) or np.isnan(rng[k]):
            continue
        o0 = O[k, 0]
        bu, bd = o0 + p["k"] * rng[k], o0 - p["k"] * rng[k]
        hu = np.flatnonzero(H[k] >= bu); hd = np.flatnonzero(L[k] <= bd)
        iu = hu[0] if len(hu) else 999
        idn = hd[0] if len(hd) and p["side"] == "both" else 999
        if iu == 999 and idn == 999:
            continue
        side, i0, ent = (1, iu, bu) if iu <= idn else (-1, idn, bd)
        stop = o0 if p["stop_at_open"] else None
        i, px, why = walk(H[k], L[k], C[k], i0 + 1, 389, side, stop, None) if i0 < 389 else (389, C[k, 389], "time")
        rows.append((_t(days[k], i0), _t(days[k], i), side, ent, px, 2))
    return _finish(rows, sym, s, cm)


REGISTRY = [
    dict(name="F01 Noise band", fn=noise_band,
         space={"k": [0.75, 1.0, 1.25, 1.5], "lookback": [10, 14, 20], "check": [15, 30, 60], "side": ["both"]},
         default={"k": 1.0, "lookback": 14, "check": 30, "side": "both"},
         notes="Zarattini-Aziz-Barbon (2024) noise area, every 30 min from 10:00, trailing exit at max(band, VWAP), flat at 16:00."),
    dict(name="F02 Opening range breakout", fn=orb,
         space={"minutes": [5, 15, 30], "R": [0, 1, 2, 5, 10], "stop": ["range", "atr10"], "side": ["both"]},
         default={"minutes": 5, "R": 10, "stop": "range", "side": "both"},
         notes="Zarattini-Barbon-Aziz (2023) ORB: direction of the first candle, stop at the range, 10R or 16:00."),
    dict(name="F03 Intraday momentum", fn=intraday_momentum,
         space={"signal": ["first30", "first30_agree", "first30_1500", "restofday"], "min_move": [0.0, 0.25, 0.5]},
         default={"signal": "first30", "min_move": 0.0},
         notes="Gao-Han-Li-Zhou (2018) / Baltussen et al (2021): the day's return so far sets the direction of the last half hour."),
    dict(name="F04 Overnight drift", fn=overnight,
         space={"down": [False, True], "trend": [False, True], "exit": ["03:00", "09:30"]},
         default={"down": False, "trend": False, "exit": "09:30"},
         notes="Buy the 16:00 close, sell at 03:00 or 09:30 (Boyarchenko-Larsen-Whelan 2023 overnight drift)."),
    dict(name="F05 Daily fair value gap", fn=daily_fvg,
         space={"R": [1.5, 2.0, 3.0, 4.0], "hours": [48, 96, 168], "min_gap": [0.1, 0.25], "skip_news": [True]},
         default={"R": 3.0, "hours": 96, "min_gap": 0.1, "skip_news": True},
         notes="Your PA Lab daily FVG (C-fair_value_gap-00364): limit at the gap edge, stop beyond the far edge + 0.1 ATR, 3R, 96 hours."),
    dict(name="F06 IBS dip buy", fn=ibs,
         space={"thr": [0.1, 0.15, 0.2, 0.25, 0.3], "trend": [False, True]},
         default={"thr": 0.2, "trend": False},
         notes="IBS < X at the close, out above yesterday's high or IBS > 0.8 (Pagonidis 2013), held overnight in futures."),
    dict(name="F07 Lower band IBS", fn=lower_band,
         space={"n": [5, 10, 20], "k": [2.0, 2.5, 3.0]}, default={"n": 10, "k": 2.5},
         notes="Quantitativo lower band + IBS < 0.3, out above yesterday's high."),
    dict(name="F08 Opening gap", fn=gap,
         space={"k": [0.1, 0.25, 0.5], "mode": ["fade", "go"]}, default={"k": 0.25, "mode": "fade"},
         notes="Fade (or follow) an opening gap of at least k x ATR; fade targets yesterday's close."),
    dict(name="F09 Turn of the month", fn=turn_of_month,
         space={"before": [1, 2, 3, 4, 5], "after": [1, 2, 3, 4, 5]}, default={"before": 1, "after": 3},
         notes="Long from N days before month end to day M of the next month (Lakonishok-Smidt, McConnell-Xu)."),
    dict(name="F10 Volatility breakout", fn=vol_breakout,
         space={"k": [0.25, 0.5, 0.75, 1.0], "side": ["both", "long"], "stop_at_open": [False, True]},
         default={"k": 0.5, "side": "both", "stop_at_open": False},
         notes="Larry Williams: stop orders at open +/- k x yesterday's range, out at 16:00."),
]

# ------------------------------------------------------------- F11 VWAP trend
def vwap_trend(p, cm=1.0, sym="NQ"):
    """Zarattini & Aziz (2023) 'VWAP: the Holy Grail for day trading systems':
    from 09:31, long when the 1-minute close is above the session VWAP, short
    below; reverse on a close on the other side; flat at 16:00. HistData has no
    volume, so 'VWAP' here is the running mean of typical price (a TWAP), which
    is a real difference. `confirm` = minutes on the other side before reversing,
    to cut the ~15 flips a day the paper's version makes."""
    s = session(sym)
    O, H, L, C, days = s["O"], s["H"], s["L"], s["C"], s["days"]
    tp = (H + L + C) / 3
    vw = np.cumsum(tp, axis=1) / np.arange(1, 391)
    rows = []
    k = p["confirm"]
    for d in range(len(days)):
        if days[d] < pd.Timestamp(START):
            continue
        above = C[d] > vw[d]
        pos, ent, em, run = 0, 0.0, 0, 0
        for m in range(p["start"], 389):
            want = 1 if above[m] else -1
            if p["side"] == "long" and want < 0:
                want = 0
            if want == pos:
                run = 0
                continue
            run += 1
            if run < k:
                continue
            if pos != 0:
                rows.append((_t(days[d], em), _t(days[d], m), pos, ent, C[d, m], 2))
            pos, ent, em, run = want, C[d, m], m, 0
            if pos == 0:
                continue
        if pos != 0:
            rows.append((_t(days[d], em), _t(days[d], 389), pos, ent, C[d, 389], 2))
    return _finish(rows, sym, s, cm)


# ------------------------------------------------------- F12 Turnaround Tuesday
def turnaround_tuesday(p, cm=1.0, sym="NQ"):
    """Buy Monday's 16:00 close when Monday fell at least X% (vs Friday's close),
    sell at Tuesday's close (or hold to Wednesday's close)."""
    s = session(sym)
    d = s["daily"]
    c = d["close"]
    r = c.pct_change()
    rows = []
    idx = d.index
    for i in range(1, len(idx) - 2):
        if idx[i] < pd.Timestamp(START) or idx[i].dayofweek != 0:
            continue
        if r.iloc[i] > -p["drop"] / 100:
            continue
        j = i + p["hold"]
        rows.append((_t(idx[i], 389), _t(idx[j], 389), 1, c.iloc[i], c.iloc[j], 2))
    return _finish(rows, sym, s, cm)


REGISTRY += [
    dict(name="F11 VWAP trend", fn=vwap_trend,
         space={"confirm": [1, 5, 15], "start": [1, 30], "side": ["both", "long"]},
         default={"confirm": 1, "start": 1, "side": "both"},
         notes="Zarattini-Aziz (2023) VWAP trend, always in from 09:31, reverse on a close across VWAP (TWAP stand-in)."),
    dict(name="F12 Turnaround Tuesday", fn=turnaround_tuesday,
         space={"drop": [0.0, 0.5, 1.0, 1.5], "hold": [1, 2]}, default={"drop": 0.0, "hold": 1},
         notes="Buy Monday's close after a down Monday, sell Tuesday's close."),
]
