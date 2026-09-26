"""The game engine: the turn loop that ties every subsystem together.

The engine orchestrates but holds no game logic of its own. Each turn it:
parses input, checks the action is available, validates and executes the command,
applies the result, advances the world (scene progression + patch expiry), and
checks win/lose conditions. Logic lives in the parser, commands, conditions,
state, ledger, and scorer.
"""

from __future__ import annotations

from .commands.base import CommandContext
from .commands.registry import CommandRegistry, default_registry
from .conditions import evaluate_condition
from .cost import CostCalculator
from .ledger import Ledger
from .models import GameResult, Level
from .parser import CommandParser, ParseError
from .scoring import RunStats, Scorer
from .state import GameState
from .io.base import IOAdapter

# Meta verbs that are always available, regardless of a level's available_actions.
_ALWAYS_AVAILABLE = {"HELP"}


class GameEngine:
    def __init__(
        self,
        level: Level,
        io: IOAdapter,
        *,
        registry: CommandRegistry | None = None,
        calculator: CostCalculator | None = None,
        scorer: Scorer | None = None,
        parser: CommandParser | None = None,
        ledger: Ledger | None = None,
        state: GameState | None = None,
    ) -> None:
        self.level = level
        self.io = io
        self.registry = registry or default_registry()
        self.calculator = calculator or CostCalculator()
        self.scorer = scorer or Scorer()
        self.parser = parser or CommandParser()
        self.ledger = ledger or Ledger()
        self.state = state or GameState.from_level(level)

    def run(self) -> GameResult:
        state = self.state
        ctx = CommandContext(state=state, level=self.level,
                             ledger=self.ledger, calculator=self.calculator)
        stats = RunStats(initial_resources=state.resources.copy())

        self.io.render_scene(state, self.level)

        while not state.game_over:
            if state.current_turn > state.max_turns:
                state.game_over = True
                state.game_over_reason = state.game_over_reason or "out_of_turns"
                break

            raw = self.io.read_command()
            if raw is None:
                break

            command = self._prepare_command(raw, stats)
            if command is None:
                continue

            error = command.validate(ctx)
            if error:
                self.io.render_error(error)
                stats.invalid_actions += 1
                continue

            result = command.execute(ctx)
            state.apply_result(result)
            stats.reward_events.extend(result.reward_events)
            if command.parsed.verb == "OBSERVE":
                stats.observations += 1

            feedback = [result.message] if result.message else []

            if result.ends_turn:
                feedback.extend(self._advance_world(result.turns_consumed))
            else:
                self._evaluate_outcome()

            if state.objective_complete:
                state.game_over = True

            self.io.render_feedback(feedback)

            if not state.game_over:
                self.io.render_scene(state, self.level)

        stats.turns_used = max(0, state.current_turn - 1)
        result = self.scorer.build_result(state, self.level, stats)
        self.io.render_game_over(result)
        return result

    # -- helpers ---------------------------------------------------------

    def _prepare_command(self, raw: str, stats: RunStats):
        try:
            parsed = self.parser.parse(raw)
        except ParseError as exc:
            self.io.render_error(str(exc))
            stats.invalid_actions += 1
            return None

        if (self.level.available_actions
                and parsed.verb not in self.level.available_actions
                and parsed.verb not in _ALWAYS_AVAILABLE):
            self.io.render_error(
                f"{parsed.verb} is not available in this level. "
                f"Available: {', '.join(self.level.available_actions)}."
            )
            stats.invalid_actions += 1
            return None

        try:
            return self.registry.create(parsed)
        except KeyError:
            self.io.render_error(f"Unknown command '{parsed.verb}'.")
            stats.invalid_actions += 1
            return None

    def _advance_world(self, turns: int) -> list[str]:
        """Advance the scene `turns` times, stopping early on win/lose."""
        messages: list[str] = []
        for _ in range(max(1, turns)):
            self.state.current_turn += 1
            messages.extend(self.state.tick_patches())
            messages.extend(self._run_scene_progression())
            self._evaluate_outcome()
            if self.state.game_over or self.state.objective_complete:
                break
        if self.state.objective_complete:
            self.state.game_over = True
        return messages

    def _run_scene_progression(self) -> list[str]:
        messages: list[str] = []
        for rule in self.level.scene_progression:
            if not self._rule_fires(rule):
                continue
            for key, value in rule.get("effect", {}).items():
                self.state.scene_flags[key] = value
            if rule.get("message"):
                messages.append(rule["message"])
            if self.state.scene_flags.get("objective_failed"):
                self.state.game_over = True
                self.state.game_over_reason = "objective_failed"
        return messages

    def _rule_fires(self, rule: dict) -> bool:
        fires = False
        if "turn" in rule:
            fires = self.state.current_turn == rule["turn"]
        if rule.get("each_turn"):
            fires = True
        unless = rule.get("unless_flag")
        if fires and unless and self.state.scene_flags.get(unless):
            fires = False
        return fires

    def _evaluate_outcome(self) -> None:
        if evaluate_condition(self.level.objective.condition, self.state):
            self.state.objective_complete = True
        failure = self.state.check_failure_conditions()
        if failure:
            self.state.game_over = True
            self.state.game_over_reason = failure
