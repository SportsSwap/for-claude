import datetime as dt

import pandas as pd

from lab.config import DEFAULT_WINDOWS, derive_windows
from lab.seed import rng
from lab.sessions import in_halt_hour, session_bounds, session_date

D = dt.date


def et(s):
    return pd.Series([pd.Timestamp(s, tz="America/New_York").tz_convert("UTC")])


def test_sunday_evening_belongs_to_monday():
    assert session_date(et("2022-01-02 18:00")).iat[0] == D(2022, 1, 3)  # Sunday -> Monday


def test_session_dated_by_the_day_it_ends():
    assert session_date(et("2022-01-04 16:59")).iat[0] == D(2022, 1, 4)
    assert session_date(et("2022-01-04 18:00")).iat[0] == D(2022, 1, 5)
    assert session_date(et("2022-01-04 23:59")).iat[0] == D(2022, 1, 5)
    assert session_date(et("2022-01-05 00:00")).iat[0] == D(2022, 1, 5)


def test_halt_hour():
    assert in_halt_hour(et("2022-01-04 17:00")).iat[0]
    assert in_halt_hour(et("2022-01-04 17:59")).iat[0]
    assert not in_halt_hour(et("2022-01-04 16:59")).iat[0]
    assert not in_halt_hour(et("2022-01-04 18:00")).iat[0]


def test_bounds_follow_daylight_saving():
    b = session_bounds([D(2022, 3, 11), D(2022, 3, 14)])  # Fri before / Mon after DST start
    assert b.open_utc.iat[0] == pd.Timestamp("2022-03-10 23:00", tz="UTC")  # 18:00 EST
    assert b.close_utc.iat[0] == pd.Timestamp("2022-03-11 22:00", tz="UTC")  # 17:00 EST
    assert b.open_utc.iat[1] == pd.Timestamp("2022-03-13 22:00", tz="UTC")  # Sunday 18:00 EDT
    assert b.close_utc.iat[1] == pd.Timestamp("2022-03-14 21:00", tz="UTC")


def test_default_windows_used_when_data_covers_them():
    w = derive_windows(D(2021, 10, 1), D(2026, 10, 16))
    assert w == DEFAULT_WINDOWS
    assert w.label(D(2021, 12, 31)) == "warmup"
    assert w.label(D(2022, 1, 3)) == "discovery" and w.era(D(2022, 6, 1)) == "era1"
    assert w.era(D(2023, 1, 3)) == "era2"
    assert w.label(D(2024, 8, 1)) == "final"


def test_other_dates_keep_the_shape():
    w = derive_windows(D(2019, 1, 2), D(2025, 3, 14))
    assert w.final == (D(2023, 4, 1), D(2025, 3, 14))          # last ~2 years sealed
    assert w.discovery == (D(2020, 10, 1), D(2023, 3, 31))      # 2.5 years
    assert w.warmup == (D(2020, 7, 1), D(2020, 9, 30))          # 3 months
    assert w.era1[1] + dt.timedelta(days=1) == w.era2[0]


def test_master_seed_streams_reproduce():
    assert (rng("x").normal(size=5) == rng("x").normal(size=5)).all()
    assert not (rng("x").normal(size=5) == rng("y").normal(size=5)).all()
