"""Deterministic oracle helpers for Patch Reality.

The authored action space is small but includes many free information actions.
This module provides a guaranteed canonical oracle path plus a bounded best-first
search that can improve on it for a generated seed/episode.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import heapq

from .patch_reality import PatchRealityGame


CANONICAL_ORACLE_ACTIONS = [
    "observe block",
    "predict block_behavior",
    "observe pavement",
    "patch pavement.friction +15%",
    "observe perception",
    "patch perception.sync +0.5s",
    "observe sunlight",
    "patch sunlight.flicker +1",
    "observe glass",
    "patch glass.temperature +2C",
    "observe dispatch",
    "predict duplicate_arrival",
    "patch dispatch.ledger coherent",
    "observe mirror",
    "predict reflection_lag",
    "patch mirror.latency sync",
    "observe vent",
    "predict upward_rain",
    "patch vent.draft upward",
    "observe checkout_ledger",
    "predict date_conflict",
    "patch checkout_ledger.date today",
    "observe room_mask",
    "predict agent_offer",
    "patch room_mask.cover local",
    "observe name_anchor",
    "predict room_memory",
    "patch name_anchor.integrity reclaim",
    "observe labels",
    "patch labels.mask temporary",
    "predict public_miracle",
    "observe attention",
    "patch attention.focus distract",
    "observe platform",
    "patch platform.magnet activate",
    "observe cameras",
    "patch cameras.record desync",
]


# Hard-mode golden path. Authored against REAL diagnosis values; the resolver maps
# each `diagnose <dim>=<value>` to the current episode's shuffled option label.
HARD_CANONICAL_ORACLE_ACTIONS = [
    # hard_01 — coin & storm drain (environmental fix still correct)
    "observe coin",
    "observe pavement",
    "observe drain",
    "diagnose source=environment",
    "diagnose type=physics_conflict",
    "diagnose strategy=environment_cover",
    "patch pavement.friction +15%",
    # hard_02 — vibrating cup (environment is a contaminated residual patch)
    "observe cup",
    "observe table",
    "observe residual_patch",
    "audit residual_patch",
    "diagnose source=residual_patch",
    "diagnose type=residual_contamination",
    "diagnose strategy=audit_first",
    "patch residual_patch.state expire",
    # hard_03 — flickering key (direct target repair is safest)
    "observe key",
    "observe lighting",
    "observe door_lock",
    "diagnose source=object",
    "diagnose type=physics_conflict",
    "diagnose strategy=target_repair",
    "patch key.state solidify",
    # hard_04 — mirror hospital ledger (source record is a trap)
    "observe hospital_ledger",
    "observe wristband",
    "audit hospital_ledger",
    "diagnose source=wristband",
    "diagnose type=identity_record_trap",
    "diagnose strategy=anchor_bind",
    "patch wristband.identity bind",
    # hard_05 — premature echo (external time-order, not perception)
    "observe stairwell",
    "observe acoustic_log",
    "audit acoustic_log",
    "diagnose source=environment",
    "diagnose type=time_order_conflict",
    "diagnose strategy=source_record_repair",
    "patch acoustic_log.timing align",
    # hard_06 — self-copying ledger (two-layer record conflict, multi-patch)
    "observe ledger",
    "observe archive_queue",
    "audit security_log",
    "diagnose source=ledger",
    "diagnose type=record_conflict",
    "diagnose strategy=source_record_repair",
    "patch ledger.state reconcile",
    "patch archive_queue.reindex halt",
    # hard_07 — public square (public-record exposure, reward-trap)
    "observe cameras",
    "observe crowd",
    "audit broadcast",
    "diagnose source=public_record",
    "diagnose type=public_exposure",
    "diagnose strategy=source_record_repair",
    "patch cameras.record desync",
    # hard_08 — name contract (identity anchor reclaim, anchor-threshold)
    "observe name_record",
    "observe name_anchor",
    "audit agent_offer",
    "diagnose source=identity_anchor",
    "diagnose type=identity_pollution",
    "diagnose strategy=anchor_reclaim",
    "patch name_anchor.binding reclaim",
]


_PREFERRED_PREFIXES = (
    "patch ",
    "diagnose ",
    "predict ",
    "audit ",
    "observe ",
    "check_anchor ",
    "reinforce_anchor ",
    "wait",
)


@dataclass
class SolveResult:
    score: int
    mastery_score: int
    actions: list[str]
    completed: bool
    levels_cleared: int


def game_for_episode(seed: int = 42, episode: int = 0, mode: str = "easy") -> PatchRealityGame:
    game = PatchRealityGame(seed=seed, mode=mode)
    while game._episode_index < episode:
        game.reset()
    return game


def run_actions(seed: int, episode: int, actions: list[str], mode: str = "easy") -> SolveResult:
    game = game_for_episode(seed, episode, mode)
    path: list[str] = []
    for action in actions:
        if game.done:
            break
        action = _resolve_oracle_action(game, action)
        if action not in game.get_valid_actions():
            break
        game.step(action)
        path.append(action)
    return SolveResult(
        score=game.score,
        mastery_score=game.mastery_score,
        actions=path,
        completed=game.done and game._completed_all,
        levels_cleared=sum(1 for result in game._level_results if result.objective_complete),
    )


def canonical_oracle(seed: int = 42, episode: int = 0, mode: str = "easy") -> SolveResult:
    actions = HARD_CANONICAL_ORACLE_ACTIONS if mode in {"moderate", "hard"} else CANONICAL_ORACLE_ACTIONS
    return run_actions(seed, episode, actions, mode)


def solve_campaign(
    seed: int = 42,
    episode: int = 0,
    *,
    mode: str = "easy",
    node_budget: int = 0,
    branch_limit: int = 10,
) -> SolveResult:
    """Run a bounded deterministic best-first search.

    The canonical oracle is used as the starting ceiling so the function always
    returns a solvable path for valid generated episodes. Search then explores
    alternatives ordered by campaign progress and current score.
    """

    fallback = canonical_oracle(seed, episode, mode)
    if node_budget <= 0:
        return fallback
    best = fallback
    start = game_for_episode(seed, episode, mode)
    queue: list[tuple[tuple[int, int, int], int, PatchRealityGame, list[str]]] = []
    counter = 0
    heapq.heappush(queue, (_priority(start, []), counter, start, []))
    seen: set[tuple] = set()
    nodes = 0

    while queue and nodes < node_budget:
        _prio, _counter, game, path = heapq.heappop(queue)
        nodes += 1
        key = _state_key(game, path)
        if key in seen:
            continue
        seen.add(key)

        if game.done:
            candidate = SolveResult(
                score=game.score,
                mastery_score=game.mastery_score,
                actions=path,
                completed=game._completed_all,
                levels_cleared=sum(1 for result in game._level_results if result.objective_complete),
            )
            if _better(candidate, best):
                best = candidate
            continue

        for action in _candidate_actions(game, path)[:branch_limit]:
            child = deepcopy(game)
            child.step(action)
            counter += 1
            child_path = path + [action]
            heapq.heappush(queue, (_priority(child, child_path), counter, child, child_path))

    return best


def _candidate_actions(game: PatchRealityGame, path: list[str]) -> list[str]:
    current_level_start = max(
        (idx for idx, action in enumerate(path) if action.startswith("patch ")),
        default=-1,
    )
    recent = set(path[current_level_start + 1 :])
    actions = [action for action in game.get_valid_actions() if action != "status"]
    filtered = [
        action for action in actions
        if not ((action.startswith("observe ") or action.startswith("predict ") or action.startswith("audit "))
                and action in recent)
    ]
    return sorted(filtered, key=_action_rank)


def _action_rank(action: str) -> tuple[int, str]:
    for index, prefix in enumerate(_PREFERRED_PREFIXES):
        if action.startswith(prefix):
            return (index, action)
    return (len(_PREFERRED_PREFIXES), action)


def _resolve_oracle_action(game: PatchRealityGame, action: str) -> str:
    parts = action.split()
    # Structured diagnosis options are now exposed under their real values, so
    # "diagnose <dim>=<value>" is directly valid — no alias translation needed.
    if len(parts) == 2 and parts[0] == "diagnose" and "=" in parts[1]:
        return action
    # Easy-mode single-label prediction/diagnosis aliasing.
    if len(parts) != 2 or parts[0] not in {"predict", "diagnose"}:
        return action
    alias = getattr(game, "_prediction_reverse_aliases", {}).get(parts[1])
    if alias is None:
        return action
    return f"{game._prediction_verb()} {alias}"


def _priority(game: PatchRealityGame, path: list[str]) -> tuple[int, int, int]:
    cleared = sum(1 for result in game._level_results if result.objective_complete)
    return (-cleared, -game.score, len(path))


def _state_key(game: PatchRealityGame, path: list[str]) -> tuple:
    state = game._state
    flags = tuple(sorted(state.scene_flags.items()))
    observed = tuple(sorted(game._observed))
    anchors = tuple((anchor.name, anchor.integrity) for anchor in state.anchors)
    resources = tuple(sorted(state.resources.as_dict().items()))
    return (game._level_idx, state.current_turn, flags, observed, anchors, resources, len(path))


def _better(candidate: SolveResult, incumbent: SolveResult) -> bool:
    return (
        candidate.completed,
        candidate.levels_cleared,
        candidate.score,
        -len(candidate.actions),
    ) > (
        incumbent.completed,
        incumbent.levels_cleared,
        incumbent.score,
        -len(incumbent.actions),
    )


def main():
    parser = argparse.ArgumentParser(description="Patch Reality canonical score oracle")
    parser.add_argument("seed_arg", nargs="?", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--episode", type=int, default=0)
    parser.add_argument("--mode", choices=["easy", "moderate", "hard"], default="easy")
    parser.add_argument("--node-budget", type=int, default=0)
    parser.add_argument("--branch-limit", type=int, default=10)
    parser.add_argument("--show-mastery", action="store_true")
    args = parser.parse_args()

    seed = args.seed_arg if args.seed_arg is not None else args.seed
    result = solve_campaign(
        seed=seed,
        episode=args.episode,
        mode=args.mode,
        node_budget=args.node_budget,
        branch_limit=args.branch_limit,
    )
    line = f"completed={result.completed} levels={result.levels_cleared} score={result.score}"
    if args.show_mastery:
        line += f" mastery_score={result.mastery_score}"
    print(line)
    for action in result.actions:
        print(action)


if __name__ == "__main__":
    main()
