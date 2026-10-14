from datetime import date
from decimal import Decimal

from tra.figures import CgtEvent
from tra.labels import load_labels
from tra.models import Figure
from tra.return_.cgt import compute_cgt, discount_eligible
from tra.return_.prepare import build_draft

LABELS = load_labels()
D = Decimal


def _event(eid, acquired, disposed, proceeds, cost, confirmed=True):
    return CgtEvent(eid, f"asset {eid}", acquired, disposed, D(proceeds), D(cost), "D009", 1, confirmed)


def _fig(fid, key, amount, confirmed=True):
    return Figure(fid, key, "x", D(amount), None, "D001", 1, "parser", confirmed, None, "")


def test_discount_eligibility():
    assert discount_eligible(date(2024, 7, 1), date(2025, 7, 1)) is False
    assert discount_eligible(date(2024, 7, 1), date(2025, 7, 2)) is True
    assert discount_eligible(date(2024, 2, 29), date(2025, 3, 1)) is False
    assert discount_eligible(date(2024, 2, 29), date(2025, 3, 2)) is True


def test_cgt_loss_ordering():
    events = [
        _event("C001", date(2020, 1, 1), date(2026, 3, 1), "20000", "10000"),   # discount gain 10,000
        _event("C002", date(2025, 9, 1), date(2026, 3, 1), "9000", "5000"),     # non-discount gain 4,000
        _event("C003", date(2021, 1, 1), date(2026, 3, 1), "1000", "6000"),     # loss 5,000
    ]
    s = compute_cgt(events, prior_losses=D("0"))
    assert s.total_current_gains == D("14000")
    assert s.net_capital_gain == D("4500.00")
    assert s.losses_carried_forward == D("0")
    assert s.discount_events == ("C001",)
    assert s.events_used == ("C001", "C002", "C003")


def test_cgt_prior_losses_carried_forward():
    s = compute_cgt([_event("C001", date(2020, 1, 1), date(2026, 3, 1), "3000", "1000")], prior_losses=D("5000"))
    assert s.net_capital_gain == D("0")
    assert s.losses_carried_forward == D("3000")


def test_cgt_current_loss_only_carried_forward():
    s = compute_cgt([_event("C001", date(2020, 1, 1), date(2026, 3, 1), "1000", "2500")], prior_losses=D("0"))
    assert s.total_current_gains == D("0")
    assert s.net_capital_gain == D("0")
    assert s.losses_carried_forward == D("1500")


def test_cgt_non_resident_no_discount():
    s = compute_cgt([_event("C001", date(2020, 1, 1), date(2026, 3, 1), "3000", "1000")], D("0"), resident=False)
    assert s.net_capital_gain == D("2000")


def test_cgt_unconfirmed_ignored():
    s = compute_cgt([_event("C001", date(2020, 1, 1), date(2026, 3, 1), "3000", "1000", confirmed=False)], D("0"))
    assert s.net_capital_gain == D("0") and s.events_used == ()


def test_build_draft_confirmed_only():
    figures = [_fig("F0001", "income.interest", "100.00"), _fig("F0002", "income.interest", "312.35"),
               _fig("F0003", "income.interest", "999.00", confirmed=False), _fig("F0004", "cgt.prior_losses", "500")]
    events = [_event("C001", date(2020, 1, 1), date(2026, 3, 1), "3000", "1000")]
    draft = build_draft("SMIT01", 2026, figures, events, LABELS)
    assert draft.amount("income.interest") == D("412.35")
    assert draft.lines["income.interest"].figure_ids == ("F0001", "F0002")
    assert draft.amount("income.salary") == D("0")
    assert draft.amount("cgt.total_gains") == D("2000")
    assert draft.amount("cgt.net_gain") == D("750.00")
    assert draft.lines["cgt.net_gain"].figure_ids == ("C001",)
    assert draft.cgt.losses_carried_forward == D("0")
