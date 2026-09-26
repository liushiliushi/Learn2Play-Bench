"""PatchReality — EvolveBench adapter for the patch_reality game.

patch_reality (vendored under ``_engine/``) is a deterministic, multi-file engine
whose ``GameEngine.run()`` owns its own command loop. EvolveBench instead wants a
single self-contained class with a passive ``step(action)`` interface, driven by
the harness, that measures *learning across episodes*.

This module is that adapter. It re-drives patch_reality's subsystems (parser,
command registry, cost calculator, ledger, state, scorer) turn-by-turn — mirroring
the body of ``GameEngine.run()`` — without ever calling the blocking ``run()``.
Nothing in the vendored engine is modified.

Design (see plan / CLAUDE.md):
- **Episode = one full campaign over all levels** (resource/anchor carryover, the
  same logic as ``CampaignRunner``). ``score`` = the campaign's total reward.
- **Actions are discrete and OBSERVE-gated** (the ``dungeon`` pattern): a
  ``patch <target>.<property> <change>`` action only appears in
  ``get_valid_actions()`` after the agent has ``observe``d that object. Costs and
  effects stay hidden until discovered by doing / ``audit``.
- The PATCH grammar's ``FOR/SCOPE/PAY`` clauses do not affect cost (verified in
  ``_engine/cost.py``), so a discrete patch maps to ``(target.property, change)``;
  the adapter fills the unused clauses with placeholders for the parser.
- ``reset()`` deep-copies the authored campaign and applies seed/episode-bounded
  variation so agents must learn reusable patch principles instead of replaying
  one fixed script.
"""

from copy import deepcopy
from pathlib import Path
import random

from ._engine.commands.base import CommandContext
from ._engine.commands.registry import default_registry
from ._engine.conditions import evaluate_condition
from ._engine.cost import CostCalculator
from ._engine.ledger import Ledger
from ._engine.level_loader import LevelLoader
from ._engine.parser import CommandParser, ParseError
from ._engine.scoring import RunStats, Scorer
from ._engine.state import GameState
from ._i18n import zh_token
from ._engine.models import Anchor, Resources

_LEVELS_DIR = Path(__file__).parent / "levels"
_HARD_LEVELS_DIR = Path(__file__).parent / "levels_hard"

# Campaign-terminating failures (mirrors CampaignRunner._HARD_FAILURES).
_HARD_FAILURES = {
    "identity_erasure",
    "total_amnesia",
    "local_reality_reset",
    "timeline_collapse",
    "forced_synchronization",
}

_ALWAYS_AVAILABLE = {"HELP"}

# Verbs that take a single target argument (for discrete-token translation).
_TARGET_VERBS = {"observe", "audit", "anchor", "check_anchor", "reinforce_anchor"}
_FOCUS_VERBS = {"OBSERVE", "PREDICT", "AUDIT", "CHECK_ANCHOR"}
_PREDICTION_ALIASES = tuple(f"option_{chr(ord('a') + idx)}" for idx in range(26))
_DIAGNOSIS_LEVELS = {
    "level_06",
    "level_07",
    "level_08",
    "level_09",
    "level_10",
    "level_11",
    "level_12",
}
_DEFAULT_FOCUS_LIMIT = 3
_FINAL_FOCUS_LIMIT = 4
# Hard mode needs room to gather evidence (observe/audit) *and* set three diagnosis
# dimensions, so it gets a larger — but still bounded — investigation budget.
_HARD_FOCUS_LIMIT = 8
# Moderate keeps diagnosis constrained, but leaves enough room to inspect the
# whole scene and reconsider a small number of choices.
_MODERATE_FOCUS_LIMIT = 10

_INFORMATION_REWARD_EVENTS = {
    "correct_prediction",
    "successful_audit",
    "reveal_hidden_cost",
}

# Adapter-level partial-credit milestones. These intentionally live outside the
# vendored engine so the original patch_reality scoring remains untouched.
_PROGRESS_MARKERS = {
    "level_01": [
        ("observe:block", 8, "inspected the primary anomaly"),
        ("observe:dust", 4, "noticed a secondary seam clue"),
    ],
    "level_02": [
        ("observe:coin", 5, "identified the immediate risk"),
        ("observe:pavement", 12, "found the quiet environmental fix"),
        ("observe:rainwater", 8, "found an indirect environmental fix"),
    ],
    "level_03": [
        ("observe:door", 5, "checked the external symptom"),
        ("observe:perception", 15, "found the self-scoped correction"),
    ],
    "level_04": [
        ("observe:onlookers", 5, "noticed the exposure risk"),
        ("observe:sunlight", 15, "found the plausible cover event"),
    ],
    "level_05": [
        ("observe:water", 5, "identified the deep-rule violation"),
        ("observe:glass", 15, "found the shallow environmental fix"),
        ("check_anchor:beach_memory", 5, "checked vulnerable collateral"),
    ],
    "level_06": [
        ("observe:dispatch", 15, "found the source bookkeeping contradiction"),
        ("observe:courier", 5, "noticed the witness timing"),
        ("predict:duplicate_arrival", 10, "predicted the duplicate-arrival cause"),
    ],
    "level_07": [
        ("observe:mirror", 12, "identified the medium-scoped repair"),
        ("observe:face", 5, "noticed the identity risk"),
        ("check_anchor:true_name", 5, "checked the threatened identity anchor"),
    ],
    "level_08": [
        ("observe:vent", 12, "found a plausible local explanation"),
        ("observe:phones", 5, "noticed recording exposure"),
        ("predict:upward_rain", 10, "predicted context over reversal"),
    ],
    "level_09": [
        ("observe:checkout_ledger", 15, "found the source record"),
        ("audit:transaction_history", 10, "audited the transaction history"),
        ("predict:date_conflict", 10, "predicted source-before-display repair"),
    ],
    "level_10": [
        ("observe:agent_offer", 8, "identified the tempting official repair"),
        ("audit:agent_offer", 15, "audited the anchor-payment trap"),
        ("observe:room_mask", 10, "found the local mask"),
    ],
    "level_11": [
        ("observe:name_anchor", 15, "found the correct personal anchor"),
        ("observe:labels", 10, "found the environmental overwrite channel"),
        ("check_anchor:true_name", 5, "checked the contested name"),
    ],
    "level_12": [
        ("observe:attention", 10, "identified the witness layer"),
        ("observe:platform", 10, "found the plausible physical cover"),
        ("observe:cameras", 10, "identified the record layer"),
        ("predict:public_miracle", 15, "planned the layered repair"),
    ],
}

# Hard-mode partial-credit milestones. ``diagnosis:complete`` and
# ``patch_supported:<key> <change>`` are synthetic events emitted by the adapter
# (not engine progress keys) when the structured diagnosis is fully correct and
# when a patch is applied with full evidence support, respectively.
_HARD_PROGRESS_MARKERS = {
    "hard_01": [
        ("observe:coin", 5, "assessed the immediate risk"),
        ("observe:pavement", 8, "inspected the environment surface"),
        ("observe:drain", 4, "noted the deadline"),
        ("diagnosis:complete", 12, "diagnosed source / type / strategy"),
        ("patch_supported:pavement.friction +15%", 15, "patched with full evidence support"),
    ],
    "hard_02": [
        ("observe:table", 5, "checked the environment"),
        ("observe:cup", 5, "inspected the anomaly"),
        ("audit:residual_patch", 12, "uncovered the residual contamination"),
        ("diagnosis:complete", 12, "diagnosed the residual source"),
        ("patch_supported:residual_patch.state expire", 15, "expired the residual patch"),
    ],
    "hard_03": [
        ("observe:key", 8, "inspected the bistable object"),
        ("observe:lighting", 5, "ruled out the lighting"),
        ("observe:door_lock", 6, "found the coupling risk"),
        ("diagnosis:complete", 12, "diagnosed object / physics / target_repair"),
        ("patch_supported:key.state solidify", 15, "stabilized the target directly"),
    ],
    "hard_04": [
        ("observe:hospital_ledger", 5, "read the death record"),
        ("audit:hospital_ledger", 12, "exposed the mirror-ledger trap"),
        ("observe:wristband", 8, "found the true identity source"),
        ("diagnosis:complete", 12, "diagnosed the identity-record trap"),
        ("patch_supported:wristband.identity bind", 15, "bound the true identity anchor"),
    ],
    "hard_05": [
        ("observe:stairwell", 8, "measured the echo externally"),
        ("audit:acoustic_log", 12, "found the record running ahead"),
        ("diagnosis:complete", 12, "diagnosed external time-order, not perception"),
        ("patch_supported:acoustic_log.timing align", 15, "repaired the source record's clock"),
    ],
    "hard_06": [
        ("observe:ledger", 8, "found the source contradiction"),
        ("observe:archive_queue", 8, "found the propagating layer"),
        ("audit:security_log", 10, "confirmed the mirror record"),
        ("diagnosis:complete", 12, "diagnosed the two-layer record conflict"),
        ("patch_supported:ledger.state reconcile", 12, "repaired the source ledger"),
        ("patch_supported:archive_queue.reindex halt", 12, "halted the propagation"),
    ],
    "hard_07": [
        ("observe:cameras", 8, "found where the exposure persists"),
        ("observe:crowd", 6, "noted the moment is already recorded"),
        ("audit:broadcast", 12, "confirmed the upload window"),
        ("diagnosis:complete", 12, "diagnosed public-record exposure"),
        ("patch_supported:cameras.record desync", 15, "contained the record layer"),
    ],
    "hard_08": [
        ("observe:name_record", 6, "saw the overwritten record"),
        ("observe:name_anchor", 8, "found the recoverable anchor"),
        ("audit:agent_offer", 14, "exposed the contract as bait"),
        ("diagnosis:complete", 12, "diagnosed identity pollution at the anchor"),
        ("patch_supported:name_anchor.binding reclaim", 15, "reclaimed identity without surrendering the anchor"),
    ],
}

# The three structured-diagnosis dimensions, in display order.
_DIAGNOSIS_DIMENSIONS = ("source", "type", "strategy")

# Per-level patch targets whose costs are nudged in some episodes so agents must
# learn principles rather than one fixed cheapest action.
_EASY_PREFERRED_TARGETS = {
    "level_02": ["pavement.friction", "rainwater.flow"],
    "level_06": ["dispatch.ledger", "indicator.floor"],
    "level_07": ["mirror.latency", "lighting.angle"],
    "level_08": ["vent.draft", "mist.pattern"],
    "level_09": ["checkout_ledger.date", "archive_queue.delay"],
    "level_10": ["room_mask.cover", "agent_offer.delay"],
    "level_11": ["name_anchor.integrity", "labels.mask"],
    "level_12": ["attention.focus", "suitcase.support"],
}
_HARD_PREFERRED_TARGETS = {
    "hard_01": ["pavement.friction", "coin.path"],
}

# Moderate is the human-playable bridge between the 12-level tutorial campaign
# and the strict benchmark.  The first encounter teaches the complete loop; the
# second fades to a process reminder.  Later encounters receive no coaching.
_MODERATE_TUTORIAL_INTROS = {
    "hard_01": (
        "教学 1/2：先观察，再根据证据完成三维诊断，最后施行修补。本关会在关键观察后给出明确指导。",
        "TUTORIAL 1/2: Observe first, use the evidence to complete all three diagnosis axes, "
        "then apply a patch. This encounter gives explicit guidance after key observations.",
    ),
    "hard_02": (
        "教学 2/2：这一次只提示调查方法，不再给出完整答案。若观察文字指出表面信息不足，请寻找审计行动。",
        "TUTORIAL 2/2: This time you get process reminders, not the complete answer. "
        "When an observation says the surface is insufficient, look for an audit action.",
    ),
}

_MODERATE_TUTORIAL_FEEDBACK = {
    ("hard_01", "observe:coin"): (
        "教学：硬币是症状，但症状未必是来源。接着观察人行道。",
        "Tutorial: the coin is the symptom, but the symptom need not be the source. Observe the pavement next.",
    ),
    ("hard_01", "observe:pavement"): (
        "教学：湿滑斜坡的证据表明——来源是「环境」，类型是「物理冲突」。接着查看雨水渠的期限。",
        "Tutorial: the wet slope points to source=environment and type=physics_conflict. "
        "Inspect the drain's deadline next.",
    ),
    ("hard_01", "observe:drain"): (
        "教学：策略应选「环境掩护」——它能伪装成路面自然变干，而不是直接改写硬币。三项诊断都设定后，受证据支持的修补就会出现。",
        "Tutorial: prefer strategy=environment_cover, which can look like ordinary drying, "
        "over rewriting the coin directly. Set all three axes; the evidence-supported patch will then appear.",
    ),
    ("hard_02", "observe:residual_patch"): (
        "教学提示：这条接缝明确说表面读数不足。先审计「残留补丁」，再作诊断。",
        "Tutorial reminder: the seam says its surface reading is insufficient. Audit residual_patch before diagnosing it.",
    ),
    ("hard_02", "audit:residual_patch"): (
        "教学提示：现在分别问自己：信号从哪里发出？这是什么类型的污染？哪种策略符合你刚做的调查？",
        "Tutorial reminder: now ask where the signal originates, what kind of contamination it is, "
        "and which strategy matches the investigation you just performed.",
    ),
}

# One Hard observation literally names the correct repair. Moderate keeps the
# evidence but removes that answer sentence so challenge levels still have
# episode-one headroom after the diagnosis glossary is taught.
_MODERATE_OBSERVE_OVERRIDES = {
    ("hard_08", "name_anchor"): (
        "在那些记录之下，端坐着决定它们指向何人的锚点。它与你之间的绑定已经松脱；每当这道绑定偏移，下游记录便随之改写。",
        "Beneath the records sits the anchor that decides whom they refer to. Its binding "
        "to you has gone slack; whenever that binding shifts, the downstream record changes with it.",
    ),
}


class PatchRealityGame:
    """EvolveBench-contract wrapper around the patch_reality campaign."""

    def __init__(self, seed=None, lang="en", mode="easy"):
        if seed is None:
            seed = random.randint(0, 10 ** 9)
        self.seed = seed
        # Localization: prose (level narrative + wrapper UI) is bilingual; the
        # action grammar / tokens stay canonical English so the solver and
        # mechanics are language-independent. Default 'en' keeps the automated
        # benchmark (main.py, which constructs without lang) on the English
        # baseline; play.py passes the interactive --lang (default zh).
        self._lang = lang if lang in ("zh", "en") else "en"
        if mode not in ("easy", "moderate", "hard"):
            raise ValueError(
                f"Unknown patch_reality mode '{mode}'. Use 'easy', 'moderate', or 'hard'.")
        self.mode = mode
        self._episode_index = -1

        # Mode-specific behavior tables. Easy mode keeps the original module-level
        # tables verbatim; hard mode swaps in structured diagnosis + hard markers.
        levels_dir = _LEVELS_DIR if mode == "easy" else _HARD_LEVELS_DIR
        self._diagnosis_levels = _DIAGNOSIS_LEVELS if mode == "easy" else set()
        self._progress_markers = _PROGRESS_MARKERS if mode == "easy" else _HARD_PROGRESS_MARKERS
        self._preferred_targets = (
            _EASY_PREFERRED_TARGETS if mode == "easy" else _HARD_PREFERRED_TARGETS
        )

        # Load the authored campaign once. reset() deep-copies these templates and
        # applies bounded seed/episode variation.
        _loader = LevelLoader(lang=self._lang)
        self._base_levels = [
            _loader.load(str(p)) for p in sorted(levels_dir.glob("*.json"))
        ]
        if mode == "moderate":
            self._apply_moderate_content(self._base_levels)
        if not self._base_levels:
            raise RuntimeError(f"No patch_reality levels found under {levels_dir}")

        self._levels = []
        self.MAX_TURNS = sum(lvl.turn_limit for lvl in self._base_levels)
        # Safety net so a pathological agent that only emits free actions can't loop
        # forever (free actions don't advance turns). Generous; real play stays well under.
        self._step_budget = self.MAX_TURNS * 8 + 200

        # Shared, stateless subsystems.
        self._registry = default_registry()
        self._calculator = CostCalculator()
        self._scorer = Scorer()
        self._parser = CommandParser()

        self.reset()

    # ── Episode lifecycle ──────────────────────────────────────────────────────

    def reset(self):
        """Start a fresh campaign at level 0.

        Each reset builds a deterministic, seed/episode-specific campaign copy.
        The level order and lesson family stay fixed; costs and a few pressure
        values vary within narrow bands so agents must learn principles rather
        than replay one exact script.
        """
        self._episode_index += 1
        self._levels = self._build_episode_levels(self._episode_index)
        self.MAX_TURNS = sum(lvl.turn_limit for lvl in self._levels)
        self._step_budget = self.MAX_TURNS * 8 + 200

        self._level_idx = 0
        self._finished_reward = 0.0
        self._finished_mastery_reward = 0.0
        self._finished_turns = 0
        self._level_results = []
        self._level_progress_bonuses = []
        self._completed_all = False
        self._reached_end = False
        self._failed_levels = []
        self._failed_at = None
        self._done = False
        self._steps = 0

        self._carried_resources = None
        self._carried_anchors = None

        self._begin_level(self._levels[0], intro=False)

        obs = self._campaign_intro() + self._scene_intro(self._level) + "\n" + self._state_footer()
        return obs, {"valid": self.get_valid_actions()}

    def _begin_level(self, level, intro=True):
        """Initialise per-level state, applying campaign carryover."""
        self._level = level
        state = GameState.from_level(level)
        if self._carried_resources is not None:
            state.resources = self._carried_resources.copy()
        if self._carried_anchors is not None:
            state.anchors = self._merge_anchors(self._carried_anchors, level.anchors)
        self._state = state
        self._ledger = Ledger()
        self._stats = RunStats(initial_resources=state.resources.copy())
        self._ctx = CommandContext(
            state=state, level=level, ledger=self._ledger, calculator=self._calculator,
            lang=self._lang, tr=self._disp,
        )
        self._observed = set()  # objects revealed via OBSERVE → unlocks their patches
        self._pending_intro = intro  # show the level intro once, in the next footer
        self._progress_events = set()
        self._focus_limit = self._focus_limit_for(level)
        self._focus_remaining = self._focus_limit
        self._prediction_aliases = self._build_prediction_aliases(level)
        self._prediction_reverse_aliases = {
            event: alias for alias, event in self._prediction_aliases.items()
        }
        # Hard-mode structured diagnosis: per-dimension current selection + aliasing
        # (so option labels never expose the correct answer, like predictions do).
        self._diagnosis_selected = {dim: None for dim in level.diagnosis}
        self._diagnosis_aliases, self._diagnosis_reverse_aliases = (
            self._build_diagnosis_aliases(level)
        )
        self._free_no_progress = 0
        self._free_no_progress_budget = max(8, len(level.objects) * 4 + 4)

    def _focus_limit_for(self, level):
        if self.mode == "moderate":
            return _MODERATE_FOCUS_LIMIT
        if self.mode == "hard":
            override = getattr(level, "focus_limit", None)
            return int(override) if override is not None else _HARD_FOCUS_LIMIT
        try:
            phase = int(level.phase)
        except (TypeError, ValueError):
            phase = 0
        return _FINAL_FOCUS_LIMIT if phase >= 5 else _DEFAULT_FOCUS_LIMIT

    def _apply_moderate_content(self, levels):
        """Apply small prose-only overrides without duplicating the hard YAML set."""
        for level in levels:
            for object_name, obj in level.objects.items():
                override = _MODERATE_OBSERVE_OVERRIDES.get((level.id, object_name))
                if override:
                    obj.observe_text = self._t(*override)

    def _build_prediction_aliases(self, level):
        events = list(level.predictions)
        rng = random.Random(f"{self.seed}:{self._episode_index}:{level.id}:prediction_aliases")
        rng.shuffle(events)
        return {
            _PREDICTION_ALIASES[index]: event
            for index, event in enumerate(events)
            if index < len(_PREDICTION_ALIASES)
        }

    def _build_diagnosis_aliases(self, level):
        """Per-dimension option maps for structured diagnosis.

        Options are exposed under their real values (an identity map) in the authored
        YAML order — diagnosis is fully deterministic, so a learned agent transfers the
        *meaning* of the correct source/type/strategy directly, with nothing random to
        re-derive each episode. The learning signal lives in knowing which evidence
        implies which diagnosis, not in decoding a shuffled label. Returns
        ``(aliases, reverse)`` where both ``aliases[dim][value] = value`` and
        ``reverse[dim][value] = value``. Empty for easy levels (no ``diagnosis``).
        """
        aliases = {}
        reverse = {}
        for dim, spec in level.diagnosis.items():
            dim_map = {value: value for value in spec.get("options", [])}
            aliases[dim] = dim_map
            reverse[dim] = dict(dim_map)
        return aliases, reverse

    def _build_episode_levels(self, episode_index):
        levels = deepcopy(self._base_levels)
        rng = random.Random(f"{self.seed}:{episode_index}")
        self._apply_episode_variation(levels, rng)
        return levels

    def _apply_episode_variation(self, levels, rng):
        preferred_targets = self._preferred_targets
        for level in levels:
            if level.id != "level_01":
                level.turn_limit = max(3, level.turn_limit + rng.choice([-1, 0, 0, 1]))
            choices = preferred_targets.get(level.id, [])
            if not choices:
                continue
            preferred = rng.choice(choices)
            for patch_key, changes in level.valid_patches.items():
                for entry in changes.values():
                    surface = entry.get("surface_cost", {})
                    for resource, delta in list(surface.items()):
                        if resource == "agent_suspicion" or delta >= 0:
                            continue
                        if patch_key == preferred:
                            surface[resource] = min(0, delta + 1)
                        else:
                            surface[resource] = delta - rng.choice([0, 1])
                    factors = entry.get("cost_factors", {})
                    if patch_key == preferred:
                        factors["rationalization"] = max(
                            0.3, float(factors.get("rationalization", 1.0)) - 0.1
                        )

    # ── EvolveBench properties ─────────────────────────────────────────────────

    @property
    def score(self):
        return round(self._live_reward())

    @property
    def mastery_score(self):
        return round(self._live_mastery_reward())

    @property
    def comprehension_delta(self):
        return self.mastery_score - self.score

    @property
    def turn_count(self):
        in_progress = 0 if self._done else max(0, self._state.current_turn - 1)
        return self._finished_turns + in_progress

    @property
    def done(self):
        return self._done

    def _live_reward(self):
        total = self._finished_reward
        if not self._done:
            total += self._scorer.calculate_reward(self._state, self._canonical_stats())
        return total

    def _live_mastery_reward(self):
        total = self._finished_mastery_reward
        if not self._done:
            total += self._scorer.calculate_reward(self._state, self._stats)
            total += self._current_progress_bonus()
        return total

    def _canonical_stats(self):
        """Stats for the benchmark score, excluding free information bonuses."""
        return RunStats(
            initial_resources=self._stats.initial_resources.copy(),
            turns_used=self._stats.turns_used,
            reward_events=[
                event for event in self._stats.reward_events
                if event not in _INFORMATION_REWARD_EVENTS
            ],
            invalid_actions=self._stats.invalid_actions,
            observations=0,
            hidden_settlements=self._stats.hidden_settlements,
        )

    # ── Valid actions (discrete, OBSERVE-gated) ────────────────────────────────

    def get_valid_actions(self):
        if self._done:
            return []
        lvl, st = self._level, self._state
        avail = set(lvl.available_actions)
        actions = []
        has_focus = self._focus_remaining > 0

        if has_focus and "OBSERVE" in avail:
            actions += [f"observe {name}" for name in st.scene_objects]
        if has_focus and self._structured_diagnosis():
            for dim in _DIAGNOSIS_DIMENSIONS:
                actions += [f"diagnose {dim}={alias}"
                            for alias in self._diagnosis_aliases.get(dim, {})]
        elif has_focus and "PREDICT" in avail:
            verb = self._prediction_verb()
            actions += [f"{verb} {alias}" for alias in self._prediction_aliases]
        if "WAIT" in avail:
            actions.append("wait")
        if "PATCH" in avail and self._patches_unlocked():
            # Only objects the agent has OBSERVEd expose their patch options, and a
            # patch with declared required_evidence stays hidden until that evidence
            # has been gathered (observe/audit). Easy levels declare neither, so they
            # behave exactly as before.
            for tgt in sorted(self._observed):
                obj = st.scene_objects.get(tgt)
                if obj is None:
                    continue
                for prop in obj.patchable_properties:
                    entry = lvl.valid_patches.get(f"{tgt}.{prop}")
                    if not entry:
                        continue
                    for change in entry:
                        if not self._patch_evidence_met(tgt, prop, change):
                            continue
                        actions.append(f"patch {tgt}.{prop} {change}")
        if has_focus and "AUDIT" in avail:
            if self._ledger.entries:
                actions.append("audit")
            actions += [f"audit {entry['target']}" for entry in lvl.audit_entries
                        if entry.get("target")]
        for verb, tok in (("ANCHOR", "anchor"),
                          ("CHECK_ANCHOR", "check_anchor"),
                          ("REINFORCE_ANCHOR", "reinforce_anchor")):
            if verb in avail and (verb not in _FOCUS_VERBS or has_focus):
                actions += [f"{tok} {a.name}" for a in st.anchors]
        if self.mode == "moderate":
            actions.append("help")
        actions.append("status")
        return actions

    # Verbs whose single operand is a plain token (object/anchor name).
    _SINGLE_TOKEN_VERBS = {"observe", "audit", "anchor", "check_anchor", "reinforce_anchor"}

    def get_action_label(self, action):
        """Display label for one canonical action (Chinese in zh, verbatim in en)."""
        return self._zh_label(action) if self._lang == "zh" else action

    def _zh_label(self, action):
        """Chinese label for one canonical action, regardless of ``self._lang``.

        Translates the verb AND its operands via the glossary, while the engine,
        ``get_valid_actions()`` and the solver keep the canonical English string.
        This is also the single source of the label↔canonical relationship used by
        ``_canonicalize_zh`` to map typed Chinese back to canonical — so any change
        here is automatically reflected on the input side.
        """
        parts = action.split(None, 1)
        verb = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        zh_verb = zh_token(verb)
        if not rest:
            return zh_verb
        if verb == "diagnose" and "=" in rest:
            dim, val = rest.split("=", 1)
            return f"{zh_verb} {zh_token(dim.strip())}={zh_token(val.strip())}"
        if verb == "patch":
            # rest: "<target>.<property> <change...>"
            tp, _, change = rest.partition(" ")
            target, _, prop = tp.partition(".")
            zh_tp = f"{zh_token(target)}.{zh_token(prop, as_property=True)}" if prop else zh_token(target)
            zh_change = zh_token(change.strip()) if change.strip() else ""
            return f"{zh_verb} {zh_tp} {zh_change}".rstrip()
        if verb in self._SINGLE_TOKEN_VERBS:
            return f"{zh_verb} {zh_token(rest.strip())}"
        # predict (easy-mode letter aliases) and anything else: keep operand as-is.
        return f"{zh_verb} {rest}"

    def _prediction_verb(self):
        return "diagnose" if self._diagnosis_required() else "predict"

    def _diagnosis_required(self):
        if self._structured_diagnosis():
            return True
        return self._level.id in self._diagnosis_levels and bool(self._level.predictions)

    def _structured_diagnosis(self):
        """True when the current level uses the hard-mode source/type/strategy diagnosis."""
        return bool(getattr(self._level, "diagnosis", None))

    def _diagnosis_complete(self):
        if self._structured_diagnosis():
            return self._structured_diagnosis_correct()
        if not self._diagnosis_required():
            return True
        for event, entry in self._level.predictions.items():
            if entry.get("reward") == "correct_prediction" and f"predict:{event}" in self._progress_events:
                return True
        return False

    def _structured_diagnosis_correct(self):
        diag = self._level.diagnosis
        return bool(diag) and all(
            self._diagnosis_selected.get(dim) == spec.get("correct")
            for dim, spec in diag.items()
        )

    def _patches_unlocked(self):
        return not self._diagnosis_required() or self._diagnosis_complete()

    # ── Evidence support (hard mode) ────────────────────────────────────────────

    def _patch_requirement(self, target, prop, change):
        return self._level.patch_requirements.get(f"{target}.{prop} {change}")

    def _patch_evidence_met(self, target, prop, change):
        """True when a patch's required_evidence has been collected (or none declared)."""
        reqs = self._patch_requirement(target, prop, change)
        if not reqs:
            return True
        required = set(reqs.get("required_evidence", []))
        return required.issubset(self._state.evidence_tags)

    def _evidence_support(self, target, prop, change):
        """Evidence-support score in [0, 1] for a patch (see improvement plan)."""
        reqs = self._patch_requirement(target, prop, change)
        if not reqs:
            return 1.0
        have = self._state.evidence_tags
        required = set(reqs.get("required_evidence", []))
        helpful = set(reqs.get("helpful_evidence", []))
        helpful_score = (len(helpful & have) / len(helpful)) if helpful else 1.0
        if not required.issubset(have):
            return 0.3 * helpful_score
        return 0.7 + 0.3 * helpful_score

    def _collect_audit_evidence(self, target):
        """A targeted level audit_entry may carry an ``evidence`` list (hard mode)."""
        if not target:
            return
        for entry in self._level.audit_entries:
            if entry.get("target") == target and entry.get("evidence"):
                self._state.evidence_tags.update(entry["evidence"])

    def _mark_supported_patch(self, spec):
        """Record a one-time mastery mark for patching with full evidence support."""
        if spec is None:
            return
        key = f"{spec.key()} {spec.change}"
        if self._patch_evidence_met(spec.target, spec.property, spec.change) \
                and self._patch_requirement(spec.target, spec.property, spec.change):
            self._progress_events.add(f"patch_supported:{key}")

    # ── Step ───────────────────────────────────────────────────────────────────

    def _canonicalize_zh(self, action):
        """Map a typed Chinese action label back to its canonical English action.

        Reuses ``_zh_label`` as the single label↔canonical source: an exact
        Chinese label match returns the canonical action; anything else (a number-
        derived canonical, typed English, or unrecognized text) is returned
        unchanged for the normal pipeline to handle. Runs in every language so a
        history recorded under one lang replays cleanly under the other (webplay
        stores the localized labels the user clicked and pipes them back through
        ``play.py`` with whatever lang is active after a lobby switch).
        """
        if not action:
            return action
        labels = {self._zh_label(a): a for a in self.get_valid_actions()}
        return labels.get(action, action)

    def step(self, action):
        if self._done:
            return self._t("本场战役已经结束。", "The campaign is over."), 0, True, {"valid": []}

        action = self._canonicalize_zh((action or "").strip())
        low = action.lower()

        if low == "help" and self.mode == "moderate":
            return self._moderate_help(), 0, False, {"valid": self.get_valid_actions()}

        if low in ("status", ""):
            if self._record_no_progress_action("status"):
                self._state.game_over = True
                self._state.game_over_reason = "no_progress"
                settlement = self._finalize_and_advance()
                obs = (
                    self._t("你一直忙着查看元数据，异常却在你不知不觉间自行收束了。\n",
                            "You keep checking metadata while the anomaly settles without you.\n")
                    + "\n".join(settlement)
                    + "\n"
                    + self._tail_obs()
                )
                return obs, self.score, self._done, {"valid": self.get_valid_actions()}
            return self._render_status(), 0, False, {"valid": self.get_valid_actions()}

        self._steps += 1
        if self._steps > self._step_budget:
            # Pathological loop guard: end the current level and the campaign.
            self._state.game_over = True
            self._state.game_over_reason = self._state.game_over_reason or "out_of_turns"
            self._finalize_and_advance()
            obs = self._t("你耗费的时间实在太久了。现实不再等你，径自向前。\n",
                          "You have spent far too long. Reality moves on without you.\n") + self._tail_obs()
            return obs, self.score, self._done, {"valid": self.get_valid_actions()}

        if self._structured_diagnosis() and low.startswith("diagnose ") and "=" in action:
            return self._apply_diagnosis(action)

        raw, err = self._translate(action)
        if err is not None:
            self._stats.invalid_actions += 1
            return (f"{err}", 0, False, {"valid": self.get_valid_actions()})

        before = self.score
        feedback = self._apply_raw(raw)
        reward = self.score - before

        obs = "\n".join(feedback) if feedback else self._t("（没有效果）", "(no effect)")
        obs += "\n" + self._tail_obs()
        return obs, reward, self._done, {"valid": self.get_valid_actions()}

    def _tail_obs(self):
        """Footer shown after a step: state line, or next-level intro on transition."""
        if self._done:
            return self._campaign_summary()
        # If we just transitioned to a new level, lead with its intro (once).
        if self._pending_intro:
            self._pending_intro = False
            return "\n" + self._scene_intro(self._level) + "\n" + self._state_footer()
        return self._state_footer()

    # ── Structured diagnosis (hard mode) ────────────────────────────────────────

    def _apply_diagnosis(self, action):
        """Record one structured-diagnosis dimension selection.

        Diagnosis is a free, FOCUS-costing, non-turn-ending investigation action.
        Patch options only stabilize once every dimension matches its correct value.
        """
        invalid = lambda msg: (msg, 0, False, {"valid": self.get_valid_actions()})
        body = action.split(None, 1)[1] if len(action.split(None, 1)) > 1 else ""
        if "=" not in body:
            self._stats.invalid_actions += 1
            return invalid(self._t("诊断需采用 'diagnose <维度>=<选项>' 的形式。",
                                   "Diagnosis needs the form 'diagnose <dimension>=<option>'."))
        dim, alias = (part.strip().lower() for part in body.split("=", 1))
        if dim not in self._diagnosis_selected:
            self._stats.invalid_actions += 1
            return invalid(self._t(f"未知的诊断维度 '{dim}'。",
                                   f"Unknown diagnosis dimension '{dim}'."))
        value = self._diagnosis_aliases.get(dim, {}).get(alias)
        if value is None:
            self._stats.invalid_actions += 1
            choices_en = ", ".join(self._diagnosis_aliases.get(dim, {})) or "(none)"
            choices_zh = self._disp_join(self._diagnosis_aliases.get(dim, {})) or "（无）"
            return invalid(self._t(f"未知的 {self._disp(dim)} 选项 '{alias}'。可选项：{choices_zh}。",
                                   f"Unknown {dim} option '{alias}'. Valid options: {choices_en}."))
        if self._focus_remaining <= 0:
            self._stats.invalid_actions += 1
            return invalid(self._t("本关已无专注力可用于进一步调查。",
                                   "No focus remains for more investigation on this level."))

        self._focus_remaining = max(0, self._focus_remaining - 1)
        made_progress = self._diagnosis_selected[dim] != value
        self._diagnosis_selected[dim] = value
        if self._structured_diagnosis_correct():
            self._progress_events.add("diagnosis:complete")

        if self._record_no_progress_action("diagnose", made_progress=made_progress):
            self._state.game_over = True
            self._state.game_over_reason = "no_progress"
            settlement = self._finalize_and_advance()
            obs = (self._t("你反复推翻自己的诊断，异常却在你不知不觉间自行收束了。\n",
                           "You keep second-guessing the diagnosis while the anomaly settles "
                           "without you.\n") + "\n".join(settlement) + "\n" + self._tail_obs())
            return obs, self.score, self._done, {"valid": self.get_valid_actions()}

        msg = self._t(f"诊断 {self._disp(dim)} 已设为 '{self._disp(value)}'。",
                      f"Diagnosis {dim} set to '{value}'.")
        if self._structured_diagnosis_correct():
            msg += self._t(" 诊断现已内部自洽；修补选项随之稳定下来。",
                           " The diagnosis is now internally consistent; patch options stabilize.")
        elif self.mode == "moderate" and all(
                self._diagnosis_selected.get(axis) is not None
                for axis in self._diagnosis_selected):
            msg += self._t(
                " 当前组合与已收集的证据并不自洽；请重新考虑一个或多个维度。",
                " This combination is inconsistent with the evidence gathered; "
                "reconsider one or more axes.")
        obs = msg + "\n" + self._tail_obs()
        return obs, 0, False, {"valid": self.get_valid_actions()}

    # ── Discrete-token → raw-command translation ───────────────────────────────

    def _translate(self, action):
        """Map a discrete action token to a raw patch_reality command string.

        Returns (raw_command, None) on success, or (None, error_message).
        """
        low = action.lower()
        if low == "wait":
            return "WAIT", None
        if low == "audit":
            return "AUDIT", None

        parts = action.split()
        verb = parts[0].lower()

        if verb in {"predict", "diagnose"}:
            if len(parts) < 2:
                return None, self._t(f"'{verb}' 需要一个选项。", f"'{verb}' needs an option.")
            alias = parts[1].lower()
            target = self._prediction_aliases.get(alias)
            if target is None:
                return None, self._t("预测目标以选项标签的形式给出。",
                                     "Prediction targets are exposed as option labels.")
            return f"PREDICT {target}", None

        if verb == "patch":
            # Expected: "patch <target>.<property> <change...>"
            if len(parts) < 3 or "." not in parts[1]:
                return None, self._t("无效的修补行动。", "Invalid patch action.")
            target, prop = parts[1].split(".", 1)
            target = target.lower()
            prop = prop.lower()
            if target not in self._observed:
                return None, self._t(f"在修补 '{self._disp(target)}' 之前，你必须先观察它。",
                                     f"You must observe '{target}' before you can patch it.")
            if not self._patches_unlocked():
                return None, self._t("修补选项稳定之前，你需要先得出正确的诊断。",
                                     "You need a correct diagnosis before patch options stabilize.")
            change = " ".join(parts[2:])
            if not self._patch_evidence_met(target, prop, change):
                return None, self._t("目前所观察到的证据还不足以支撑这个修补。先进一步调查再施行。",
                                     "This patch isn't supported by what you've observed yet. "
                                     "Investigate further before applying it.")
            # FOR/SCOPE/PAY are required by the grammar but do not affect cost.
            return f"PATCH {target}.{prop} {change} FOR 1t SCOPE local PAY reality_stability", None

        if verb in _TARGET_VERBS:
            if len(parts) < 2:
                return None, self._t(f"'{verb}' 需要一个目标。", f"'{verb}' needs a target.")
            target = parts[1].lower()
            return f"{verb.upper()} {target}", None

        return None, self._t(f"未知行动：{low}", f"Unknown action: {low}")

    # ── Engine loop body (mirrors GameEngine.run / _advance_world) ──────────────

    def _apply_raw(self, raw):
        """Execute one raw command against the current level, mirroring the engine.

        Returns a list of feedback lines. Handles level completion + campaign
        advancement when the current level ends.
        """
        st, lvl, ctx = self._state, self._level, self._ctx

        try:
            parsed = self._parser.parse(raw)
        except ParseError as exc:
            self._stats.invalid_actions += 1
            return [str(exc)]

        if (lvl.available_actions
                and parsed.verb not in lvl.available_actions
                and parsed.verb not in _ALWAYS_AVAILABLE):
            self._stats.invalid_actions += 1
            return [self._t(f"此处无法使用 {self._disp(parsed.verb.lower())}。",
                            f"{parsed.verb} is not available here.")]

        command = self._registry.create(parsed)
        error = command.validate(ctx)
        if error:
            self._stats.invalid_actions += 1
            return [error]
        if parsed.verb in _FOCUS_VERBS and self._focus_remaining <= 0:
            self._stats.invalid_actions += 1
            return [self._t("本关已无专注力可用于进一步调查。",
                            "No focus remains for more investigation on this level.")]

        result = command.execute(ctx)
        if parsed.verb in _FOCUS_VERBS:
            self._focus_remaining = max(0, self._focus_remaining - 1)
        progress_key = self._progress_key(parsed)
        is_new_progress = progress_key is not None and progress_key not in self._progress_events
        if not result.ends_turn and not is_new_progress:
            result.reward_events = []
        self._record_progress_event(parsed)
        st.apply_result(result)
        self._stats.reward_events.extend(result.reward_events)
        if parsed.verb == "OBSERVE":
            self._stats.observations += 1
            target = parsed.args["target"]
            self._observed.add(target)
            obj = lvl.objects.get(target)
            if obj is not None and obj.evidence_tags:
                st.evidence_tags.update(obj.evidence_tags)  # hard-mode evidence
        elif parsed.verb == "AUDIT":
            self._collect_audit_evidence(parsed.args.get("target"))
        elif parsed.verb == "PATCH":
            self._mark_supported_patch(parsed.args.get("spec"))

        feedback = [result.message] if result.message else []
        tutorial = self._moderate_tutorial_feedback(parsed, is_new_progress)
        if tutorial:
            feedback.append(tutorial)
        if result.ends_turn:
            self._free_no_progress = 0
            feedback += self._advance_world(result.turns_consumed)
        else:
            if self._record_no_progress_action(parsed.verb.lower(), made_progress=is_new_progress):
                st.game_over = True
                st.game_over_reason = "no_progress"
            self._evaluate_outcome()

        if st.objective_complete:
            st.game_over = True

        if st.game_over:
            feedback += self._finalize_and_advance()

        return feedback

    def _progress_key(self, parsed):
        if parsed.verb == "PATCH":
            spec = parsed.args.get("spec")
            if spec is not None:
                return f"patch:{spec.key()} {spec.change}"
            return None
        if parsed.verb in {"OBSERVE", "PREDICT", "AUDIT", "ANCHOR", "CHECK_ANCHOR", "REINFORCE_ANCHOR"}:
            target = parsed.args.get("target")
            return f"{parsed.verb.lower()}:{target}" if target else parsed.verb.lower()
        return parsed.verb.lower()

    def _record_no_progress_action(self, action, made_progress=False):
        if made_progress:
            self._free_no_progress = 0
            return False
        self._free_no_progress += 1
        if self._free_no_progress <= self._free_no_progress_budget:
            return False
        self._stats.invalid_actions += 1
        return True

    def _record_progress_event(self, parsed):
        """Record successful actions that can earn one-time progress marks."""
        key = self._progress_key(parsed)
        if key:
            self._progress_events.add(key)

    def _moderate_tutorial_feedback(self, parsed, is_new_progress):
        if self.mode != "moderate" or not is_new_progress:
            return ""
        prompt = _MODERATE_TUTORIAL_FEEDBACK.get(
            (self._level.id, self._progress_key(parsed)))
        return self._t(*prompt) if prompt else ""

    def _earned_progress_markers(self):
        markers = self._progress_markers.get(self._level.id, [])
        return [
            (points, label)
            for event, points, label in markers
            if event in self._progress_events
        ]

    def _current_progress_bonus(self):
        return sum(points for points, _label in self._earned_progress_markers())

    def _advance_world(self, turns):
        st = self._state
        messages = []
        for _ in range(max(1, turns)):
            st.current_turn += 1
            messages += st.tick_patches()
            messages += self._run_scene_progression()
            self._evaluate_outcome()
            if st.game_over or st.objective_complete:
                break
        if st.objective_complete:
            st.game_over = True
        if not st.game_over and st.current_turn > st.max_turns:
            st.game_over = True
            st.game_over_reason = st.game_over_reason or "out_of_turns"
        return messages

    def _run_scene_progression(self):
        st, lvl = self._state, self._level
        messages = []
        for rule in lvl.scene_progression:
            if not self._rule_fires(rule):
                continue
            for key, value in rule.get("effect", {}).items():
                st.scene_flags[key] = value
            if rule.get("message"):
                messages.append(rule["message"])
            if st.scene_flags.get("objective_failed"):
                st.game_over = True
                st.game_over_reason = "objective_failed"
        return messages

    def _rule_fires(self, rule):
        st = self._state
        fires = False
        if "turn" in rule:
            fires = st.current_turn == rule["turn"]
        if rule.get("each_turn"):
            fires = True
        unless = rule.get("unless_flag")
        if fires and unless and st.scene_flags.get(unless):
            fires = False
        return fires

    def _evaluate_outcome(self):
        st, lvl = self._state, self._level
        if evaluate_condition(lvl.objective.condition, st):
            st.objective_complete = True
        failure = st.check_failure_conditions()
        if failure:
            st.game_over = True
            st.game_over_reason = failure

    # ── Level completion + campaign advancement (mirrors CampaignRunner.run) ────

    def _finalize_and_advance(self):
        st, lvl = self._state, self._level
        settlement_messages = self._settle_unrevealed_hidden_costs()
        settlement_messages += self._settle_stability_pressure()
        failure = st.check_failure_conditions()
        if failure and not st.game_over_reason:
            st.game_over_reason = failure
        self._stats.turns_used = max(0, st.current_turn - 1)
        result = self._scorer.build_result(st, lvl, self._canonical_stats())
        mastery_reward = self._scorer.calculate_reward(st, self._stats)
        progress_bonus = self._current_progress_bonus()
        self._level_results.append(result)
        self._level_progress_bonuses.append((lvl.id, progress_bonus))
        self._finished_reward += result.reward
        self._finished_mastery_reward += mastery_reward + progress_bonus
        self._finished_turns += result.turns_used

        self._carried_resources = result.final_resources
        self._carried_anchors = self._merge_anchors(result.surviving_anchors, [])

        if not result.objective_complete:
            self._failed_levels.append(lvl.id)
            if self.mode == "moderate":
                settlement_messages.append(self._moderate_failure_debrief())

        terminal = ((result.game_over_reason in _HARD_FAILURES)
                    or (not result.objective_complete and self.mode != "moderate"))
        if terminal:
            self._failed_at = lvl.id
            self._done = True
            return settlement_messages

        if self._level_idx + 1 < len(self._levels):
            self._level_idx += 1
            self._begin_level(self._levels[self._level_idx], intro=True)
        else:
            self._reached_end = True
            self._completed_all = all(r.objective_complete for r in self._level_results)
            self._done = True
        return settlement_messages

    def _moderate_failure_debrief(self):
        """Give learnable outcome feedback without disclosing any correct value."""
        if not self._structured_diagnosis():
            return self._t(
                "事后复盘：本关目标未完成。战役仍将继续。",
                "After-action review: the objective was not completed. The campaign continues.")
        verdicts = []
        for dim in _DIAGNOSIS_DIMENSIONS:
            spec = self._level.diagnosis.get(dim)
            if not spec:
                continue
            selected = self._diagnosis_selected.get(dim)
            if selected is None:
                verdict = self._t("未提交", "not set")
            elif selected == spec.get("correct"):
                verdict = self._t("符合证据", "matched the evidence")
            else:
                verdict = self._t("不符合证据", "did not match the evidence")
            selected_label = self._disp(selected) if selected else "?"
            verdicts.append(
                f"{self._disp(dim)}={selected_label} ({verdict})")
        evidence_complete = any(
            self._patch_evidence_met(*self._split_patch_requirement(key))
            for key in self._level.patch_requirements
        )
        evidence_state = self._t(
            "调查证据已足以支持至少一个安全修补。" if evidence_complete
            else "调查证据仍不完整。",
            "The investigation supported at least one safe patch." if evidence_complete
            else "The investigation evidence was still incomplete.",
        )
        prefix = self._t("事后复盘：", "After-action review: ")
        return prefix + "; ".join(verdicts) + ". " + evidence_state

    @staticmethod
    def _split_patch_requirement(key):
        target_property, change = key.split(" ", 1)
        target, prop = target_property.split(".", 1)
        return target, prop, change

    def _settle_unrevealed_hidden_costs(self):
        messages = []
        for entry in self._ledger.entries:
            if not entry.hidden_costs or entry.revealed:
                continue
            entry.revealed = True
            self._stats.hidden_settlements += 1
            for key, delta in entry.hidden_costs.items():
                anchor = self._state.get_anchor(key)
                if anchor is not None:
                    anchor.integrity += delta
                elif hasattr(self._state.resources, key):
                    setattr(self._state.resources, key, getattr(self._state.resources, key) + delta)
            costs = ", ".join(f"{key}: {delta}" for key, delta in entry.hidden_costs.items())
            costs_zh = "、".join(f"{self._disp(key)} {delta}" for key, delta in entry.hidden_costs.items())
            messages.append(
                self._t(
                    f"关卡结束时的隐藏结算：{entry.patch_id} 产生 {costs_zh}。{entry.system_note}",
                    f"Hidden settlement at level end: {entry.patch_id} applies {costs}. "
                    f"{entry.system_note}",
                )
            )
        return messages

    def _settle_stability_pressure(self):
        suspicion = self._state.resources.agent_suspicion
        if suspicion < 4:
            return []
        rs_loss = max(1, suspicion - 3)
        mem_loss = max(0, suspicion - 6)
        self._state.resources.reality_stability -= rs_loss
        if mem_loss:
            self._state.resources.memory -= mem_loss
        parts_en = [f"reality_stability: -{rs_loss}"]
        parts_zh = [f"{self._disp('reality_stability')} -{rs_loss}"]
        if mem_loss:
            parts_en.append(f"memory: -{mem_loss}")
            parts_zh.append(f"{self._disp('memory')} -{mem_loss}")
        return [
            self._t(
                "嘈杂修补累积的稳定性压力在整条战役中延迟结算：" + "、".join(parts_zh) + "。",
                "Delayed Stability pressure from noisy repairs settles across the campaign: "
                + ", ".join(parts_en)
                + ".",
            )
        ]

    @staticmethod
    def _merge_anchors(carried, level_anchors):
        merged = [Anchor(a.name, a.integrity, a.category, a.description) for a in carried]
        held = {a.name for a in merged}
        for anchor in level_anchors:
            if anchor.name not in held:
                merged.append(Anchor(anchor.name, anchor.integrity,
                                     anchor.category, anchor.description))
                held.add(anchor.name)
        return merged

    # ── Rendering ───────────────────────────────────────────────────────────────

    def _t(self, zh, en):
        """Pick a localized prose string by the active language."""
        return zh if self._lang == "zh" else en

    def _disp(self, token, as_property=False):
        """Glossary display name for a canonical token (zh), else the token itself."""
        if self._lang != "zh":
            return token
        return zh_token(token, as_property=as_property)

    def _disp_join(self, tokens):
        return ", ".join(self._disp(t) for t in tokens)

    def _campaign_intro(self):
        """One-time campaign framing printed above the first scene.

        Hard receives pure backstory; Moderate receives its public mechanics brief.
        Easy returns "" so that path stays byte-for-byte unchanged. Called only by
        reset(), so it never reprints between levels within a campaign.
        """
        if self.mode == "moderate":
            return self._moderate_help() + "\n\n"
        if self.mode != "hard":
            return ""
        en = (
            "One day, in an empty workshop, you notice a small metal block resting on a\n"
            "workbench. Nothing about it looks unusual — except that you know, with a\n"
            "certainty you can't explain, that it is wrong. It sits a fraction out of true\n"
            "with the world around it, as though reality had made a small error in copying\n"
            "it down and never noticed.\n\n"
            "Most people walk straight past details like this. You are one of the few who\n"
            "can see them — the places where reality has come loose — and, more rarely\n"
            "still, reach in and set them right.\n\n"
            "What lies ahead is a series of such breaks, each its own quiet emergency.\n"
            "Work through them one at a time; each one you mend leads on to the next.\n\n"
        )
        zh = (
            "某一天，在一间空荡荡的工坊里，你注意到工作台上搁着一小块金属。它看上去毫无异常——\n"
            "可你却莫名地确信，它是「错」的。它与周遭的世界差着那么一丝，仿佛现实在誊录它时\n"
            "出了个小小的纰漏，却始终未曾察觉。\n\n"
            "这样的细节，大多数人都会径直走过。而你是少数能看见它们的人——那些现实「松脱」之处——\n"
            "而更为罕见的是，你还能伸手进去，把它们重新校正过来。\n\n"
            "接下来，是一连串这样的裂隙，每一道都是一场无声的紧急事件。请一道一道地处置；\n"
            "你每修补好一处，便会引出下一处。\n\n"
        )
        return self._t(zh, en)

    def _moderate_help(self):
        return self._t(
            "补丁现实 · 适中模式\n\n"
            "你能观察现实的裂缝，并在有限的专注力内修补异常。调查行动会消耗专注力；修补与等待会推进场景。\n\n"
            "诊断有三个维度：\n"
            "  来源：异常从哪里产生，而不只是在哪里显现。\n"
            "  类型：冲突属于物理、记录、身份或其它哪一类。\n"
            "  策略：哪种处理方式能修复根因并减少附带损失。\n\n"
            "先「观察」收集事实；若表面信息不足，使用「审计」。"
            "三个维度都与证据一致后，受证据支持的「修补」才会出现。错误组合不会揭示答案，"
            "但适中模式会提醒你重新考虑。普通关卡失败后战役仍会继续。",
            "PATCH REALITY · MODERATE\n\n"
            "You can inspect seams in reality and repair anomalies with limited Focus. "
            "Investigation actions spend Focus; patches and waiting advance the scene.\n\n"
            "A diagnosis has three axes:\n"
            "  source: where the anomaly originates, not merely where it appears.\n"
            "  type: whether the conflict concerns physics, records, identity, or another family.\n"
            "  strategy: the response that repairs the cause with the least collateral.\n\n"
            "OBSERVE to collect facts; when surface information is insufficient, AUDIT. "
            "Only a three-axis diagnosis consistent with the evidence stabilizes supported PATCH options. "
            "A wrong combination will not reveal the answer, but Moderate will tell you to reconsider. "
            "The campaign continues after an ordinary encounter failure.",
        )

    def _scene_intro(self, level):
        none = self._t("（无）", "(none)")
        lines = [
            self._t(
                f"=== 关卡 {self._level_idx + 1}/{len(self._levels)}：{level.name}（阶段 {level.phase}）===",
                f"=== Level {self._level_idx + 1}/{len(self._levels)}: {level.name} (phase {level.phase}) ===",
            ),
            level.premise.strip(),
            self._t(f"目标：{level.objective.description}", f"Objective: {level.objective.description}"),
            self._t(f"可观察对象：{self._disp_join(level.objects.keys()) or none}",
                    f"Observable: {', '.join(level.objects.keys()) or none}"),
            self._t(f"可用行动：{', '.join(self._disp(v.lower()) for v in level.available_actions) or none}",
                    f"Verbs available: {', '.join(level.available_actions) or none}"),
            self._t(f"可用于调查的专注力：{self._focus_limit}",
                    f"Focus available for investigation: {self._focus_limit}"),
        ]
        tutorial = _MODERATE_TUTORIAL_INTROS.get(level.id) if self.mode == "moderate" else None
        if tutorial:
            lines.append(self._t(*tutorial))
        if self._structured_diagnosis():
            for dim in _DIAGNOSIS_DIMENSIONS:
                opts_en = ", ".join(self._diagnosis_aliases.get(dim, {})) or none
                opts_zh = self._disp_join(self._diagnosis_aliases.get(dim, {})) or none
                lines.append(self._t(f"诊断 {self._disp(dim)} 选项：{opts_zh}",
                                     f"Diagnose {dim} options: {opts_en}"))
            lines.append(self._t(
                "需要诊断：在修补选项稳定之前，先把 来源、类型、策略 三者设得彼此自洽。",
                "Diagnosis required: set source, type and strategy consistently "
                "before patch options stabilize."))
        elif level.predictions:
            verb = self._prediction_verb()
            aliases = ", ".join(self._prediction_aliases) or none
            lines.append(self._t(f"{self._disp(verb)} 选项：{aliases}", f"{verb.title()} options: {aliases}"))
            if self._diagnosis_required():
                lines.append(self._t("需要诊断：修补之前先选出有证据支撑的那个选项。",
                                     "Diagnosis required: choose the supported option before patching."))
        return "\n".join(lines)

    def _state_footer(self):
        st = self._state
        r = st.resources
        turn_word = self._t("回合", "turn")
        focus_word = self._t("专注", "FOCUS")
        return (
            f"[L{self._level_idx + 1}/{len(self._levels)} | "
            f"{turn_word} {st.current_turn}/{st.max_turns} | "
            f"{focus_word} {self._focus_remaining}/{self._focus_limit} | "
            f"RS {r.reality_stability} MEM {r.memory} TIME {r.personal_time} "
            f"EXIST {r.existence} SUSP {r.agent_suspicion}]"
        )

    def _render_status(self):
        st, lvl = self._state, self._level
        observed = self._disp_join(sorted(self._observed)) or self._t("（暂无）", "(nothing yet)")
        resources = ", ".join(f"{self._disp(k)}={v}" for k, v in st.resources.as_dict().items())
        lines = [
            self._t(f"关卡 {self._level_idx + 1}/{len(self._levels)}：{lvl.name}",
                    f"Level {self._level_idx + 1}/{len(self._levels)}: {lvl.name}"),
            self._t(f"目标：{lvl.objective.description}", f"Objective: {lvl.objective.description}"),
            self._t(f"回合：{st.current_turn}/{st.max_turns}", f"Turn: {st.current_turn}/{st.max_turns}"),
            self._t(f"专注力：{self._focus_remaining}/{self._focus_limit}",
                    f"Focus: {self._focus_remaining}/{self._focus_limit}"),
            self._t("资源：", "Resources: ") + resources,
            self._t(f"已观察：{observed}", f"Observed: {observed}"),
            self._t(f"已记录的修补：{len(self._ledger.entries)}", f"Patches recorded: {len(self._ledger.entries)}"),
        ]
        if self._structured_diagnosis():
            chosen = ", ".join(
                f"{self._disp(dim)}={self._disp(self._diagnosis_selected[dim]) if self._diagnosis_selected.get(dim) else '?'}"
                for dim in _DIAGNOSIS_DIMENSIONS if dim in self._diagnosis_selected
            )
            state = (self._t("已确定", "resolved") if self._diagnosis_complete()
                     else self._t("未确定", "unresolved"))
            lines.append(self._t(f"诊断（{state}）：{chosen}", f"Diagnosis ({state}): {chosen}"))
        elif self._diagnosis_required():
            state = (self._t("已确定", "resolved") if self._diagnosis_complete()
                     else self._t("未确定", "unresolved"))
            lines.append(self._t(f"诊断：{state}", f"Diagnosis: {state}"))
        if st.discovered_rules:
            lines.append(self._t("已发现的规律：", "Discovered rules:"))
            lines += [f"  - {r}" for r in st.discovered_rules]
        lines.append(self._t(f"目前战役得分：{self.score}", f"Campaign score so far: {self.score}"))
        return "\n".join(lines)

    def _campaign_summary(self):
        if self.mode == "moderate" and self._reached_end:
            status = (self._t("全部关卡通关", "ALL LEVELS COMPLETE")
                      if self._completed_all else
                      self._t("战役已完成（有未解决关卡）",
                              "CAMPAIGN COMPLETE WITH UNRESOLVED ENCOUNTERS"))
        elif self._completed_all:
            status = self._t("全部关卡通关", "ALL LEVELS COMPLETE")
        else:
            status = self._t(f"在「{self._level_display(self._failed_at)}」处失败",
                             f"FAILED at {self._failed_at}")
        cleared = sum(1 for r in self._level_results if r.objective_complete)
        lines = [
            self._t(f"=== 战役结束：{status} ===", f"=== Campaign over: {status} ==="),
            self._t(f"已通关：{cleared}/{len(self._levels)}",
                    f"Levels cleared: {cleared}/{len(self._levels)}"),
            self._t(f"总得分：{self.score}", f"Total score: {self.score}"),
        ]
        if self.mode == "moderate" and self._failed_levels:
            failed = ", ".join(self._failed_levels)
            failed_zh = "、".join(self._level_display(l) for l in self._failed_levels)
            lines.insert(2, self._t(f"未解决：{failed_zh}", f"Unresolved: {failed}"))
        return "\n".join(lines)

    def _level_display(self, level_id):
        """Localized display name for a level id (zh only; ids stay canonical)."""
        if self._lang != "zh":
            return level_id
        return next((l.name for l in self._levels if l.id == level_id), level_id)

    # ── Verification hook (used by the Stage-A smoke test only) ─────────────────

    def _debug_feed_raw(self, raw):
        """Feed a RAW patch_reality command, bypassing discretization/OBSERVE-gating.

        Lets the smoke test verify this adapter's loop reproduces GameEngine.run()
        for the same command sequence. Not used in normal play.
        """
        return self._apply_raw(raw)
