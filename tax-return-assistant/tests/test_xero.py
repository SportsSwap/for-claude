import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest

from tra.figures import read_figures
from tra.filing.index import DocumentIndex
from tra.filing.local_store import LocalStore
from tra.ingest.classify import CATEGORIES
from tra.labels import load_labels
from tra.models import ClientState
from tra.privacy.audit import AuditLog
from tra.workspace import Workspace
from tra.xero.auth import TOKEN_URL, Tokens, authorize_url, exchange_code, pkce_pair, refresh_tokens
from tra.xero.client import XeroAuthError, XeroClient, XeroPermissionError, strip_sensitive
from tra.xero.to_figures import load_mapping, pl_to_figures, pull_to_workspace


class FakeResponse:
    def __init__(self, status=200, data=None, headers=None, text=""):
        self.status_code, self._data, self.headers, self.text = status, data, headers or {}, text or json.dumps(data)

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def _next(self, method, url, **kw):
        self.calls.append((method, url, kw))
        return self.responses.pop(0)

    def get(self, url, **kw):
        return self._next("GET", url, **kw)

    def post(self, url, **kw):
        return self._next("POST", url, **kw)


def test_pkce_challenge():
    verifier, challenge = pkce_pair()
    assert 43 <= len(verifier) <= 128
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected and "=" not in challenge


def test_authorize_url_params():
    url = authorize_url("CLIENT", "http://localhost:8765/callback", ["openid", "accounting.settings.read"], "st8", "chal")
    q = parse_qs(urlparse(url).query)
    assert q["code_challenge_method"] == ["S256"] and q["code_challenge"] == ["chal"]
    assert q["scope"] == ["openid accounting.settings.read"]
    assert q["response_type"] == ["code"] and "client_secret" not in q


def test_exchange_and_refresh():
    s = FakeSession(FakeResponse(data={"access_token": "a1", "refresh_token": "r1", "expires_in": 1800}),
                    FakeResponse(data={"access_token": "a2", "refresh_token": "r2", "expires_in": 1800}))
    t = exchange_code(s, "CLIENT", "code123", "verifier", "http://localhost:8765/callback")
    assert t.access_token == "a1" and t.expires_at > datetime.now(timezone.utc)
    assert s.calls[0][1] == TOKEN_URL and s.calls[0][2]["data"]["code_verifier"] == "verifier"
    t2 = refresh_tokens(s, "CLIENT", "r1")
    assert s.calls[1][2]["data"]["grant_type"] == "refresh_token" and t2.refresh_token == "r2"


def test_bank_transactions_paging():
    page1 = {"BankTransactions": [{"BankTransactionID": str(i)} for i in range(100)]}
    page2 = {"BankTransactions": [{"BankTransactionID": str(i)} for i in range(37)]}
    s = FakeSession(FakeResponse(data=page1), FakeResponse(data=page2))
    rows = XeroClient(s, "tok", "tenant-1").bank_transactions(datetime(2025, 7, 1).date(), datetime(2026, 6, 30).date())
    assert len(rows) == 137 and len(s.calls) == 2
    assert all(c[2]["headers"]["xero-tenant-id"] == "tenant-1" for c in s.calls)
    assert [c[2]["params"]["page"] for c in s.calls] == [1, 2]


def test_429_retry_then_ok():
    slept = []
    s = FakeSession(FakeResponse(429, headers={"Retry-After": "2"}), FakeResponse(data={"Accounts": []}))
    assert XeroClient(s, "tok", "t", sleep=slept.append).accounts() == []
    assert slept == [2]


def test_401_insufficient_scope_and_auth():
    s = FakeSession(FakeResponse(401, text='{"error":"insufficient_scope"}'))
    with pytest.raises(XeroPermissionError, match="tra xero connect"):
        XeroClient(s, "tok", "t").accounts()
    s = FakeSession(FakeResponse(401, text="expired"))
    with pytest.raises(XeroAuthError, match="tra xero connect"):
        XeroClient(s, "tok", "t").accounts()


def test_strip_sensitive():
    data = {"Accounts": [{"Name": "Business Cheque", "BankAccountNumber": "062000 12345678",
                          "Description": "Paid with card 4111 1111 1111 1111"}]}
    cleaned = strip_sensitive(data)
    assert "BankAccountNumber" not in cleaned["Accounts"][0]
    assert cleaned["Accounts"][0]["Description"] == "Paid with card [CARD REDACTED]"


PL = {"Reports": [{"ReportID": "ProfitAndLoss", "Rows": [
    {"RowType": "Header", "Cells": [{"Value": ""}, {"Value": "30 Jun 26"}]},
    {"RowType": "Section", "Title": "Income", "Rows": [
        {"RowType": "Row", "Cells": [{"Value": "Sales"}, {"Value": "120000.00"}]},
        {"RowType": "Row", "Cells": [{"Value": "Other Revenue"}, {"Value": "150.00"}]},
        {"RowType": "SummaryRow", "Cells": [{"Value": "Total Income"}, {"Value": "120150.00"}]}]},
    {"RowType": "Section", "Title": "Less Operating Expenses", "Rows": [
        {"RowType": "Row", "Cells": [{"Value": "Advertising"}, {"Value": "1200.00"}]},
        {"RowType": "Row", "Cells": [{"Value": "Motor Vehicle Expenses"}, {"Value": "3400.50"}]},
        {"RowType": "Row", "Cells": [{"Value": "Rent"}, {"Value": "24000.00"}]},
        {"RowType": "SummaryRow", "Cells": [{"Value": "Total Operating Expenses"}, {"Value": "28600.50"}]}]},
    {"RowType": "Section", "Title": "Mystery", "Rows": [
        {"RowType": "Row", "Cells": [{"Value": "Thing"}, {"Value": "5.00"}]}]},
    {"RowType": "Section", "Title": "", "Rows": [
        {"RowType": "SummaryRow", "Cells": [{"Value": "Net Profit"}, {"Value": "91549.50"}]}]},
]}]}


def test_pl_to_figures():
    figures, unknown = pl_to_figures(PL, load_mapping(), "D010")
    assert [(f.label_key, f.description, f.amount) for f in figures] == [
        ("income.business_income", "Sales", Decimal("120000.00")),
        ("income.business_income", "Other Revenue", Decimal("150.00")),
        ("income.business_expenses", "Advertising", Decimal("1200.00")),
        ("income.business_expenses", "Motor Vehicle Expenses", Decimal("3400.50")),
        ("income.business_expenses", "Rent", Decimal("24000.00")),
    ]
    assert all(f.method == "xero" and f.doc_id == "D010" and not f.confirmed for f in figures)
    assert unknown == ["Mystery"]


class FakeXero:
    def profit_and_loss(self, start, end):
        return PL

    def balance_sheet(self, as_at):
        return {"Reports": [{"ReportID": "BalanceSheet", "Rows": []}]}

    def bank_transactions(self, start, end):
        return [{"BankTransactionID": "1", "Total": 10.0}]

    def accounts(self):
        return [{"Code": "200", "Name": "Sales"}]


def test_pull_files_snapshots(tmp_path):
    ws = Workspace(tmp_path, "PLMB01", 2026)
    ws.create(list(CATEGORIES))
    ws.save_state(ClientState("PLMB01", 2026, sole_trader=True))
    audit = AuditLog(ws.audit_path)
    report = pull_to_workspace(ws, LocalStore(tmp_path), audit, FakeXero(), "tenant-9")
    docs = DocumentIndex(ws.index_csv).load()
    assert sorted(d.doc_type for d in docs) == ["XEROBANK", "XEROBS", "XEROCOA", "XEROPL"]
    pl_id = next(d.doc_id for d in docs if d.doc_type == "XEROPL")
    figures, errors = read_figures(ws.figures_csv, load_labels())
    assert errors == [] and len(figures) == 5 and {f.doc_id for f in figures} == {pl_id}
    assert ws.load_state().xero_tenant_id == "tenant-9"
    assert report.unknown_sections == ["Mystery"]
    audit_text = ws.audit_path.read_text()
    assert "xero_pull" in audit_text and "ProfitAndLoss" in audit_text


def test_cli_pull_requires_sign_in(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from tra.cli import main
    from tra.xero import auth
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(auth.TokenStore, "__init__", lambda self, *a, **k: None)
    monkeypatch.setattr(auth.TokenStore, "get", lambda self: None)
    env = {"TRA_HOME": str(home), "XERO_CLIENT_ID": "CLIENT"}
    runner = CliRunner()
    assert runner.invoke(main, ["new", "PLMB01", "--sole-trader"], env=env).exit_code == 0
    result = runner.invoke(main, ["xero", "pull", "PLMB01"], env=env)
    assert result.exit_code == 1 and "tra xero connect" in result.output


def test_cli_connect_needs_client_id(tmp_path):
    from click.testing import CliRunner

    from tra.cli import main
    home = tmp_path / "home"
    home.mkdir()
    result = CliRunner().invoke(main, ["xero", "connect"], env={"TRA_HOME": str(home), "XERO_CLIENT_ID": ""})
    assert result.exit_code == 1 and "XERO_CLIENT_ID" in result.output
