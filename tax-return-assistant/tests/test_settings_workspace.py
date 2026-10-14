from pathlib import Path

import pytest

from tra.models import ClientState
from tra.settings import ConfigError, Settings, check_tra_home, validate_client_code
from tra.workspace import Workspace

CATEGORIES = ("ATO", "Income", "Investments", "Rental", "Deductions", "Business", "Health", "Other")


def test_settings_from_env(tmp_path):
    s = Settings.from_env({"TRA_HOME": str(tmp_path)})
    assert s.tra_home == tmp_path
    assert s.store == "local"
    assert s.client_code_pattern == r"^[A-Z0-9]{2,12}$"
    with pytest.raises(ConfigError, match="TRA_HOME is not set"):
        Settings.from_env({})


def test_check_tra_home_cloud_paths(tmp_path):
    for name in ("OneDrive - Firm Pty Ltd", "onedrive", "Dropbox", "Google Drive", "iCloud Drive"):
        home = tmp_path / name / "Tax"
        home.mkdir(parents=True)
        problems = check_tra_home(home)
        assert problems and "sync" in problems[0].lower(), name
    ok = tmp_path / "Tax Assistant"
    ok.mkdir()
    assert check_tra_home(ok) == []


def test_check_tra_home_missing(tmp_path):
    assert check_tra_home(tmp_path / "nope")


def test_check_tra_home_inside_git(tmp_path):
    (tmp_path / ".git").mkdir()
    home = tmp_path / "data" / "home"
    home.mkdir(parents=True)
    problems = check_tra_home(home)
    assert problems and "git" in problems[0].lower()


def test_client_code():
    validate_client_code("SMIT01", r"^[A-Z0-9]{2,12}$")
    for bad in ("Smith John", "SMIT 01", "smit01", ""):
        with pytest.raises(ValueError):
            validate_client_code(bad, r"^[A-Z0-9]{2,12}$")


def test_workspace_paths(tmp_path):
    ws = Workspace(tmp_path, "SMIT01", 2026)
    assert ws.clients_dir == tmp_path / "Clients" / "SMIT01" / "FY2026"
    assert ws.work_dir == tmp_path / "Work" / "SMIT01" / "FY2026"
    assert ws.index_csv == ws.clients_dir / "index.csv"
    assert ws.figures_csv == ws.work_dir / "figures.csv"
    assert ws.cgt_csv == ws.work_dir / "cgt_events.csv"
    assert ws.output_dir == ws.work_dir / "Output"
    assert ws.audit_path.parent == tmp_path / "audit"
    assert ws.audit_path.name.startswith("audit-") and ws.audit_path.suffix == ".jsonl"


def test_workspace_create_and_state_roundtrip(tmp_path):
    ws = Workspace(tmp_path, "SMIT01", 2026)
    assert not ws.exists()
    ws.create(list(CATEGORIES))
    assert ws.exists()
    for c in CATEGORIES:
        assert (ws.clients_dir / c).is_dir()
    assert ws.output_dir.is_dir()
    state = ClientState(client_code="SMIT01", income_year=2026, help_debt=True, hospital_cover_days=200)
    ws.save_state(state)
    assert ws.load_state() == state


def test_paths_with_spaces(tmp_path):
    home = tmp_path / "My Tax Folder"
    home.mkdir()
    ws = Workspace(home, "AB12", 2026)
    ws.create(list(CATEGORIES))
    assert Path(ws.clients_dir, "Rental").is_dir()
