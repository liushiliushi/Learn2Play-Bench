"""Structured state for Lost & Found Office."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class ClaimantRole(Enum):
    OWNER = auto()
    FINDER = auto()
    ASSOCIATE = auto()
    MIMIC = auto()


class FactCategory(Enum):
    SURFACE = auto()
    RECOVERY_SCENE = auto()
    CONCEALED_MARKER = auto()
    RELATIONSHIP_PURPOSE = auto()
    LOSS_SEQUENCE = auto()
    EXTERNAL_RECORD = auto()
    SHALLOW_CONTENT = auto()
    NEUTRAL_NOISE = auto()


class QuestionTopic(Enum):
    CONCEALED_DETAIL = "concealed_detail"
    RELATIONSHIP = "relationship"
    LOSS_TIMELINE = "loss_timeline"
    LAST_USE = "last_use"
    RECOVERY_SCENE = "recovery_scene"


class ResolutionType(Enum):
    RETURNED = auto()
    STORED = auto()
    FORCED_STORAGE = auto()


@dataclass(frozen=True)
class Fact:
    fact_id: str
    category: FactCategory
    semantic_key: str
    public_text: str
    private_text: str


@dataclass
class FactExposure:
    fact_id: str
    first_public_turn: int | None = None
    exposed_by: str | None = None
    audience_claimant_ids: set[str] = field(default_factory=set)
    private_observers: set[str] = field(default_factory=set)


@dataclass
class StatementRecord:
    turn: int
    claimant_id: str
    topic: QuestionTopic
    semantic_fact_ids: tuple[str, ...]
    public: bool
    independent_fact_ids: tuple[str, ...]
    heard_fact_ids: tuple[str, ...]
    rendered_text: str
    wording_template_id: str = ""


@dataclass
class ClaimantState:
    claimant_id: str
    display_name: str
    biography: str
    role: ClaimantRole
    independent_fact_ids: set[str]
    heard_fact_ids: set[str] = field(default_factory=set)
    heard_source_turn: dict[str, int] = field(default_factory=dict)
    heard_source_order: dict[str, int] = field(default_factory=dict)
    heard_wording: dict[str, str] = field(default_factory=dict)
    isolated: bool = False
    statement_history: list[StatementRecord] = field(default_factory=list)


@dataclass
class CaseState:
    case_id: str
    item_name: str
    item_archetype_id: str
    surface_description: str
    facts: dict[str, Fact]
    exposures: dict[str, FactExposure]
    claimants: dict[str, ClaimantState]
    owner_id: str
    relevant_record_id: str
    decoy_record_id: str | None
    relevant_record_text: str
    decoy_record_text: str
    item_open_at_recovery: bool
    owner_imperfection: str
    mimic_preferred_topic: QuestionTopic
    opening_statements: tuple[str, ...]
    public_fact_ids: set[str] = field(default_factory=set)
    statement_history: list[StatementRecord] = field(default_factory=list)
    item_privately_inspected: bool = False
    item_publicly_opened: bool = False
    recovery_tag_inspected: bool = False
    relevant_record_checked: bool = False
    decoy_record_checked: bool = False
    privately_observed_fact_ids: set[str] = field(default_factory=set)
    asked_actions: set[str] = field(default_factory=set)
    checked_record_ids: set[str] = field(default_factory=set)
    turns_spent: int = 0
    resolved: bool = False
    resolution_type: ResolutionType | None = None
    selected_recipient_id: str | None = None
    case_score: int = 0
    correctness_score: int = 0
    evidence_bonus: int = 0
    efficiency_bonus: int = 0


@dataclass
class EpisodeState:
    seed: int
    episode_index: int
    turn: int
    max_turns: int
    case_index: int
    cases: list[CaseState]
    privacy_tokens: int
    isolation_tokens: int
    record_checks: int
    public_trust: int
    done: bool = False
