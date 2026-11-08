import pandas as pd

from lab import audit

from conftest import minute_bars


def test_flags_count_each_problem():
    df = minute_bars("2022-01-04 15:00", 30)  # 10:00 ET onward, session 2022-01-04
    df = df.drop(index=[5, 6, 7, 8, 9, 10, 20]).reset_index(drop=True)  # 7-minute and 2-minute gaps
    dup_same = df.iloc[[2]]
    dup_conflict = df.iloc[[3]].assign(close=999.0, high=1000.0)
    bad = df.index == 12
    df.loc[bad, "high"] = df.loc[bad, "low"] - 1
    df.loc[13, "volume"] = 0
    df = pd.concat([df, dup_same, dup_conflict], ignore_index=True)
    f = audit.flag_bars(df)
    assert f.f_duplicate.sum() == 2 and f.f_duplicate_conflict.sum() == 1
    assert f.f_out_of_order.sum() == 2
    assert f.f_ohlc_invalid.sum() == 1 and f.f_zero_volume.sum() == 1
    assert f.f_gap_gt_1m.sum() == 2 and f.f_gap_gt_5m.sum() == 1 and f.f_gap_gt_60m.sum() == 0


def test_gaps_across_sessions_are_not_counted():
    a = minute_bars("2022-01-04 21:55", 5)   # 16:55-16:59 ET
    b = minute_bars("2022-01-04 23:00", 5)   # 18:00 ET next session
    f = audit.flag_bars(pd.concat([a, b], ignore_index=True))
    assert f.f_gap_gt_60m.sum() == 0 and f.session.nunique() == 2


def _pair(steps_at, spread=10.0):
    adj = minute_bars("2022-01-04 15:00", 50)
    unadj = adj.copy()
    off = pd.Series(0.0, index=adj.index)
    for i in steps_at:
        off.iloc[:i] += spread
    for c in audit.PRICE:
        unadj[c] = adj[c] - off
    return adj, unadj


def test_adjustment_steps_only_at_rolls():
    adj, unadj = _pair([20])
    rolls = pd.DataFrame({"roll_time_utc": [adj.ts_event.iat[20]], "old_contract": ["A"],
                          "new_contract": ["B"], "spread": [10.0]})
    r = audit.audit_adjustment(adj, unadj, rolls, 0.01, 0.01)
    assert r["row_for_row"] and r["steps"] == 1 and not r["unexplained_steps"] and not r["spread_mismatch"]
    adj2, unadj2 = _pair([20, 35])
    r2 = audit.audit_adjustment(adj2, unadj2, rolls, 0.01, 0.01)
    assert len(r2["unexplained_steps"]) == 1


def test_contract_changes_only_at_rolls():
    df = minute_bars("2022-01-04 15:00", 30)
    df.loc[10:, "contract"] = "B"
    df.loc[25:, "contract"] = "C"
    rolls = pd.DataFrame({"roll_time_utc": [df.ts_event.iat[10]], "old_contract": ["X"],
                          "new_contract": ["B"], "spread": [1.0]})
    r = audit.audit_contracts(df, rolls)
    assert r["contract_changes"] == 2 and len(r["changes_off_roll"]) == 1
