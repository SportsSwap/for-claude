"""News calendar: CPI, jobs report (Employment Situation, "NFP") and FOMC days.

Official sources only:
  FOMC - https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
         (decision day = last day of a scheduled meeting; 14:00 ET statement)
  CPI  - https://www.bls.gov/bls/news-release/cpi.htm     (release archive)
  NFP  - https://www.bls.gov/bls/news-release/empsit.htm  (release archive)
BLS archive links are named <series>_MMDDYYYY.htm, the release date.

BLS refuses anonymous automated clients and asks them to identify themselves
with contact details, so the BLS fetch needs LAB_HTTP_CONTACT set to the
person running the lab (e.g. "Jane Doe jane@example.com"). Until it has run,
CPI and NFP rows come from data seeded by hand and are marked verified=False;
load_calendar() refuses unverified rows by default.

    python -m lab.news build          # fetch what it can, write data/news/news_calendar.csv
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

from . import io
from .config import P, sha256_file, stamp

FED_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
BLS_URLS = {"CPI": "https://www.bls.gov/bls/news-release/cpi.htm",
            "NFP": "https://www.bls.gov/bls/news-release/empsit.htm"}
BLS_PREFIX = {"CPI": "cpi", "NFP": "empsit"}
RELEASE_ET = {"CPI": "08:30", "NFP": "08:30", "FOMC": "14:00"}
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
ABBR = {m[:3]: i for m, i in MONTHS.items()}

# Seeded by hand from the BLS release schedules; replaced by the fetch.
# Stops at Sep-2025 on purpose: later dates moved with the 2025 shutdown and must
# come from BLS directly.
SEED_UNVERIFIED = {
    "CPI": ["2021-10-13", "2021-11-10", "2021-12-10",
            "2022-01-12", "2022-02-10", "2022-03-10", "2022-04-12", "2022-05-11", "2022-06-10",
            "2022-07-13", "2022-08-10", "2022-09-13", "2022-10-13", "2022-11-10", "2022-12-13",
            "2023-01-12", "2023-02-14", "2023-03-14", "2023-04-12", "2023-05-10", "2023-06-13",
            "2023-07-12", "2023-08-10", "2023-09-13", "2023-10-12", "2023-11-14", "2023-12-12",
            "2024-01-11", "2024-02-13", "2024-03-12", "2024-04-10", "2024-05-15", "2024-06-12",
            "2024-07-11", "2024-08-14", "2024-09-11", "2024-10-10", "2024-11-13", "2024-12-11",
            "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13", "2025-06-11",
            "2025-07-15", "2025-08-12", "2025-09-11"],
    "NFP": ["2021-10-08", "2021-11-05", "2021-12-03",
            "2022-01-07", "2022-02-04", "2022-03-04", "2022-04-01", "2022-05-06", "2022-06-03",
            "2022-07-08", "2022-08-05", "2022-09-02", "2022-10-07", "2022-11-04", "2022-12-02",
            "2023-01-06", "2023-02-03", "2023-03-10", "2023-04-07", "2023-05-05", "2023-06-02",
            "2023-07-07", "2023-08-04", "2023-09-01", "2023-10-06", "2023-11-03", "2023-12-08",
            "2024-01-05", "2024-02-02", "2024-03-08", "2024-04-05", "2024-05-03", "2024-06-07",
            "2024-07-05", "2024-08-02", "2024-09-06", "2024-10-04", "2024-11-01", "2024-12-06",
            "2025-01-10", "2025-02-07", "2025-03-07", "2025-04-04", "2025-05-02", "2025-06-06",
            "2025-07-03", "2025-08-01", "2025-09-05"],
}

COLS = ["date", "event", "release_et", "verified", "source", "source_url", "notes"]


def parse_fomc(html: str) -> pd.DataFrame:
    """Scheduled meetings from the Fed calendar page; notation votes are skipped."""
    rows = []
    for ym in re.finditer(r"(\d{4}) FOMC Meetings</a>", html):
        year = int(ym.group(1))
        nxt = re.search(r"\d{4} FOMC Meetings</a>", html[ym.end():])
        block = html[ym.end(): ym.end() + nxt.start() if nxt else len(html)]
        months = re.findall(r"fomc-meeting__month[^>]*><strong>([^<]+)</strong>", block)
        dates = re.findall(r"fomc-meeting__date[^>]*>([^<]+)<", block)
        for mon, day in zip(months, dates):
            day = day.strip()
            if "notation" in day.lower():
                continue
            nums = [int(x) for x in re.findall(r"\d+", day)]
            mons = [x.strip().lower() for x in mon.split("/")]
            # "Jan/Feb 31-1" wraps into the second month; otherwise the meeting ends in the first
            pick = mons[-1] if len(nums) > 1 and nums[-1] < nums[0] else mons[0]
            m = MONTHS.get(pick) or ABBR.get(pick[:3])
            d = nums[-1]
            note = "SEP" if "*" in day else ""
            if "unscheduled" in day.lower():
                note = (note + " unscheduled").strip()
            rows.append({"date": dt.date(year, m, d), "event": "FOMC", "release_et": RELEASE_ET["FOMC"],
                         "verified": True, "source": "federalreserve.gov", "source_url": FED_URL,
                         "notes": f"meeting {mon} {day}".strip() + (f"; {note}" if note else "")})
    return pd.DataFrame(rows, columns=COLS)


FED_HIST_URL = "https://www.federalreserve.gov/monetarypolicy/fomchistorical{year}.htm"


def parse_fomc_historical(html: str, year: int) -> pd.DataFrame:
    """Scheduled meetings from a Fed historical-materials page (one page per year, 2020 and
    earlier). Headings read "January 29-30 Meeting - 2013". Unscheduled meetings, notation
    votes and cancelled meetings are skipped: none was on the calendar ahead of time (or, if
    cancelled, held), so a trader could not have stood aside for them in advance."""
    rows = []
    for raw in re.findall(r"<h5[^>]*>(.*?)</h5>", html, flags=re.S):
        head = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", raw)).strip()
        m = re.fullmatch(rf"([A-Za-z/]+) (\d+(?:-\d+)?) Meeting - {year}", head)
        if not m:
            continue
        mons = [x.strip().lower() for x in m.group(1).split("/")]
        nums = [int(x) for x in m.group(2).split("-")]
        pick = mons[-1] if len(nums) > 1 and nums[-1] < nums[0] else mons[0]
        mon = MONTHS.get(pick) or ABBR.get(pick[:3])
        rows.append({"date": dt.date(year, mon, nums[-1]), "event": "FOMC", "release_et": RELEASE_ET["FOMC"],
                     "verified": True, "source": "federalreserve.gov",
                     "source_url": FED_HIST_URL.format(year=year), "notes": f"meeting {m.group(1)} {m.group(2)}"})
    return pd.DataFrame(rows, columns=COLS)


def build_fomc_history(years=range(2013, 2021), fetch: bool = True) -> pd.DataFrame:
    """Scheduled FOMC decision days for earlier years, written to data/news/fomc_history.csv.
    Kept apart from news_calendar.csv, which the main lab reads and the dashboard cites."""
    frames = []
    for y in years:
        name = f"fomchistorical{y}.htm"
        html = _cached(name)
        if html is None and fetch:
            html = _fetch(FED_HIST_URL.format(year=y), "pa-lab/0.1 (research backtest; python-urllib)", name)
        if html is None:
            raise RuntimeError(f"no source page for FOMC {y}")
        df = parse_fomc_historical(html, y)
        want = 7 if y == 2020 else 8      # March 17-18, 2020 was cancelled two days ahead
        if len(df) != want:
            raise RuntimeError(f"FOMC {y}: expected {want} scheduled meetings, parsed {len(df)}")
        frames.append(df)
    cal = pd.concat(frames, ignore_index=True).sort_values("date").reset_index(drop=True)
    io.write_table(cal, P.news() / "fomc_history.csv")
    return cal


def parse_bls_archive(html: str, event: str) -> pd.DataFrame:
    pat = rf"{BLS_PREFIX[event]}_(\d{{2}})(\d{{2}})(\d{{4}})\.htm"
    days = sorted({dt.date(int(y), int(m), int(d)) for m, d, y in re.findall(pat, html)})
    return pd.DataFrame([{"date": d, "event": event, "release_et": RELEASE_ET[event], "verified": True,
                          "source": "bls.gov", "source_url": BLS_URLS[event], "notes": ""}
                         for d in days], columns=COLS)


def _fetch(url: str, user_agent: str, name: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    out = P.news() / "sources" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(body)
    return body.decode("utf-8", "replace")


def _cached(name: str) -> str | None:
    p = P.news() / "sources" / name
    return io.read_bytes(p).decode("utf-8", "replace") if p.exists() else None


def build(fetch: bool = True) -> pd.DataFrame:
    log, frames = [], []
    agent = "pa-lab/0.1 (research backtest; python-urllib)"
    # FOMC
    html = None
    if fetch:
        try:
            html = _fetch(FED_URL, agent, "fomccalendars.htm")
        except Exception as e:  # noqa: BLE001
            log.append(f"FOMC fetch failed: {e}")
    html = html or _cached("fomccalendars.htm")
    if html:
        frames.append(parse_fomc(html))
    else:
        log.append("no FOMC source page available")
    # CPI / NFP
    contact = os.environ.get("LAB_HTTP_CONTACT")
    for ev, url in BLS_URLS.items():
        name = f"bls_{BLS_PREFIX[ev]}_archive.htm"
        html = None
        if fetch and contact:
            try:
                html = _fetch(url, f"pa-lab/0.1 research backtest; contact: {contact}", name)
            except Exception as e:  # noqa: BLE001
                log.append(f"{ev} fetch failed: {e}")
        elif fetch:
            log.append(f"{ev}: LAB_HTTP_CONTACT not set; BLS requires automated clients to identify themselves")
        html = html or _cached(name)
        df = parse_bls_archive(html, ev) if html else pd.DataFrame(columns=COLS)
        if len(df):
            frames.append(df)
        else:
            frames.append(pd.DataFrame([{"date": dt.date.fromisoformat(d), "event": ev,
                                         "release_et": RELEASE_ET[ev], "verified": False,
                                         "source": "hand-seeded from BLS schedules", "source_url": url,
                                         "notes": "UNVERIFIED: run the BLS fetch"}
                                        for d in SEED_UNVERIFIED[ev]], columns=COLS))
    cal = pd.concat(frames, ignore_index=True).sort_values(["date", "event"]).reset_index(drop=True)
    io.write_table(cal, P.news() / "news_calendar.csv")
    srcs = {p.name: sha256_file(p) for p in sorted((P.news() / "sources").glob("*"))} \
        if (P.news() / "sources").exists() else {}
    io.write_json({"rows": int(len(cal)), "by_event": cal.groupby("event").size().to_dict(),
                   "verified_by_event": cal.groupby("event")["verified"].all().to_dict(),
                   "first": str(cal["date"].min()), "last": str(cal["date"].max()),
                   "source_pages_sha256": srcs, "log": log, **stamp()},
                  P.news() / "news_calendar_meta.json")
    return cal


def load_calendar(require_verified: bool = True, start=None, end=None) -> pd.DataFrame:
    cal = io.read_table(P.news() / "news_calendar.csv", parse_dates=["date"])
    cal["date"] = cal["date"].dt.date
    if start is not None:
        cal = cal[cal["date"] >= start]
    if end is not None:
        cal = cal[cal["date"] <= end]
    bad = cal[~cal["verified"].astype(bool)]
    if require_verified and len(bad):
        raise RuntimeError(f"{len(bad)} news rows are unverified ({sorted(bad.event.unique())}); "
                           "run `LAB_HTTP_CONTACT='name email' python -m lab.news build`")
    return cal.reset_index(drop=True)


def news_days(events=("CPI", "NFP", "FOMC"), **kw) -> set:
    cal = load_calendar(**kw)
    return set(cal.loc[cal["event"].isin(events), "date"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "fomc-history"])
    ap.add_argument("--offline", action="store_true", help="use cached source pages only")
    a = ap.parse_args(argv)
    if a.cmd == "fomc-history":
        cal = build_fomc_history(fetch=not a.offline)
        print(cal.groupby(cal["date"].map(lambda d: d.year)).size())
        return 0
    cal = build(fetch=not a.offline)
    print(cal.groupby(["event", "verified"]).size())
    return 0


if __name__ == "__main__":
    sys.exit(main())
