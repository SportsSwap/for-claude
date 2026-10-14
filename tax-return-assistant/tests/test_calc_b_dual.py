import dataclasses
import random

from taxcases import DEMO, D, draft, state

from tra.checks.context import CheckContext
from tra.checks.dual_calc import check_dual_calc, check_rates_status
from tra.labels import load_labels
from tra.taxcalc.calc_a import calculate_a
from tra.taxcalc.calc_b import calculate_b
from tra.taxcalc.rates import load_rates

LABELS = load_labels()
RATES = {2025: load_rates(2025), 2026: load_rates(2026)}


def test_b_matches_a_across_range():
    rng = random.Random(42)
    for _ in range(5000):
        year = rng.choice((2025, 2026))
        amounts = dict(salary=rng.randint(0, 500000))
        if rng.random() < 0.3:
            amounts.update(rent=rng.randint(0, 40000), rent_interest=rng.randint(0, 40000))
        if rng.random() < 0.3:
            amounts.update(rfb=rng.randint(0, 20000), resc=rng.randint(0, 20000))
        if rng.random() < 0.3:
            amounts.update(p1=rng.randint(0, 3000), r1=rng.randint(0, 700), p2=rng.randint(0, 1000), r2=rng.randint(0, 250))
        if rng.random() < 0.2:
            amounts.update(franked=rng.randint(0, 5000), credit=rng.randint(0, 2000), d5=rng.randint(0, 5000))
        st = state(year, help_debt=rng.random() < 0.5, age_band=rng.choice(["under65", "65to69", "70plus"]),
                   sapto_status=rng.choice(["none", "none", "single", "couple", "illness_separated"]),
                   has_spouse=rng.random() < 0.2, dependants=rng.choice([0, 0, 1, 3]),
                   hospital_cover_days=rng.choice([None, 0, 100, 365]))
        d = draft(year, **amounts)
        a = calculate_a(d, st, RATES[year]).components()
        b = calculate_b(d, st, RATES[year], LABELS).components()
        assert a == b, (year, amounts, st, {k: (a[k], b[k]) for k in a if a[k] != b[k]})


def test_b_matches_a_demo():
    d, st = draft(**DEMO), state()
    assert calculate_b(d, st, RATES[2026], LABELS) == calculate_a(d, st, RATES[2026])


def _ctx(**kw):
    d, st = draft(**DEMO), state()
    a = calculate_a(d, st, RATES[2026])
    base = dict(draft=d, rates=RATES[2026], state=st, calc_a=a, calc_b=a, labels=LABELS)
    base.update(kw)
    return CheckContext(**base)


def test_dual_calc_flags_difference():
    ctx = _ctx()
    ctx.calc_b = dataclasses.replace(ctx.calc_a, medicare_levy=ctx.calc_a.medicare_levy + D("0.01"))
    notes = check_dual_calc(ctx)
    assert len(notes) == 1
    assert notes[0].check_id == "C1" and notes[0].risk == "High"
    assert "medicare_levy" in notes[0].message
    assert notes[0].dollar_impact == D("0.01")
    assert check_dual_calc(_ctx()) == []


def test_rates_status_note():
    [note] = check_rates_status(_ctx())
    assert note.check_id == "C2" and note.risk == "High"
    assert note.message == "FY2026 rates not yet verified against ato.gov.au by a registered agent"
    verified = dataclasses.replace(RATES[2026], status="verified")
    assert check_rates_status(_ctx(rates=verified)) == []
