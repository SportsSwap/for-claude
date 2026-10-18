"""A Sawnx app on a temporary TRA_HOME, for web tests. Everything here is invented at test time."""

from flask.testing import FlaskClient

from tra.settings import Settings
from tra.web import create_app

KEY = "test-session-key-0123456789"
PORT = 8766
ORIGIN = f"http://127.0.0.1:{PORT}"


class SawnxClient(FlaskClient):
    """Talks to Sawnx the way the browser does: from 127.0.0.1, same-origin POSTs."""

    def open(self, *args, **kwargs):
        kwargs.setdefault("base_url", ORIGIN)
        method = kwargs.get("method", "GET").upper()
        if method not in ("GET", "HEAD"):
            headers = dict(kwargs.pop("headers", None) or {})
            headers.setdefault("Origin", ORIGIN)
            kwargs["headers"] = headers
        return super().open(*args, **kwargs)


def make_app(tmp_path, monkeypatch, **kwargs):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("TRA_HOME", str(home))
    settings = Settings.from_env()
    app = create_app(settings, KEY, PORT, **kwargs)
    app.test_client_class = SawnxClient
    return app, settings


def make_client(tmp_path, monkeypatch, **kwargs):
    """App, a client that already holds the session cookie, and the settings."""
    app, settings = make_app(tmp_path, monkeypatch, **kwargs)
    client = app.test_client()
    client.get(f"/?key={KEY}")
    return app, client, settings


def new_client(settings, code="TEST01", fy=2026, **state_options):
    from tra.clients import create_client
    from tra.privacy.audit import AuditLog
    from tra.workspace import Workspace

    audit = AuditLog(Workspace(settings.tra_home, code, fy).audit_path)
    return create_client(settings.tra_home, code, fy, state_options, audit)


def ingest_demo(settings, ws, *stems, tmp_dir=None):
    """Run named demo documents (e.g. "income_statement") through the real ingest pipeline."""
    from tra.demo import build_demo_documents
    from tra.filing.local_store import LocalStore
    from tra.ingest.classify import load_doc_types
    from tra.ingest.pipeline import ingest_file
    from tra.privacy.audit import AuditLog

    source = build_demo_documents((tmp_dir or settings.tra_home.parent) / "demo_src")
    audit = AuditLog(ws.audit_path)
    return [ingest_file(source.paths[s], ws, LocalStore(settings.tra_home), load_doc_types(), audit) for s in stems]


TEST01_DOCUMENTS = {
    "income_statement": ["Income statement", "Payer: SAMPLE CO PTY LTD", "Period 1 July 2025 to 30 June 2026",
                         "Gross payments 60,000.00", "Total tax withheld 11,000.00"],
    "bank_interest": ["SAMPLE BANK", "Account statement", "Period 1 July 2025 to 30 June 2026",
                      "Opening balance 20,000.00", "Interest earned 500.00", "Closing balance 20,500.00"],
    "dividend": ["SAMPLE MINING LTD", "Dividend statement", "Payment date 20 March 2026", "Unfranked amount 0.00",
                 "Franked amount 700.00", "Franking credit 300.00"],
    "receipt": ["SAMPLE PROFESSIONAL ASSOCIATION", "TAX INVOICE", "Date: 14/09/2025",
                "Annual membership fees 250.00", "Total 250.00"],
}


def build_test01(settings, code="TEST01"):
    """The hand-checked accuracy client: refund $993.25 on the FY2026 rates. Every figure confirmed."""
    from tra.demo import _write_pdf
    from tra.figures import read_figures, write_figures
    from tra.filing.local_store import LocalStore
    from tra.ingest.classify import load_doc_types
    from tra.ingest.pipeline import ingest_file
    from tra.labels import load_labels
    from tra.privacy.audit import AuditLog

    ws = new_client(settings, code)
    folder = settings.tra_home.parent / f"{code}_src"
    folder.mkdir(exist_ok=True)
    for stem, lines in TEST01_DOCUMENTS.items():
        _write_pdf(folder / f"{stem}.pdf", lines)
        ingest_file(folder / f"{stem}.pdf", ws, LocalStore(settings.tra_home), load_doc_types(),
                    AuditLog(ws.audit_path))
    figures, errors = read_figures(ws.figures_csv, load_labels())
    assert not errors and len(figures) == 6
    for f in figures:
        f.confirmed = True
    write_figures(ws.figures_csv, figures)
    return ws
