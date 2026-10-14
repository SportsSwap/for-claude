"""The whole flow on a fake client, then a scan of everything the tool wrote."""

import csv
import hashlib
import io
import random
from decimal import Decimal

import openpyxl
import pytest
from click.testing import CliRunner

from tra.cli import main
from tra.demo import DemoIdentifiers, build_demo_documents
from tra.workspace import Workspace


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


def _run(home, *args):
    return CliRunner().invoke(main, list(args), env={"TRA_HOME": str(home), "TRA_STORE": "local"},
                              catch_exceptions=False)


def _confirm_all_but_prefill(home, code):
    path = Workspace(home, code, 2026).figures_csv
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["confirmed"] = "N" if r["notes"] == "prefill" else "Y"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def _identifiers(make_tfn, make_medicare, make_card):
    rng = random.Random(7)
    t, m, c = make_tfn(), make_medicare(irn=False), make_card()
    return DemoIdentifiers(tfn=f"{t[:3]} {t[3:6]} {t[6:]}", medicare=f"{m[:4]} {m[4:9]} {m[9]}",
                           card=" ".join(c[i:i + 4] for i in range(0, 16, 4)),
                           bsb=f"0{rng.randint(10, 99)}-{rng.randint(100, 999)}",
                           account=f"{rng.randint(1000, 9999)} {rng.randint(1000, 9999)}",
                           licence=str(rng.randint(10_000_000, 99_999_999)))


def _all_text(path):
    if path.suffix == ".xlsx":
        wb = openpyxl.load_workbook(path)
        return "\n".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows() for c in row
                         if c.value is not None)
    return path.read_bytes().decode("utf-8", errors="ignore")


def test_end_to_end_no_leaks(home, tmp_path, make_tfn, make_medicare, make_card):
    ids = _identifiers(make_tfn, make_medicare, make_card)
    demo = build_demo_documents(tmp_path / "inbox", ids)
    assert _run(home, "new", "SMIT01").exit_code == 0
    result = _run(home, "ingest", "SMIT01", *map(str, demo.paths.values()))
    assert result.exit_code == 0, result.output
    for planted in ("TFN×1", "MEDICARE×1", "CARD×1", "ACCOUNT×1, BSB×1"):
        assert planted in result.output  # the identifiers really were in the documents, and were removed
    _confirm_all_but_prefill(home, "SMIT01")
    result = _run(home, "prepare", "SMIT01")
    assert result.exit_code == 0, result.output
    assert "Estimated payable $5,697.11" in result.output
    assert "Nothing has been lodged" in result.output
    ws = Workspace(home, "SMIT01", 2026)
    assert (ws.output_dir / "SMIT01_FY2026_Workpaper_DRAFT_v1.xlsx").exists()
    audit = "".join(p.read_text() for p in (home / "audit").glob("*.jsonl"))
    assert "workpaper_generated" in audit

    long_ids = [ids.tfn, ids.medicare, ids.card]
    exact_ids = [ids.bsb, ids.account, ids.licence]
    scanned = 0
    for path in home.rglob("*"):
        if not path.is_file() or path.suffix == ".pdf":
            continue  # filed originals are the client's own documents, kept unchanged by design
        text = _all_text(path)
        flat = text.replace(" ", "").replace("-", "")
        for ident in long_ids:
            assert ident.replace(" ", "") not in flat, f"{ident!r} leaked into {path.relative_to(home)}"
        for ident in exact_ids:
            assert ident not in text, f"{ident!r} leaked into {path.relative_to(home)}"
        scanned += 1
    assert scanned >= 8  # figures, cgt, prefill, notes, state, index, last_return, workpaper, audit, log


def test_prepare_twice_versions(home):
    assert _run(home, "demo", "--auto-confirm").exit_code == 0
    assert _run(home, "prepare", "DEMO01").exit_code == 0
    out = Workspace(home, "DEMO01", 2026).output_dir
    v1 = out / "DEMO01_FY2026_Workpaper_DRAFT_v1.xlsx"
    before = hashlib.sha256(v1.read_bytes()).hexdigest()
    assert _run(home, "prepare", "DEMO01").exit_code == 0
    assert (out / "DEMO01_FY2026_Workpaper_DRAFT_v2.xlsx").exists()
    assert hashlib.sha256(v1.read_bytes()).hexdigest() == before


def test_prepare_reports_figure_errors(home):
    assert _run(home, "demo").exit_code == 0
    ws = Workspace(home, "DEMO01", 2026)
    with ws.figures_csv.open("a", encoding="utf-8") as fh:
        fh.write("F0999,income.salry,typo,10.00,,,,manual,Y,,\r\n")
    rows_before = ws.figures_csv.read_text(encoding="utf-8").count("\n")
    result = _run(home, "prepare", "DEMO01")
    assert result.exit_code == 1
    assert "income.salry" in result.output and "row" in result.output
    assert not list(ws.output_dir.glob("*.xlsx"))
    assert ws.figures_csv.read_text(encoding="utf-8").count("\n") == rows_before


def test_demo_expected_notes(home):
    from tra.privacy.audit import AuditLog
    from tra.run import prepare_client
    assert _run(home, "demo", "--auto-confirm").exit_code == 0
    ws = Workspace(home, "DEMO01", 2026)
    result = prepare_client(ws, AuditLog(ws.audit_path), "tester")
    found = {n.check_id for n in result.notes}
    assert {"C2", "S4", "S13", "S9"} <= found
    assert not {"C1", "R1", "R4", "P1", "P2"} & found
    assert result.calc_a.net_result == Decimal("5697.11")
