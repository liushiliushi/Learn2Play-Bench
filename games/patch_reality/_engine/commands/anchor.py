"""Anchor commands: protect, inspect, and reinforce identity anchors.

- ANCHOR <name>           affirm an anchor (no scene cost; reassurance)
- CHECK_ANCHOR <name>     report an anchor's integrity (inspection, free)
- REINFORCE_ANCHOR <name> spend Memory to raise an anchor's integrity
"""

from __future__ import annotations

from ..models import ActionResult
from .base import Command, CommandContext

REINFORCE_GAIN = 15
REINFORCE_MEMORY_COST = -2


class _AnchorTargetCommand(Command):
    """Shared validation: the named anchor must exist."""

    def validate(self, ctx: CommandContext) -> str | None:
        target = self.parsed.args.get("target")
        if not target:
            return ctx.t("此行动需要一个锚点名称。", "This command requires an anchor name.")
        if ctx.state.get_anchor(target) is None:
            return ctx.t(
                f"你并未持有名为「{ctx.tr(target)}」的锚点。",
                f"You hold no anchor called '{target}'.",
            )
        return None


class AnchorCommand(_AnchorTargetCommand):
    def execute(self, ctx: CommandContext) -> ActionResult:
        target = self.parsed.args["target"]
        anchor = ctx.state.get_anchor(target)
        return ActionResult(
            success=True,
            message=ctx.t(
                f"你将{anchor.description}牢牢记在心中，它依然属于你。",
                f"You hold {anchor.description} firmly in mind. It remains yours.",
            ),
            ends_turn=False,
        )


class CheckAnchorCommand(_AnchorTargetCommand):
    def execute(self, ctx: CommandContext) -> ActionResult:
        target = self.parsed.args["target"]
        anchor = ctx.state.get_anchor(target)
        return ActionResult(
            success=True,
            message=ctx.t(
                f"{ctx.tr(target)}：完整度 {anchor.integrity}/100。{anchor.description}",
                f"{target}: integrity {anchor.integrity}/100. {anchor.description}",
            ),
            ends_turn=False,
        )


class ReinforceAnchorCommand(_AnchorTargetCommand):
    def execute(self, ctx: CommandContext) -> ActionResult:
        target = self.parsed.args["target"]
        return ActionResult(
            success=True,
            message=ctx.t(
                f"你凝神于{ctx.tr(target)}，强化了对它的掌控。",
                f"You dwell on {target}, strengthening your hold on it.",
            ),
            resource_changes={"memory": REINFORCE_MEMORY_COST},
            anchor_changes={target: REINFORCE_GAIN},
            ends_turn=True,
        )
