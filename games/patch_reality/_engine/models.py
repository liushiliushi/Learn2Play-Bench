"""Domain models for Patch Reality.

Every other module imports its data structures from here. These are pure data
holders (dataclasses) with no game logic, except small derived helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Canonical resource names. These match the field names on `Resources` and are
# the keys used in ActionResult.resource_changes and cost tables.
RESOURCE_NAMES = (
    "reality_stability",
    "memory",
    "personal_time",
    "existence",
    "agent_suspicion",
)


@dataclass
class Resources:
    """The player's spendable resources.

    `personal_time` is measured in minutes; the others are 0-100 scales,
    except `agent_suspicion` which rises from 0 toward a max threshold.
    """

    reality_stability: int = 100
    memory: int = 100
    personal_time: int = 60
    existence: int = 100
    agent_suspicion: int = 0

    def copy(self) -> "Resources":
        return Resources(
            reality_stability=self.reality_stability,
            memory=self.memory,
            personal_time=self.personal_time,
            existence=self.existence,
            agent_suspicion=self.agent_suspicion,
        )

    def as_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in RESOURCE_NAMES}


@dataclass
class Anchor:
    """A memory, person, object, name, place, or record that keeps the player
    connected to reality."""

    name: str
    integrity: int
    category: str  # "memory", "object", "person", "name", "place", "record"
    description: str


@dataclass
class SceneObject:
    """An observable thing in a level scene."""

    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    observe_text: str = ""
    patchable_properties: list[str] = field(default_factory=list)
    # Hard-mode only: evidence tags revealed when this object is OBSERVEd.
    # Empty for easy levels, so observation keeps unlocking patches directly.
    evidence_tags: list[str] = field(default_factory=list)


@dataclass
class PatchSpec:
    """A parsed PATCH command's clauses.

    Mirrors: PATCH <target>.<property> <change> FOR <duration> SCOPE <scope> PAY <resource>
    """

    target: str
    property: str
    change: str
    duration: str
    scope: str
    pay_resource: str

    def key(self) -> str:
        """The lookup key into a level's valid_patches table."""
        return f"{self.target}.{self.property}"


@dataclass
class CostFactors:
    """The six factors of the patch cost formula."""

    magnitude: float
    duration: float
    scope: float
    rule_depth: float
    exposure: float
    rationalization: float

    def product(self) -> float:
        return (
            self.magnitude
            * self.duration
            * self.scope
            * self.rule_depth
            * self.exposure
            * self.rationalization
        )


@dataclass
class CostResult:
    """The outcome of a cost calculation: visible and hidden deductions."""

    surface: dict[str, int]
    hidden: dict[str, int]
    factors: CostFactors


@dataclass
class LedgerEntry:
    """A record of one patch and its cost settlement."""

    patch_id: str
    turn: int
    patch_spec: PatchSpec
    surface_costs: dict[str, int] = field(default_factory=dict)
    hidden_costs: dict[str, int] = field(default_factory=dict)
    collateral_destination: str | None = None
    system_note: str = ""
    revealed: bool = False


@dataclass
class ActionResult:
    """The product of executing a Command. The engine applies this to state."""

    success: bool
    message: str
    resource_changes: dict[str, int] = field(default_factory=dict)
    hidden_changes: dict[str, int] = field(default_factory=dict)
    anchor_changes: dict[str, int] = field(default_factory=dict)
    suspicion_change: int = 0
    discovered_rule: str | None = None
    scene_changes: dict[str, Any] = field(default_factory=dict)
    reward_events: list[str] = field(default_factory=list)
    ends_turn: bool = True
    turns_consumed: int = 1


@dataclass
class ActivePatch:
    """A patch with a remaining duration, tracked across turns."""

    name: str
    remaining_turns: int
    expiry_message: str = ""


@dataclass
class LevelObjective:
    description: str
    condition: str  # name resolved via conditions.py registry
    completed: bool = False


@dataclass
class Level:
    """A fully-loaded level definition (parsed from YAML)."""

    id: str
    name: str
    phase: int
    premise: str
    objective: LevelObjective
    turn_limit: int
    initial_resources: Resources = field(default_factory=Resources)
    anchors: list[Anchor] = field(default_factory=list)
    available_actions: list[str] = field(default_factory=list)
    objects: dict[str, SceneObject] = field(default_factory=dict)
    valid_patches: dict[str, Any] = field(default_factory=dict)
    predictions: dict[str, Any] = field(default_factory=dict)
    scene_progression: list[dict] = field(default_factory=list)
    hidden_rules: list[str] = field(default_factory=list)
    triggers: list[dict] = field(default_factory=list)
    audit_entries: list[dict] = field(default_factory=list)
    # Hard-mode only: structured-diagnosis dimensions and evidence requirements
    # per patch. Both empty for easy levels, so existing behavior is unchanged.
    #   diagnosis: {source: {correct: x, options: [...]}, type: {...}, strategy: {...}}
    #   patch_requirements: {"target.property change": {required_evidence: [...], helpful_evidence: [...]}}
    diagnosis: dict = field(default_factory=dict)
    patch_requirements: dict = field(default_factory=dict)
    # Hard-mode only: optional per-level investigation budget override. None falls
    # back to the mode/phase default, so easy levels are unaffected.
    focus_limit: int | None = None


@dataclass
class GameResult:
    """The final outcome of a level, for scoring and reporting."""

    level_id: str
    objective_complete: bool
    game_over_reason: str | None
    reward: float
    rank: str
    final_resources: Resources
    turns_used: int
    discovered_rules: list[str] = field(default_factory=list)
    surviving_anchors: list[Anchor] = field(default_factory=list)
