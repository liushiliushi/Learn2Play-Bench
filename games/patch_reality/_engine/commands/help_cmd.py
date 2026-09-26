"""HELP command: print the onboarding brief. Free action, takes no arguments."""

from __future__ import annotations

from ..help_text import HELP_TEXT
from ..models import ActionResult
from .base import Command, CommandContext


class HelpCommand(Command):
    def execute(self, ctx: CommandContext) -> ActionResult:
        return ActionResult(success=True, message=HELP_TEXT, ends_turn=False)
