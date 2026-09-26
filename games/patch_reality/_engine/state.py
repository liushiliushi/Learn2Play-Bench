"""Mutable game state for a single level playthrough.

GameState is a data holder with a few convenience mutators. It does NOT decide
what a patch does or how much it costs — that lives in the command handlers and
the cost calculator. GameState only tracks numbers and scene flags.
"""

from __future__ import annotations

from typing import Any

from .models import (
    ActionResult,
    ActivePatch,
    Anchor,
    Level,
    SceneObject,
)

# Failure thresholds.
MAX_SUSPICION = 100


class GameState:
    def __init__(
        self,
        resources,
        anchors: list[Anchor],
        scene_objects: dict[str, SceneObject],
        max_turns: int,
    ) -> None:
        self.resources = resources
        self.anchors = anchors
        self.scene_objects = scene_objects
        self.max_turns = max_turns

        self.current_turn = 1
        self.discovered_rules: list[str] = []
        # Hard-mode only: evidence tags collected by OBSERVE/AUDIT. Empty for easy
        # levels; the `evidence:<tag>` condition and patch-support checks read this.
        self.evidence_tags: set[str] = set()
        self.audit_access_level = 0
        self.active_patches: list[ActivePatch] = []
        self.scene_flags: dict[str, Any] = {}
        self.game_over = False
        self.game_over_reason: str | None = None
        self.objective_complete = False

    @classmethod
    def from_level(cls, level: Level) -> "GameState":
        """Build a fresh state from a level's template (deep-copying mutable parts)."""
        anchors = [
            Anchor(a.name, a.integrity, a.category, a.description)
            for a in level.anchors
        ]
        scene_objects = {
            name: SceneObject(
                obj.name,
                dict(obj.properties),
                obj.observe_text,
                list(obj.patchable_properties),
            )
            for name, obj in level.objects.items()
        }
        return cls(
            resources=level.initial_resources.copy(),
            anchors=anchors,
            scene_objects=scene_objects,
            max_turns=level.turn_limit,
        )

    # -- queries ---------------------------------------------------------

    def get_anchor(self, name: str) -> Anchor | None:
        for anchor in self.anchors:
            if anchor.name == name:
                return anchor
        return None

    # -- mutation --------------------------------------------------------

    def apply_result(self, result: ActionResult) -> None:
        """Apply an ActionResult's visible effects to this state.

        Hidden costs are NOT applied here; they live in the ledger until an
        AUDIT reveals (and applies) them.
        """
        for name, delta in result.resource_changes.items():
            setattr(self.resources, name, getattr(self.resources, name) + delta)

        if result.suspicion_change:
            self.resources.agent_suspicion += result.suspicion_change

        for anchor_name, delta in result.anchor_changes.items():
            anchor = self.get_anchor(anchor_name)
            if anchor is not None:
                anchor.integrity += delta

        if result.discovered_rule and result.discovered_rule not in self.discovered_rules:
            self.discovered_rules.append(result.discovered_rule)

        if result.scene_changes:
            self.scene_flags.update(result.scene_changes)

    def tick_patches(self) -> list[str]:
        """Decrement active-patch durations; return expiry messages for any that end."""
        messages: list[str] = []
        survivors: list[ActivePatch] = []
        for patch in self.active_patches:
            patch.remaining_turns -= 1
            if patch.remaining_turns <= 0:
                if patch.expiry_message:
                    messages.append(patch.expiry_message)
            else:
                survivors.append(patch)
        self.active_patches = survivors
        return messages

    # -- failure checks --------------------------------------------------

    def check_failure_conditions(self) -> str | None:
        """Return a failure reason string if a hard-failure threshold is hit."""
        if self.resources.existence <= 0:
            return "identity_erasure"
        if self.resources.memory <= 0:
            return "total_amnesia"
        if self.resources.reality_stability <= 0:
            return "local_reality_reset"
        if self.resources.personal_time <= 0:
            return "timeline_collapse"
        if self.resources.agent_suspicion >= MAX_SUSPICION:
            return "forced_synchronization"
        return None

    # -- serialization ---------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Structured view of the current state (for LLM agents and save/load)."""
        return {
            "turn": self.current_turn,
            "max_turns": self.max_turns,
            "resources": self.resources.as_dict(),
            "observable_objects": list(self.scene_objects.keys()),
            "anchors": [
                {"name": a.name, "integrity": a.integrity, "category": a.category}
                for a in self.anchors
            ],
            "discovered_rules": list(self.discovered_rules),
            "evidence_tags": sorted(self.evidence_tags),
            "audit_access_level": self.audit_access_level,
            "scene_flags": dict(self.scene_flags),
            "game_over": self.game_over,
            "game_over_reason": self.game_over_reason,
            "objective_complete": self.objective_complete,
        }
