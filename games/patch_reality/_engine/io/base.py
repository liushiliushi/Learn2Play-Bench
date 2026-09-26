"""I/O adapter interface.

The engine talks to the world only through an IOAdapter. The same engine drives
a human terminal (CliAdapter) and a programmatic LLM agent (AgentAdapter).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import GameResult, Level
from ..state import GameState


class IOAdapter(ABC):
    @abstractmethod
    def render_scene(self, state: GameState, level: Level) -> None:
        """Present the current scene and state to the player."""

    @abstractmethod
    def read_command(self) -> str | None:
        """Return the next command, or None to end the run (player gave up / no input)."""

    @abstractmethod
    def render_feedback(self, lines: list[str]) -> None:
        """Present the textual outcome of an action and any world events."""

    @abstractmethod
    def render_error(self, message: str) -> None:
        """Present a parse/validation error without consuming a turn."""

    @abstractmethod
    def render_game_over(self, result: GameResult) -> None:
        """Present the final result of the level."""
