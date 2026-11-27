"""The 11 bots. Each one is a function (params, cost_mult) -> backtest.Result,
a parameter grid, the published/default setting, and the in-sample end date.

Costs per side (one-way), before the 2x stress test:
  big index ETFs (SPY, QQQ, IWM, DIA)        2 bps   (spread ~0.3-1 bp + slippage)
  other ETFs                                  4 bps
  SVXY                                        8 bps
  crypto (BTC, ETH)                          20 bps   (taker fee ~10 bps + spread/slippage)
  FX majors                                   1 bp    (IBKR IDEALPRO ~0.2 bp + ~0.3 pip spread)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine import backtest as B
from engine import data
from engine import indicators as I

INDEX_ETF = {"SPY", "QQQ", "IWM", "DIA"}


def cost_for(tickers, mult=1.0, crypto=False, fx=False):
    out = {}
    for t in tickers:
        if crypto:
            c = 20
        elif fx:
            c = 1
        elif t in INDEX_ETF:
            c = 2
        elif t == "SVXY":
            c = 8
        else:
            c = 4
        out[t] = c * mult
    return out


def bh(ticker, start=None):
    c = data.load(ticker)["close"]
    r = c.pct_change().fillna(0.0)
    return r.loc[start:] if start else r


def _monthly_hold(weights_me: pd.DataFrame, index) -> pd.DataFrame:
    """Weights decided on month-end rows, held until the next month end."""
    return weights_me.reindex(index).ffill().fillna(0.0)


# =========================================================== 01 Faber GTAA
GTAA = ["SPY", "EFA", "IEF", "VNQ", "DBC"]


def faber_gtaa(p, cm=1.0):
    tk = GTAA + ["SHY"]
    px = data.ohlc_panel(tk)
    c = px["close"]
    sma = c[GTAA].rolling(21 * p["months"]).mean()
    me = I.month_end_flags(c.index)
    on = (c[GTAA] > sma).astype(float)[me]
    w = on / len(GTAA)
    w["SHY"] = 1 - w.sum(axis=1)
    w = _monthly_hold(w, c.index)
    return B.run(px["open"], c, w, mode="open", cost_bps=cost_for(tk, cm))


# ================================================ 02 Time-series momentum
TSMOM = ["SPY", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD", "DBC", "VNQ"]


def tsmom(p, cm=1.0):
    tk = TSMOM + ["SHY"]
    px = data.ohlc_panel(tk)
    c = px["close"]
    look = p["lookback"]
    sig = (c[TSMOM] / c[TSMOM].shift(look) - 1 > 0).astype(float)
    vol = np.log(c[TSMOM]).diff().ewm(com=60, min_periods=60).std() * np.sqrt(252)
    raw = sig * (p["target_vol"] / len(TSMOM)) / vol
    gross = raw.sum(axis=1)
    raw = raw.div(np.maximum(gross, 1.0), axis=0)  # no leverage: cap at 100%
    reb = I.month_end_flags(c.index) if p["rebalance"] == "M" else \
        pd.Series(c.index.dayofweek, index=c.index).diff().lt(0).shift(-1, fill_value=True)
    w = raw[reb]
    w["SHY"] = 1 - w.sum(axis=1)
    w = w.reindex(c.index).ffill().fillna(0.0)
    return B.run(px["open"], c, w, mode="open", cost_bps=cost_for(tk, cm))


# ============================================= 03 Keller VAA (dual momentum)
VAA_OFF = ["SPY", "EFA", "EEM", "AGG"]
VAA_DEF = ["LQD", "IEF", "SHY"]


def _mom_score(cm_, kind):
    if kind == "13612W":
        return (12 * (cm_ / cm_.shift(1) - 1) + 4 * (cm_ / cm_.shift(3) - 1)
                + 2 * (cm_ / cm_.shift(6) - 1) + (cm_ / cm_.shift(12) - 1))
    return cm_ / cm_.shift(12) - 1


def vaa(p, cm=1.0):
    tk = VAA_OFF + VAA_DEF
    px = data.ohlc_panel(tk)
    c = px["close"]
    mc = I.resample_month_end(c)
    sc = _mom_score(mc, p["score"])
    w = pd.DataFrame(0.0, index=mc.index, columns=tk)
    for d in mc.index:
        s = sc.loc[d]
        if s[VAA_OFF].isna().any():
            continue
        bad = (s[VAA_OFF] <= 0).sum()
        if bad >= p["breadth"]:
            pick = s[VAA_DEF].sort_values(ascending=False).index[:1]
        else:
            pick = s[VAA_OFF].sort_values(ascending=False).index[:p["top"]]
        w.loc[d, pick] = 1.0 / len(pick)
    w = _monthly_hold(w, c.index)
    return B.run(px["open"], c, w, mode="open", cost_bps=cost_for(tk, cm))


# ======================================== 04 Crypto Donchian trend ensemble
LOOKS = {"short": [5, 10, 20, 30, 60], "all": [5, 10, 20, 30, 60, 90, 150, 250, 360],
         "long": [30, 60, 90, 150, 250, 360]}


def donchian_state(df, n):
    hi = df["high"].rolling(n).max().shift(1)
    lo = df["low"].rolling(max(2, n // 2)).min().shift(1)
    c = df["close"].values
    st = np.zeros(len(df))
    h, l = hi.values, lo.values
    for i in range(1, len(df)):
        prev = st[i - 1]
        if prev == 0 and not np.isnan(h[i]) and c[i] > h[i]:
            st[i] = 1
        elif prev == 1 and not np.isnan(l[i]) and c[i] < l[i]:
            st[i] = 0
        else:
            st[i] = prev
    return pd.Series(st, index=df.index)


def crypto_trend(p, cm=1.0, ticker="BTC-USD"):
    df = data.load(ticker)
    sig = pd.concat([donchian_state(df, n) for n in LOOKS[p["looks"]]], axis=1).mean(axis=1)
    if p["target_vol"] > 0:
        vol = I.realized_vol(df["close"], 90, 365)
        size = (p["target_vol"] / vol).clip(upper=1.0)
    else:
        size = 1.0
    w = (sig * size).fillna(0.0)
    w = w.round(2)  # avoid paying costs for tiny daily resizes
    return B.run(df["open"].rename(ticker), df["close"].rename(ticker), w.rename(ticker),
                 mode="open", cost_bps=20 * cm)


# =========================================== 05 VIX term structure (SVXY)
def vix_carry(p, cm=1.0):
    sv = data.load("SVXY")
    vix = data.load("^VIX")["close"].reindex(sv.index).ffill()
    v3 = data.load("^VIX3M")["close"].reindex(sv.index).ffill()
    spy = data.load("SPY")["close"].reindex(sv.index).ffill()
    ratio = (vix / v3).rolling(p["smooth"]).mean()
    sig = (ratio < p["thr"]).astype(float)
    if p["vrp"]:
        rv = I.realized_vol(spy, 10) * 100
        sig = sig * (vix > rv).astype(float)
    w = sig * p["size"]
    return B.run(sv["open"].rename("SVXY"), sv["close"].rename("SVXY"), w.rename("SVXY"),
                 mode="open", cost_bps=8 * cm)


# ======================================== 06 Connors RSI(2) on index ETFs
MR_UNI = ["SPY", "QQQ", "IWM", "DIA"]


def _basket(sig: pd.DataFrame) -> pd.DataFrame:
    n = sig.sum(axis=1)
    return sig.div(np.maximum(n, 1.0), axis=0)


def _state(entry: pd.Series, exit_: pd.Series) -> pd.Series:
    st = np.zeros(len(entry))
    e, x = entry.values, exit_.values
    for i in range(len(entry)):
        prev = st[i - 1] if i else 0
        st[i] = 1 if (prev == 0 and e[i]) else (0 if (prev == 1 and x[i]) else prev)
    return pd.Series(st, index=entry.index)


def connors_rsi2(p, cm=1.0, universe=MR_UNI):
    px = data.ohlc_panel(universe)
    c = px["close"]
    sig = {}
    for t in universe:
        r = I.rsi(c[t], 2)
        trend = c[t] > I.sma(c[t], 200)
        entry = (r < p["entry"]) & trend
        if p["exit"] == "sma5":
            ex = c[t] > I.sma(c[t], 5)
        else:
            ex = r > 70
        sig[t] = _state(entry, ex)
    w = _basket(pd.DataFrame(sig))
    return B.run(px["open"], c, w, mode="close", cost_bps=cost_for(universe, cm))


# ================================================ 07 IBS mean reversion
def ibs_mr(p, cm=1.0, universe=MR_UNI):
    px = data.ohlc_panel(universe)
    c, h, l = px["close"], px["high"], px["low"]
    sig = {}
    for t in universe:
        x = I.ibs(h[t], l[t], c[t])
        entry = x < p["thr"]
        if p["trend"]:
            entry &= c[t] > I.sma(c[t], 200)
        ex = (c[t] > h[t].shift(1)) | (x > 0.8)
        sig[t] = _state(entry, ex)
    w = _basket(pd.DataFrame(sig))
    return B.run(px["open"], c, w, mode="close", cost_bps=cost_for(universe, cm))


# ======================================== 08 Overnight after down days
def overnight_dip(p, cm=1.0, universe=("SPY", "QQQ")):
    universe = list(universe)
    px = data.ohlc_panel(universe)
    c = px["close"]
    sig = {}
    for t in universe:
        down = (c[t] < c[t].shift(1)).astype(int)
        streak = down.groupby((down == 0).cumsum()).cumsum()
        s = streak >= p["down_days"]
        if p["trend"]:
            s &= c[t] > I.sma(c[t], 200)
        sig[t] = s.astype(float)
    w = _basket(pd.DataFrame(sig))
    return B.run(px["open"], c, w, mode="overnight", cost_bps=cost_for(universe, cm))


# ============================================== 09 Turn of the month
def turn_of_month(p, cm=1.0, ticker="SPY"):
    df = data.load(ticker)
    fwd, bwd = I.trading_day_of_month(df.index)
    # signal at close of day d -> held close d to close d+1 (mode close)
    # hold from close of day -N through close of day +M
    s = (bwd >= -p["before"]) | (fwd < p["after"])
    w = s.astype(float)
    return B.run(df["open"].rename(ticker), df["close"].rename(ticker), w.rename(ticker),
                 mode="close", cost_bps=2 * cm)


# =========================================== 10 Sector momentum rotation
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]


def sector_rotation(p, cm=1.0):
    tk = SECTORS + ["SPY", "IEF"]
    px = data.ohlc_panel(tk)
    c = px["close"]
    mc = I.resample_month_end(c)
    mom = mc[SECTORS] / mc[SECTORS].shift(p["months"]) - 1
    spy_up = mc["SPY"] > c["SPY"].rolling(200).mean().reindex(mc.index)
    w = pd.DataFrame(0.0, index=mc.index, columns=tk)
    for d in mc.index:
        m = mom.loc[d]
        if m.isna().any():
            continue
        if p["filter"] and not spy_up.loc[d]:
            w.loc[d, "IEF"] = 1.0
            continue
        top = m.sort_values(ascending=False).index[:p["top"]]
        w.loc[d, top] = 1.0 / p["top"]
    w = _monthly_hold(w, c.index)
    return B.run(px["open"], c, w, mode="open", cost_bps=cost_for(tk, cm))


# ============================================== 11 FX trend (majors)
FX = {"EURUSD=X": 1, "GBPUSD=X": 1, "AUDUSD=X": 1, "NZDUSD=X": 1,
      "JPY=X": -1, "CAD=X": -1, "CHF=X": -1}  # -1: quoted USDxxx, invert to xxxUSD


def fx_trend(p, cm=1.0):
    tk = list(FX)
    px = data.ohlc_panel(tk)
    o, c = px["open"].copy(), px["close"].copy()
    for t, sgn in FX.items():
        if sgn < 0:  # express every pair as foreign currency in USD
            o[t], c[t] = 1 / o[t], 1 / c[t]
    sig = np.sign(c - c.rolling(p["sma"]).mean())
    if not p["short"]:
        sig = sig.clip(lower=0)
    vol = np.log(c).diff().ewm(com=60, min_periods=60).std() * np.sqrt(252)
    raw = sig * (p["target_vol"] / np.sqrt(len(tk))) / vol
    gross = raw.abs().sum(axis=1)
    raw = raw.div(np.maximum(gross / 2.0, 1.0), axis=0)  # cap gross at 200%
    fri = pd.Series(c.index.dayofweek == 4, index=c.index)
    w = raw[fri].reindex(c.index).ffill().fillna(0.0)
    return B.run(o, c, w, mode="open", cost_bps=cost_for(tk, cm, fx=True))


# ====================================================== registry
REGISTRY = [
    dict(name="01 Faber GTAA trend", fn=faber_gtaa,
         space={"months": [6, 8, 10, 12, 14]}, default={"months": 10},
         is_end="2014-12-31", bench="SPY",
         notes="5 ETFs (SPY EFA IEF VNQ DBC), 20% each when above its N-month SMA at month end, else SHY. Faber (2007/2013)."),
    dict(name="02 Time series momentum", fn=tsmom,
         space={"lookback": [42, 63, 126, 189, 252], "target_vol": [0.10, 0.15], "rebalance": ["W", "M"]},
         default={"lookback": 252, "target_vol": 0.10, "rebalance": "M"},
         is_end="2014-12-31", bench="SPY",
         notes="9 ETFs, long if trailing return > 0, inverse-volatility sized to a target, rest in SHY, no leverage. Moskowitz-Ooi-Pedersen (2012), Hurst-Ooi-Pedersen (2017)."),
    dict(name="03 Keller VAA dual momentum", fn=vaa,
         space={"score": ["13612W", "12m"], "breadth": [1, 2], "top": [1, 2]},
         default={"score": "13612W", "breadth": 1, "top": 1},
         is_end="2014-12-31", bench="SPY",
         notes="Offensive SPY EFA EEM AGG, defensive LQD IEF SHY, monthly. Keller & Keuning VAA-G4 (2017); 12m score = Antonacci-style dual momentum."),
    dict(name="04 Crypto Donchian trend BTC", fn=crypto_trend,
         space={"looks": ["short", "all", "long"], "target_vol": [0.0, 0.25, 0.4, 0.6]},
         default={"looks": "all", "target_vol": 0.25},
         is_end="2019-12-31", bench="BTC-USD",
         notes="Average of Donchian breakout states (enter above N-day high, exit below N/2-day low), volatility targeted, max 100%. After Zarattini-Pagani-Barbon (2025)."),
    dict(name="05 VIX term structure SVXY", fn=vix_carry,
         space={"thr": [0.85, 0.9, 0.95, 1.0], "smooth": [1, 3, 5, 10], "vrp": [False, True], "size": [1.0]},
         default={"thr": 0.95, "smooth": 1, "vrp": False, "size": 1.0},
         is_end="2016-12-31", bench="SPY",
         notes="Long SVXY when VIX/VIX3M < threshold (contango), optional VIX > 10d realised vol filter, else cash. Simon-Campasano (2014), Zarattini-Aziz-Mele (2025)."),
    dict(name="06 Connors RSI2 index ETFs", fn=connors_rsi2,
         space={"entry": [5, 10, 15, 20, 25], "exit": ["sma5", "rsi70"]},
         default={"entry": 10, "exit": "sma5"},
         is_end="2012-12-31", bench="SPY",
         notes="SPY QQQ IWM DIA: buy at the close when RSI(2) < X and close > 200d SMA, sell at the close above the 5d SMA. Connors & Alvarez (2008)."),
    dict(name="07 IBS mean reversion", fn=ibs_mr,
         space={"thr": [0.1, 0.15, 0.2, 0.25, 0.3], "trend": [False, True]},
         default={"thr": 0.2, "trend": False},
         is_end="2012-12-31", bench="SPY",
         notes="SPY QQQ IWM DIA: buy at the close when IBS < X, sell at a close above yesterday's high or IBS > 0.8. Pagonidis (2013)."),
    dict(name="08 Overnight after down days", fn=overnight_dip,
         space={"down_days": [1, 2, 3], "trend": [False, True]},
         default={"down_days": 1, "trend": True},
         is_end="2012-12-31", bench="SPY",
         notes="SPY QQQ: buy market-on-close after N down closes, sell at the next open. Overnight-return literature (Cooper-Cliff-Gulen 2008, Lou-Polk-Skouras 2019)."),
    dict(name="09 Turn of the month SPY", fn=turn_of_month,
         space={"before": [1, 2, 3, 4, 5], "after": [1, 2, 3, 4, 5]},
         default={"before": 1, "after": 3},
         is_end="2012-12-31", bench="SPY",
         notes="Hold SPY from the close N trading days before month end to the close of trading day M of the new month. Lakonishok-Smidt (1988), McConnell-Xu (2008)."),
    dict(name="10 Sector momentum rotation", fn=sector_rotation,
         space={"months": [3, 6, 9, 12], "top": [1, 2, 3, 4], "filter": [False, True]},
         default={"months": 6, "top": 3, "filter": True},
         is_end="2012-12-31", bench="SPY",
         notes="9 SPDR sectors, hold the top K by N-month return, monthly; IEF when SPY < 200d SMA. Moskowitz-Grinblatt (1999) industry momentum."),
    dict(name="11 FX trend majors", fn=fx_trend,
         space={"sma": [50, 100, 200, 300], "target_vol": [0.10], "short": [False, True]},
         default={"sma": 200, "target_vol": 0.10, "short": True},
         is_end="2014-12-31", bench=None,
         notes="7 USD majors, long/short vs N-day SMA, inverse-vol sized, weekly. Spot only: carry (interest differential) NOT included."),
]


# ================================= 12 Quantitativo lower band + IBS (SPY/QQQ)
def band_ibs(p, cm=1.0, universe=("SPY", "QQQ")):
    """Buy at the close when close < (N-day high - k * 25-day mean range) and
    IBS < 0.3; sell at a close above yesterday's high. Rules as published on
    quantitativo.substack.com ("A mean reversion strategy with 2.11 Sharpe")."""
    universe = list(universe)
    px = data.ohlc_panel(universe)
    c, h, l = px["close"], px["high"], px["low"]
    sig = {}
    for t in universe:
        rng = (h[t] - l[t]).rolling(25).mean()
        band = h[t].rolling(p["n"]).max() - p["k"] * rng
        entry = (c[t] < band) & (I.ibs(h[t], l[t], c[t]) < p["ibs"])
        ex = c[t] > h[t].shift(1)
        sig[t] = _state(entry, ex)
    w = _basket(pd.DataFrame(sig))
    return B.run(px["open"], c, w, mode="close", cost_bps=cost_for(universe, cm))


# ======================== 13 The user's MACD 12/144/9 dip rule (daily bars)
MACD_UNI = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "AVGO", "NFLX", "MU", "ORCL"]


def macd_dip(p, cm=1.0, universe=MACD_UNI):
    """From the earlier '$20 challenge' sessions: buy when MACD(12,slow,9)
    crosses above its signal while below zero and close > 200-day EMA; exit
    on a cross back down, a close below entry - 3 ATR, or after 15 days.
    Tested here on DAILY bars (the sessions used 2h/4h, which Yahoo only has
    for 2 years). Stock list = today's big names: survivorship bias flatters it."""
    px = data.ohlc_panel(universe, how="outer")
    c, h, l = px["close"], px["high"], px["low"]
    sig = {}
    for t in universe:
        ct = c[t].dropna()
        m = I.ema(ct, 12) - I.ema(ct, p["slow"])
        s = I.ema(m, 9)
        up = (m > s) & (m.shift(1) <= s.shift(1)) & (m < 0)
        if p["trend"]:
            up &= ct > I.ema(ct, 200)
        dn = (m < s) & (m.shift(1) >= s.shift(1))
        tr = pd.concat([h[t] - l[t], (h[t] - ct.shift()).abs(), (l[t] - ct.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().reindex(ct.index)
        st = np.zeros(len(ct)); entry_px = 0.0; stop = 0.0; days = 0
        cv, upv, dnv, av = ct.values, up.values, dn.values, atr.values
        for i in range(len(ct)):
            prev = st[i - 1] if i else 0
            if prev == 0 and upv[i]:
                st[i], entry_px, stop, days = 1, cv[i], cv[i] - 3 * av[i], 0
            elif prev == 1:
                days += 1
                st[i] = 0 if (dnv[i] or cv[i] < stop or days >= p["max_days"]) else 1
        sig[t] = pd.Series(st, index=ct.index)
    sig = pd.DataFrame(sig).reindex(c.index).fillna(0.0)
    w = sig.div(np.maximum(sig.sum(axis=1), p["slots"]), axis=0)
    o = px["open"].fillna(c)
    return B.run(o.fillna(0), c.ffill().fillna(0), w, mode="close", cost_bps=cost_for(universe, cm))


def macd_bench():
    c = data.panel(MACD_UNI, how="outer")
    return c.pct_change().mean(axis=1).fillna(0.0)


REGISTRY += [
    dict(name="12 Lower band IBS SPY QQQ", fn=band_ibs,
         space={"n": [5, 10, 20], "k": [2.0, 2.5, 3.0], "ibs": [0.3]},
         default={"n": 10, "k": 2.5, "ibs": 0.3},
         is_end="2012-12-31", bench="SPY",
         notes="Quantitativo (2024) mean reversion: close below (10d high - 2.5 x 25d avg range) and IBS < 0.3, exit above yesterday's high."),
    dict(name="13 Your MACD 12-144-9 dip rule", fn=macd_dip,
         space={"slow": [26, 144], "trend": [False, True], "max_days": [15, 60], "slots": [3]},
         default={"slow": 144, "trend": True, "max_days": 15, "slots": 3},
         is_end="2014-12-31", bench="MACD_BASKET",
         notes="The earlier sessions' MACD(12,144,9) cross-up-below-zero rule, daily bars, 12 big tech names, max 3 positions. Survivorship bias: the names are today's winners."),
]


# ======================================= 14 Keller HAA (Hybrid Asset Allocation)
HAA_OFF = ["SPY", "IWM", "EFA", "EEM", "VNQ", "DBC", "IEF", "TLT"]


def haa(p, cm=1.0):
    """Keller (2023), rules as on allocatesmartly.com/hybrid-asset-allocation:
    momentum = mean of 1/3/6/12-month returns. Canary TIP > 0 -> top N of the
    offensive 8 at 1/N each, any pick with momentum <= 0 swapped for the
    better of IEF / cash. Canary < 0 -> all in the better of IEF / cash.
    Cash = SHY (BIL starts 2007). PDBC -> DBC (longer history)."""
    tk = HAA_OFF + ["TIP", "SHY"]
    px = data.ohlc_panel(tk)
    c = px["close"]
    mc = I.resample_month_end(c)
    mom = sum(mc / mc.shift(k) - 1 for k in (1, 3, 6, 12)) / 4
    w = pd.DataFrame(0.0, index=mc.index, columns=tk)
    for d in mc.index:
        m = mom.loc[d]
        if m.isna().any():
            continue
        safe = "IEF" if m["IEF"] > m["SHY"] else "SHY"
        if m["TIP"] <= 0:
            w.loc[d, safe] = 1.0
            continue
        for t in m[HAA_OFF].sort_values(ascending=False).index[:p["top"]]:
            w.loc[d, t if m[t] > 0 else safe] += 1.0 / p["top"]
    w = _monthly_hold(w, c.index)
    return B.run(px["open"], c, w, mode="open", cost_bps=cost_for(tk, cm))


# ======================== 15 Zarattini-Aziz-Mele "The Volatility Edge" (S4)
def vol_edge(p, cm=1.0):
    """Strategy 4 of Zarattini, Aziz & Mele (2025), read from the paper:
    eRV = stdev of last N SPY daily returns x sqrt(252) x 100, eVRP = VIX - eRV.
      eVRP > 0 and VIX < VIX3M  -> short vol, size VIX/100
      eVRP <= 0 and VIX < VIX3M -> short vol, size 0.5 x VIX/100
      eVRP <= 0 and VIX > VIX3M -> long vol (VIXY), size VIX/100
      else cash.
    Short vol = SVXY. SVXY was -1x until 2018-02-27 and -0.5x after, so its
    weight is halved before that date to keep the same vol exposure. The paper
    trades at 3:45pm; here the signal at the close is traded at the next open."""
    tk = ["SVXY", "VIXY"]
    px = data.ohlc_panel(tk)
    c = px["close"]
    vix = data.load("^VIX")["close"].reindex(c.index).ffill()
    v3 = data.load("^VIX3M")["close"].reindex(c.index).ffill()
    spy = data.load("SPY")["close"].reindex(c.index).ffill()
    erv = spy.pct_change().rolling(p["rv"]).std() * np.sqrt(252) * 100
    vrp = vix - erv
    contango = vix < v3
    size = vix / 100 * p["mult"]
    short = np.where(vrp > 0, 1.0, 0.5) * contango * size
    long_ = ((vrp <= 0) & ~contango) * size * (1.0 if p["long_leg"] else 0.0)
    short = pd.Series(short, index=c.index)
    short[c.index < "2018-02-28"] *= 0.5
    w = pd.DataFrame({"SVXY": short, "VIXY": long_}).fillna(0.0).round(3)
    return B.run(px["open"], c, w, mode="open", cost_bps=cost_for(tk, cm) | {"VIXY": 8 * cm})


# ============================================= 16 Connors Double 7s
def double7(p, cm=1.0, universe=MR_UNI):
    """Connors & Alvarez: close > 200d SMA and close at an N-day closing low ->
    buy at the close; sell at the close on an N-day closing high."""
    px = data.ohlc_panel(universe)
    c = px["close"]
    sig = {}
    for t in universe:
        entry = c[t] <= c[t].rolling(p["n"]).min()
        if p["trend"]:
            entry &= c[t] > I.sma(c[t], 200)
        ex = c[t] >= c[t].rolling(p["n"]).max()
        sig[t] = _state(entry, ex)
    w = _basket(pd.DataFrame(sig))
    return B.run(px["open"], c, w, mode="close", cost_bps=cost_for(universe, cm))


# ============================== 17 Multi-coin crypto trend (top liquid coins)
COINS = ["BTC-USD", "ETH-USD", "BNB-USD", "XRP-USD", "ADA-USD", "DOGE-USD", "SOL-USD"]


def crypto_multi(p, cm=1.0):
    """Zarattini-Pagani-Barbon style: Donchian ensemble per coin, each coin
    volatility-targeted, equal risk across the coins trading, gross <= 100%.
    Coin list = today's large caps: survivorship bias flatters it."""
    px = data.ohlc_panel(COINS, how="outer")
    o, c = px["open"], px["close"]
    sig = {}
    for t in COINS:
        df = pd.DataFrame({k: px[k][t] for k in ("open", "high", "low", "close")}).dropna()
        s = pd.concat([donchian_state(df, n) for n in LOOKS[p["looks"]]], axis=1).mean(axis=1)
        vol = I.realized_vol(df["close"], 90, 365)
        sig[t] = (s * (p["target_vol"] / vol).clip(upper=1.0)).reindex(c.index)
    S_ = pd.DataFrame(sig).fillna(0.0)
    n_live = c.notna().sum(axis=1).clip(lower=1)
    w = S_.div(n_live, axis=0)
    w = w.div(np.maximum(w.sum(axis=1), 1.0), axis=0).round(3)
    return B.run(o.fillna(c).fillna(0), c.ffill().fillna(0), w, mode="open",
                 cost_bps=cost_for(COINS, cm, crypto=True))


REGISTRY += [
    dict(name="14 Keller HAA", fn=haa, space={"top": [2, 3, 4, 5]}, default={"top": 4},
         is_end="2014-12-31", bench="SPY",
         notes="Hybrid Asset Allocation (Keller 2023): TIP canary, top 4 of 8 by 1/3/6/12m momentum, else IEF/cash. Rules read from allocatesmartly.com."),
    dict(name="15 Volatility Edge VIX", fn=vol_edge,
         space={"rv": [5, 10, 20], "long_leg": [False, True], "mult": [1.0]},
         default={"rv": 10, "long_leg": True, "mult": 1.0},
         is_end="2016-12-31", bench="SPY",
         notes="Zarattini-Aziz-Mele (2025) Strategy 4: short vol (SVXY) sized VIX/100 in contango with positive VRP, half size with negative VRP, long VIXY in backwardation."),
    dict(name="16 Connors Double 7s", fn=double7,
         space={"n": [5, 7, 10], "trend": [False, True]}, default={"n": 7, "trend": True},
         is_end="2012-12-31", bench="SPY",
         notes="Short Term Trading Strategies That Work (Connors & Alvarez 2008): buy a 7-day closing low above the 200d SMA, sell a 7-day closing high."),
    dict(name="17 Crypto trend top coins", fn=crypto_multi,
         space={"looks": ["short", "all", "long"], "target_vol": [0.25, 0.4, 0.6]},
         default={"looks": "all", "target_vol": 0.25},
         is_end="2020-12-31", bench="BTC-USD",
         notes="Donchian ensemble across BTC ETH BNB XRP ADA DOGE SOL, vol targeted, equal risk. After Zarattini-Pagani-Barbon (2025) 'Catching Crypto Trends'."),
]
