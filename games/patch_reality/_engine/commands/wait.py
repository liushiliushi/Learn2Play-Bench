"""WAIT command: let the scene progress without acting on it."""

from __future__ import annotations

from ..models import ActionResult
from .base import Command, CommandContext


class WaitCommand(Command):
    def execute(self, ctx: CommandContext) -> ActionResult:
        turns = self.parsed.args.get("turns", 1)
        message = ctx.t("你静观其变，等待场景自行展开。", "You wait and watch the scene unfold.")
        if turns > 1:
            message = ctx.t(
                f"你等待了 {turns} 个回合，静观场景推进。",
                f"You wait for {turns} turns, watching the scene unfold.",
            )
        return ActionResult(
            success=True,
            message=message,
            ends_turn=True,
            turns_consumed=turns,
        )
