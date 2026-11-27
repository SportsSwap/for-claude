"""Today's target positions for every bot that passed (grade A or B).

    python3 signals.py            # passing bots
    python3 signals.py --all      # every bot

It downloads fresh prices, runs each bot with the settings it was validated
with, and prints the weights it wants to hold for the NEXT session. It never
places an order. To trade, take the weights to your broker yourself, or
through /trader-risk and /trader-broker (paper account first).

Timing: bots marked "at the close" decide on the day's final bar and buy
market-on-close. Live, run this at about 3:45pm New York time (NYSE's MOC
cut-off is 3:50pm) with the current price standing in for the close. Bots
marked "next open" can run any time after the close.
"""
import json
import sys

from bots.strategies import REGISTRY
from engine.validate import RESULTS
from portfolio import grade

TIMING = {"open": "next open", "close": "at the close", "overnight": "close -> next open"}


def parse(chosen: str, space: dict) -> dict:
    out = {}
    for part in chosen.split(","):
        k, v = part.split("=", 1)
        out[k] = next(x for x in space[k] if str(x) == v)
    return out


def main():
    show_all = "--all" in sys.argv
    summary = {o["name"]: o for o in json.loads((RESULTS / "summary.json").read_text())}
    for spec in REGISTRY:
        o = summary.get(spec["name"])
        if o is None:
            continue
        g = grade(o)
        if g not in ("A", "B") and not show_all:
            continue
        p = parse(o["chosen"], spec["space"])
        res = spec["fn"](p, 1.0)
        w = res.weights.iloc[-1]
        held = {k: round(float(v), 3) for k, v in w.items() if abs(v) > 1e-6}
        print(f"[{g}] {spec['name']}  ({o['chosen']})  as of {res.weights.index[-1].date()}")
        print(f"     target: {held if held else 'all cash'}")


if __name__ == "__main__":
    main()
