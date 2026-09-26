"""AUDIT command: inspect ledger entries and reveal hidden costs.

Auditing is powerful but risky — it exposes deductions the system made quietly,
but draws Stability Agent attention (raises suspicion).
"""

from __future__ import annotations

from ..models import RESOURCE_NAMES, ActionResult
from .base import Command, CommandContext


class AuditCommand(Command):
    def _resolve_entry(self, ctx: CommandContext):
        target = self.parsed.args.get("target", "last_patch")
        if target == "last_patch":
            return ctx.ledger.get_last()
        return ctx.ledger.get_by_id(target)

    def _resolve_level_entry(self, ctx: CommandContext):
        target = self.parsed.args.get("target", "last_patch")
        for entry in ctx.level.audit_entries:
            if entry.get("target") == target:
                return entry
        return None

    def validate(self, ctx: CommandContext) -> str | None:
        if self._resolve_level_entry(ctx) is not None:
            return None
        if not ctx.ledger.entries:
            return ctx.t(
                "目前没有可审计的内容，尚未记录任何补丁。",
                "There is nothing to audit yet. No patches have been recorded.",
            )
        if self._resolve_entry(ctx) is None:
            target = self.parsed.args.get("target", "last_patch")
            return ctx.t(
                f"没有与「{target}」匹配的账本记录。",
                f"No ledger entry matches '{target}'.",
            )
        return None

    def execute(self, ctx: CommandContext) -> ActionResult:
        level_entry = self._resolve_level_entry(ctx)
        if level_entry is not None:
            return ActionResult(
                success=True,
                message=level_entry.get("text", ""),
                scene_changes=dict(level_entry.get("effect", {})),
                suspicion_change=int(level_entry.get("suspicion_change", 1)),
                reward_events=list(level_entry.get("reward_events", ["successful_audit"])),
                ends_turn=bool(level_entry.get("ends_turn", False)),
            )

        entry = self._resolve_entry(ctx)
        hidden = ctx.ledger.reveal(entry)

        anchor_changes: dict[str, int] = {}
        resource_changes: dict[str, int] = {}
        for key, delta in hidden.items():
            if ctx.state.get_anchor(key) is not None:
                anchor_changes[key] = delta
            elif key in RESOURCE_NAMES:
                resource_changes[key] = delta

        reward_events = ["successful_audit"]
        if hidden:
            reward_events.append("reveal_hidden_cost")
            lines = ", ".join(f"{ctx.tr(k)}: {v}" for k, v in hidden.items())
            message = ctx.t(
                f"对 {entry.patch_id} 的审计完成。揭示出隐藏扣除——{lines}。{entry.system_note}",
                f"Audit of {entry.patch_id} complete. Hidden deduction revealed — "
                f"{lines}. {entry.system_note}",
            )
        else:
            message = ctx.t(
                f"对 {entry.patch_id} 的审计完成。未发现隐藏扣除。{entry.system_note}",
                f"Audit of {entry.patch_id} complete. No hidden deductions found. "
                f"{entry.system_note}",
            )

        return ActionResult(
            success=True,
            message=message,
            resource_changes=resource_changes,
            anchor_changes=anchor_changes,
            suspicion_change=1,
            reward_events=reward_events,
            ends_turn=False,
        )
