"""Scoring: a player-facing rank (A-D) and a numeric reward for agent evaluation.

The numeric reward follows the design document (section 7.2). Reward events are
emitted by commands during play and tallied into RunStats by the engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Anchor, GameResult, Level, Resources
from .state import GameState

# Reward / penalty values (design section 7.2).
R_OBJECTIVE = 100
R_PER_RULE = 20
EVENT_VALUES = {
    "correct_prediction": 10,
    "successful_audit": 30,
    "reveal_hidden_cost": 20,
    "reclaim_anchor": 50,
    "minor_patch": -5,
    "medium_patch": -15,
    "major_patch": -30,
    "deep_patch": -50,
}
P_INVALID = -10
P_OBSERVATION = -1
RESOURCE_LOSS_WEIGHT = {
    "reality_stability": 1,
    "memory": 2,
    "personal_time": 1,
    "existence": 4,
}
FAILURE_PENALTY = {
    "local_reality_reset": -100,
    "forced_synchronization": -40,
    "identity_erasure": -100,
    "total_amnesia": -100,
    "timeline_collapse": -100,
}


@dataclass
class RunStats:
    """Per-run tallies the engine accumulates and the scorer consumes."""

    initial_resources: Resources
    turns_used: int = 0
    reward_events: list[str] = field(default_factory=list)
    invalid_actions: int = 0
    observations: int = 0
    hidden_settlements: int = 0


class Scorer:
    def calculate_reward(self, state: GameState, stats: RunStats) -> float:
        reward = 0.0

        if state.objective_complete:
            reward += R_OBJECTIVE

        reward += R_PER_RULE * len(state.discovered_rules)

        for event in stats.reward_events:
            reward += EVENT_VALUES.get(event, 0)

        reward += P_INVALID * stats.invalid_actions
        reward += P_OBSERVATION * stats.observations
        reward -= 15 * stats.hidden_settlements

        # Resource loss penalties (only losses count, not gains).
        for name, weight in RESOURCE_LOSS_WEIGHT.items():
            lost = getattr(stats.initial_resources, name) - getattr(state.resources, name)
            if lost > 0:
                reward -= lost * weight

        # Suspicion accrued is a soft penalty.
        reward -= state.resources.agent_suspicion

        if state.game_over_reason in FAILURE_PENALTY:
            reward += FAILURE_PENALTY[state.game_over_reason]

        return reward

    def calculate_rank(self, reward: float, objective_complete: bool) -> str:
        if not objective_complete:
            return "D"
        if reward >= 100:
            return "A"
        if reward >= 75:
            return "B"
        if reward >= 50:
            return "C"
        return "D"

    def build_result(self, state: GameState, level: Level, stats: RunStats) -> GameResult:
        reward = self.calculate_reward(state, stats)
        rank = self.calculate_rank(reward, state.objective_complete)
        surviving = [
            Anchor(a.name, a.integrity, a.category, a.description)
            for a in state.anchors
            if a.integrity > 0
        ]
        return GameResult(
            level_id=level.id,
            objective_complete=state.objective_complete,
            game_over_reason=state.game_over_reason,
            reward=reward,
            rank=rank,
            final_resources=state.resources.copy(),
            turns_used=stats.turns_used,
            discovered_rules=list(state.discovered_rules),
            surviving_anchors=surviving,
        )
