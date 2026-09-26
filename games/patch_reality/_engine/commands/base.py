"""Command base class and execution context.

A Command wraps a ParsedCommand and knows how to validate and execute itself
against the game. The engine supplies a CommandContext bundling everything a
command might touch: the mutable state, the read-only level, the ledger, and the
cost calculator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

from ..cost import CostCalculator
from ..ledger import Ledger
from ..models import ActionResult, Level
from ..parser import ParsedCommand
from ..state import GameState


def _identity(token: str) -> str:
    """Default token translator: leave canonical tokens untouched (English path)."""
    return token


@dataclass
class CommandContext:
    state: GameState
    level: Level
    ledger: Ledger
    calculator: CostCalculator
    # Localization hooks. Defaults keep the standalone engine and the English
    # path byte-for-byte unchanged; the play.py wrapper injects the active
    # language and a glossary translator so command feedback renders in zh.
    lang: str = "en"
    tr: Callable[[str], str] = field(default=_identity)

    def t(self, zh: str, en: str) -> str:
        """Pick a localized message by the active language (mirrors ``_t``)."""
        return zh if self.lang == "zh" else en


class Command(ABC):
    """Base for all command handlers."""

    def __init__(self, parsed: ParsedCommand) -> None:
        self.parsed = parsed

    def validate(self, ctx: CommandContext) -> str | None:
        """Return an error message if the command cannot run, else None."""
        return None

    @abstractmethod
    def execute(self, ctx: CommandContext) -> ActionResult:
        """Run the command and return its effects."""
        raise NotImplementedError
