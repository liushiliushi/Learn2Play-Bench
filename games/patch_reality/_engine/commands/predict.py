"""PREDICT command: get the level's analysis of an event. Does not advance the scene."""

from __future__ import annotations

from ..models import ActionResult
from .base import Command, CommandContext


class PredictCommand(Command):
    def validate(self, ctx: CommandContext) -> str | None:
        target = self.parsed.args.get("target")
        if not target:
            return ctx.t("PREDICT 需要一个目标事件。", "PREDICT requires a target event.")
        if target not in ctx.level.predictions:
            return ctx.t(
                f"你无法对「{ctx.tr(target)}」形成清晰的预测。",
                f"You cannot form a clear prediction about '{target}'.",
            )
        return None

    def execute(self, ctx: CommandContext) -> ActionResult:
        target = self.parsed.args["target"]
        entry = ctx.level.predictions[target]
        reward_events = []
        if entry.get("reward"):
            reward_events.append(entry["reward"])
        return ActionResult(
            success=True,
            message=entry.get("text", ""),
            scene_changes=dict(entry.get("effect", {})),
            reward_events=reward_events,
            ends_turn=False,
        )
