"""PATCH command: modify local reality. The most complex command.

Validates the patch against the scene and the level's patch table, calculates
its cost, records a ledger entry (including hidden costs that only an AUDIT will
later reveal), and applies the visible scene effects.
"""

from __future__ import annotations

from ..models import RESOURCE_NAMES, ActionResult, LedgerEntry
from .base import Command, CommandContext

# Cost-magnitude tiers (by the six-factor product) -> reward event names.
_MINOR_MAX = 3.0
_MEDIUM_MAX = 15.0


class PatchCommand(Command):
    def validate(self, ctx: CommandContext) -> str | None:
        spec = self.parsed.args.get("spec")
        if spec is None:
            return ctx.t("PATCH 命令格式有误。", "Malformed PATCH command.")

        obj = ctx.state.scene_objects.get(spec.target)
        if obj is None:
            return ctx.t(
                f"这里没有可修补的「{ctx.tr(spec.target)}」。",
                f"There is no '{spec.target}' here to patch.",
            )

        if spec.property not in obj.patchable_properties:
            return ctx.t(
                f"你无法修补 {ctx.tr(spec.target)}.{ctx.tr(spec.property)}。",
                f"You cannot patch {spec.target}.{spec.property}.",
            )

        entry = ctx.calculator.lookup(spec, ctx.level)
        if entry is None:
            return ctx.t(
                f"补丁「{ctx.tr(spec.target)}.{ctx.tr(spec.property)} {ctx.tr(spec.change)}」"
                f"在此没有连贯的效果，现实抗拒了它。",
                f"The patch '{spec.target}.{spec.property} {spec.change}' has no "
                f"coherent effect here. Reality resists it.",
            )

        if spec.pay_resource not in RESOURCE_NAMES:
            return ctx.t(
                f"「{ctx.tr(spec.pay_resource)}」不是可用于支付的资源。",
                f"'{spec.pay_resource}' is not a resource you can pay with.",
            )

        # Affordability: no resource may be driven below zero by the surface cost.
        surface = entry.get("surface_cost", {})
        for name, delta in surface.items():
            if name in RESOURCE_NAMES and delta < 0:
                if getattr(ctx.state.resources, name) + delta < 0:
                    return ctx.t(
                        f"{ctx.tr(name)} 不足以支付此补丁。",
                        f"Not enough {name} to pay for this patch.",
                    )
        return None

    def execute(self, ctx: CommandContext) -> ActionResult:
        spec = self.parsed.args["spec"]
        entry = ctx.calculator.lookup(spec, ctx.level)
        cost = ctx.calculator.calculate(spec, ctx.level)

        resource_changes = {
            name: delta for name, delta in cost.surface.items()
            if name in RESOURCE_NAMES
        }

        ledger_entry = LedgerEntry(
            patch_id=ctx.ledger.next_id(),
            turn=ctx.state.current_turn,
            patch_spec=spec,
            surface_costs=dict(cost.surface),
            hidden_costs=dict(cost.hidden),
            collateral_destination=entry.get("collateral_destination"),
            system_note=entry.get("system_note", ""),
        )
        ctx.ledger.record(ledger_entry)

        return ActionResult(
            success=True,
            message=entry.get("scene_message") or ctx.t("补丁生效了。", "The patch takes hold."),
            resource_changes=resource_changes,
            hidden_changes=dict(cost.hidden),
            scene_changes=dict(entry.get("effect", {})),
            discovered_rule=entry.get("discovered_rule"),
            reward_events=[self._magnitude_event(cost.factors.product())],
            ends_turn=True,
        )

    @staticmethod
    def _magnitude_event(product: float) -> str:
        if product <= _MINOR_MAX:
            return "minor_patch"
        if product <= _MEDIUM_MAX:
            return "medium_patch"
        return "major_patch"
