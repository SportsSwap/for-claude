"""The `tra` command. Prepares drafts only; nothing here lodges anything."""

from __future__ import annotations

import dataclasses
import functools
import getpass
import os
import platform
import secrets
import sys
import webbrowser
from pathlib import Path

import click
import openpyxl
import pdfplumber
import requests
import yaml

from . import __version__
from .figures import read_figures, write_figures, write_header_files
from .filing.fyi_store import FyiError, FyiStore, load_fyi_config
from .filing.fyi_store import make_store as _make_store
from .filing.index import DocumentIndex
from .filing.store import DocumentStore, FilingRequest
from .ingest.classify import CATEGORIES, load_doc_types
from .ingest.pipeline import IngestError, ingest_file
from .labels import load_labels
from .models import ClientState
from .paths import CONFIG_DIR
from .privacy.audit import AuditLog
from .privacy.detectors import find_sensitive
from .privacy import guard
from .privacy.guard import FileLockedError, SensitiveDataBlocked
from .privacy.logging_filter import configure_logging
from .run import PrepareError, prepare_client
from .settings import ConfigError, Settings, check_tra_home, validate_client_code
from .workspace import Workspace

DEFAULT_FY = 2026
ENV_NAMES = ("TRA_HOME", "TRA_STORE", "XERO_CLIENT_ID", "FYI_BASE_URL", "FYI_ACCESS_ID", "FYI_ACCESS_SECRET",
             "FYI_APP_ID")
EXPECTED_ERRORS = (ConfigError, FileLockedError, SensitiveDataBlocked, IngestError, PrepareError, ValueError,
                   UnicodeDecodeError, OSError)


def _friendly(fn):
    """Show expected problems as a one-line message instead of a traceback."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except EXPECTED_ERRORS as exc:
            raise click.ClickException(str(exc)) from None
    return wrapper


def _settings() -> Settings:
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from None
    problems = check_tra_home(settings.tra_home)
    if problems:
        raise click.ClickException("\n".join(problems))
    configure_logging(settings.tra_home / "logs" / "tra.log")
    return settings


def _workspace(code: str, fy: int, *, must_exist: bool = True) -> tuple[Settings, Workspace, AuditLog]:
    settings = _settings()
    try:
        validate_client_code(code, settings.client_code_pattern)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from None
    ws = Workspace(settings.tra_home, code, fy)
    if must_exist and not ws.state_json.exists():
        raise click.ClickException(f"{code} FY{fy} doesn't exist yet. Run: tra new {code} --fy {fy}")
    audit = AuditLog(ws.audit_path)
    guard.set_block_listener(lambda location, kind: audit.record("guard_blocked", client=code, location=location,
                                                                 detector=kind))
    return settings, ws, audit


def make_store(settings: Settings) -> DocumentStore:
    return _make_store(settings, warn=lambda message: click.echo(f"WARNING {message}", err=True))


def _counts(counts: dict) -> str:
    return ", ".join(f"{k}×{v}" for k, v in sorted(counts.items())) or "nothing"


@click.group()
@click.version_option(__version__, prog_name="tra")
def main() -> None:
    """Tax Return Assistant: prepares DRAFT returns for review by a registered tax agent. Never lodges."""


@main.command()
@click.argument("code")
@click.option("--fy", default=DEFAULT_FY, show_default=True, help="Income year (FY2026 = 1 Jul 2025 – 30 Jun 2026).")
@click.option("--help-debt", is_flag=True, help="Client has a HELP/study loan debt.")
@click.option("--sole-trader", is_flag=True, help="Client runs a business (Xero).")
@click.option("--age-band", type=click.Choice(["under65", "65to69", "70plus"]), default="under65", show_default=True)
@click.option("--sapto", type=click.Choice(["none", "single", "couple", "illness_separated"]), default="none",
              show_default=True, help="Seniors and pensioners tax offset status.")
@click.option("--spouse", is_flag=True, help="Client had a spouse during the year.")
@click.option("--dependants", default=0, show_default=True)
@click.option("--hospital-days", type=int, default=None,
              help="Days covered by private hospital insurance (leave out if unknown).")
@_friendly
def new(code, fy, help_debt, sole_trader, age_band, sapto, spouse, dependants, hospital_days):
    """Set up a client for an income year."""
    _settings_, ws, audit = _workspace(code, fy, must_exist=False)
    if ws.state_json.exists():
        raise click.ClickException(f"{code} FY{fy} already exists.")
    ws.create(list(CATEGORIES))
    ws.save_state(ClientState(client_code=code, income_year=fy, help_debt=help_debt, sole_trader=sole_trader,
                              age_band=age_band, sapto_status=sapto, has_spouse=spouse, dependants=dependants,
                              hospital_cover_days=hospital_days))
    write_header_files(ws)
    audit.record("client_created", client=code, income_year=fy)
    click.echo(f"Created {code} FY{fy}.\nNext: tra ingest {code} <files...>")


def _skip(path: Path) -> bool:
    """Office lock files (~$name.xlsx) and hidden files are never client documents."""
    return path.name.startswith(("~$", "."))


def _expand(args: tuple[str, ...]) -> list[Path]:
    """Files, folders and wildcard patterns (PowerShell passes *.pdf through unexpanded)."""
    from .ingest.readers import SUPPORTED

    files: list[Path] = []
    for arg in args:
        path = Path(arg)
        if any(ch in arg for ch in "*?["):
            matches = sorted(p for p in path.parent.glob(path.name) if p.is_file() and not _skip(p))
        elif path.is_dir():
            matches = sorted(p for p in path.iterdir()
                             if p.is_file() and p.suffix.lower() in SUPPORTED and not _skip(p))
        else:
            matches = [path] if path.is_file() else []
        if not matches:
            raise click.ClickException(f"No files match {arg}")
        files += [m for m in matches if m not in files]
    return files


@main.command()
@click.argument("code")
@click.argument("paths", nargs=-1, required=True)
@click.option("--fy", default=DEFAULT_FY, show_default=True)
@click.option("--type", "override_type", default=None, help="Force a document type, e.g. DIVSTMT.")
@_friendly
def ingest(code, paths, fy, override_type):
    """Read, redact, file and extract figures from source documents (files, folders or *.pdf patterns)."""
    settings, ws, audit = _workspace(code, fy)
    files = _expand(paths)
    store, doc_types = make_store(settings), load_doc_types()
    failed = 0
    for n, path in enumerate(files, start=1):
        label = f"[{n}/{len(files)}]"
        try:
            report = ingest_file(path, ws, store, doc_types, audit, override_type)
        except EXPECTED_ERRORS as exc:
            failed += 1
            click.echo(f"{label} FAILED: {exc}", err=True)
            continue
        if report.duplicate:
            click.echo(f"{label} duplicate of {report.doc.doc_id}; skipped")
            continue
        d = report.doc
        click.echo(f"{label} {d.doc_id} {d.doc_type} {d.parse_status} {report.figures_added} figures "
                   f"(redacted: {_counts(d.redaction_counts)}) → {d.filed_name}")
        for note in report.notes:
            click.echo(f"      {note.risk}: {note.message}")
    click.echo(f"\nNext: tra figures {code}   (check and confirm the figures)")
    if failed:
        raise SystemExit(1)


@main.command()
@click.argument("code")
@click.option("--fy", default=DEFAULT_FY, show_default=True)
@click.option("--no-open", is_flag=True, help="Validate only; don't open Excel.")
@_friendly
def figures(code, fy, no_open):
    """Check figures.csv and open it in Excel to confirm figures."""
    _s, ws, _a = _workspace(code, fy)
    loaded, errors = read_figures(ws.figures_csv, load_labels())
    for error in errors:
        click.echo(f"PROBLEM {error}")
    if errors:
        raise click.ClickException(f"{len(errors)} row(s) in figures.csv need fixing.")
    write_figures(ws.figures_csv, loaded)
    confirmed = sum(f.confirmed for f in loaded)
    click.echo(f"{len(loaded)} figures, {confirmed} confirmed, {len(loaded) - confirmed} not yet confirmed.")
    click.echo("Set confirmed to Y for each figure you have checked against its source. "
               "Pre-fill rows (notes = prefill) only need confirming when no other document supports the figure.")
    if not no_open:
        if hasattr(os, "startfile"):
            os.startfile(ws.figures_csv)  # noqa: S606 - Windows only
        else:
            click.echo(str(ws.figures_csv))


@main.command()
@click.argument("code")
@click.option("--fy", default=DEFAULT_FY, show_default=True)
@_friendly
def prepare(code, fy):
    """Build the draft return, run both tax calculations and every check, and write the workpaper."""
    _s, ws, audit = _workspace(code, fy)
    try:
        result = prepare_client(ws, audit, getpass.getuser())
    except EXPECTED_ERRORS as exc:
        raise click.ClickException(str(exc)) from None
    net = result.calc_a.net_result
    risks = {r: sum(n.risk == r for n in result.notes) for r in ("High", "Medium", "Low")}
    click.echo(f"Workpaper: {result.workpaper}")
    click.echo(f"Estimated {'payable' if net >= 0 else 'refund'} ${abs(net):,.2f}")
    click.echo(f"Review notes: {risks['High']} High, {risks['Medium']} Medium, {risks['Low']} Low")
    for note in [n for n in result.notes if n.risk == "High"][:5]:
        click.echo(f"  High {note.check_id}: {note.message}")
    click.echo("Draft only — review and sign-off by a registered tax agent required. Nothing has been lodged.")

def _scan_file(path: Path) -> list[tuple[str, str]]:
    suffix = path.suffix.lower()
    hits = []
    if suffix == ".xlsx":
        wb = openpyxl.load_workbook(path, data_only=False)
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value is not None:
                        hits += [(f"{ws.title}!{cell.coordinate}", m.type) for m in find_sensitive(str(cell.value))]
    elif suffix == ".pdf":
        with pdfplumber.open(path) as pdf:
            for n, page in enumerate(pdf.pages, start=1):
                hits += [(f"page {n}", m.type) for m in find_sensitive(page.extract_text() or "")]
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in find_sensitive(text):
            hits.append((str(text.count("\n", 0, m.start) + 1), m.type))
    return hits


@main.command()
@click.argument("target", type=click.Path(exists=True, path_type=Path))
@_friendly
def scan(target):
    """Report possible identifiers in a file or folder (types and locations, never values)."""
    files = [p for p in sorted(target.rglob("*")) if p.is_file()] if target.is_dir() else [target]
    found = 0
    for path in files:
        try:
            hits = _scan_file(path)
        except Exception as exc:  # unreadable file: report and carry on
            click.echo(f"{path}: could not read ({type(exc).__name__})")
            continue
        for where, kind in hits:
            found += 1
            click.echo(f"{path}:{where} {kind}")
    click.echo(f"{found} possible identifier(s) found.")
    if found:
        raise SystemExit(1)


@main.command()
@_friendly
def doctor():
    """Check this computer's setup."""
    problem = False
    ok = sys.version_info >= (3, 11)
    click.echo(f"{'OK     ' if ok else 'PROBLEM'} Python {platform.python_version()}")
    problem |= not ok
    try:
        settings = Settings.from_env()
        problems = check_tra_home(settings.tra_home)
        for p in problems:
            click.echo(f"PROBLEM {p}")
        if not problems:
            click.echo(f"OK      TRA_HOME {settings.tra_home}")
        click.echo(f"OK      TRA_STORE {settings.store}")
        problem |= bool(problems)
    except ConfigError as exc:
        click.echo(f"PROBLEM {exc}")
        problem = True
    for rates in sorted((CONFIG_DIR / "rates").glob("fy*.yaml")):
        data = yaml.safe_load(rates.read_text(encoding="utf-8"))
        status = data.get("status", "unknown")
        mark = "OK     " if status == "verified" else "WARNING"
        click.echo(f"{mark} FY{data.get('income_year')} rates: status: {status}"
                   + ("" if status == "verified" else " (a registered agent must verify against ato.gov.au)"))
    for name in ENV_NAMES[2:]:
        click.echo(f"INFO    {name} {'set' if os.environ.get(name) else 'not set'}")
    if problem:
        raise SystemExit(1)


@main.group()
def xero():
    """Xero, for sole trader clients. Read-only: nothing is ever written to Xero."""


def _xero_client_id() -> str:
    client_id = os.environ.get("XERO_CLIENT_ID", "").strip()
    if not client_id:
        raise click.ClickException("XERO_CLIENT_ID is not set. Register the firm's app on developer.xero.com "
                                   "(see README, 'Xero setup') and set it as a Windows user environment variable.")
    return client_id


@xero.command()
@_friendly
def connect():
    """Sign in to Xero in your browser and list the organisations you can read."""
    from .xero.auth import REDIRECT_URI, TokenStore, XeroSignInError, authorize_url, exchange_code, pkce_pair, wait_for_code
    from .xero.client import XeroError, connections
    from .xero.to_figures import load_mapping

    client_id = _xero_client_id()
    _settings()
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    click.echo("Opening Xero sign-in in your browser. Approve access, then come back here.")
    webbrowser.open(authorize_url(client_id, REDIRECT_URI, load_mapping()["scopes"], state, challenge))
    try:
        code = wait_for_code(state)
        session = requests.Session()
        tokens = exchange_code(session, client_id, code, verifier, REDIRECT_URI)
        TokenStore().set(tokens)
        orgs = connections(session, tokens.access_token)
    except (XeroSignInError, XeroError) as exc:
        raise click.ClickException(str(exc)) from None
    click.echo("Signed in. Organisations available:")
    for org in orgs:
        click.echo(f"  {org.get('tenantName')}  (tenant id {org.get('tenantId')})")
    click.echo("Next: tra xero pull <CLIENT CODE> --tenant <tenant id>")


@xero.command()
@click.argument("code")
@click.option("--fy", default=DEFAULT_FY, show_default=True)
@click.option("--tenant", default=None, help="Xero tenant id (from `tra xero connect`). Remembered per client.")
@_friendly
def pull(code, fy, tenant):
    """Pull P&L, balance sheet, bank transactions and chart of accounts for the income year."""
    from .xero.auth import TokenStore, XeroSignInError, refresh_tokens
    from .xero.client import XeroClient, XeroError, connections
    from .xero.to_figures import pull_to_workspace

    settings, ws, audit = _workspace(code, fy)
    client_id = _xero_client_id()
    store = TokenStore()
    tokens = store.get()
    if tokens is None:
        raise click.ClickException("Not signed in to Xero: run 'tra xero connect' first.")
    session = requests.Session()
    try:
        if tokens.expired():
            tokens = refresh_tokens(session, client_id, tokens.refresh_token)
            store.set(tokens)
        tenant = tenant or ws.load_state().xero_tenant_id
        if not tenant:
            orgs = connections(session, tokens.access_token)
            if len(orgs) != 1:
                names = ", ".join(f"{o.get('tenantName')} ({o.get('tenantId')})" for o in orgs)
                raise click.ClickException(f"Choose the organisation with --tenant. Available: {names}")
            tenant = orgs[0]["tenantId"]
        report = pull_to_workspace(ws, make_store(settings), audit,
                                   XeroClient(session, tokens.access_token, tenant), tenant)
    except (XeroSignInError, XeroError) as exc:
        raise click.ClickException(str(exc)) from None
    click.echo(f"Filed Xero reports as {', '.join(report.doc_ids.values())}; {report.figures_added} figures added "
               "to figures.csv (unconfirmed).")
    if report.unknown_sections:
        click.echo(f"Not mapped: {', '.join(report.unknown_sections)} (see config/xero_mapping.yaml)")
    click.echo(f"Next: tra figures {code}")

@main.group()
def fyi():
    """FYI Docs filing."""


@fyi.command()
@click.argument("code")
@click.option("--fy", default=DEFAULT_FY, show_default=True)
@_friendly
def push(code, fy):
    """File documents that are still only in local folders into FYI."""
    settings, ws, audit = _workspace(code, fy)
    env = {name: os.environ.get(name, "") for name in ("FYI_BASE_URL", "FYI_ACCESS_ID", "FYI_ACCESS_SECRET", "FYI_APP_ID")}
    if not all(env.values()):
        raise click.ClickException("Set FYI_BASE_URL, FYI_ACCESS_ID, FYI_ACCESS_SECRET and FYI_APP_ID first "
                                   "(see README, 'FYI setup').")
    store = FyiStore(requests.Session(), env["FYI_BASE_URL"], env["FYI_ACCESS_ID"], env["FYI_ACCESS_SECRET"],
                     env["FYI_APP_ID"], load_fyi_config())
    index = DocumentIndex(ws.index_csv)
    pushed, failed = [], 0
    for doc in [d for d in index.load() if d.store == "local"]:
        req = FilingRequest(ws.client_code, ws.income_year, doc.category, doc.filed_name, doc.doc_type, doc.doc_date)
        try:
            ref = store.file(Path(doc.filed_location), req)
        except (FyiError, OSError) as exc:
            failed += 1
            click.echo(f"{doc.doc_id} FAILED: {exc}", err=True)
            continue
        index.update(dataclasses.replace(doc, store=ref.store, filed_location=ref.location))
        pushed.append(doc.doc_id)
        click.echo(f"{doc.doc_id} → FYI")
    audit.record("fyi_push", client=code, doc_ids=pushed, failed=failed)
    click.echo(f"{len(pushed)} pushed, {failed} failed.")
    if failed:
        raise SystemExit(1)

@main.command()
@click.option("--auto-confirm", is_flag=True, help="Mark the demo figures confirmed so you can run prepare straight away.")
@_friendly
def demo(auto_confirm):
    """Create a fake client DEMO01 from invented documents, to try the tool safely."""
    from .demo import build_demo_documents

    settings, ws, audit = _workspace("DEMO01", DEFAULT_FY, must_exist=False)
    if not ws.state_json.exists():
        ws.create(list(CATEGORIES))
        ws.save_state(ClientState(client_code="DEMO01", income_year=DEFAULT_FY))
        write_header_files(ws)
        audit.record("client_created", client="DEMO01", income_year=DEFAULT_FY)
    inbox = settings.tra_home / "Inbox" / "DEMO01"
    client = build_demo_documents(inbox)
    store, doc_types = make_store(settings), load_doc_types()
    for path in client.paths.values():
        report = ingest_file(path, ws, store, doc_types, audit)
        if not report.duplicate:
            click.echo(f"{report.doc.doc_id} {report.doc.doc_type} → {report.doc.filed_name}")
    if auto_confirm:
        loaded, _errors = read_figures(ws.figures_csv, load_labels())
        for f in loaded:
            f.confirmed = f.notes != "prefill"
        write_figures(ws.figures_csv, loaded)
        click.echo("Demo figures confirmed (pre-fill duplicates left unconfirmed).")
    click.echo(f"\nDemo documents are in {inbox}.\nNext: tra prepare DEMO01")


if __name__ == "__main__":
    main()
