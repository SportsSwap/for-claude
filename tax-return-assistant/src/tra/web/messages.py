"""Plain-English versions of the tool's errors, for pages."""

from __future__ import annotations

from ..privacy.guard import FileLockedError, SensitiveDataBlocked

GUARD_MESSAGE = ("Sawnx refused to save that because it looks like it contains a TFN, Medicare, card, bank account, "
                 "licence or passport number. If you didn't type one, stop and tell the privacy officer.")
LOCKED_MESSAGE = "A file Sawnx needs is open in another program (probably Excel). Close it and try again."


def problem_text(exc: BaseException) -> str:
    if isinstance(exc, SensitiveDataBlocked):
        return GUARD_MESSAGE
    if isinstance(exc, FileLockedError):
        return LOCKED_MESSAGE
    return str(exc)
