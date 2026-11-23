"""Noise-band bot for Interactive Brokers (MNQ by default).

    python noise_band_bot.py --config config.toml

Connects to IB Gateway (or TWS), loads about 30 days of 1-minute history, then follows live
1-minute bars and trades one signal a day with bot/noise_band_core.py (the lab's exact rules).

Safety:
  - dry_run = true in the config: it logs every signal and never sends an order. Start here.
  - every entry also places a broker-side emergency stop (GTC) in case this program dies;
  - kill switch: no new trades once the account's net value is max_drawdown_pct below its high;
  - no trading on half-day sessions (the lab never traded them) or with an unknown open position;
  - it flattens its position at 15:45 New York, and again at 15:50 if anything was left;
  - if the connection drops it exits; run it under systemd (see README) so it restarts.
Every signal, order, fill and exit goes to logs/events.csv and logs/trades.csv.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
import json
import logging
import math
import sys
import tomllib
from pathlib import Path
from zoneinfo import ZoneInfo

from ib_async import IB, Future, MarketOrder, StopOrder

sys.path.insert(0, str(Path(__file__).resolve().parent))
from noise_band_core import RTH, NoiseBand  # noqa: E402

NY = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
log = logging.getLogger("noise_band_bot")


# =========================================================================== helpers (tested offline)
def minute_index(ts: dt.datetime) -> tuple[dt.date, int]:
    """(New York date, minute index from 09:30) for a bar's start time."""
    t = ts.astimezone(NY)
    return t.date(), t.hour * 60 + t.minute - (9 * 60 + 30)


def expiry_of(contract) -> dt.date:
    return dt.datetime.strptime(contract.lastTradeDateOrContractMonth[:8], "%Y%m%d").date()


def front_contract(details: list, day: dt.date, roll_days: int):
    """The contract to trade on `day`: the nearest expiry more than roll_days away."""
    cands = [(expiry_of(d.contract), d) for d in details]
    cands = [x for x in cands if (x[0] - day).days > roll_days]
    return min(cands, key=lambda x: x[0])[1] if cands else None


def session_end_ny(details, day: dt.date) -> dt.datetime | None:
    """End of today's liquid (regular) session in New York time, from IB's liquidHours.
    None when the market is closed that day."""
    tz = ZoneInfo(details.timeZoneId or "US/Central")
    end = None
    for seg in (details.liquidHours or "").split(";"):
        if not seg or "CLOSED" in seg:
            continue
        try:
            a, b = seg.split("-")
            e = dt.datetime.strptime(b, "%Y%m%d:%H%M").replace(tzinfo=tz).astimezone(NY)
            s = dt.datetime.strptime(a, "%Y%m%d:%H%M").replace(tzinfo=tz).astimezone(NY)
        except ValueError:
            continue
        if s.date() == day or e.date() == day:
            end = e if end is None or e > end else end
    return end


def round_tick(price: float, tick: float) -> float:
    return round(round(price / tick) * tick, 10)


class CsvLog:
    def __init__(self, path: Path, header: list[str]):
        self.path, self.header = path, header
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with open(path, "w", newline="") as f:
                csv.writer(f).writerow(header)

    def write(self, **row):
        with open(self.path, "a", newline="") as f:
            csv.writer(f).writerow([row.get(h, "") for h in self.header])


# =========================================================================== the bot
class Bot:
    def __init__(self, cfg: dict, cfg_dir: Path):
        self.cfg = cfg
        b, m, s, sf, fl = cfg["broker"], cfg["market"], cfg["strategy"], cfg["safety"], cfg["files"]
        self.dry = bool(sf.get("dry_run", True))
        self.qty = int(s.get("contracts", 1))
        if self.qty > int(sf.get("max_contracts", 1)):
            raise SystemExit(f"contracts ({self.qty}) is above max_contracts ({sf.get('max_contracts')})")
        self.strat = NoiseBand(s.get("version", "best"))
        self.ib = IB()
        logs = cfg_dir / fl.get("log_dir", "logs")
        self.state_path = cfg_dir / fl.get("state_file", "state.json")
        self.events = CsvLog(logs / "events.csv", ["utc", "new_york", "type", "message"])
        self.trades = CsvLog(logs / "trades.csv", ["day", "version", "side", "contracts", "signal_time", "signal_price",
                                                   "fill_price", "exit_time", "exit_reason", "exit_signal_price",
                                                   "exit_fill_price", "points", "usd_before_costs", "dry_run"])
        self.state = self._load_state()
        self.queue: asyncio.Queue = asyncio.Queue()
        self.contract = self.details = None
        self.all_details = []
        self.live = None
        self.last_ts = None
        self.stop_trade = None
        self.half_day = False
        self.paused_reason = None

    # ---------------------------------------------------------------- state and logging
    def _load_state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text())
        except (OSError, ValueError):
            return {"hwm": None, "open_trade": None}

    def _save_state(self):
        self.state_path.write_text(json.dumps(self.state, indent=1, default=str))

    def event(self, kind: str, msg: str):
        now = dt.datetime.now(UTC)
        log.info("%s: %s", kind, msg)
        self.events.write(utc=now.isoformat(timespec="seconds"), new_york=now.astimezone(NY).strftime("%Y-%m-%d %H:%M:%S"),
                          type=kind, message=msg)

    # ---------------------------------------------------------------- start-up
    async def connect(self):
        b = self.cfg["broker"]
        await self.ib.connectAsync(b.get("host", "127.0.0.1"), int(b.get("port", 4002)), clientId=int(b.get("client_id", 11)),
                                   account=b.get("account", ""))
        self.ib.disconnectedEvent += self._on_disconnect
        self.event("connected", f"port {b.get('port')} account {b.get('account') or 'default'} dry_run={self.dry}")

    def _on_disconnect(self):
        self.event("disconnected", "connection to IB lost; exiting so the service manager restarts the bot")
        asyncio.get_event_loop().stop()

    async def pick_contract(self, day: dt.date):
        m = self.cfg["market"]
        probe = Future(m.get("symbol", "MNQ"), exchange=m.get("exchange", "CME"), currency=m.get("currency", "USD"))
        probe.includeExpired = True
        self.all_details = await self.ib.reqContractDetailsAsync(probe)
        d = front_contract(self.all_details, day, int(m.get("roll_days_before_expiry", 8)))
        if d is None:
            raise SystemExit("no tradable contract found")
        changed = self.contract is None or d.contract.conId != self.contract.conId
        self.details, self.contract = d, d.contract
        if changed:
            self.event("contract", f"trading {self.contract.localSymbol} (expires {expiry_of(self.contract)})")
        return changed

    async def load_history(self, today: dt.date, calendar_days: int = 45):
        """Day-by-day 1-minute regular-hours bars, each day from the contract that was front then."""
        m = self.cfg["market"]
        roll = int(m.get("roll_days_before_expiry", 8))
        n = 0
        for back in range(calendar_days, 0, -1):
            day = today - dt.timedelta(days=back)
            if day.weekday() >= 5:
                continue
            d = front_contract(self.all_details, day, roll)
            if d is None:
                continue
            end = dt.datetime.combine(day, dt.time(23, 59), NY).astimezone(UTC)
            try:
                bars = await self.ib.reqHistoricalDataAsync(d.contract, end, "1 D", "1 min", "TRADES", True, formatDate=2)
            except Exception as e:  # noqa: BLE001
                self.event("history_error", f"{day}: {e}")
                bars = []
            day_bars = [b for b in bars if minute_index(b.date)[0] == day]
            if day_bars:
                self.strat.start_day(day)
                for b in day_bars:
                    _, k = minute_index(b.date)
                    self.strat.on_bar(k, b.open, b.high, b.low, b.close, float(b.volume or 0))
                self.strat.finish_day()
                self.last_ts = day_bars[-1].date
                n += 1
            await asyncio.sleep(2.2)        # IB's pacing rules for historical data
        self.event("history", f"{n} sessions loaded, {self.strat.n_kept} kept for the band "
                              f"(needs 21), ATR {self.strat.atr()}")

    async def subscribe(self):
        if self.live is not None:
            self.ib.cancelHistoricalData(self.live)
        self.live = await self.ib.reqHistoricalDataAsync(self.contract, "", "1 D", "1 min", "TRADES", True,
                                                         formatDate=2, keepUpToDate=True)
        self.live.updateEvent += self._on_bars
        # bars of today already finished: catch up without trading on them
        done = list(self.live)[:-1]
        today = dt.datetime.now(NY).date()
        caught = 0
        for b in done:
            d, k = minute_index(b.date)
            if d == today and (self.last_ts is None or b.date > self.last_ts):
                self._feed(b, catch_up=True)
                caught += 1
        if caught:
            self.event("catch_up", f"{caught} bars of today replayed")
        await self._reconcile_after_catch_up()

    def _on_bars(self, bars, has_new_bar):
        if has_new_bar and len(bars) >= 2:
            self.queue.put_nowait(bars[-2])

    # ---------------------------------------------------------------- per bar
    def _feed(self, bar, catch_up=False) -> list[dict]:
        day, k = minute_index(bar.date)
        if self.last_ts is not None and bar.date <= self.last_ts:
            return []
        self.last_ts = bar.date
        if self.strat.day != day:
            self.strat.start_day(day)
            self._new_day(day)
        acts = self.strat.on_bar(k, bar.open, bar.high, bar.low, bar.close, float(bar.volume or 0))
        if catch_up:
            return []
        return acts

    def _new_day(self, day):
        end = session_end_ny(self.details, day) if self.details else None
        self.half_day = end is not None and end.time() < dt.time(16, 0)
        if self.half_day:
            self.strat.blocked = True
            self.event("half_day", f"session ends {end:%H:%M} New York: no trading today (the lab skipped these days)")
        if self.paused_reason:
            self.strat.blocked = True

    async def _reconcile_after_catch_up(self):
        pos = self._broker_position()
        ot = self.state.get("open_trade")
        today = str(dt.datetime.now(NY).date())
        if pos != 0 and ot and ot.get("day") == today:
            acts = self.strat.restore_position(ot["side"], ot["entry_k"], ot["entry_ref"], ot["atr"])
            self.event("restored", f"open {ot['side']:+d} trade from {ot['signal_time']} restored")
            for a in acts:
                await self._exit(a)
        elif pos != 0:
            self.paused_reason = f"the account holds {pos} {self.contract.localSymbol} that this bot did not open"
            self.strat.blocked = True
            self.event("paused", self.paused_reason + "; close it by hand, then restart the bot")
        else:
            if ot:
                self.event("state", "a saved trade has no position at the broker (stop filled or closed by hand)")
                self.state["open_trade"] = None
                self._save_state()
            if self.strat.traded or self.strat.pos is not None:
                self.strat.drop_position()
                self.event("catch_up", "today's signal happened while the bot was offline: no trade today")

    async def run_bars(self):
        while True:
            bar = await self.queue.get()
            for a in self._feed(bar):
                if a["type"] == "enter":
                    await self._enter(a)
                else:
                    await self._exit(a)

    # ---------------------------------------------------------------- orders
    def _broker_position(self) -> float:
        acct = self.cfg["broker"].get("account", "")
        return sum(p.position for p in self.ib.positions()
                   if p.contract.conId == self.contract.conId and (not acct or p.account == acct))

    async def _net_liquidation(self) -> float | None:
        try:
            vals = await self.ib.accountSummaryAsync(self.cfg["broker"].get("account", ""))
        except Exception:  # noqa: BLE001
            return None
        for v in vals:
            if v.tag == "NetLiquidation":
                return float(v.value)
        return None

    async def _kill_switch(self) -> bool:
        net = await self._net_liquidation()
        if net is None:
            return False
        hwm = max(self.state.get("hwm") or net, net)
        self.state["hwm"] = hwm
        self._save_state()
        lim = float(self.cfg["safety"].get("max_drawdown_pct", 20))
        if net < hwm * (1 - lim / 100):
            self.event("KILL_SWITCH", f"net value {net:,.0f} is more than {lim}% below its high {hwm:,.0f}: "
                                      "no new trades until you reset hwm in the state file")
            return True
        return False

    def _clock(self, k):
        t = 9 * 60 + 31 + k
        return f"{t // 60:02d}:{t % 60:02d}"

    async def _enter(self, a):
        side = a["side"]
        day = str(self.strat.day)
        self.event("signal", f"{'LONG' if side > 0 else 'SHORT'} at {self._clock(a['k'])} close {a['price']} "
                             f"(upper band {a['upper']:.2f}, lower {a['lower']:.2f}, VWAP {a['vwap']:.2f}, ATR {a['atr']:.2f})")
        if self.paused_reason or self.half_day:
            self.strat.drop_position()
            return
        if await self._kill_switch():
            self.strat.drop_position()
            return
        if self._broker_position() != 0:
            self.event("skip", "the account already has a position in this contract")
            self.strat.drop_position()
            return
        fill = None
        if self.dry:
            self.event("dry_run", f"would {'BUY' if side > 0 else 'SELL'} {self.qty} {self.contract.localSymbol}")
            fill = a["price"]
        else:
            order = MarketOrder("BUY" if side > 0 else "SELL", self.qty, tif="DAY")
            if self.cfg["broker"].get("account"):
                order.account = self.cfg["broker"]["account"]
            trade = self.ib.placeOrder(self.contract, order)
            fill = await self._wait_fill(trade)
            if fill is None:
                self.event("order_problem", f"entry order not filled: {trade.orderStatus.status}; cancelling")
                self.ib.cancelOrder(order)
                self.strat.drop_position()
                return
            stop_pts = float(self.cfg["safety"].get("emergency_stop_atr", 1.0)) * a["atr"]
            tick = self.details.minTick or 0.25
            stop_px = round_tick(fill - side * stop_pts, tick)
            st = StopOrder("SELL" if side > 0 else "BUY", self.qty, stop_px, tif="GTC", outsideRth=True)
            if self.cfg["broker"].get("account"):
                st.account = self.cfg["broker"]["account"]
            self.stop_trade = self.ib.placeOrder(self.contract, st)
            self.event("emergency_stop", f"broker-side stop at {stop_px}")
        self.state["open_trade"] = {"day": day, "side": side, "entry_k": a["k"], "entry_ref": a["price"], "atr": a["atr"],
                                    "signal_time": self._clock(a["k"]), "fill": fill, "contracts": self.qty,
                                    "stop_order_id": getattr(getattr(self.stop_trade, "order", None), "orderId", None)}
        self._save_state()
        self.event("entered", f"{'long' if side > 0 else 'short'} {self.qty} at {fill}")

    async def _exit(self, a):
        ot = self.state.get("open_trade") or {}
        fill = None
        if self.dry:
            self.event("dry_run", f"would close the position ({a['reason']})")
            fill = a["price"]
        else:
            await self._cancel_stop(ot)
            fill = await self._flatten(a["reason"])
        side = ot.get("side", 0)
        pts = (side * ((fill or a["price"]) - (ot.get("fill") or ot.get("entry_ref") or a["price"]))) if side else 0.0
        mult = float(self.contract.multiplier or 2)
        self.trades.write(day=ot.get("day"), version=self.strat.version, side="long" if side > 0 else "short",
                          contracts=ot.get("contracts", self.qty), signal_time=ot.get("signal_time"),
                          signal_price=ot.get("entry_ref"), fill_price=ot.get("fill"), exit_time=self._clock(a["k"]),
                          exit_reason=a["reason"], exit_signal_price=a["price"], exit_fill_price=fill,
                          points=round(pts, 2), usd_before_costs=round(pts * mult * ot.get("contracts", self.qty), 2),
                          dry_run=self.dry)
        self.event("exited", f"{a['reason']} at {fill}, {pts:+.2f} points")
        self.state["open_trade"] = None
        self._save_state()

    async def _cancel_stop(self, ot):
        for t in self.ib.openTrades():
            if t.contract.conId == self.contract.conId and t.order.orderType == "STP":
                self.ib.cancelOrder(t.order)
        self.stop_trade = None

    async def _flatten(self, reason) -> float | None:
        pos = self._broker_position()
        if pos == 0:
            self.event("flatten", "already flat (the emergency stop may have filled)")
            return None
        order = MarketOrder("SELL" if pos > 0 else "BUY", abs(pos), tif="DAY")
        if self.cfg["broker"].get("account"):
            order.account = self.cfg["broker"]["account"]
        trade = self.ib.placeOrder(self.contract, order)
        fill = await self._wait_fill(trade)
        if fill is None:
            self.event("order_problem", f"exit order not filled: {trade.orderStatus.status} - CHECK THE ACCOUNT")
        return fill

    async def _wait_fill(self, trade, timeout=30.0) -> float | None:
        waited = 0.0
        while not trade.isDone() and waited < timeout:
            await asyncio.sleep(0.25)
            waited += 0.25
        st = trade.orderStatus
        return float(st.avgFillPrice) if st.status == "Filled" and st.avgFillPrice else None

    # ---------------------------------------------------------------- watchdog
    async def watchdog(self):
        """15:50 New York: make sure nothing is left open. 09:00: re-check the contract (rolls)."""
        done_flat = done_roll = None
        while True:
            now = dt.datetime.now(NY)
            if now.weekday() < 5 and now.time() >= dt.time(15, 50) and done_flat != now.date():
                done_flat = now.date()
                if not self.dry and self.contract is not None and self._broker_position() != 0:
                    self.event("watchdog", "position still open at 15:50: closing it")
                    await self._cancel_stop(self.state.get("open_trade") or {})
                    await self._flatten("watchdog 15:50")
                    self.state["open_trade"] = None
                    self._save_state()
            if now.weekday() < 5 and dt.time(9, 0) <= now.time() < dt.time(9, 25) and done_roll != now.date():
                done_roll = now.date()
                if await self.pick_contract(now.date()):
                    await self.subscribe()
            await asyncio.sleep(20)

    async def main(self):
        await self.connect()
        today = dt.datetime.now(NY).date()
        await self.pick_contract(today)
        await self.load_history(today)
        await self.subscribe()
        await asyncio.gather(self.run_bars(), self.watchdog())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config.toml")
    a = ap.parse_args(argv)
    path = Path(a.config).resolve()
    cfg = tomllib.loads(path.read_text())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bot = Bot(cfg, path.parent)
    try:
        asyncio.run(bot.main())
    except (KeyboardInterrupt, RuntimeError) as e:
        log.info("stopped: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
