"""Performance metrics, plus the overfitting statistics from the literature.

- Probabilistic / Deflated Sharpe Ratio: Bailey & Lopez de Prado (2012, 2014).
- Probability of Backtest Overfitting via CSCV: Bailey, Borwein, Lopez de
  Prado & Zhu (2015).
"""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
from scipy import stats

ANN = 252


def max_drawdown(r: pd.Series) -> float:
    eq = (1 + r).cumprod()
    return float((eq / eq.cummax() - 1).min())


def summary(r: pd.Series, exposure: pd.Series | None = None,
            turnover: pd.Series | None = None, trials: int = 1,
            sr_var_trials: float | None = None) -> dict:
    r = r.dropna()
    n = len(r)
    if n < 20:
        return {"days": n}
    years = max((r.index[-1] - r.index[0]).days / 365.25, 1 / 365.25)
    ppy = n / years  # ~252 for stocks, ~365 for crypto
    total = float((1 + r).prod())
    cagr = total ** (1 / years) - 1 if total > 0 else -1.0
    vol = float(r.std() * math.sqrt(ppy))
    sr_d = float(r.mean() / r.std()) if r.std() > 0 else 0.0
    downside = r[r < 0].std()
    sortino = float(r.mean() / downside * math.sqrt(n / max((r.index[-1] - r.index[0]).days / 365.25, 1e-9))) if downside and downside > 0 else np.nan
    mdd = max_drawdown(r)
    out = {
        "start": str(r.index[0].date()), "end": str(r.index[-1].date()),
        "years": round(years, 1),
        "CAGR": cagr, "vol": vol, "Sharpe": sr_d * math.sqrt(ppy),
        "Sortino": sortino, "maxDD": mdd,
        "Calmar": cagr / abs(mdd) if mdd < 0 else np.nan,
        "t_stat": sr_d * math.sqrt(n),
        "PSR0": psr(r, 0.0),
    }
    if trials > 1:
        out["DSR"] = dsr(r, trials, sr_var_trials)
    if exposure is not None:
        out["exposure"] = float(exposure.reindex(r.index).mean())
    if turnover is not None:
        out["turnover_yr"] = float(turnover.reindex(r.index).sum() / years)
    yearly = (1 + r).groupby(r.index.year).prod() - 1
    out["pct_years_up"] = float((yearly > 0).mean())
    out["worst_year"] = float(yearly.min())
    return out


def trade_stats(tr: pd.Series) -> dict:
    tr = pd.Series(tr).dropna()
    if len(tr) == 0:
        return {"trades": 0}
    wins, losses = tr[tr > 0], tr[tr <= 0]
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else np.inf
    return {"trades": int(len(tr)), "win_rate": float(len(wins) / len(tr)),
            "avg_trade": float(tr.mean()), "profit_factor": float(pf),
            "avg_win": float(wins.mean()) if len(wins) else 0.0,
            "avg_loss": float(losses.mean()) if len(losses) else 0.0}


# ---------------------------------------------------------------- Sharpe stats
def psr(r: pd.Series, sr_star_daily: float = 0.0) -> float:
    """Probability that the true (daily) Sharpe exceeds sr_star, allowing for
    skew and fat tails (Bailey & Lopez de Prado 2012)."""
    r = r.dropna()
    n = len(r)
    if n < 30 or r.std() == 0:
        return float("nan")
    sr = r.mean() / r.std()
    g3 = stats.skew(r)
    g4 = stats.kurtosis(r, fisher=False)
    denom = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    return float(stats.norm.cdf((sr - sr_star_daily) * math.sqrt(n - 1) / denom))


def expected_max_sr(trials: int, sr_var: float) -> float:
    """Expected maximum Sharpe among `trials` skill-less strategies whose
    Sharpe estimates have variance sr_var (daily units)."""
    if trials <= 1:
        return 0.0
    g = 0.5772156649
    z1 = stats.norm.ppf(1 - 1 / trials)
    z2 = stats.norm.ppf(1 - 1 / (trials * math.e))
    return math.sqrt(sr_var) * ((1 - g) * z1 + g * z2)


def dsr(r: pd.Series, trials: int, sr_var: float | None = None) -> float:
    """Deflated Sharpe Ratio: PSR against the Sharpe you'd expect from the
    best of `trials` random strategies. sr_var defaults to the sampling
    variance of a zero-Sharpe estimate, 1/n."""
    r = r.dropna()
    if sr_var is None:
        sr_var = 1.0 / len(r)
    return psr(r, expected_max_sr(trials, sr_var))


# ---------------------------------------------------------------- PBO / CSCV
def pbo(returns: pd.DataFrame, blocks: int = 16, metric=None) -> dict:
    """Probability of Backtest Overfitting by combinatorially symmetric cross
    validation. `returns`: daily returns, one column per parameter set.
    Returns PBO (share of splits where the in-sample winner ranks in the
    bottom half out of sample) and the median OOS rank of the IS winner."""
    if metric is None:
        def metric(x):
            sd = x.std(axis=0)
            return np.where(sd > 0, x.mean(axis=0) / sd, 0.0)
    X = returns.dropna(how="all").fillna(0.0).values
    T, N = X.shape
    if N < 2:
        return {"PBO": float("nan")}
    size = T // blocks
    parts = [X[i * size:(i + 1) * size] for i in range(blocks)]
    lambdas, ranks = [], []
    for combo in itertools.combinations(range(blocks), blocks // 2):
        is_ = np.vstack([parts[i] for i in combo])
        oos = np.vstack([parts[i] for i in range(blocks) if i not in combo])
        m_is, m_oos = metric(is_), metric(oos)
        best = int(np.argmax(m_is))
        rank = (stats.rankdata(m_oos)[best]) / (N + 1)
        ranks.append(rank)
        lambdas.append(math.log(rank / (1 - rank)))
    lambdas = np.array(lambdas)
    return {"PBO": float((lambdas <= 0).mean()), "median_oos_rank": float(np.median(ranks)),
            "splits": len(lambdas)}
