"""Campaign runner: play a sequence of levels, carrying resources and anchors.

Resources and surviving anchors flow from each completed level into the next. A
hard failure (or an unmet objective) ends the campaign early.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .engine import GameEngine
from .io.base import IOAdapter
from .models import Anchor, GameResult, Level, Resources
from .state import GameState

# Reasons that terminate a campaign run.
_HARD_FAILURES = {
    "identity_erasure",
    "total_amnesia",
    "local_reality_reset",
    "timeline_collapse",
    "forced_synchronization",
}

IOFactory = Callable[[Level, int], IOAdapter]


@dataclass
class CampaignResult:
    level_results: list[GameResult] = field(default_factory=list)
    total_reward: float = 0.0
    completed_all: bool = False
    failed_at: str | None = None


class CampaignRunner:
    def __init__(self, levels: list[Level], io_factory: IOFactory) -> None:
        self.levels = levels
        self.io_factory = io_factory

    def run(self) -> CampaignResult:
        result = CampaignResult()
        carried_resources: Resources | None = None
        carried_anchors: list[Anchor] | None = None

        for index, level in enumerate(self.levels):
            state = GameState.from_level(level)
            if carried_resources is not None:
                state.resources = carried_resources.copy()
            if carried_anchors is not None:
                state.anchors = self._merge_anchors(carried_anchors, level.anchors)

            io = self.io_factory(level, index)
            engine = GameEngine(level, io, state=state)
            level_result = engine.run()
            result.level_results.append(level_result)

            carried_resources = level_result.final_resources
            carried_anchors = self._merge_anchors(level_result.surviving_anchors, [])

            if self._is_terminal_failure(level_result):
                result.failed_at = level.id
                break
        else:
            result.completed_all = True

        result.total_reward = sum(r.reward for r in result.level_results)
        return result

    @staticmethod
    def _is_terminal_failure(level_result: GameResult) -> bool:
        if level_result.game_over_reason in _HARD_FAILURES:
            return True
        # An unmet objective also ends the campaign.
        return not level_result.objective_complete

    @staticmethod
    def _merge_anchors(carried: list[Anchor], level_anchors: list[Anchor]) -> list[Anchor]:
        """Carried anchors persist (with their current integrity); new level
        anchors are introduced only if not already held."""
        merged = [Anchor(a.name, a.integrity, a.category, a.description) for a in carried]
        held = {a.name for a in merged}
        for anchor in level_anchors:
            if anchor.name not in held:
                merged.append(Anchor(anchor.name, anchor.integrity,
                                     anchor.category, anchor.description))
                held.add(anchor.name)
        return merged
