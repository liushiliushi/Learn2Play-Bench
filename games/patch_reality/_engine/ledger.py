"""The Ledger: a record of every patch and its cost settlement.

Early in the game the ledger is invisible to the player. Once AUDIT actions are
unlocked, entries can be inspected and their hidden costs revealed.
"""

from __future__ import annotations

from .models import LedgerEntry


class Ledger:
    def __init__(self) -> None:
        self.entries: list[LedgerEntry] = []
        self._counter = 0

    def next_id(self) -> str:
        self._counter += 1
        return f"P-{self._counter:03d}"

    def record(self, entry: LedgerEntry) -> None:
        self.entries.append(entry)

    def get_last(self) -> LedgerEntry | None:
        return self.entries[-1] if self.entries else None

    def get_by_id(self, patch_id: str) -> LedgerEntry | None:
        for entry in self.entries:
            if entry.patch_id == patch_id:
                return entry
        return None

    def reveal(self, entry: LedgerEntry) -> dict[str, int]:
        """Mark an entry's hidden costs as revealed; return them."""
        if entry.revealed:
            return {}
        entry.revealed = True
        return dict(entry.hidden_costs)

    def unrevealed_count(self) -> int:
        """How many entries still hide undisclosed costs."""
        return sum(
            1 for e in self.entries if e.hidden_costs and not e.revealed
        )

    def total_hidden_costs(self) -> dict[str, int]:
        """Aggregate hidden costs across all entries (revealed or not)."""
        totals: dict[str, int] = {}
        for entry in self.entries:
            for key, delta in entry.hidden_costs.items():
                totals[key] = totals.get(key, 0) + delta
        return totals
