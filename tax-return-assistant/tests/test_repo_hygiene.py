"""No committed file may contain a checksum-valid TFN, Medicare or card number.

Test identifiers are generated in memory at runtime precisely so this holds.
The one allowed card number is the public Visa test number.
"""

import subprocess
from pathlib import Path

from tra.privacy.detectors import find_sensitive

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {"4111111111111111"}
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".toml", ".txt", ".ps1", ".cfg", ".ini", ".example", ""}


def _tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True, text=True).stdout
        return [ROOT / name for name in out.split("\0") if name]
    except (OSError, subprocess.CalledProcessError):
        skip = {".venv", "__pycache__", ".git", ".pytest_cache"}
        return [p for p in ROOT.rglob("*") if p.is_file() and not skip & set(p.parts)]


def _scan(files: list[Path], root: Path) -> list[str]:
    found = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for m in find_sensitive(text, context=False):
            digits = "".join(c for c in text[m.start:m.end] if c.isdigit())
            if digits not in ALLOWED:
                found.append(f"{path.relative_to(root)}: {m.type} at offset {m.start}")
    return found


def test_no_identifiers_committed():
    files = [p for p in _tracked_files() if p.suffix in TEXT_SUFFIXES or p.name.startswith(".")]
    assert len(files) > 30
    assert _scan(files, ROOT) == []


def test_scan_catches_a_planted_identifier(tmp_path, make_tfn):
    planted = tmp_path / "fixture.py"
    planted.write_text(f'CLIENT = "{make_tfn()}"\nCARD = "4111 1111 1111 1111"\n', encoding="utf-8")
    assert [line.split(": ")[1].split()[0] for line in _scan([planted], tmp_path)] == ["TFN"]
