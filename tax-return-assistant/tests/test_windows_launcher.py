"""tra.cmd runs the tool without activating .venv.

Windows blocks Activate.ps1 until the PowerShell script policy is changed, and firm
laptops may not allow that. The policy doesn't apply to .cmd files.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "tra.cmd"
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="runs a Windows batch file")


def _run(launcher: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(launcher), *args], capture_output=True, text=True, errors="replace", timeout=120)


def test_launcher_has_windows_line_endings():
    # cmd.exe can misread a batch file with bare LF endings (e.g. a GitHub ZIP without .gitattributes).
    data = LAUNCHER.read_bytes()
    assert data.count(b"\n") > 0 and data.count(b"\n") == data.count(b"\r\n")


@windows_only
@pytest.mark.skipif(not (ROOT / ".venv" / "Scripts" / "tra.exe").exists(), reason="setup.ps1 hasn't been run here")
def test_launcher_runs_the_installed_tool():
    result = _run(LAUNCHER, "--help")
    assert result.returncode == 0, result.stderr
    assert "Usage:" in result.stdout
    assert _run(LAUNCHER, "no-such-command").returncode == 2  # the tool's exit code comes back


@windows_only
def test_launcher_before_setup_says_to_run_setup(tmp_path):
    copy = tmp_path / "tra.cmd"
    shutil.copy(LAUNCHER, copy)
    result = _run(copy, "doctor")
    assert result.returncode == 1
    assert "setup.ps1" in result.stdout + result.stderr


SAWNX = ROOT / "Sawnx.cmd"


def test_sawnx_cmd_has_crlf_and_calls_tra_web():
    data = SAWNX.read_bytes()
    assert data.count(b"\n") > 0 and data.count(b"\n") == data.count(b"\r\n")
    assert rb'.venv\Scripts\tra.exe" web' in data and b"\t" not in data


@windows_only
def test_sawnx_before_setup_says_to_run_setup(tmp_path):
    copy = tmp_path / "Sawnx.cmd"
    shutil.copy(SAWNX, copy)
    result = subprocess.run([str(copy)], capture_output=True, text=True, errors="replace", timeout=120,
                            input="\n")
    assert result.returncode == 1
    assert "setup.ps1" in result.stdout + result.stderr
