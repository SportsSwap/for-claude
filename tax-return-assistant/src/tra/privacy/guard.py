"""Output guard: nothing is written until it has been scanned.

Every file the tool creates (CSV, JSON, the workpaper, the index, the audit
log, filenames) passes through here first. If a detector fires, the write is
refused and the error names the place and the detector type, never the value.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import openpyxl

from .detectors import find_sensitive


class SensitiveDataBlocked(Exception):
    def __init__(self, location: str, detector_type: str):
        self.location = location
        self.detector_type = detector_type
        super().__init__(f"Refused to write {location}: looks like a {detector_type}")


class FileLockedError(Exception):
    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"{path.name} is open in another program (probably Excel). Close it and re-run.")


_listener = None
_notifying = False


def set_block_listener(listener) -> None:
    """Call ``listener(location, detector_type)`` whenever a write is refused (the CLI audits it)."""
    global _listener
    _listener = listener


def _blocked(location: str, detector_type: str) -> SensitiveDataBlocked:
    global _notifying
    if _listener is not None and not _notifying:
        _notifying = True
        try:
            _listener(location, detector_type)
        except Exception:  # an audit failure must not hide the block itself
            pass
        finally:
            _notifying = False
    return SensitiveDataBlocked(location, detector_type)


def check_text(value: str, location: str) -> None:
    matches = find_sensitive(value)
    if matches:
        raise _blocked(location, matches[0].type)


def _check_scalar(value: object, location: str) -> None:
    if isinstance(value, str):
        check_text(value, location)
    elif isinstance(value, int) and not isinstance(value, bool) and 8 <= len(str(abs(value))) <= 19:
        check_text(str(value), location)


def check_value(value: object, location: str) -> None:
    """Scan a scalar or a nested dict/list structure (JSON-shaped data)."""
    if isinstance(value, dict):
        for k, v in value.items():
            check_text(str(k), location)
            check_value(v, location)
    elif isinstance(value, (list, tuple)):
        for v in value:
            check_value(v, location)
    else:
        _check_scalar(value, location)


def check_rows(rows: Iterable[Iterable[object]], location: str) -> None:
    for r, row in enumerate(rows, start=1):
        for value in row:
            _check_scalar(value, f"{location} row {r}")


def check_workbook(wb: openpyxl.Workbook, location: str) -> None:
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                value = cell.value
                if isinstance(value, str) and value.startswith("="):
                    continue
                _check_scalar(value, f"{ws.title}!{cell.coordinate}")


def atomic_write_text(path: Path, text: str, location: str, *, prechecked: bool = False,
                      encoding: str = "utf-8") -> None:
    """Guard, write to a temp file beside the target, then swap it in.

    ``prechecked`` is for callers that have already scanned the content
    cell by cell (CSV rows, JSON values), which avoids false matches that
    span unrelated cells.
    """
    if not prechecked:
        check_text(text, location)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding, newline="")
    try:
        os.replace(tmp, path)
    except PermissionError:
        tmp.unlink(missing_ok=True)
        raise FileLockedError(path) from None
