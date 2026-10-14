"""Helpers shared by the tax calculation tests."""

from decimal import Decimal

from tra.models import ClientState
from tra.return_.prepare import DraftReturn, LabelLine

D = Decimal


def draft(year=2026, **amounts) -> DraftReturn:
    """draft(salary=85000) -> a DraftReturn; keyword names map to label keys via KEYS."""
    lines = {}
    for name, value in amounts.items():
        key = KEYS.get(name, name.replace("__", "."))
        lines[key] = LabelLine(key, D(str(value)), ())
    return DraftReturn("TEST01", year, lines)


def state(year=2026, **kw) -> ClientState:
    return ClientState(client_code="TEST01", income_year=year, **kw)


KEYS = {
    "salary": "income.salary",
    "withheld": "income.salary_tax_withheld",
    "allowances": "income.allowances",
    "interest": "income.interest",
    "franked": "income.div_franked",
    "unfranked": "income.div_unfranked",
    "credit": "income.franking_credit",
    "rent": "rent.gross",
    "rent_other": "rent.other",
    "rent_interest": "rent.interest",
    "d5": "ded.d5",
    "d12": "ded.d12",
    "rfb": "it.rfb",
    "resc": "it.resc",
    "p1": "phi.premiums_p1",
    "r1": "phi.rebate_p1",
    "p2": "phi.premiums_p2",
    "r2": "phi.rebate_p2",
}

DEMO = dict(salary=85000, allowances=1200, withheld=19000, interest="412.35", franked=1200, credit="514.29",
            rent=26000, rent_other=5340, d5=2019, p1=1800, r1="437.18", p2=600, r2="144.71")
