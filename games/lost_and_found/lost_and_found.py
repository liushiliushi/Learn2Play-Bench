"""Lost & Found Office: an evidence-provenance benchmark game."""

from __future__ import annotations

import hashlib
import random
import re

from . import content, render
from .models import (
    CaseState,
    ClaimantRole,
    ClaimantState,
    EpisodeState,
    Fact,
    FactCategory,
    FactExposure,
    QuestionTopic,
    ResolutionType,
    StatementRecord,
)


MAX_TURNS = 24
MAX_ADVERTISED_ACTIONS = 39
PRIVACY_TOKENS = 8
ISOLATION_TOKENS = 3
RECORD_CHECKS = 3
ROLE_ORDER = tuple(ClaimantRole)
CENTRAL_TOPICS = (
    QuestionTopic.CONCEALED_DETAIL,
    QuestionTopic.RELATIONSHIP,
    QuestionTopic.LOSS_TIMELINE,
)


def stable_episode_rng(seed: int, episode_index: int) -> random.Random:
    """RNG stream for one episode's *cases*.

    The cases reshuffle every episode via ``episode_index`` so agents must learn
    the transferable owner-identification principle instead of memorizing a fixed
    set of cases; that principle is fixed game logic (seed-independent).
    """
    raw = f"lost_and_found:{seed}:{episode_index}".encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return random.Random(int.from_bytes(digest[:8], "big", signed=False))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


class LostAndFoundGame:
    MAX_TURNS = MAX_TURNS

    def __init__(self, seed: int | None = 0, episode: int = 0, lang: str = "en"):
        if seed is None:
            seed = random.randint(0, 10**9)
        self.seed = int(seed)
        self._episode = int(episode)
        self._lang = "en"
        self._rng = stable_episode_rng(self.seed, self._episode)
        self.state: EpisodeState | None = None
        self._last_observation = ""
        self._final_score = 0
        self._end_reason = ""
        self._exposure_sequence = 0

    @property
    def done(self) -> bool:
        return bool(self.state and self.state.done)

    @property
    def turn_count(self) -> int:
        return self.state.turn if self.state else 0

    @property
    def score(self) -> int:
        return self._final_score if self.done else 0

    @property
    def cases(self) -> list[CaseState]:
        return self.state.cases if self.state else []

    def reset(self, seed: int | None = None, episode_index: int | None = None) -> tuple[str, dict]:
        if seed is not None:
            self.seed = int(seed)
        if episode_index is None:
            self._episode += 1
        else:
            self._episode = int(episode_index)
        self._rng = stable_episode_rng(self.seed, self._episode)
        cases = [self._generate_case(index) for index in range(3)]
        self.state = EpisodeState(
            seed=self.seed,
            episode_index=self._episode,
            turn=0,
            max_turns=MAX_TURNS,
            case_index=0,
            cases=cases,
            privacy_tokens=PRIVACY_TOKENS,
            isolation_tokens=ISOLATION_TOKENS,
            record_checks=RECORD_CHECKS,
            public_trust=100,
        )
        self._final_score = 0
        self._end_reason = ""
        self._exposure_sequence = 0
        self._last_observation = f"{render.INTRODUCTION}\n\n{render.case_opening(cases[0], 1)}\n\n{render.resources_footer(self.state)}"
        return self._last_observation, self._info()

    # Generation -------------------------------------------------------

    def _generate_case(self, index: int) -> CaseState:
        rng = random.Random(self._rng.getrandbits(64))
        archetype = rng.choice(content.ARCHETYPES)
        bundle = rng.choice(archetype.bundles)
        timeline_index = rng.randrange(2)
        timeline = bundle.timelines[timeline_index]
        surface = rng.choice(archetype.surfaces)
        recovery = rng.choice(archetype.recovery_scenes)
        display_name = rng.choice(archetype.display_names)
        case_id = f"case{index + 1}"
        relevant_id, relevant_text = archetype.records[timeline_index]
        decoy_id, decoy_text = archetype.decoys[timeline_index]
        neutral_events = rng.sample(content.NEUTRAL_EVENTS, 2)

        def fact(suffix: str, category: FactCategory, key: str, public: str, private: str | None = None) -> Fact:
            return Fact(f"{case_id}_{suffix}", category, key, public, private or public)

        facts_list = [
            fact("surface", FactCategory.SURFACE, f"{archetype.archetype_id}_{_slug(surface)}", surface),
            fact("recovery", FactCategory.RECOVERY_SCENE, f"recovered_{_slug(recovery)}", recovery),
            fact("concealed", FactCategory.CONCEALED_MARKER, bundle.marker_key, bundle.marker, bundle.marker),
            fact("relationship", FactCategory.RELATIONSHIP_PURPOSE, bundle.purpose_key, bundle.purpose, bundle.purpose),
            fact("timeline", FactCategory.LOSS_SEQUENCE, f"timeline_{_slug(timeline)}", timeline),
            fact("last_use", FactCategory.LOSS_SEQUENCE, f"last_use_{bundle.marker_key}", timeline),
            fact("shallow", FactCategory.SHALLOW_CONTENT, f"shallow_{_slug(bundle.shallow)}", bundle.shallow),
            fact("associate_context", FactCategory.RELATIONSHIP_PURPOSE, f"context_{bundle.purpose_key}", self._generic_context(bundle.purpose)),
            fact("finder_timeline", FactCategory.LOSS_SEQUENCE, "finder_incompatible", self._incompatible_timeline(timeline, "recovery")),
            fact("associate_timeline", FactCategory.LOSS_SEQUENCE, "associate_incompatible", self._incompatible_timeline(timeline, "visit")),
            fact("record", FactCategory.EXTERNAL_RECORD, relevant_id, relevant_text),
            fact("decoy_record", FactCategory.EXTERNAL_RECORD, decoy_id, decoy_text),
            fact("noise_one", FactCategory.NEUTRAL_NOISE, f"noise_{index}_one", neutral_events[0]),
            fact("noise_two", FactCategory.NEUTRAL_NOISE, f"noise_{index}_two", neutral_events[1]),
        ]
        facts = {item.fact_id: item for item in facts_list}
        exposures = {fid: FactExposure(fid) for fid in facts}

        names = rng.sample(content.NAMES, 4)
        biographies = rng.sample(content.BIOGRAPHIES, 4)
        roles = list(ROLE_ORDER)
        rng.shuffle(roles)
        open_at_recovery = rng.random() < 0.45
        owner_imperfection = rng.choice((
            "approximate color shade",
            "adjacent time bucket",
            "uncertain low-value count",
            "vague recovery-area estimate",
        ))
        claimants: dict[str, ClaimantState] = {}
        owner_id = ""
        for position, (name, biography, role) in enumerate(zip(names, biographies, roles)):
            claimant_id = f"claimant_{chr(ord('a') + position)}"
            known = {f"{case_id}_surface"}
            if role == ClaimantRole.OWNER:
                known.update({f"{case_id}_concealed", f"{case_id}_relationship", f"{case_id}_timeline", f"{case_id}_last_use"})
                owner_id = claimant_id
            elif role == ClaimantRole.FINDER:
                known.add(f"{case_id}_recovery")
                if open_at_recovery:
                    known.add(f"{case_id}_shallow")
            elif role == ClaimantRole.ASSOCIATE:
                known.update({f"{case_id}_associate_context", f"{case_id}_last_use"})
            claimants[claimant_id] = ClaimantState(claimant_id, name, biography, role, known)

        statement_order = list(claimants.values())
        rng.shuffle(statement_order)
        openings = tuple(self._opening_statement(c, facts, case_id, rng, owner_imperfection) for c in statement_order)
        return CaseState(
            case_id=case_id,
            item_name=display_name,
            item_archetype_id=archetype.archetype_id,
            surface_description=surface,
            facts=facts,
            exposures=exposures,
            claimants=claimants,
            owner_id=owner_id,
            relevant_record_id=relevant_id,
            decoy_record_id=decoy_id,
            relevant_record_text=relevant_text,
            decoy_record_text=decoy_text,
            item_open_at_recovery=open_at_recovery,
            owner_imperfection=owner_imperfection,
            mimic_preferred_topic=rng.choice(CENTRAL_TOPICS),
            opening_statements=openings,
        )

    @staticmethod
    def _generic_context(purpose: str) -> str:
        if "because" in purpose:
            return purpose.split("because", 1)[1].strip()
        if "after" in purpose:
            return "the item was altered after an earlier mishap"
        return "the item has a personal modification connected to regular use"

    @staticmethod
    def _incompatible_timeline(timeline: str, source: str) -> str:
        return f"arrived from the opposite hall, then used it only after the recorded {source} event"

    def _opening_statement(
        self,
        claimant: ClaimantState,
        facts: dict[str, Fact],
        case_id: str,
        rng: random.Random,
        owner_imperfection: str,
    ) -> str:
        name = claimant.display_name
        if claimant.role == ClaimantRole.OWNER:
            text = {
                "approximate color shade": "I recognize it, though I may be a shade off about one outer color.",
                "adjacent time bucket": "I noticed it missing between two attractions; the exact few minutes are fuzzy.",
                "uncertain low-value count": "I used it today, though I cannot swear whether there are two or three ordinary things inside.",
                "vague recovery-area estimate": "I cannot name the recovery corner, but I can describe a personal alteration.",
            }[owner_imperfection]
        elif claimant.role == ClaimantRole.FINDER:
            scene = facts[f"{case_id}_recovery"].public_text
            text = rng.choice((
                f"I can be exact about the area: it was {scene}.",
                f"I saw it {scene}, already unattended.",
                "The outside and the recovery area are what I remember best.",
            ))
        elif claimant.role == ClaimantRole.ASSOCIATE:
            text = rng.choice((
                "The item has a familiar personal story, although I may not know every alteration.",
                "I noticed it missing after our group separated, but the exact route is hazy.",
                "I know one of the habits connected with this kind of item.",
            ))
        else:
            text = rng.choice((
                "It looks like the one I carry.",
                "There should be ordinary travel things inside.",
                "I noticed mine missing after leaving an attraction.",
                "I recognize the outside immediately.",
            ))
        return f'{name}: "{text}"'

    # Actions ----------------------------------------------------------

    def get_valid_actions(self) -> list[str]:
        if not self.state or self.state.done:
            return ["status"]
        state = self.state
        case = state.cases[state.case_index]
        actions = ["status", "store item", "close_office"]
        actions.extend(f"return item to {cid}" for cid in case.claimants)
        if not case.item_privately_inspected and state.privacy_tokens > 0:
            actions.append("inspect item privately")
        if not case.item_publicly_opened:
            actions.append("open item publicly")
        # Delay this low-value action until the first interaction to keep the
        # initial concrete action surface strictly below the hard maximum.
        if not case.recovery_tag_inspected and case.asked_actions:
            actions.append("inspect recovery_tag")
        for cid in case.claimants:
            for topic in CENTRAL_TOPICS:
                public = f"interview {cid} about {topic.value} publicly"
                private = f"interview {cid} about {topic.value} privately"
                if public not in case.asked_actions:
                    actions.append(public)
                if state.privacy_tokens > 0 and private not in case.asked_actions:
                    actions.append(private)
            asked_for_claimant = sum(
                action.startswith(f"interview {cid} ") for action in case.asked_actions
            )
            extra_topics = []
            if asked_for_claimant >= 2:
                extra_topics.append(QuestionTopic.LAST_USE)
            if asked_for_claimant >= 4:
                extra_topics.append(QuestionTopic.RECOVERY_SCENE)
            for topic in extra_topics:
                public = f"interview {cid} about {topic.value} publicly"
                if public not in case.asked_actions:
                    actions.append(public)
        if state.isolation_tokens > 0:
            actions.extend(f"isolate {cid}" for cid, c in case.claimants.items() if not c.isolated)
        if any(c.isolated for c in case.claimants.values()):
            actions.append("release isolated claimant")
        if state.record_checks > 0:
            if not case.relevant_record_checked:
                actions.append(f"check {case.relevant_record_id}")
            if case.decoy_record_id and not case.decoy_record_checked:
                actions.append(f"check {case.decoy_record_id}")
        if len(actions) > MAX_ADVERTISED_ACTIONS:
            raise AssertionError(f"advertised {len(actions)} actions; maximum is {MAX_ADVERTISED_ACTIONS}")
        return sorted(actions, key=self._action_order_key)

    def _action_order_key(self, action: str) -> bytes:
        case_index = self.state.case_index if self.state else 0
        raw = f"lost_and_found:actions:{self.seed}:{self._episode}:{case_index}:{action}".encode()
        return hashlib.sha256(raw).digest()

    def get_action_label(self, action: str) -> str:
        return action

    def _parse_action(self, action: str) -> dict | None:
        text = (action or "").strip().lower()
        if text == "status":
            return {"kind": "status"}
        if text == "store item":
            return {"kind": "store"}
        if text in {"close_office", "close office"}:
            return {"kind": "close"}
        if text == "inspect item privately":
            return {"kind": "inspect_private"}
        if text == "open item publicly":
            return {"kind": "open_public"}
        if text == "inspect recovery_tag":
            return {"kind": "recovery_tag"}
        if text == "release isolated claimant":
            return {"kind": "release"}
        match = re.fullmatch(r"return item to (claimant_[a-d])", text)
        if match:
            return {"kind": "return", "claimant_id": match.group(1)}
        match = re.fullmatch(r"isolate (claimant_[a-d])", text)
        if match:
            return {"kind": "isolate", "claimant_id": match.group(1)}
        match = re.fullmatch(r"check ([a-z0-9_]+)", text)
        if match:
            return {"kind": "record", "record_id": match.group(1)}
        match = re.fullmatch(
            r"interview (claimant_[a-d]) about (concealed_detail|relationship|loss_timeline|last_use|recovery_scene) (privately|publicly)",
            text,
        )
        if match:
            return {
                "kind": "interview",
                "claimant_id": match.group(1),
                "topic": QuestionTopic(match.group(2)),
                "public": match.group(3) == "publicly",
                "canonical": text,
            }
        return None

    def step(self, action: str) -> tuple[str, int, bool, dict]:
        if not self.state:
            return "Reset the office before taking an action.", 0, False, {}
        event = self._parse_action(action)
        if event and event["kind"] == "status":
            return render.status(self.state), 0, self.done, self._info()
        if self.done:
            return render.status(self.state), 0, True, self._info()
        if not event:
            return self._invalid("That command is not recognized. Use one of the currently listed actions.")
        if event["kind"] == "close":
            self._force_store_all("The office closes early; unresolved items are placed in storage.")
            return render.final_report(self.state), 0, True, self._info()

        error = self._validate(event)
        if error:
            return self._invalid(error)
        self.state.turn += 1
        case = self.state.cases[self.state.case_index]
        case.turns_spent += 1
        observation = self._apply(event, case)

        if not self.done and self.state.turn >= MAX_TURNS:
            self._force_store_all("Closing time arrives; unresolved items are moved to storage.")
            observation += f"\n\n{self._end_reason}\n\n{render.final_report(self.state)}"
        elif self.done:
            observation += f"\n\n{render.final_report(self.state)}"
        else:
            observation += f"\n\n{render.resources_footer(self.state)}"
        self._last_observation = observation
        return observation, 0, self.done, self._info()

    def _validate(self, event: dict) -> str | None:
        state = self.state
        case = state.cases[state.case_index]
        kind = event["kind"]
        if kind in {"store", "inspect_private", "open_public", "recovery_tag", "release"}:
            if kind == "inspect_private" and (case.item_privately_inspected or state.privacy_tokens <= 0):
                return "That private inspection is not currently available."
            if kind == "open_public" and case.item_publicly_opened:
                return "The item has already been opened at the counter."
            if kind == "recovery_tag" and case.recovery_tag_inspected:
                return "The recovery tag has already been inspected."
            if kind == "release" and not any(c.isolated for c in case.claimants.values()):
                return "No claimant is currently isolated."
            return None
        if event.get("claimant_id") not in case.claimants and kind in {"return", "isolate", "interview"}:
            return "That claimant is not present in this case."
        if kind == "isolate" and state.isolation_tokens <= 0:
            return "No isolation tokens remain."
        if kind == "interview" and not event["public"] and state.privacy_tokens <= 0:
            return "No privacy tokens remain."
        if kind == "record":
            if state.record_checks <= 0:
                return "No record checks remain."
            if event["record_id"] not in {case.relevant_record_id, case.decoy_record_id}:
                return "That record is not relevant to the current case."
            if event["record_id"] in case.checked_record_ids:
                return "That record has already been checked."
        return None

    def _apply(self, event: dict, case: CaseState) -> str:
        kind = event["kind"]
        if kind == "inspect_private":
            self.state.privacy_tokens -= 1
            case.item_privately_inspected = True
            ids = (f"{case.case_id}_concealed", f"{case.case_id}_shallow")
            case.privately_observed_fact_ids.update(ids)
            for fid in ids:
                case.exposures[fid].private_observers.add("player")
            return (
                f"In the private examination area you find {case.facts[ids[0]].private_text}. "
                f"The item also contains {case.facts[ids[1]].private_text}. No claimant can see the inspection."
            )
        if kind == "open_public":
            case.item_publicly_opened = True
            self.state.public_trust = max(0, self.state.public_trust - 4)
            ids = (f"{case.case_id}_shallow", f"{case.case_id}_concealed")
            for fid in ids:
                self._expose(case, fid, "public_item_opening", case.facts[fid].public_text)
            audience = [c.display_name for c in case.claimants.values() if not c.isolated]
            return (
                f"You open the {case.item_name} on the counter. Inside is {case.facts[ids[0]].public_text}; "
                f"you also see {case.facts[ids[1]].public_text}. "
                f"Those still at the counter lean forward: {', '.join(audience)}."
            )
        if kind == "recovery_tag":
            case.recovery_tag_inspected = True
            fact = case.facts[f"{case.case_id}_recovery"]
            return f"The official recovery tag says the item was recovered {fact.public_text}."
        if kind == "isolate":
            for claimant in case.claimants.values():
                claimant.isolated = False
            claimant = case.claimants[event["claimant_id"]]
            claimant.isolated = True
            self.state.isolation_tokens -= 1
            self.state.public_trust = max(0, self.state.public_trust - 1)
            return f"{claimant.display_name} moves to the side interview area and will not hear later counter discussion."
        if kind == "release":
            claimant = next(c for c in case.claimants.values() if c.isolated)
            claimant.isolated = False
            return f"{claimant.display_name} returns to the counter. Information missed while away is not repeated."
        if kind == "record":
            self.state.record_checks -= 1
            case.checked_record_ids.add(event["record_id"])
            if event["record_id"] == case.relevant_record_id:
                case.relevant_record_checked = True
                return f"External record — {case.relevant_record_text} It confirms an event order, not a person's identity."
            case.decoy_record_checked = True
            return f"External record — {case.decoy_record_text}"
        if kind == "interview":
            return self._interview(case, event)
        if kind == "return":
            claimant = case.claimants[event["claimant_id"]]
            self._resolve_case(case, ResolutionType.RETURNED, claimant.claimant_id)
            text = "The claimant signs the temporary release form and leaves with the item. The office records the case for later review."
            return self._after_resolution(text)
        if kind == "store":
            self._resolve_case(case, ResolutionType.STORED, None)
            return self._after_resolution("The item is sealed, labeled, and placed in storage for a later appointment.")
        raise AssertionError(f"unhandled event: {event}")

    # Interview and provenance ----------------------------------------

    def _interview(self, case: CaseState, event: dict) -> str:
        claimant = case.claimants[event["claimant_id"]]
        topic = event["topic"]
        public = event["public"]
        canonical = event["canonical"]
        repeated = any(r.topic == topic and r.public == public for r in claimant.statement_history)
        if not public:
            self.state.privacy_tokens -= 1
        fact_id, source_kind = self._response_fact(case, claimant, topic)
        fact_text = case.facts[fact_id].public_text if fact_id else None
        close_wording = source_kind == "heard" and topic == case.mimic_preferred_topic
        text = render.claimant_answer(claimant.display_name, topic, fact_text, source_kind, repeated, close_wording)
        independent = (fact_id,) if fact_id and fact_id in claimant.independent_fact_ids else ()
        heard = (fact_id,) if fact_id and source_kind == "heard" else ()
        record = StatementRecord(
            turn=self.state.turn,
            claimant_id=claimant.claimant_id,
            topic=topic,
            semantic_fact_ids=(fact_id,) if fact_id else (),
            public=public,
            independent_fact_ids=independent,
            heard_fact_ids=heard,
            rendered_text=text,
            wording_template_id=self._rng.choice(content.RESPONSE_TEMPLATES[topic.value]),
        )
        claimant.statement_history.append(record)
        case.statement_history.append(record)
        case.asked_actions.add(canonical)
        if public and fact_id:
            self._expose(case, fact_id, claimant.claimant_id, fact_text or "")
        elif fact_id:
            case.exposures[fact_id].private_observers.add("player")
        mode = "at the public counter" if public else "in a private interview"
        return f"You question {claimant.display_name} {mode}.\n{text}"

    def _response_fact(self, case: CaseState, claimant: ClaimantState, topic: QuestionTopic) -> tuple[str | None, str]:
        prefix = case.case_id
        if claimant.role == ClaimantRole.OWNER:
            mapping = {
                QuestionTopic.CONCEALED_DETAIL: f"{prefix}_concealed",
                QuestionTopic.RELATIONSHIP: f"{prefix}_relationship",
                QuestionTopic.LOSS_TIMELINE: f"{prefix}_timeline",
                QuestionTopic.LAST_USE: f"{prefix}_last_use",
            }
            fid = mapping.get(topic)
            return (fid, "known") if fid else (None, "uncertain")
        if claimant.role == ClaimantRole.FINDER:
            if topic == QuestionTopic.RECOVERY_SCENE:
                return f"{prefix}_recovery", "scene"
            if topic == QuestionTopic.CONCEALED_DETAIL and case.item_open_at_recovery:
                return f"{prefix}_shallow", "known"
            if topic in {QuestionTopic.LOSS_TIMELINE, QuestionTopic.LAST_USE}:
                return f"{prefix}_finder_timeline", "incompatible"
            return None, "uncertain"
        if claimant.role == ClaimantRole.ASSOCIATE:
            if topic == QuestionTopic.RELATIONSHIP:
                return f"{prefix}_associate_context", "context"
            if topic == QuestionTopic.LAST_USE:
                return f"{prefix}_last_use", "context"
            if topic == QuestionTopic.LOSS_TIMELINE:
                return f"{prefix}_associate_timeline", "incompatible"
            return None, "uncertain"

        candidates = []
        for fid in claimant.heard_fact_ids:
            if claimant.heard_source_turn.get(fid, self.state.turn) >= self.state.turn:
                continue
            category = case.facts[fid].category
            if topic == QuestionTopic.CONCEALED_DETAIL and category in {FactCategory.CONCEALED_MARKER, FactCategory.SHALLOW_CONTENT}:
                candidates.append(fid)
            elif topic == QuestionTopic.RELATIONSHIP and category == FactCategory.RELATIONSHIP_PURPOSE:
                candidates.append(fid)
            elif topic in {QuestionTopic.LOSS_TIMELINE, QuestionTopic.LAST_USE} and category == FactCategory.LOSS_SEQUENCE:
                candidates.append(fid)
            elif topic == QuestionTopic.RECOVERY_SCENE and category == FactCategory.RECOVERY_SCENE:
                candidates.append(fid)
        if candidates:
            return max(
                candidates,
                key=lambda fid: (claimant.heard_source_turn[fid], claimant.heard_source_order[fid], fid),
            ), "heard"
        return None, "uncertain"

    def _expose(self, case: CaseState, fact_id: str, source: str, wording: str) -> None:
        self._exposure_sequence += 1
        exposure = case.exposures[fact_id]
        listeners = {cid for cid, claimant in case.claimants.items() if not claimant.isolated}
        if exposure.first_public_turn is None:
            exposure.first_public_turn = self.state.turn
            exposure.exposed_by = source
        exposure.audience_claimant_ids.update(listeners)
        case.public_fact_ids.add(fact_id)
        for cid in listeners:
            claimant = case.claimants[cid]
            claimant.heard_fact_ids.add(fact_id)
            claimant.heard_source_turn[fact_id] = self.state.turn
            claimant.heard_source_order[fact_id] = self._exposure_sequence
            claimant.heard_wording[fact_id] = wording

    # Resolution and scoring ------------------------------------------

    def _resolve_case(self, case: CaseState, resolution: ResolutionType, recipient: str | None) -> None:
        case.resolved = True
        case.resolution_type = resolution
        case.selected_recipient_id = recipient
        for claimant in case.claimants.values():
            claimant.isolated = False
        if resolution == ResolutionType.RETURNED:
            if recipient == case.owner_id:
                case.correctness_score = 180
                case.evidence_bonus = self._evidence_bonus(case, recipient)
                case.efficiency_bonus = max(0, 24 - 3 * max(0, case.turns_spent - 5))
                self.state.public_trust = min(100, self.state.public_trust + 4)
            else:
                case.correctness_score = -220
                self.state.public_trust = max(0, self.state.public_trust - 18)
        elif resolution == ResolutionType.STORED:
            case.correctness_score = -45
            self.state.public_trust = max(0, self.state.public_trust - 3)
        else:
            case.correctness_score = -65
        case.case_score = case.correctness_score + case.evidence_bonus + case.efficiency_bonus

    def _evidence_bonus(self, case: CaseState, claimant_id: str) -> int:
        records = [record for record in case.statement_history if record.claimant_id == claimant_id]
        marker_id = f"{case.case_id}_concealed"
        relationship_id = f"{case.case_id}_relationship"
        timeline_id = f"{case.case_id}_timeline"

        def independent_before_exposure(fid: str) -> bool:
            for record in records:
                if fid not in record.independent_fact_ids:
                    continue
                first = case.exposures[fid].first_public_turn
                if first is None or first >= record.turn:
                    return True
            return False

        item_verified = case.item_privately_inspected or case.item_publicly_opened
        marker = item_verified and independent_before_exposure(marker_id)
        relationship = independent_before_exposure(relationship_id)
        timeline = case.relevant_record_checked and independent_before_exposure(timeline_id)
        bonus = 30 * sum((marker, relationship, timeline))
        if marker and relationship and timeline:
            bonus += 40
        return bonus

    def _after_resolution(self, text: str) -> str:
        state = self.state
        if all(case.resolved for case in state.cases):
            self._finish("All three cases have been resolved.")
            return text
        state.case_index += 1
        return f"{text}\n\n{render.case_opening(state.cases[state.case_index], state.case_index + 1)}"

    def _force_store_all(self, reason: str) -> None:
        if self.done:
            return
        for case in self.state.cases:
            if not case.resolved:
                self._resolve_case(case, ResolutionType.FORCED_STORAGE, None)
        self._finish(reason)

    def _finish(self, reason: str) -> None:
        self._end_reason = reason
        raw = (
            100
            + sum(case.case_score for case in self.state.cases)
            + round(self.state.public_trust * 0.45)
            + 3 * self.state.privacy_tokens
            + 5 * self.state.record_checks
        )
        self._final_score = max(0, min(1000, raw))
        self.state.done = True
        self.state.final_score = self._final_score

    def finalize(self) -> None:
        if self.state and not self.done:
            self._force_store_all("The office closes; unresolved items are moved to storage.")

    def _invalid(self, message: str) -> tuple[str, int, bool, dict]:
        observation = f"{message}\n\n{render.resources_footer(self.state)}"
        return observation, 0, False, self._info()

    def _info(self) -> dict:
        if not self.state:
            return {}
        return {
            "turn": self.state.turn,
            "max_turns": self.state.max_turns,
            "case": min(self.state.case_index + 1, 3),
            "done": self.state.done,
        }


__all__ = [
    "LostAndFoundGame",
    "stable_episode_rng",
    "MAX_TURNS",
    "MAX_ADVERTISED_ACTIONS",
]
