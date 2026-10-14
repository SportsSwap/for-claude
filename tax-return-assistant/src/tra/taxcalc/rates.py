"""Load and validate a year's rates file (config/rates/fyYYYY.yaml).

Validation catches typos before they reach a calculation: bracket base
amounts must equal the tax on the brackets below, thresholds must be
continuous, and every rate must be between 0 and 1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

from ..paths import CONFIG_DIR


class RatesError(Exception):
    pass


def _d(value) -> Decimal:
    return Decimal(str(value))


@dataclass(frozen=True)
class Bracket:
    from_: Decimal
    rate: Decimal
    base: Decimal


@dataclass(frozen=True)
class Lito:
    max: Decimal
    full_to: Decimal
    taper1_rate: Decimal
    taper1_to: Decimal
    taper2_base: Decimal
    taper2_rate: Decimal


@dataclass(frozen=True)
class Threshold:
    lower: Decimal
    upper: Decimal


@dataclass(frozen=True)
class FamilyThreshold:
    lower: Decimal
    per_child: Decimal


@dataclass(frozen=True)
class Medicare:
    rate: Decimal
    shade_in: Decimal
    single: Threshold
    sapto_single: Threshold
    family: FamilyThreshold
    sapto_family: FamilyThreshold


@dataclass(frozen=True)
class Tier:
    from_: Decimal
    rate: Decimal


@dataclass(frozen=True)
class Mls:
    single: tuple[Tier, ...]
    family: tuple[Tier, ...]
    family_per_child_after_first: Decimal


@dataclass(frozen=True)
class PhiPeriod:
    start: date
    end: date
    rates: dict[str, tuple[Decimal, ...]]  # age band -> (base, tier 1, tier 2, tier 3)


@dataclass(frozen=True)
class HelpBand:
    from_: Decimal
    base: Decimal
    rate: Decimal


@dataclass(frozen=True)
class Help:
    method: str  # marginal | percent_of_income
    bands: tuple[HelpBand, ...]
    flat_from: Decimal | None
    flat_rate: Decimal | None


@dataclass(frozen=True)
class Sapto:
    max: Decimal
    shade_out: Decimal
    cut_out: Decimal


@dataclass(frozen=True)
class CarRate:
    rate: Decimal
    km_cap: Decimal


@dataclass(frozen=True)
class Rates:
    income_year: int
    status: str
    verified_by: str | None
    verified_on: str | None
    sources: dict[str, str]
    brackets: tuple[Bracket, ...]
    lito: Lito
    medicare: Medicare
    mls: Mls
    phi_rebate: tuple[PhiPeriod, ...]
    help: Help
    sapto: dict[str, Sapto]
    sapto_taper: Decimal
    car: CarRate
    wfh_rate: Decimal


AGE_BANDS = ("under65", "65to69", "70plus")


def _parse(raw: dict) -> Rates:
    m = raw["medicare"]
    h = raw["help"]
    if h["method"] == "marginal":
        bands = tuple(HelpBand(_d(b["from"]), _d(b["base"]), _d(b["rate"])) for b in h["bands"])
        flat_from, flat_rate = _d(h["flat_from"]), _d(h["flat_rate"])
    else:
        bands = tuple(HelpBand(_d(r["from"]), Decimal("0"), _d(r["rate"])) for r in h["rows"])
        flat_from = flat_rate = None
    sapto = raw["sapto"]
    return Rates(
        income_year=int(raw["income_year"]),
        status=str(raw.get("status", "unverified")),
        verified_by=raw.get("verified_by"),
        verified_on=None if raw.get("verified_on") is None else str(raw.get("verified_on")),
        sources=dict(raw.get("sources", {})),
        brackets=tuple(Bracket(_d(b["from"]), _d(b["rate"]), _d(b["base"])) for b in raw["resident_brackets"]),
        lito=Lito(**{k: _d(v) for k, v in raw["lito"].items()}),
        medicare=Medicare(
            rate=_d(m["rate"]), shade_in=_d(m["shade_in"]),
            single=Threshold(_d(m["single"]["lower"]), _d(m["single"]["upper"])),
            sapto_single=Threshold(_d(m["sapto_single"]["lower"]), _d(m["sapto_single"]["upper"])),
            family=FamilyThreshold(_d(m["family"]["lower"]), _d(m["family"]["per_child"])),
            sapto_family=FamilyThreshold(_d(m["sapto_family"]["lower"]), _d(m["sapto_family"]["per_child"]))),
        mls=Mls(
            single=tuple(Tier(_d(t["from"]), _d(t["rate"])) for t in raw["mls"]["single"]),
            family=tuple(Tier(_d(t["from"]), _d(t["rate"])) for t in raw["mls"]["family"]),
            family_per_child_after_first=_d(raw["mls"]["family_per_child_after_first"])),
        phi_rebate=tuple(
            PhiPeriod(p["from"], p["to"], {band: tuple(_d(x) for x in p[band]) for band in AGE_BANDS})
            for p in raw["phi_rebate"]),
        help=Help(h["method"], bands, flat_from, flat_rate),
        sapto={k: Sapto(_d(v["max"]), _d(v["shade_out"]), _d(v["cut_out"])) for k, v in sapto.items() if k != "taper"},
        sapto_taper=_d(sapto["taper"]),
        car=CarRate(_d(raw["car_cents_per_km"]["rate"]), _d(raw["car_cents_per_km"]["km_cap"])),
        wfh_rate=_d(raw["wfh_rate"]),
    )


def _rates_in_range(r: Rates) -> list[tuple[str, Decimal]]:
    out = [("bracket rate", b.rate) for b in r.brackets]
    out += [("LITO rate", r.lito.taper1_rate), ("LITO rate", r.lito.taper2_rate)]
    out += [("Medicare rate", r.medicare.rate), ("Medicare shade-in rate", r.medicare.shade_in)]
    out += [("MLS rate", t.rate) for t in r.mls.single + r.mls.family]
    out += [("PHI rebate rate", x) for p in r.phi_rebate for tiers in p.rates.values() for x in tiers]
    out += [("HELP rate", b.rate) for b in r.help.bands]
    if r.help.flat_rate is not None:
        out.append(("HELP flat rate", r.help.flat_rate))
    out.append(("SAPTO taper rate", r.sapto_taper))
    return out


def validate_rates(r: Rates) -> None:
    for name, value in _rates_in_range(r):
        if not Decimal("0") <= value <= Decimal("1"):
            raise RatesError(f"{name} {value} is outside 0-1 (rates are decimals: 0.16 means 16%)")
    froms = [b.from_ for b in r.brackets]
    if froms != sorted(froms) or len(set(froms)) != len(froms):
        raise RatesError("tax brackets must be in ascending order")
    if r.brackets[0].base != 0:
        raise RatesError("the first tax bracket base must be 0")
    for prev, cur in zip(r.brackets, r.brackets[1:]):
        expected = prev.base + prev.rate * (cur.from_ - prev.from_)
        if cur.base != expected:
            raise RatesError(f"bracket base at {cur.from_} is {cur.base}, expected {expected}")
    for name, t in (("single", r.medicare.single), ("SAPTO single", r.medicare.sapto_single)):
        # 10c shade-in meets the 2% levy at lower x 1.25; upper is the last whole dollar before that.
        expected = Decimal(math.floor(t.lower * Decimal("1.25")))
        if t.upper != expected:
            raise RatesError(f"Medicare {name} upper threshold {t.upper} should be {expected} (lower x 1.25)")
    for name, s in r.sapto.items():
        if abs(s.max - r.sapto_taper * (s.cut_out - s.shade_out)) > 1:
            raise RatesError(f"SAPTO {name}: max, shade-out and cut-out don't agree with the taper")
    lito = r.lito
    if lito.max - lito.taper1_rate * (lito.taper1_to - lito.full_to) != lito.taper2_base:
        raise RatesError("LITO is not continuous at taper1_to")
    for tiers, name in ((r.mls.single, "single"), (r.mls.family, "family")):
        if [t.from_ for t in tiers] != sorted(t.from_ for t in tiers):
            raise RatesError(f"MLS {name} tiers must be ascending")
    bands = r.help.bands
    if [b.from_ for b in bands] != sorted(b.from_ for b in bands):
        raise RatesError("HELP thresholds must be ascending")
    if r.help.method == "marginal":
        for prev, cur in zip(bands, bands[1:]):
            expected = prev.base + prev.rate * (cur.from_ - prev.from_)
            if cur.base != expected:
                raise RatesError(f"HELP base at {cur.from_} is {cur.base}, expected {expected}")
    elif r.help.method != "percent_of_income":
        raise RatesError(f"unknown HELP method {r.help.method!r}")


def load_rates(income_year: int, path: Path | None = None) -> Rates:
    path = path or CONFIG_DIR / "rates" / f"fy{income_year}.yaml"
    if not path.exists():
        raise RatesError(f"No rates file for FY{income_year}: expected config/rates/fy{income_year}.yaml")
    try:
        rates = _parse(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (KeyError, TypeError, ValueError) as exc:
        raise RatesError(f"{path.name} is incomplete or malformed ({type(exc).__name__}: {exc})") from None
    validate_rates(rates)
    return rates
