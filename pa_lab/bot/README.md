# Noise-band bot for Interactive Brokers

Trades the noise band on MNQ (micro Nasdaq-100 futures) by itself: one trade a day at most,
always flat by 15:45 New York. The strategy code (`noise_band_core.py`) makes exactly the
lab's decisions: replaying 2013 to July 2024 through it gives the same 1,028 trades as the
lab for the "best" version and the same 926 for "as_written" (`scripts/bot_replay_check.py`).

## Files

| File | What it is |
|---|---|
| `noise_band_core.py` | The strategy, bar by bar. No broker code. |
| `noise_band_bot.py` | Connects to Interactive Brokers, feeds live bars to the strategy, places orders. |
| `config.example.toml` | Settings. Copy to `config.toml`. |
| `noise-band-bot.service` | Keeps the bot running on a Linux cloud computer. |
| `logs/events.csv`, `logs/trades.csv` | Written by the bot: every signal, order, fill and exit. |

## What you need

1. **An Interactive Brokers account** with futures trading switched on
   (Settings > Account Settings > Trading Permissions > Futures, United States).
2. **CME real-time market data** in Interactive Brokers (Settings > Market Data Subscriptions),
   shared with your paper account (Settings > Paper Trading Account > share market data).
   Without it the bot gets no live bars.
3. **A computer that stays on from 09:30 to 16:00 New York** (01:30-08:00 Sydney in summer):
   a small Linux cloud computer (2 CPUs, 4 GB) is enough.
4. **IB Gateway** running on that computer and logged in to your **paper** account first.

## Setting it up (Linux cloud computer)

```bash
sudo adduser --disabled-password trader
sudo mkdir -p /opt/pa-bot && sudo chown trader /opt/pa-bot
# copy the files in this folder to /opt/pa-bot, then:
cd /opt/pa-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.example.toml config.toml        # then edit config.toml
```

IB Gateway must be running and logged in before the bot starts. On a cloud computer the
simplest way is a ready-made IB Gateway container that logs in for you and restarts it daily;
we will set that up together on the day. Interactive Brokers asks you to approve a login on
your phone about once a week.

## Running it

1. **Dry run first** (`dry_run = true`): the bot logs what it would do and sends no orders.
   Run it for a week and compare `logs/trades.csv` with the TradingView chart.
2. **Paper account** (`dry_run = false`, `port = 4002` for paper): a few weeks. Check each day
   that the fills in `trades.csv` match the signals and that it was flat by 15:45.
3. **Live** (`port = 4001`), one contract.

```bash
.venv/bin/python noise_band_bot.py --config config.toml      # by hand
sudo cp noise-band-bot.service /etc/systemd/system/          # or as a service that restarts itself
sudo systemctl daemon-reload && sudo systemctl enable --now noise-band-bot
journalctl -u noise-band-bot -f                               # watch it
```

## What it does each day

- On start: loads about 30 days of 1-minute bars (2-3 minutes), picks the front contract
  (rolls 8 days before expiry), and checks the account for positions it did not open.
- 10:00-14:00: checks every 30 minutes ("best") or 10 minutes ("as_written").
  One trade a day at most: a market order, plus a broker-side emergency stop (1 daily ATR).
- Exits when price closes back through VWAP or 0.5 ATR against ("best"), otherwise at 15:45.
  A watchdog closes anything still open at 15:50.
- No trading on half-day sessions (the lab never traded them).

## Safety switches (config.toml)

- `dry_run`: log only, no orders.
- `max_contracts`: the bot refuses to start with more contracts than this.
- `max_drawdown_pct`: no new trades once the account's value is this far below its high
  (the high is kept in `state.json`; delete the `hwm` value there to reset it).
- If it finds a position in the account that it did not open, it trades nothing until you
  close that position and restart it.
- If the connection drops, it exits; the service restarts it a minute later and it picks
  up any open trade from `state.json`.

## Not tested yet

Everything that needs a live Interactive Brokers connection (orders, fills, the live bar feed,
contract rolls) has only been tested offline against a fake broker. The dry run and paper
stages are where those get checked.
