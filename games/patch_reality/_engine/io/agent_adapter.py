"""Programmatic I/O adapter for LLM-agent / benchmark play.

Commands are supplied up front (a queue). Every render call appends a structured
record to `log`, giving a complete, deterministic trace of the run.
"""

from __future__ import annotations

from typing import Any

from ..models import GameResult, Level
from ..state import GameState
from .base import IOAdapter


class AgentAdapter(IOAdapter):
    def __init__(self, commands: list[str] | None = None) -> None:
        self.commands: list[str] = list(commands or [])
        self.log: list[dict[str, Any]] = []

    def render_scene(self, state: GameState, level: Level) -> None:
        self.log.append({
            "type": "scene",
            "premise": level.premise,
            "objective": level.objective.description,
            "available_actions": level.available_actions,
            "state": state.snapshot(),
        })

    def read_command(self) -> str | None:
        if not self.commands:
            return None
        return self.commands.pop(0)

    def render_feedback(self, lines: list[str]) -> None:
        self.log.append({"type": "feedback", "lines": list(lines)})

    def render_error(self, message: str) -> None:
        self.log.append({"type": "error", "message": message})

    def render_game_over(self, result: GameResult) -> None:
        self.log.append({
            "type": "game_over",
            "objective_complete": result.objective_complete,
            "game_over_reason": result.game_over_reason,
            "reward": result.reward,
            "rank": result.rank,
            "turns_used": result.turns_used,
            "final_resources": result.final_resources.as_dict(),
            "discovered_rules": result.discovered_rules,
        })
