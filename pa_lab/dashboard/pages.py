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


FUNNEL_PAGES = [
    Spec("funnel_stages", "Funnel", ["funnel/funnel_stages.csv"],
         generic_bars("funnel_stages", "Funnel", "The Funnel", "Versions left after each stage on NQ discovery",
                      "funnel/funnel_stages.csv", "stage", "versions", "int", tone_by_sign=False,
                      conclusion="Each stage removes versions; the last ones standing become candidates.")),
    Spec("setup_judgment", "Funnel", ["funnel/setup_judgment.csv"],
         generic_bars("setup_judgment", "Funnel", "Setups as a Whole", "Equal-weight net per year by setup, NQ discovery",
                      "funnel/setup_judgment.csv", "setup", "net_per_year", "usd0", where={"market": "NQ", "chart": "all"},
                      conclusion="A setup works only when its average version makes money in both eras.")),
    Spec("named_versions", "Funnel", ["funnel/named_versions.csv"],
         generic_bars("named_versions", "Funnel", "Named Systems", "Net after costs on NQ discovery",
                      "funnel/named_versions.csv", "name", "net", "usd0", where={"market": "NQ"},
                      conclusion="The systems as usually taught, run through the same engine.")),
]
FINAL_PAGES = [
    Spec("final_held_up", "Final test", ["final/held_up.csv"],
         generic_bars("final_held_up", "Final test", "What Held Up", "Share of versions profitable with Sharpe of half or more",
                      "final/held_up.csv", "group", "share", "pct1", where={"market": "NQ"}, tone_by_sign=False,
                      conclusion="Measured once, on sessions no rule had seen.")),
    Spec("final_setups", "Final test", ["final/setup_totals.csv"],
         generic_bars("final_setups", "Final test", "Setups in the Final Window", "Equal-weight net over the sealed window, NQ",
                      "final/setup_totals.csv", "setup", "net", "usd0", where={"market": "NQ", "chart": "all"},
                      conclusion="Green held up, red did not.")),
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
