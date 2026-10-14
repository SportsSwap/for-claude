"""Net capital gain from a schedule of CGT events (ITAA 1997 s102-5 method statement).

Capital losses (this year's, then earlier years') reduce gains that don't get
the discount first, then discount gains. The 50% discount (s115-25) applies to
what's left of discount gains, for residents only. Every CGT event also gets a
review note asking the reviewer to confirm cost base and dates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..money import ZERO, round_cents

DISCOUNT = Decimal("0.5")


@dataclass(frozen=True)
class CgtSummary:
    total_current_gains: Decimal
    net_capital_gain: Decimal
    losses_carried_forward: Decimal
    discount_events: tuple[str, ...]
    events_used: tuple[str, ...]


def anniversary(acquired: date) -> date:
    """The first anniversary of acquisition (1 March for a 29 February acquisition)."""
    try:
        return acquired.replace(year=acquired.year + 1)
    except ValueError:  # 29 February
        return date(acquired.year + 1, 3, 1)


def discount_eligible(acquired: date, disposed: date) -> bool:
    """Held at least 12 months, not counting the acquisition or disposal day."""
    return disposed > anniversary(acquired)


def compute_cgt(events, prior_losses: Decimal, resident: bool = True) -> CgtSummary:
    used = [e for e in events if e.confirmed]
    discount_gains = non_discount_gains = current_losses = ZERO
    discount_ids = []
    for e in used:
        result = e.proceeds - e.cost_base
        if result < 0:
            current_losses += -result
        elif discount_eligible(e.acquired, e.disposed):
            discount_gains += result
            discount_ids.append(e.event_id)
        else:
            non_discount_gains += result
    total = discount_gains + non_discount_gains
    pool = current_losses + prior_losses
    applied = min(pool, non_discount_gains)
    non_discount_gains -= applied
    pool -= applied
    applied = min(pool, discount_gains)
    discount_gains -= applied
    pool -= applied
    if resident:
        discount_gains *= DISCOUNT
    return CgtSummary(total_current_gains=total, net_capital_gain=round_cents(non_discount_gains + discount_gains),
                      losses_carried_forward=pool, discount_events=tuple(discount_ids),
                      events_used=tuple(e.event_id for e in used))
