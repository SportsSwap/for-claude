import pytest
from taxcases import DEMO, D, draft, state

from tra.taxcalc.calc_a import calculate_a
from tra.taxcalc.rates import load_rates

R26, R25 = load_rates(2026), load_rates(2025)


def calc(year=2026, st=None, **amounts):
    rates = R26 if year == 2026 else R25
    return calculate_a(draft(year, **amounts), st or state(year), rates)


@pytest.mark.parametrize("ti,tax", [(18200, "0"), (18201, "0.16"), (45000, "4288.00"), (45001, "4288.30"),
                                    (135000, "31288.00"), (190000, "51638.00"), (200000, "56138.00")])
def test_bracket_edges(ti, tax):
    result = calc(salary=ti)
    assert result.taxable_income == D(ti)
    assert result.basic_tax == D(tax)


@pytest.mark.parametrize("ti,lito", [(37500, "700.00"), (40000, "575.00"), (45000, "325.00"), (50000, "250.00"),
                                     (66667, "0.00"), (90000, "0.00")])
def test_lito(ti, lito):
    assert calc(salary=ti).lito == D(lito)


@pytest.mark.parametrize("ti,levy", [(28011, "0.00"), (30000, "198.90"), (35013, "700.20"), (35014, "700.28"),
                                     (85000, "1700.00")])
def test_medicare_shade_in(ti, levy):
    assert calc(salary=ti).medicare_levy == D(levy)


@pytest.mark.parametrize("ri,repay", [(67000, "0.00"), (80000, "1950.00"), (125000, "8700.00"),
                                      (150000, "12950.00"), (179286, "17928.60")])
def test_help_fy2026(ri, repay):
    assert calc(salary=ri, st=state(help_debt=True)).help == D(repay)


@pytest.mark.parametrize("ri,repay", [(54434, "0.00"), (54435, "544.35"), (100000, "5500.00")])
def test_help_fy2025_percent(ri, repay):
    assert calc(2025, st=state(2025, help_debt=True), salary=ri).help == D(repay)


def test_help_only_with_debt():
    assert calc(salary=150000).help == D("0.00")


def test_mls():
    assert calc(salary=120000, st=state(hospital_cover_days=0)).mls == D("1500.00")
    assert calc(salary=120000, st=state(hospital_cover_days=365)).mls == D("0.00")
    assert calc(salary=120000).mls == D("0.00")  # unknown cover: assumed covered, flagged by S9
    assert calc(salary=100000, st=state(hospital_cover_days=0)).mls == D("0.00")


def test_mls_part_year():
    # 1.25% x 120,000 x 165/365
    assert calc(salary=120000, st=state(hospital_cover_days=200)).mls == D("678.08")


def test_phi_adjustment_base_tier():
    result = calc(salary=85000, p1=1800, r1="437.18", p2=600, r2="144.71")
    assert result.phi_adjustment == D("0.00")


def test_sapto_single():
    # Rebate income 40,000: 2,230 - 12.5% x (40,000 - 34,919) = 1,594.88
    result = calc(salary=40000, st=state(sapto_status="single", age_band="70plus"))
    assert result.sapto == D("1594.88")
    assert result.offsets_used == min(result.basic_tax, result.lito + result.sapto)
    assert result.medicare_levy == D("0.00")  # below the SAPTO threshold of 44,268


def test_offsets_limited_to_tax():
    result = calc(salary=20000)
    assert result.basic_tax == D("288.00")
    assert result.offsets_used == D("288.00")


def test_negative_gearing_and_rental_loss_in_mls_income():
    result = calc(salary=100000, rent=10000, rent_interest=15000)
    assert result.taxable_income == D("95000")
    assert result.mls_income == D("100000")


def test_demo_client_net_result():
    """Demo client, FY2026, single, under 65, no HELP, hospital cover assumed.

    Total income  85,000 + 1,200 + 412.35 + 1,200 + 514.29 + (26,000 - 5,340) = 108,986.64
    Deductions    2,019            Taxable income 106,967 (cents dropped)
    Basic tax     4,288 + 30% x (106,967 - 45,000)     = 22,878.10
    LITO          nil above 66,667
    Medicare      2% x 106,967                          =  2,139.34
    PHI           MLS income 106,967 is Tier 1:
                  1,800 x 16.192% = 291.46; 600 x 16.079% = 96.47
                  received 437.18 + 144.71 = 581.89 -> over-received 193.96
    Credits       franking 514.29, PAYG 19,000
    Net           22,878.10 + 2,139.34 + 193.96 - 514.29 - 19,000 = 5,697.11 payable
    """
    r = calc(**DEMO)
    assert r.total_income == D("108986.64")
    assert r.deductions == D("2019")
    assert r.taxable_income == D("106967")
    assert r.basic_tax == D("22878.10")
    assert r.lito == D("0.00")
    assert r.medicare_levy == D("2139.34")
    assert r.phi_adjustment == D("193.96")
    assert r.franking_credits == D("514.29")
    assert r.payg_withheld == D("19000")
    assert r.net_result == D("5697.11")
    assert set(r.components()) >= {"taxable_income", "basic_tax", "net_result"}


def test_personal_super_counts_in_income_tests():
    # Reportable super contributions include deductible personal contributions (D12).
    assert calc(salary=100000, d12=10000, st=state(help_debt=True)).help == D("4950.00")
    assert calc(salary=110000, d12=15000, st=state(hospital_cover_days=0)).mls == D("950.00")
