"""A fake client's source documents, for trying the tool and for tests.

Every name, number and amount here is invented. By default the identifiers
fail their check digits and are caught only by the keyword rules, so running
the demo never writes a number that could be a real person's TFN or Medicare
number. Tests pass checksum-valid identifiers generated in memory instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


@dataclass(frozen=True)
class DemoIdentifiers:
    tfn: str
    medicare: str
    card: str
    bsb: str
    account: str
    licence: str


SAFE_IDENTIFIERS = DemoIdentifiers(
    tfn="123 456 789",
    medicare="1234 56789 0",
    card="4111 1111 1111 1111",  # the public Visa test number
    bsb="062-000",
    account="1234 5678",
    licence="12345678",
)


@dataclass
class DemoClient:
    paths: dict[str, Path]
    expected: dict[str, Decimal]


def _documents(ids: DemoIdentifiers) -> dict[str, list[str]]:
    return {
        "prefill": [
            "Individual pre-fill report",
            "Income year 2026",
            "Taxpayer: ALEX DEMO",
            f"TFN {ids.tfn}",
            "Issue date: 15/07/2026",
            "Salary or wages  ACME PTY LTD  Gross payments 85,000.00  Tax withheld 19,000.00",
            "Interest  COMMONWEALTH BANK  Gross interest 412.35  TFN amounts withheld 0.00",
            "Dividends  BHP GROUP LTD  Unfranked 0.00  Franked 1,200.00  Franking credit 514.29",
            "Private health insurance  DEMO HEALTH FUND  Premiums eligible 2,400.00  Rebate received 581.89",
            "HELP  Debt balance indicator  No",
        ],
        "income_statement": [
            "Income statement",
            "Payer: ACME PTY LTD",
            f"Payee TFN {ids.tfn}",
            "Period 1 July 2025 to 30 June 2026",
            "Gross payments 85,000.00",
            "Total tax withheld 19,000.00",
            "Allowances 1,200.00",
            "Reportable fringe benefits amount 0.00",
            "Reportable employer superannuation contributions 0.00",
        ],
        "bank_interest": [
            "COMMONWEALTH BANK",
            "Account statement",
            f"BSB {ids.bsb} Account number {ids.account}",
            "Period 1 July 2025 to 30 June 2026",
            "Opening balance 10,240.00",
            "Interest earned 412.35",
            "Closing balance 10,652.35",
        ],
        "dividend_bhp": [
            "BHP GROUP LTD",
            "Dividend statement",
            "Payment date 24 March 2026",
            "Unfranked amount 0.00",
            "Franked amount 1,200.00",
            "Franking credit 514.29",
        ],
        "rental": [
            "Rental statement",
            "Property manager: DEMO REALTY",
            "Property: 1 Example Street, Demo NSW",
            "Period 1 July 2025 to 30 June 2026",
            "Total rent received 26,000.00",
            "Management fees 1,820.00",
            "Repairs - leaking tap 640.00",
            "Council rates 2,100.00",
            "Water rates 780.00",
            "Total expenses 5,340.00",
            "Net to owner 20,660.00",
        ],
        "phi": [
            "Private health insurance statement",
            "DEMO HEALTH FUND",
            "Statement period 1 July 2025 to 30 June 2026",
            f"Medicare card {ids.medicare}",
            "Premiums eligible for rebate 1 July - 31 March 1,800.00",
            "Rebate received 1 July - 31 March 437.18",
            "Premiums eligible for rebate 1 April - 30 June 600.00",
            "Rebate received 1 April - 30 June 144.71",
            "Benefit code 30",
        ],
        "receipt_laptop": [
            "OFFICEWORKS",
            "TAX INVOICE",
            "ABN 51 824 753 556",
            "Date: 12/08/2025",
            "Laptop computer 1,499.00",
            "Total 1,499.00",
            f"Paid by card {ids.card}",
        ],
        "receipt_union": [
            # Deliberately undated, so it is not treated as substantiated.
            "DEMO WORKERS UNION",
            "Receipt",
            "Annual membership fees 520.00",
            "Amount paid 520.00",
        ],
    }


EXPECTED = {
    "income.salary": Decimal("85000.00"),
    "income.salary_tax_withheld": Decimal("19000.00"),
    "income.allowances": Decimal("1200.00"),
    "income.interest": Decimal("412.35"),
    "income.div_franked": Decimal("1200.00"),
    "income.franking_credit": Decimal("514.29"),
    "rent.gross": Decimal("26000.00"),
    "rent.other": Decimal("5340.00"),
    "phi.premiums_p1": Decimal("1800.00"),
    "phi.rebate_p1": Decimal("437.18"),
    "phi.premiums_p2": Decimal("600.00"),
    "phi.rebate_p2": Decimal("144.71"),
    "ded.d5": Decimal("2019.00"),
}


def _write_pdf(path: Path, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 16
    c.showPage()
    c.save()


def build_demo_documents(target: Path, ids: DemoIdentifiers = SAFE_IDENTIFIERS) -> DemoClient:
    """Write the demo PDFs into ``target``. Keys of ``paths`` are the file stems."""
    target.mkdir(parents=True, exist_ok=True)
    paths = {}
    for stem, lines in _documents(ids).items():
        path = target / f"{stem}.pdf"
        _write_pdf(path, lines)
        paths[stem] = path
    return DemoClient(paths=paths, expected=dict(EXPECTED))
