"""Terminal I/O adapter for human play.

Renders the explicit [Scene] / [State] / [Observable Objects] blocks described in
the game design document and reads commands from stdin.
"""

from __future__ import annotations

from ..models import GameResult, Level
from ..state import GameState
from .base import IOAdapter

_FAILURE_TEXT = {
    "identity_erasure": "Your Existence reached zero. The world no longer remembers you.",
    "total_amnesia": "Your Memory reached zero. You no longer recall why you resist.",
    "local_reality_reset": "Reality Stability collapsed. The scene resets to normal.",
    "timeline_collapse": "Your Personal Time ran out mid-patch. The timeline collapses.",
    "forced_synchronization": "A Stability Agent overwrote your awareness. You are synchronized.",
    "objective_failed": "The moment passed. You failed to prevent it.",
    "out_of_turns": "You ran out of turns.",
}


class CliAdapter(IOAdapter):
    def __init__(self, input_fn=input, output_fn=print) -> None:
        self._input = input_fn
        self._output = output_fn

    def render_scene(self, state: GameState, level: Level) -> None:
        r = state.resources
        lines = [
            "",
            "[Scene]",
            level.premise.strip(),
            "",
            "[State]",
            f"Turn: {state.current_turn}/{state.max_turns}",
            f"Reality Stability: {r.reality_stability}",
            f"Memory: {r.memory}",
            f"Personal Time: {r.personal_time} min",
            f"Existence: {r.existence}",
            f"Agent Suspicion: {r.agent_suspicion}",
        ]
        if state.anchors:
            anchors = ", ".join(f"{a.name}({a.integrity})" for a in state.anchors)
            lines.append(f"Anchors: {anchors}")
        lines += [
            "",
            "[Observable Objects]",
            ", ".join(state.scene_objects.keys()) or "(none)",
            "",
            f"[Objective] {level.objective.description}",
        ]
        if level.available_actions:
            lines.append(f"[Actions] {', '.join(level.available_actions)}")
        if state.current_turn == 1:
            lines.append("Type HELP for how to play.")
        self._output("\n".join(lines))

    def read_command(self) -> str | None:
        try:
            return self._input("\n> ")
        except (EOFError, KeyboardInterrupt):
            return None

    def render_feedback(self, lines: list[str]) -> None:
        for line in lines:
            self._output(line)

    def render_error(self, message: str) -> None:
        self._output(f"! {message}")

    def render_game_over(self, result: GameResult) -> None:
        self._output("\n" + "=" * 48)
        if result.objective_complete:
            self._output("Objective Completed: Yes")
        else:
            self._output("Objective Completed: No")
            if result.game_over_reason in _FAILURE_TEXT:
                self._output(_FAILURE_TEXT[result.game_over_reason])
        self._output(f"Turns Used: {result.turns_used}")
        self._output(f"Reward: {result.reward:.0f}")
        self._output(f"Final Rank: {result.rank}")
        if result.discovered_rules:
            self._output("Hidden Rules Discovered:")
            for rule in result.discovered_rules:
                self._output(f"  - {rule}")
        self._output("=" * 48)
