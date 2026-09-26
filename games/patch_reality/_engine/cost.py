"""Patch cost calculator.

Cost tables live in the level YAML, not here. The calculator reads the explicit
surface and hidden costs a level defines for each patch, and also exposes the
six-factor product (Magnitude x Duration x Scope x Rule Depth x Exposure x
Rationalization) as a difficulty signal used by scoring.
"""

from __future__ import annotations

from .models import CostFactors, CostResult, Level, PatchSpec


class CostCalculator:
    def lookup(self, spec: PatchSpec, level: Level) -> dict | None:
        """Return the level's patch-table entry for this spec, or None."""
        prop_entry = level.valid_patches.get(spec.key())
        if not prop_entry:
            return None
        return prop_entry.get(spec.change)

    def calculate(self, spec: PatchSpec, level: Level) -> CostResult:
        """Resolve the surface costs, hidden costs, and cost factors for a patch."""
        entry = self.lookup(spec, level)
        if entry is None:
            raise ValueError(
                f"No cost entry for patch '{spec.key()} {spec.change}' in level {level.id}."
            )

        factors = self._resolve_factors(entry.get("cost_factors", {}))
        surface = dict(entry.get("surface_cost", {}))
        hidden = dict(entry.get("hidden_cost", {}))
        return CostResult(surface=surface, hidden=hidden, factors=factors)

    @staticmethod
    def _resolve_factors(raw: dict) -> CostFactors:
        return CostFactors(
            magnitude=float(raw.get("magnitude", 1.0)),
            duration=float(raw.get("duration", 1.0)),
            scope=float(raw.get("scope", 1.0)),
            rule_depth=float(raw.get("rule_depth", 1.0)),
            exposure=float(raw.get("exposure", 1.0)),
            rationalization=float(raw.get("rationalization", 1.0)),
        )
