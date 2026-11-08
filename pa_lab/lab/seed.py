"""One master seed for every random draw.

Each consumer asks for a named stream; the stream's seed is derived from the
master seed and the name, so adding a new consumer never shifts another's draws.
"""
from __future__ import annotations

import hashlib

import numpy as np

from .config import MASTER_SEED


def child_seed(name: str) -> int:
    digest = hashlib.sha256(f"{MASTER_SEED}:{name}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def rng(name: str) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([MASTER_SEED, child_seed(name)]))
