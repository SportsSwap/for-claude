"""The dials: every price-action rule as a fixed list of values.

    python -m lab.dials        # writes rulebook_spec.json and rulebook.md, prints the count

A *version* is one setup + one (setup chart, trigger chart) pair + one value
for every dial. Exclusion rules remove versions that make no sense. Every rule
depends only on the context (setup, setup chart, trigger chart), so the number
of valid versions is an exact product per context; tests/test_dials.py checks
that product against brute-force enumeration with an independent validity check.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path

CHARTS = ["1m", "5m", "15m", "1h", "4h", "daily"]


def V(value, meaning):
    return {"value": value, "meaning": meaning}


# ----------------------------------------------------------------------------- dials
DETECTOR_DIALS = {
    "swing_strength": {
        "group": "detector", "meaning": "Bars on each side a swing high/low must out-reach to count as a confirmed swing.",
        "values": [V(2, "2 bars each side: fast, many swings"), V(3, "3 bars each side"),
                   V(5, "5 bars each side"), V(8, "8 bars each side: slow, only major swings")]},
    "level_tol_atr": {
        "group": "detector", "meaning": "Swings within this many ATR of each other cluster into one level.",
        "values": [V(0.1, "tight cluster: 0.1 ATR"), V(0.25, "medium cluster: 0.25 ATR"), V(0.5, "wide cluster: 0.5 ATR")]},
    "level_min_touches": {
        "group": "detector", "meaning": "Swings a cluster needs before it is a level.",
        "values": [V(1, "a single swing is a level"), V(2, "two touches"), V(3, "three touches"), V(4, "four touches")]},
    "level_shape": {
        "group": "detector", "meaning": "How a level is drawn.",
        "values": [V("line", "one price: the mean of the clustered swings"),
                   V("box", "a band from the lowest to the highest clustered swing")]},
    "trendline_min_touches": {
        "group": "detector", "meaning": "Swings a trend line must pass through (within tolerance).",
        "values": [V(2, "two swings define the line"), V(3, "a third swing confirms it"), V(4, "four swings")]},
    "trendline_tol_atr": {
        "group": "detector", "meaning": "How far a swing may sit from the line and still count as a touch.",
        "values": [V(0.1, "0.1 ATR"), V(0.25, "0.25 ATR"), V(0.5, "0.5 ATR")]},
    "zone_run_candles": {
        "group": "detector", "meaning": "Length of the same-direction candle run that leaves a supply/demand zone.",
        "values": [V(2, "2-candle run"), V(3, "3-candle run"), V(4, "4-candle run"), V(5, "5-candle run")]},
    "zone_span_atr": {
        "group": "detector", "meaning": "Minimum distance the run must cover, in ATR, for its base to be a zone.",
        "values": [V(1.5, "run covers at least 1.5 ATR"), V(2.0, "at least 2 ATR"),
                   V(2.5, "at least 2.5 ATR"), V(3.0, "at least 3 ATR")]},
    "fvg_min_gap_atr": {
        "group": "detector", "meaning": "Smallest three-candle fair value gap kept (candle 1 wick to candle 3 wick).",
        "values": [V(0.0, "any gap"), V(0.1, "gap at least 0.1 ATR"), V(0.25, "gap at least 0.25 ATR")]},
}

SETUP_OWN_DIALS = {
    "retest_window_bars": {
        "group": "setup", "meaning": "Flip zone: setup-chart bars allowed between the break and the retest.",
        "values": [V(6, "retest within 6 bars"), V(12, "within 12 bars"), V(24, "within 24 bars"), V(48, "within 48 bars")]},
    "sweep_depth_max_atr": {
        "group": "setup", "meaning": "Sweep and reclaim: deepest allowed poke beyond the level, in ATR.",
        "values": [V(0.25, "shallow sweep, up to 0.25 ATR"), V(0.5, "up to 0.5 ATR"), V(1.0, "deep sweep, up to 1 ATR")]},
    "reclaim_bars": {
        "group": "setup", "meaning": "Sweep and reclaim: setup-chart bars allowed to close back inside the level.",
        "values": [V(1, "reclaim on the sweep bar itself"), V(2, "within 2 bars"), V(3, "within 3 bars")]},
    "trendline_event": {
        "group": "setup", "meaning": "Trend line: trade the touch or the break.",
        "values": [V("bounce", "trade a touch of the line in the line's direction"),
                   V("break", "trade the first close through the line")]},
    "zone_fresh_only": {
        "group": "setup", "meaning": "Supply/demand zone: only the first return counts.",
        "values": [V("yes", "first touch only; a zone is spent once touched"),
                   V("no", "any touch until price closes through the zone")]},
    "fvg_max_age_bars": {
        "group": "setup", "meaning": "Fair value gap: setup-chart bars a gap stays tradable.",
        "values": [V(24, "gap expires after 24 bars"), V(96, "gap expires after 96 bars")]},
}

SHARED_DIALS = {
    "direction": {
        "group": "shared", "meaning": "Which side the version may trade.",
        "values": [V("long", "longs only"), V("short", "shorts only"), V("both", "longs and shorts")]},
    "confirmation": {
        "group": "shared", "meaning": "What the trigger chart must print at the level before entry.",
        "values": [V("none", "enter on the touch/break itself"),
                   V("close_back", "a trigger bar closes back on the trade side of the level"),
                   V("rejection_wick", "a trigger bar with a wick into the level of at least half its range"),
                   V("engulfing", "a trigger bar whose body engulfs the prior bar's body, in trade direction"),
                   V("either_candle", "rejection wick or engulfing, whichever comes first"),
                   V("ltf_bos", "a break of structure in trade direction on the chart below the trigger chart")]},
    "entry": {
        "group": "shared", "meaning": "How the order is placed once confirmed.",
        "values": [V("close", "market at the confirming bar's close"),
                   V("limit_at_level", "limit order back at the level; cancelled if not filled by the time exit")]},
    "stop_mode": {
        "group": "shared", "meaning": "How the stop is triggered.",
        "values": [V("hard", "stop order: filled when any trade bar trades through it"),
                   V("close_based", "exit at the close of the first trigger bar that closes beyond it")]},
    "stop_ref": {
        "group": "shared", "meaning": "What the stop sits beyond.",
        "values": [V("beyond_level", "the far side of the level/zone/line"),
                   V("touch_wick", "the extreme of the bar(s) that touched the level"),
                   V("last_swing", "the last confirmed swing against the trade"),
                   V("gap_middle", "the far end of the fair value gap's middle candle (FVG only)")]},
    "stop_buffer_atr": {
        "group": "shared", "meaning": "Extra room added beyond the stop reference, in ATR.",
        "values": [V(0.0, "no buffer"), V(0.1, "0.1 ATR"), V(0.25, "0.25 ATR")]},
    "target": {
        "group": "shared", "meaning": "Profit target.",
        "values": [V("1R", "1 x risk"), V("1.5R", "1.5 x risk"), V("2R", "2 x risk"), V("3R", "3 x risk"),
                   V("4R", "4 x risk"), V("5R", "5 x risk"),
                   V("next_swing", "the next confirmed swing in trade direction (skip if under 1R)")]},
    "management": {
        "group": "shared", "meaning": "What happens between entry and exit.",
        "values": [V("hold", "hold to stop, target or time exit"),
                   V("exit_on_choch", "also exit at the close of a trigger-chart change of character against the trade")]},
    "time_exit": {
        "group": "shared", "meaning": "Latest exit if neither stop nor target is hit.",
        "values": [V("flat_1600", "flat at the 16:00 ET bar close"),
                   V("bars_24", "after 24 trigger-chart bars"),
                   V("bars_96", "after 96 trigger-chart bars")]},
}

FILTER_DIALS = {
    "trend_filter": {
        "group": "filter", "meaning": "Trade only when this chart's trend (last two swing highs and lows) agrees.",
        "values": [V("off", "no trend filter"), V("setup_chart", "trend on the setup chart agrees"),
                   V("one_up", "trend on the next chart up agrees"), V("daily", "daily trend agrees")]},
    "skip_choppy": {
        "group": "filter", "meaning": "Skip days the prior session was choppy (|close-open| < 30% of its range).",
        "values": [V("off", "trade every day"), V("on", "skip after a choppy session")]},
    "skip_run": {
        "group": "filter", "meaning": "Skip trades in the direction of a run of same-direction daily closes.",
        "values": [V("off", "no run filter"), V("3d", "skip with a 3-day run"), V("5d", "skip with a 5-day run")]},
    "fresh_breakouts_only": {
        "group": "filter", "meaning": "Only the first close through a level since the level formed.",
        "values": [V("off", "any break"), V("on", "first break only")]},
    "news": {
        "group": "filter", "meaning": "What to do on CPI, jobs-report and FOMC days.",
        "values": [V("trade", "trade normally"), V("skip", "no new entries that session"),
                   V("half", "half position size that session")]},
    "session": {
        "group": "filter", "meaning": "Entry time window (ET).",
        "values": [V("all", "any time in the session"), V("london_ny", "03:00 to 16:00"),
                   V("ny", "08:00 to 16:00"), V("ny_open", "09:30 to 11:00")]},
    "pullback_depth": {
        "group": "filter", "meaning": "Retracement of the last impulse leg on the setup chart.",
        "values": [V("any", "no depth filter"), V("shallow", "under 50% of the leg"),
                   V("deep", "50% to 100% of the leg")]},
    "gap_confluence": {
        "group": "filter", "meaning": "Entry level must sit inside an unfilled setup-chart fair value gap.",
        "values": [V("off", "no gap needed"), V("on", "gap confluence required")]},
}

LEVEL_DIALS = ["level_tol_atr", "level_min_touches", "level_shape"]
SETUPS = {
    "level_bounce": {"meaning": "Price returns to a support/resistance level and rejects it.",
                     "dials": LEVEL_DIALS},
    "breakout": {"meaning": "First close through a level (BOS-style), trade in break direction.",
                 "dials": LEVEL_DIALS},
    "flip_zone": {"meaning": "A broken level is retested from the other side and holds.",
                  "dials": LEVEL_DIALS + ["retest_window_bars"]},
    "trend_pullback": {"meaning": "In a trend, price pulls back then the trigger chart resumes the trend.",
                       "dials": []},
    "trend_line": {"meaning": "A trend line through swings is touched or broken.",
                   "dials": ["trendline_min_touches", "trendline_tol_atr", "trendline_event"]},
    "bos_continuation": {"meaning": "Break of structure with the trend; enter on the continuation.",
                         "dials": []},
    "choch_reversal": {"meaning": "Change of character: first close past the last swing against the trend.",
                       "dials": []},
    "sweep_reclaim": {"meaning": "Price pokes beyond a level, then closes back inside it.",
                      "dials": LEVEL_DIALS + ["sweep_depth_max_atr", "reclaim_bars"]},
    "supply_demand_zone": {"meaning": "Price returns to the base of a strong candle run.",
                           "dials": ["zone_run_candles", "zone_span_atr", "zone_fresh_only"]},
    "fair_value_gap": {"meaning": "Price returns into a three-candle imbalance.",
                       "dials": ["fvg_min_gap_atr", "fvg_max_age_bars"]},
}
COMMON = ["swing_strength"] + list(SHARED_DIALS) + list(FILTER_DIALS)

FIXED_RULES = {
    "swing": "A swing high is a bar whose high is above the highs of `swing_strength` bars on each side; confirmed only once the right-side bars have closed.",
    "trend": "Up when the last two confirmed swing highs and lows are both higher; down when both lower; otherwise range.",
    "break_of_structure": "The first close beyond the last confirmed swing in the direction of the trend.",
    "change_of_character": "The first close beyond the last confirmed swing against the trend.",
    "atr": "Wilder's 14-bar ATR of the chart in use, computed only from bars before the current one.",
    "higher_chart_use": "A higher-chart bar is visible only from its close (ts_avail).",
    "roll": "No entries in the 60 minutes before a roll; an open trade closes at the close of the last bar before it.",
    "warmup": "Warm-up sessions build detector state only; nothing is traded.",
    "time_exit_bars": "bars_24 / bars_96 count trigger-chart bars from the entry bar.",
}

# Chart pairs: same chart, or one or two steps lower; daily triggers on 1h only.
def chart_pairs() -> list[tuple[str, str]]:
    out = []
    for i, sc in enumerate(CHARTS):
        if sc == "daily":
            out.append((sc, "1h"))
            continue
        for k in (0, 1, 2):
            if i - k >= 0:
                out.append((sc, CHARTS[i - k]))
    return out


EXCLUSIONS = [
    {"id": "X1", "if": {"setup_chart": ["4h", "daily"]}, "forbid": {"time_exit": ["flat_1600"]},
     "why": "A flat-at-16:00 exit cuts a 4h or daily setup before it can play out."},
    {"id": "X2", "if": {"trigger_chart": ["1m"]}, "forbid": {"confirmation": ["ltf_bos"]},
     "why": "There is no chart below 1m for a lower-chart break of structure."},
    {"id": "X3", "if": {"setup_chart": ["daily"]}, "forbid": {"trend_filter": ["one_up", "daily"]},
     "why": "No chart above daily, and 'daily' would repeat 'setup_chart'."},
    {"id": "X4", "if": {"setup_chart": ["4h"]}, "forbid": {"trend_filter": ["one_up"]},
     "why": "One chart up from 4h is daily, which the 'daily' value already covers."},
    {"id": "X5", "if": {"trigger_chart": ["4h"]}, "forbid": {"session": ["ny_open"]},
     "why": "Only one 4h close (10:00) falls inside 09:30-11:00, so the window is not a filter but a single bar."},
    {"id": "X6", "if_not": {"setup": ["fair_value_gap"]}, "forbid": {"stop_ref": ["gap_middle"]},
     "why": "Only a fair value gap has a middle candle."},
    {"id": "X7", "if": {"setup": ["fair_value_gap"]}, "forbid": {"gap_confluence": ["on"]},
     "why": "The setup already is a gap; confluence with itself is no filter."},
    {"id": "X8", "if_not": {"setup": ["breakout", "flip_zone"]}, "forbid": {"fresh_breakouts_only": ["on"]},
     "why": "Fresh-breakout filter only applies to setups built on a level break."},
    {"id": "X9", "if_not": {"setup": ["trend_pullback", "flip_zone", "bos_continuation"]},
     "forbid": {"pullback_depth": ["shallow", "deep"]},
     "why": "Pullback depth only applies to setups entered on a pullback."},
]


def build_spec() -> dict:
    allp = {**DETECTOR_DIALS, **SETUP_OWN_DIALS, **SHARED_DIALS, **FILTER_DIALS}
    return {
        "version": 1,
        "charts": CHARTS,
        "chart_pairs": [list(p) for p in chart_pairs()],
        "dials": allp,
        "common_dials": COMMON,
        "setups": SETUPS,
        "exclusions": EXCLUSIONS,
        "fixed_rules": FIXED_RULES,
    }


# ----------------------------------------------------------------------------- counting
def _applies(rule: dict, ctx: dict) -> bool:
    if "if" in rule:
        return all(ctx[k] in v for k, v in rule["if"].items())
    return not all(ctx[k] in v for k, v in rule["if_not"].items())


def setup_dials(spec: dict, setup: str) -> list[str]:
    return spec["common_dials"] + spec["setups"][setup]["dials"]


def valid_values(spec: dict, ctx: dict, dial: str) -> list:
    vals = [v["value"] for v in spec["dials"][dial]["values"]]
    for r in spec["exclusions"]:
        if dial in r["forbid"] and _applies(r, ctx):
            vals = [x for x in vals if x not in r["forbid"][dial]]
    return vals


def count(spec: dict) -> dict:
    by_setup, by_pair, total = {}, {}, 0
    for s in spec["setups"]:
        n_s = 0
        for sc, tc in spec["chart_pairs"]:
            ctx = {"setup": s, "setup_chart": sc, "trigger_chart": tc}
            n = math.prod(len(valid_values(spec, ctx, d)) for d in setup_dials(spec, s))
            n_s += n
            by_pair[f"{sc}->{tc}"] = by_pair.get(f"{sc}->{tc}", 0) + n
        by_setup[s] = n_s
        total += n_s
    return {"total": total, "by_setup": by_setup, "by_chart_pair": by_pair}


def is_valid(spec: dict, version: dict) -> bool:
    """Independent whole-version check used by the brute-force test."""
    if [version["setup_chart"], version["trigger_chart"]] not in spec["chart_pairs"]:
        return False
    for r in spec["exclusions"]:
        if _applies(r, version):
            for d, bad in r["forbid"].items():
                if d in version and version[d] in bad:
                    return False
    return True


def iter_all(spec: dict, setup: str):
    """Every raw combination (valid or not) for one setup; for testing tiny specs."""
    dials = setup_dials(spec, setup)
    pairs = [tuple(p) for p in spec["chart_pairs"]]
    vals = [[v["value"] for v in spec["dials"][d]["values"]] for d in dials]
    for sc, tc in {(a, b) for a in CHARTS for b in CHARTS}:
        for combo in itertools.product(*vals):
            yield {"setup": setup, "setup_chart": sc, "trigger_chart": tc, **dict(zip(dials, combo))}


def decode(spec: dict, setup: str, pair_index: int, index: int) -> dict:
    """Version number -> dial values (mixed radix over the valid values)."""
    sc, tc = spec["chart_pairs"][pair_index]
    ctx = {"setup": setup, "setup_chart": sc, "trigger_chart": tc}
    out = dict(ctx)
    for d in reversed(setup_dials(spec, setup)):
        vals = valid_values(spec, ctx, d)
        index, r = divmod(index, len(vals))
        out[d] = vals[r]
    if index:
        raise IndexError("version index out of range")
    return out


# ----------------------------------------------------------------------------- writing
def _fmt(v):
    return f"`{v}`"


def rulebook_md(spec: dict, c: dict) -> str:
    L = ["# Rulebook", "",
         "Every price-action rule as dials with fixed values. Generated by `python -m lab.dials` "
         "from `lab/dials.py`; the machine-readable copy is `rulebook_spec.json` (locked by sha256 "
         "in `config/amendments.json`). Change a value only through a numbered amendment written "
         "before looking at any result.", "",
         f"**Valid versions: {c['total']:,}**", "",
         "## Charts", "",
         "Setup charts: " + ", ".join(_fmt(x) for x in spec["charts"]) + ". "
         "Trigger chart: the same chart or one or two steps lower; daily setups trigger on `1h`.", "",
         "| setup chart | trigger chart | meaning |", "|---|---|---|"]
    for sc, tc in spec["chart_pairs"]:
        rel = "same chart" if sc == tc else ("daily setup, 1h trigger" if sc == "daily"
                                             else f"{spec['charts'].index(sc) - spec['charts'].index(tc)} step(s) lower")
        L.append(f"| `{sc}` | `{tc}` | {rel} |")
    L += ["", "## Fixed rules (not dials)", ""]
    for k, v in spec["fixed_rules"].items():
        L.append(f"- **{k}** - {v}")
    L += ["", "## Setups", "", "| setup | meaning | own dials |", "|---|---|---|"]
    for s, d in spec["setups"].items():
        L.append(f"| `{s}` | {d['meaning']} | {', '.join(_fmt(x) for x in d['dials']) or '-'} |")
    groups = [("Detector dials", "detector"), ("Setup-specific dials", "setup"),
              ("Shared dials", "shared"), ("Filters", "filter")]
    for title, g in groups:
        L += ["", f"## {title}", ""]
        for name, d in spec["dials"].items():
            if d["group"] != g:
                continue
            L += [f"### `{name}`", "", d["meaning"], "", "| value | meaning |", "|---|---|"]
            L += [f"| `{v['value']}` | {v['meaning']} |" for v in d["values"]]
            L.append("")
    L += ["## Combinations removed", "", "| id | when | removes | why |", "|---|---|---|---|"]
    for r in spec["exclusions"]:
        cond = ("if " + ", ".join(f"{k} in {v}" for k, v in r["if"].items())) if "if" in r \
            else ("unless " + ", ".join(f"{k} in {v}" for k, v in r["if_not"].items()))
        rem = "; ".join(f"{k} = {', '.join(map(str, v))}" for k, v in r["forbid"].items())
        L.append(f"| {r['id']} | {cond} | {rem} | {r['why']} |")
    L += ["", "## Count", "", "| setup | versions |", "|---|---:|"]
    L += [f"| `{s}` | {n:,} |" for s, n in c["by_setup"].items()]
    L += [f"| **total** | **{c['total']:,}** |", "", "| chart pair | versions |", "|---|---:|"]
    L += [f"| `{p}` | {n:,} |" for p, n in c["by_chart_pair"].items()]
    return "\n".join(L) + "\n"


def write(root: Path | None = None) -> dict:
    root = root or Path(__file__).resolve().parent.parent
    spec = build_spec()
    c = count(spec)
    spec_out = {**spec, "count": c}
    (root / "rulebook_spec.json").write_text(json.dumps(spec_out, indent=2) + "\n")
    (root / "rulebook.md").write_text(rulebook_md(spec, c))
    return c


if __name__ == "__main__":
    res = write()
    print(f"valid versions: {res['total']:,}")
    for s, n in res["by_setup"].items():
        print(f"  {s:22s} {n:>22,}")
    sys.exit(0)
