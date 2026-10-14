"""Read-only calls to the Xero Accounting API for one organisation (tenant).

Every response is cleaned before anything else sees it: bank account number
fields are dropped and every string is run through the redactor.
"""

from __future__ import annotations

import time
from datetime import date

from ..privacy.redact import redact_text

API_BASE = "https://api.xero.com/api.xro/2.0"
PAGE_SIZE = 100
MAX_RETRIES = 3
SENSITIVE_KEYS = frozenset({"BankAccountNumber", "AccountNumber", "BSB", "TaxNumber"})


class XeroError(Exception):
    pass


class XeroAuthError(XeroError):
    def __init__(self):
        super().__init__("Xero sign-in has expired: run 'tra xero connect'.")


class XeroPermissionError(XeroError):
    def __init__(self):
        super().__init__("Xero needs extra permissions: run 'tra xero connect' and approve again.")


def strip_sensitive(obj):
    if isinstance(obj, dict):
        return {k: strip_sensitive(v) for k, v in obj.items() if k not in SENSITIVE_KEYS}
    if isinstance(obj, list):
        return [strip_sensitive(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


def _xero_date(d: date) -> str:
    return f"DateTime({d.year},{d.month:02d},{d.day:02d})"


class XeroClient:
    def __init__(self, session, access_token: str, tenant_id: str, sleep=time.sleep):
        self.session, self.token, self.tenant_id, self.sleep = session, access_token, tenant_id, sleep

    def _get(self, path: str, params: dict | None = None):
        headers = {"Authorization": f"Bearer {self.token}", "xero-tenant-id": self.tenant_id,
                   "Accept": "application/json"}
        for _attempt in range(MAX_RETRIES + 1):
            response = self.session.get(f"{API_BASE}{path}", headers=headers, params=params or {}, timeout=60)
            if response.status_code == 429:
                self.sleep(int(response.headers.get("Retry-After", "1")))
                continue
            if response.status_code == 401:
                raise XeroPermissionError() if "insufficient_scope" in (response.text or "") else XeroAuthError()
            if response.status_code != 200:
                raise XeroError(f"Xero returned HTTP {response.status_code} for {path}")
            return strip_sensitive(response.json())
        raise XeroError(f"Xero kept rate-limiting {path}; try again in a minute")

    def profit_and_loss(self, from_date: date, to_date: date) -> dict:
        return self._get("/Reports/ProfitAndLoss", {"fromDate": from_date.isoformat(), "toDate": to_date.isoformat()})

    def balance_sheet(self, as_at: date) -> dict:
        return self._get("/Reports/BalanceSheet", {"date": as_at.isoformat()})

    def bank_transactions(self, from_date: date, to_date: date) -> list[dict]:
        where = f"Date >= {_xero_date(from_date)} AND Date <= {_xero_date(to_date)}"
        rows, page = [], 1
        while True:
            batch = self._get("/BankTransactions", {"page": page, "where": where}).get("BankTransactions", [])
            rows += batch
            if len(batch) < PAGE_SIZE:
                return rows
            page += 1

    def accounts(self) -> list[dict]:
        return self._get("/Accounts").get("Accounts", [])


def connections(session, access_token: str) -> list[dict]:
    from .auth import CONNECTIONS_URL
    response = session.get(CONNECTIONS_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
    if response.status_code != 200:
        raise XeroAuthError()
    return response.json()
