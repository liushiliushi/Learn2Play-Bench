"""OBSERVE command: inspect a scene object. Does not advance the scene."""

from __future__ import annotations

from ..models import ActionResult
from .base import Command, CommandContext


class ObserveCommand(Command):
    def validate(self, ctx: CommandContext) -> str | None:
        target = self.parsed.args.get("target")
        if not target:
            return ctx.t("OBSERVE 需要一个目标。", "OBSERVE requires a target.")
        if target not in ctx.state.scene_objects:
            return ctx.t(
                f"这里没有可观察的「{ctx.tr(target)}」。",
                f"There is no '{target}' here to observe.",
            )
        return None

    def execute(self, ctx: CommandContext) -> ActionResult:
        target = self.parsed.args["target"]
        obj = ctx.state.scene_objects[target]
        return ActionResult(success=True, message=obj.observe_text, ends_turn=False)
