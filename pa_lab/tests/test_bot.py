"""The live bot's offline parts: helpers, and a dry run of the order flow on synthetic bars."""
import asyncio
import datetime as dt
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bot"))
pytest.importorskip("ib_async")
import noise_band_bot as nbb  # noqa: E402
from noise_band_core import NoiseBand  # noqa: E402

NY = nbb.NY


def test_minute_index_handles_daylight_saving():
    winter = dt.datetime(2026, 1, 5, 14, 30, tzinfo=dt.timezone.utc)   # 09:30 New York (EST)
    summer = dt.datetime(2026, 7, 6, 13, 30, tzinfo=dt.timezone.utc)   # 09:30 New York (EDT)
    assert nbb.minute_index(winter) == (dt.date(2026, 1, 5), 0)
    assert nbb.minute_index(summer) == (dt.date(2026, 7, 6), 0)


def _det(exp):
    return types.SimpleNamespace(contract=types.SimpleNamespace(lastTradeDateOrContractMonth=exp))


def test_front_contract_rolls_eight_days_before_expiry():
    ds = [_det("20261218"), _det("20270319"), _det("20260918")]
    assert nbb.front_contract(ds, dt.date(2026, 12, 1), 8).contract.lastTradeDateOrContractMonth == "20261218"
    assert nbb.front_contract(ds, dt.date(2026, 12, 10), 8).contract.lastTradeDateOrContractMonth == "20270319"


def test_session_end_reads_liquid_hours_and_half_days():
    d = types.SimpleNamespace(timeZoneId="US/Central",
                              liquidHours="20261125:0830-20261125:1515;20261126:CLOSED;20261127:0830-20261127:1215")
    assert nbb.session_end_ny(d, dt.date(2026, 11, 25)).time() == dt.time(16, 15)
    assert nbb.session_end_ny(d, dt.date(2026, 11, 26)) is None
    assert nbb.session_end_ny(d, dt.date(2026, 11, 27)).time() == dt.time(13, 15)


def test_round_tick():
    assert nbb.round_tick(21000.13, 0.25) == 21000.25
    assert nbb.round_tick(21000.12, 0.25) == 21000.0


class FakeIB:
    def positions(self):
        return []

    async def accountSummaryAsync(self, account=""):
        return [types.SimpleNamespace(tag="NetLiquidation", value="15000")]


def _bars_for_day(day, base, drift):
    """390 synthetic 1-minute bars: quiet first 15 minutes, then a steady move of `drift` per bar."""
    out, px = [], base
    for k in range(390):
        t = dt.datetime.combine(day, dt.time(9, 30), NY) + dt.timedelta(minutes=k)
        o = px
        px = px + (0.2 if k % 2 else -0.2) if k < 15 else px + drift
        out.append(types.SimpleNamespace(date=t.astimezone(dt.timezone.utc), open=o, high=max(o, px) + 0.5,
                                         low=min(o, px) - 0.5, close=px, volume=100))
    return out


def test_dry_run_flow_writes_logs(tmp_path):
    cfg = {"broker": {}, "market": {}, "strategy": {"version": "best", "contracts": 1},
           "safety": {"dry_run": True, "max_contracts": 1}, "files": {"log_dir": "logs", "state_file": "state.json"}}
    bot = nbb.Bot(cfg, tmp_path)
    bot.ib = FakeIB()
    bot.contract = types.SimpleNamespace(conId=1, localSymbol="MNQZ6", multiplier="2")
    bot.details = types.SimpleNamespace(timeZoneId="US/Central", liquidHours="", minTick=0.25)
    day0 = dt.date(2026, 9, 1)
    days = [day0 + dt.timedelta(days=i) for i in range(60) if (day0 + dt.timedelta(days=i)).weekday() < 5]

    async def go():
        acts_seen = []
        for i, day in enumerate(days):
            drift = 0.02 if i < len(days) - 1 else 1.5      # quiet days, then one strong trend day
            for b in _bars_for_day(day, 20000 + i, drift):
                for a in bot._feed(b):
                    acts_seen.append(a["type"])
                    await (bot._enter(a) if a["type"] == "enter" else bot._exit(a))
        return acts_seen

    acts = asyncio.run(go())
    assert "enter" in acts and "exit" in acts
    trades = (tmp_path / "logs" / "trades.csv").read_text().splitlines()
    assert len(trades) >= 2 and "dry_run" in trades[0]
    events = (tmp_path / "logs" / "events.csv").read_text()
    assert "would BUY 1" in events or "would SELL 1" in events
    assert NoiseBand("best").p["interval"] == 30
