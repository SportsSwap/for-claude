from decimal import Decimal

import pytest
import yaml

from tra.paths import CONFIG_DIR
from tra.taxcalc.rates import RatesError, load_rates


def test_load_both_years_valid():
    for year in (2025, 2026):
        rates = load_rates(year)
        assert rates.income_year == year
        assert rates.status == "unverified"
        assert rates.brackets[2].base == Decimal("4288")
        assert rates.brackets[1].rate == Decimal("0.16")
    assert load_rates(2026).help.method == "marginal"
    assert load_rates(2025).help.method == "percent_of_income"
    assert load_rates(2026).phi_rebate[1].rates["under65"][0] == Decimal("0.24118")


def test_missing_year():
    with pytest.raises(RatesError, match="fy2019.yaml"):
        load_rates(2019)


def _altered(tmp_path, change):
    data = yaml.safe_load((CONFIG_DIR / "rates" / "fy2026.yaml").read_text())
    change(data)
    path = tmp_path / "fy2026.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


@pytest.mark.parametrize(
    "change,rule",
    [
        (lambda d: d["resident_brackets"][2].update(base=4388), "base"),
        (lambda d: d["resident_brackets"].reverse(), "ascending"),
        (lambda d: d["medicare"]["single"].update(upper=35014), "Medicare"),
        (lambda d: d["sapto"]["single"].update(cut_out=52859), "SAPTO"),
        (lambda d: d["lito"].update(taper2_base=335), "LITO"),
        (lambda d: d["help"]["bands"][2].update(base=8800), "HELP"),
        (lambda d: d["mls"]["single"][1].update(rate=1.5), "rate"),
    ],
)
def test_validation_catches_typos(tmp_path, change, rule):
    with pytest.raises(RatesError, match=rule):
        load_rates(2026, _altered(tmp_path, change))
