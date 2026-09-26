"""White-box calibration helpers for Roadside Observatory."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from games.roadside_observatory.roadside_observatory import (  # noqa: E402
    A_COLLECTOR,
    A_DRIVER,
    A_HIKER,
    A_MECHANIC,
    A_RANGER,
    RoadsideObservatoryGame,
)


def mean(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def _travel_choice(game: RoadsideObservatoryGame) -> str:
    valid = game.get_valid_actions()
    if game.energy < 42 and "rest" in valid:
        return "rest"
    if not game._has_tag("slow_route") and "walk main road" in valid:
        return "walk main road"
    if "take bus" in valid and game.cash > 1:
        return "take bus"
    if "hitch safe" in valid:
        return "hitch safe"
    return "walk main road"


def oracle_action(game: RoadsideObservatoryGame) -> str:
    valid = game.get_valid_actions()
    enc = game._current_encounter()

    if "visit landmark" in valid:
        return "visit landmark"

    if enc is not None:
        if enc.archetype == A_MECHANIC:
            if A_MECHANIC in game._protocol_successes:
                return _travel_choice(game)
            if not enc.marks.get("small_task"):
                return "offer help"
            return "ask ride"

        if enc.archetype == A_RANGER:
            if A_RANGER in game._protocol_successes:
                return _travel_choice(game)
            if game.energy < 50:
                return "rest"
            if not enc.marks.get("asked_trail"):
                return "ask weather"
            return "ask shortcut"

        if enc.archetype == A_HIKER:
            if A_HIKER in game._protocol_successes:
                return _travel_choice(game)
            if not enc.marks.get("paid_cost"):
                if "share supply" in valid:
                    return "share supply"
                if "trade cash" in valid:
                    return "trade cash"
                return "forage"
            return "listen"

        if enc.archetype == A_COLLECTOR:
            if A_COLLECTOR in game._protocol_successes:
                return _travel_choice(game)
            return "tell story"

        if enc.archetype == A_DRIVER:
            if A_DRIVER in game._protocol_successes:
                return _travel_choice(game)
            if not enc.marks.get("refused"):
                return "refuse offer"
            if not enc.marks.get("verified"):
                return "question detail"
            return "accept offer"

        clue = game._item_alias.get("map_clue")
        if clue in game.items and f"show item {clue}" in valid:
            if game.energy < 25:
                return "rest"
            return f"show item {clue}"
        return "ask route"

    return _travel_choice(game)


def run_policy(game: RoadsideObservatoryGame, chooser) -> int:
    while not game.done:
        action = chooser(game)
        if action not in game.get_valid_actions():
            action = next(a for a in game.get_valid_actions() if a != "status")
        game.step(action)
    return game.score


def oracle_episode(seed: int = 0, episode: int = 1) -> int:
    game = RoadsideObservatoryGame(seed=seed, episode=episode - 1)
    game.reset()
    return run_policy(game, oracle_action)


def random_episode(seed: int = 0, episode: int = 1, trial: int = 0) -> int:
    rng = random.Random(f"roadside-random|{seed}|{episode}|{trial}")
    game = RoadsideObservatoryGame(seed=seed, episode=episode - 1)
    game.reset()
    while not game.done:
        actions = [a for a in game.get_valid_actions() if a != "status"]
        game.step(rng.choice(actions))
    return game.score


def naive_action(game: RoadsideObservatoryGame) -> str:
    valid = game.get_valid_actions()
    enc = game._current_encounter()
    if enc is not None:
        preferred = {
            A_MECHANIC: ["ask ride", "ask route"],
            A_RANGER: ["ask shortcut", "ask route"],
            A_HIKER: ["ask item", "ask route"],
            A_COLLECTOR: ["ask route", "listen"],
            A_DRIVER: ["accept offer", "ask route"],
        }.get(enc.archetype, ["ask route"])
        for action in preferred:
            if action in valid:
                return action
    if game.energy < 25 and "rest" in valid:
        return "rest"
    for action in ["walk main road", "take bus", "hitch safe", "check map"]:
        if action in valid:
            return action
    return next(a for a in valid if a != "status")


def naive_episode(seed: int = 0, episode: int = 1) -> int:
    game = RoadsideObservatoryGame(seed=seed, episode=episode - 1)
    game.reset()
    return run_policy(game, naive_action)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--random-trials", type=int, default=5)
    args = parser.parse_args()

    oracle = [oracle_episode(args.seed, ep) for ep in range(1, args.episodes + 1)]
    naive = [naive_episode(args.seed, ep) for ep in range(1, args.episodes + 1)]
    random_scores = [
        random_episode(args.seed, ep, trial)
        for ep in range(1, args.episodes + 1)
        for trial in range(args.random_trials)
    ]

    print(f"seed={args.seed} episodes={args.episodes}")
    print(f"oracle mean: {mean(oracle):.1f}  scores={oracle}")
    print(f"random mean: {mean(random_scores):.1f}")
    print(f"naive mean:  {mean(naive):.1f}  ratio={mean(naive) / mean(oracle):.2f}")


if __name__ == "__main__":
    main()
