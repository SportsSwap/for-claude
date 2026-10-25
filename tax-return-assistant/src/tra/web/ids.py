"""Random ids for Sawnx's records (notes, comments, jobs, tasks, time, rules, In Tray items).

Letters only. The output guard scans every saved value, ids included, and a hex
id sometimes held a run of digits that passed the TFN check digit, so the save
was refused. An id with no digits can never look like a TFN, Medicare, card,
BSB or account number.
"""

from __future__ import annotations

import secrets
import string


def new_id(length: int = 12) -> str:
    return "".join(secrets.choice(string.ascii_lowercase) for _ in range(length))
