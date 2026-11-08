"""The deck: which pages exist, which saved files each needs, and how each
number on it is read (always through Provenance).

A page whose input files are missing is listed as pending, not drawn.
Funnel and final-test pages name the files and columns they expect; when
those prompts write different names, edit FUNNEL_PAGES / FINAL_PAGES here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .provenance import Provenance, ProvenanceError
from .render import Page, bars, forest, hbars

# Fixed labels allowed to carry digits without a source file. Each is a name,
# not a measurement: chart names, test horizons, the interval width, era names.
FIXED_LABELS = [
    r"\b(1m|5m|15m|1h|4h)\b",
    r"\b(10|20|50) bars\b",
    r"\b95% interval\b",
    r"\b2023-24\b",
    r"\b2022\b",
    r"\b\d+(\.\d+)?R\b",          # R-multiple targets are dial values (1R, 1.5R, 2R ...), not measurements
]


class Pending(Exception):
    pass


@dataclass
class Spec:
    key: str
    section: str
    needs: list
    build: Callable[[Provenance], Page]


def need_cols(prov: Provenance, rel: str, cols):
    df = prov.table(rel)
    miss = [c for c in cols if c not in df.columns]
    if miss:
        raise Pending(f"{rel} lacks columns {miss}")
    return df


# =========================================================================== concept slides
def p_title(prov):
    return Page("title", "slide", "Price action lab", "Price Action Lab",
                "Chart rules against chance on NQ and ES futures",
                cards=[{"big": "NQ", "label": "Nasdaq futures"}, {"big": "ES", "label": "S&P futures"},
                       {"big": "1m", "label": "bars for every fill"}])


def p_method(prov):
    return Page("method", "slide", "Price action lab", "The Method", "Rules become dials, dials meet the data",
                cards=[{"big": "Dials", "label": "every rule exact"}, {"big": "Tests", "label": "behaviour vs chance"},
                       {"big": "Funnel", "label": "versions filtered"}, {"big": "Seal", "label": "one final test"}])


def p_windows(prov):
    f = "session_counts.csv"
    def c(win):
        return prov.cell(f, {"market": "NQ", "window": win}, "sessions", "int")
    def span(win):
        a = prov.cell(f, {"market": "NQ", "window": win}, "start", "str")
        b = prov.cell(f, {"market": "NQ", "window": win}, "end", "str")
        return f"{a} to {b}"
    return Page("windows", "slide", "Data", "Three Windows", "Sessions per window, NQ",
                cards=[{"big": c("warmup"), "label": "warm-up sessions", "note": span("warmup")},
                       {"big": c("discovery"), "label": "discovery sessions", "note": span("discovery")},
                       {"big": c("final"), "label": "sealed sessions", "note": span("final")}])


# =========================================================================== engine checks
def p_random(prov):
    f = "engine/random_entries.json"
    nq = prov.json(f, ["results", "NQ", "per_trade_dollars"], "usd")
    es = prov.json(f, ["results", "ES", "per_trade_dollars"], "usd")
    wr = prov.json(f, ["results", "NQ", "win_rate"], "pct1")
    svg, texts = bars([("NQ", nq, prov.value(nq), "bad" if prov.value(nq) < 0 else "good"),
                       ("ES", es, prov.value(es), "bad" if prov.value(es) < 0 else "good")])
    return Page("random_entries", "finding", "Engine checks", "Random Entries",
                "Market entries at random minutes, one ATR stop, target at twice the risk",
                svg, texts, [{"label": "NQ per trade after costs", "value": nq, "tone": "bad" if prov.value(nq) < 0 else "good"},
                             {"label": "NQ win rate", "value": wr}],
                "Random entries lose a little after costs, as an honest engine should.")


def p_cheat(prov):
    f = "engine/cheat_peek60.json"
    nq = prov.json(f, ["results", "NQ", "per_trade_dollars"], "usd")
    es = prov.json(f, ["results", "ES", "per_trade_dollars"], "usd")
    wr = prov.json(f, ["results", "NQ", "win_rate"], "pct1")
    svg, texts = bars([("NQ", nq, prov.value(nq), "good"), ("ES", es, prov.value(es), "good")])
    return Page("cheat", "finding", "Engine checks", "The Cheat",
                "The same entries, told where price is an hour later",
                svg, texts, [{"label": "NQ per trade after costs", "value": nq, "tone": "good"},
                             {"label": "NQ win rate", "value": wr}],
                "Peeking ahead makes a lot of money, so a leak would show. The cheat was deleted after it ran.")


# =========================================================================== behaviour tests
BEHAVIOR_TITLES = {
    "levels_vs_random": ("Levels Against Random Lines", "Hold rate at real levels minus shifted stand-in lines"),
    "hold_by_touch_count": ("Hold Rate by Touch Count", "Later touches of a level against its first touch"),
    "wall_or_target": ("Wall or Target", "Much-touched levels against random lines touched as often"),
    "shrinking_bounces": ("Shrinking Bounces", "Break rate after two shrinking bounces against other touches"),
    "line_vs_box": ("Line Against Box", "The same levels drawn as a box against drawn as a line"),
    "wick_vs_close_through": ("Wick Through Against Close Through", "Move in the level's favour over the next 20 bars"),
    "flip_zones": ("Flip Zones", "Broken levels retested from the far side against random lines"),
    "bos_follow_10": ("Break of Structure Follow-Through", "Move its way after 10 bars against random bars"),
    "bos_follow_20": ("Break of Structure Follow-Through", "Move its way after 20 bars against random bars"),
    "bos_follow_50": ("Break of Structure Follow-Through", "Move its way after 50 bars against random bars"),
    "choch_follow_10": ("Change of Character Follow-Through", "Move its way after 10 bars against random bars"),
    "choch_follow_20": ("Change of Character Follow-Through", "Move its way after 20 bars against random bars"),
    "choch_follow_50": ("Change of Character Follow-Through", "Move its way after 50 bars against random bars"),
    "sweeps_vs_closes": ("Sweeps Against Closes Through", "Reversal after a sweep against the same move after a close through"),
    "trend_start_sweep": ("Trends That Start With a Sweep", "Changes of character after a sweep against those without one"),
    "trend_lines": ("Trend Lines", "Hold rate at real trend lines minus shifted lines"),
    "fvg_hold": ("Fair Value Gaps Holding", "First-return hold rate against random bands"),
    "fvg_fill": ("Fair Value Gaps Filling", "Share filled within 50 bars against random bands"),
    "zones_first_vs_later": ("Zones, First Return", "First return to a supply or demand zone against later ones"),
    "zones_vs_random": ("Zones Against Random Bands", "First-return hold rate against random bands"),
    "pullback_depth": ("Pullback Depth", "Follow-through after shallow pullbacks against deep ones"),
    "engulfing_at_levels": ("Engulfing Candles at Levels", "Move its way against the same candle at random"),
    "rejection_at_levels": ("Rejection Candles at Levels", "Move its way against the same candle at random"),
}
CHART_ROWS = ["5m", "15m", "1h", "4h", "daily"]


def behavior_page(test: str):
    def build(prov):
        vf, tf = "behavior/verdicts.csv", f"behavior/{test}.csv"
        need_cols(prov, vf, ["test", "metric", "verdict", "why"])
        need_cols(prov, tf, ["market", "chart", "point", "lo", "hi"])
        vd = prov.table(vf)
        row = vd[vd["test"] == test]
        if len(row) != 1:
            raise Pending(f"{vf} has no single row for {test}")
        metric = str(row["metric"].iloc[0])
        kind = "pp1" if "rate" in metric else "atr2"
        rows = []
        for m, c, label, emph in [("NQ", ch, f"NQ {ch}", False) for ch in CHART_ROWS] + \
                [("NQ", "pooled", "NQ pooled", True), ("ES", "pooled", "ES pooled", True)]:
            txt = prov.cell(tf, {"market": m, "chart": c}, "point", kind)
            p = prov.value(txt)
            lo = prov.value(prov.cell(tf, {"market": m, "chart": c}, "lo", kind, shown=False))
            hi = prov.value(prov.cell(tf, {"market": m, "chart": c}, "hi", kind, shown=False))
            rows.append((label, txt, p, lo, hi, emph))
        note = "no difference · bars are the 95% interval" + (" · pp = percentage points" if kind == "pp1" else "")
        svg, texts = forest(rows, note=note)
        verdict = prov.cell(vf, {"test": test}, "verdict", "str", shown=False).strip().lower()
        why = prov.cell(vf, {"test": test}, "why", "str")
        title, sub = BEHAVIOR_TITLES.get(test, (test.replace("_", " ").title(), metric))
        nq, es = rows[5][1], rows[6][1]
        tone = lambda t: "good" if prov.value(t) > 0 else "bad"  # noqa: E731
        return Page(f"behavior_{test}", "finding", "Behavior tests", title, sub, svg, texts,
                    [{"label": "NQ pooled", "value": nq, "tone": tone(nq)},
                     {"label": "ES replication", "value": es, "tone": tone(es)}],
                    why, verdict if verdict in ("true", "split", "false") else None)
    return build


def p_behavior_summary(prov):
    f = "behavior/verdicts.csv"
    need_cols(prov, f, ["test", "verdict"])
    items = []
    for v, label, tone in (("true", "survived", "good"), ("split", "split", "amber"), ("false", "didn't survive", "bad")):
        t = prov.count(f, {"verdict": v})
        items.append((label, t, prov.value(t), tone))
    total = prov.count(f, {})
    svg, texts = bars(items)
    return Page("behavior_summary", "finding", "Behavior tests", "Behavior Verdicts",
                "Each claim scored on NQ, replicated on ES, split by era",
                svg, texts, [{"label": "claims tested", "value": total},
                             {"label": "survived", "value": items[0][1], "tone": "good"}],
                "A claim survives only when NQ, ES and both eras all point its way.")


def p_behavior_intro(prov):
    return Page("behavior_intro", "slide", "Behavior tests", "Real or Random",
                "Every claim against a stand-in that should not matter",
                cards=[{"big": "Lines", "label": "levels moved away"},
                       {"big": "Moments", "label": "same time, same side"},
                       {"big": "Sessions", "label": "resampled whole"}])


# =========================================================================== funnel and final (expected files)
def generic_bars(key, section, title, subtitle, rel, label_col, value_col, kind, where=None, conclusion="",
                 horizontal=True, tone_by_sign=True):
    def build(prov):
        df = need_cols(prov, rel, [label_col, value_col] + list((where or {}).keys()))
        for k, v in (where or {}).items():
            df = df[df[k].astype(str) == str(v)]
        if not len(df):
            raise Pending(f"{rel} has no rows for {where}")
        rows = []
        for lab in df[label_col].astype(str).tolist()[:12]:
            t = prov.cell(rel, {**(where or {}), label_col: lab}, value_col, kind)
            val = prov.value(t)
            rows.append((lab, t, val, ("good" if val > 0 else "bad") if tone_by_sign else "cyan"))
        svg, texts = (hbars(rows) if horizontal else bars(rows))
        return Page(key, "finding", section, title, subtitle, svg, texts, [], conclusion)
    return build


def _tone(prov, t):
    return "good" if prov.value(t) > 0 else "bad"


FUN = "funnel/funnel.parquet"


def p_funnel_intro(prov):
    graded = prov.count(FUN, {"graded": True})
    cand = prov.count(FUN, {"candidate": True})
    work = prov.count("funnel/setup_judgment.csv", {"works": True})
    return Page("funnel_intro", "slide", "Funnel", "Many Versions, Few Survivors",
                "Every version through the same engine and the same five stages",
                cards=[{"big": graded, "label": "versions graded"},
                       {"big": cand, "label": "candidates"},
                       {"big": work, "label": "setups that worked"}])


def p_funnel_stages(prov):
    need_cols(prov, FUN, ["graded", "s1", "s2", "s3", "s4", "candidate"])
    items = []
    st = "funnel/stages.json"
    n_tr = prov.json(st, ["stage1_min_trades"], "int")
    sh = prov.json(st, ["stage3_min_sharpe"], "dec2")
    for col, label in (("graded", "graded"), ("s1", f"{n_tr} trades"), ("s2", "profitable"), ("s3", f"Sharpe {sh}"),
                       ("s4", "beat twins"), ("candidate", "candidate")):
        t = prov.count(FUN, {col: True})
        items.append((label, t, prov.value(t), "cyan"))
    svg, texts = bars(items)
    return Page("funnel_stages", "finding", "Funnel", "The Funnel", "Versions left after each stage on NQ discovery",
                svg, texts, [{"label": "graded", "value": items[0][1]},
                             {"label": "candidates", "value": items[-1][1]}],
                "Most versions lose after costs. The few left must still face the sealed window.")


def p_setup_judgment(prov):
    f = "funnel/setup_judgment.csv"
    df = need_cols(prov, f, ["setup", "chart", "market", "sharpe", "works"])
    rows = []
    for st in sorted(df[(df.market == "NQ") & (df.chart == "1h")]["setup"].astype(str)):
        t = prov.cell(f, {"setup": st, "chart": "1h", "market": "NQ"}, "sharpe", "num2")
        rows.append((st.replace("_", " "), t, prov.value(t), _tone(prov, t)))
    svg, texts = hbars(rows)
    work = prov.count(f, {"works": True})
    cells = prov.count(f, {})
    return Page("setup_judgment", "finding", "Funnel", "Setups as a Whole",
                "Sharpe of the equal-weight average of each setup's versions, NQ 1h",
                svg, texts, [{"label": "setup, chart and market cells that worked", "value": work},
                             {"label": "cells judged", "value": cells}],
                "A setup works only when its average version made money every year and in both eras.")


def p_named_funnel(prov):
    f = "funnel/named_versions.csv"
    df = need_cols(prov, f, ["name", "nq_net"])
    rows = []
    for n in df["name"].astype(str):
        t = prov.cell(f, {"name": n}, "nq_net", "usd0")
        rows.append((n, t, prov.value(t), _tone(prov, t)))
    svg, texts = hbars(rows)
    cand = prov.count(f, {"candidate": True})
    return Page("named_funnel", "finding", "Funnel", "Named Systems",
                "Net after costs on NQ discovery, systems as usually taught",
                svg, texts, [{"label": "named systems that became candidates", "value": cand}],
                "The textbook systems, run through the same engine and costs.")


def p_rule_effects(prov):
    f = "funnel/rule_effects.csv"
    df = need_cols(prov, f, ["rule", "baseline", "value", "mean_sharpe_change_NQ"])
    rows = []
    for r, b, v in df[["rule", "baseline", "value"]].astype(str).itertuples(index=False):
        t = prov.cell(f, {"rule": r, "value": v}, "mean_sharpe_change_NQ", "num2")
        rows.append((f"{r}: {b} to {v}".replace("_", " "), t, prov.value(t), _tone(prov, t)))
    svg, texts = hbars(rows[:12])
    return Page("rule_effects", "finding", "Funnel", "Each Rule, All Else Equal",
                "Change in NQ Sharpe when one rule changes and nothing else does",
                svg, texts, [], "Pairs from the usual-settings grid, differing in one rule only.")


FIN = "final/share_held.csv"


def p_final_intro(prov):
    return Page("final_intro", "slide", "Final test", "The Sealed Window",
                "Opened once, after every choice was hashed",
                cards=[{"big": "Hash", "label": "selections checked"}, {"big": "Rehearse", "label": "seal still closed"},
                       {"big": "Unlock", "label": "once, logged"}])


def p_final_held(prov):
    df = need_cols(prov, FIN, ["market", "group", "share_held"])
    rows = []
    for g in ("all", "candidates", "set:common", "set:sampled", "set:spread"):
        if len(df[(df.market == "NQ") & (df.group == g)]) != 1:
            continue
        t = prov.cell(FIN, {"market": "NQ", "group": g}, "share_held", "pct1")
        rows.append((g.replace("set:", ""), t, prov.value(t), "cyan"))
    svg, texts = bars(rows)
    held_c = prov.cell(FIN, {"market": "NQ", "group": "candidates"}, "held", "int")
    n_c = prov.cell(FIN, {"market": "NQ", "group": "candidates"}, "versions", "int")
    v = "true" if prov.value(rows[1][1]) > prov.value(rows[0][1]) else "false"
    return Page("final_held", "finding", "Final test", "What Held Up",
                "Share of versions profitable with a Sharpe of half or more, NQ sealed window",
                svg, texts, [{"label": "candidates that held", "value": held_c},
                             {"label": "candidates", "value": n_c}],
                "Candidates should hold up more often than versions at large. Here they "
                + ("did." if v == "true" else "did not: their discovery edge was selection luck."), v)


def p_final_working(prov):
    f = "final/working_vs_random.csv"
    df = need_cols(prov, f, ["market", "setup", "setup_chart", "real_net", "beats_random"])
    rows = []
    for m, st, ch in df[["market", "setup", "setup_chart"]].astype(str).itertuples(index=False):
        t = prov.cell(f, {"market": m, "setup": st, "setup_chart": ch}, "real_net", "usd0")
        rows.append((f"{m} {st.replace('_', ' ')} {ch}", t, prov.value(t), _tone(prov, t)))
    svg, texts = hbars(rows)
    beat = prov.count(f, {"beats_random": True})
    tested = prov.count(f, {})
    v = "true" if prov.value(beat) == prov.value(tested) and prov.value(tested) > 0 else \
        ("split" if prov.value(beat) > 0 else "false")
    return Page("final_working", "finding", "Final test", "Working Setups, Sealed",
                "Net over the sealed window for each setup that worked in discovery",
                svg, texts, [{"label": "beat matched random trades", "value": beat},
                             {"label": "tested", "value": tested}],
                "A setup that worked in discovery has to beat random trades on data it never saw.", v)


def p_final_named(prov):
    f = "final/named_versions.csv"
    df = need_cols(prov, f, ["name", "market", "net"])
    rows = []
    for n in df[df.market == "NQ"]["name"].astype(str):
        t = prov.cell(f, {"name": n, "market": "NQ"}, "net", "usd0")
        rows.append((n, t, prov.value(t), _tone(prov, t)))
    svg, texts = hbars(rows)
    held = prov.count(f, {"market": "NQ", "held": True})
    return Page("final_named", "finding", "Final test", "Named Systems, Sealed",
                "Net after costs on the NQ sealed window", svg, texts,
                [{"label": "named systems that held on NQ", "value": held}],
                "The systems as taught, on sessions no rule had seen.")


FUNNEL_PAGES = [
    Spec("funnel_intro", "Funnel", [FUN, "funnel/setup_judgment.csv"], p_funnel_intro),
    Spec("funnel_stages", "Funnel", [FUN, "funnel/stages.json"], p_funnel_stages),
    Spec("setup_judgment", "Funnel", ["funnel/setup_judgment.csv"], p_setup_judgment),
    Spec("named_funnel", "Funnel", ["funnel/named_versions.csv"], p_named_funnel),
    Spec("rule_effects", "Funnel", ["funnel/rule_effects.csv"], p_rule_effects),
]
FINAL_PAGES = [
    Spec("final_intro", "Final test", ["final/DONE.json"], p_final_intro),
    Spec("final_held", "Final test", [FIN], p_final_held),
    Spec("final_working", "Final test", ["final/working_vs_random.csv"], p_final_working),
    Spec("final_named", "Final test", ["final/named_versions.csv"], p_final_named),
]


def specs(prov: Provenance) -> list[Spec]:
    out = [Spec("title", "Price action lab", [], p_title),
           Spec("method", "Price action lab", [], p_method),
           Spec("windows", "Data", ["session_counts.csv"], p_windows),
           Spec("random_entries", "Engine checks", ["engine/random_entries.json"], p_random),
           Spec("cheat", "Engine checks", ["engine/cheat_peek60.json"], p_cheat),
           Spec("behavior_intro", "Behavior tests", [], p_behavior_intro),
           Spec("behavior_summary", "Behavior tests", ["behavior/verdicts.csv"], p_behavior_summary)]
    tests = list(BEHAVIOR_TITLES)
    if prov.exists("behavior/verdicts.csv"):
        try:
            tests = prov.table("behavior/verdicts.csv")["test"].astype(str).tolist()
        except Exception:  # noqa: BLE001
            pass
    for t in tests:
        out.append(Spec(f"behavior_{t}", "Behavior tests", ["behavior/verdicts.csv", f"behavior/{t}.csv"],
                        behavior_page(t)))
    return out + FUNNEL_PAGES + FINAL_PAGES
