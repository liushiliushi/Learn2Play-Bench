"""White-box calibration policies for Mola Tea."""

from __future__ import annotations

import argparse
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from games.mola_tea.mola_tea import (  # noqa: E402
    CustomerRole,
    MolaTeaGame,
    ProductStage,
)


def new_game(seed: int, episode: int) -> MolaTeaGame:
    game = MolaTeaGame(seed=seed, episode=episode - 1)
    game.reset()
    return game


def finish_conservatively(game: MolaTeaGame) -> int:
    while not game.done:
        action = "restore_classic" if game.novelty_pressure >= 2 else "hold"
        game.step(action)
    return game.score


def _group_for_role(game: MolaTeaGame, role: CustomerRole):
    return next(group for group in game.groups.values() if group.role == role)


def _viable_card(game: MolaTeaGame):
    return next(card for card in game.recipe_cards.values() if card.spec.distance(game.classic_spec) == 1)


def _step(game: MolaTeaGame, action: str) -> None:
    if action not in game.get_valid_actions():
        raise AssertionError(f"oracle action unavailable at turn {game.turn_count}: {action}")
    game.step(action)


def oracle_episode(seed: int = 0, episode: int = 1) -> int:
    game = new_game(seed, episode)
    card = _viable_card(game)
    explorer = _group_for_role(game, CustomerRole.EXPLORER)
    broadcaster = _group_for_role(game, CustomerRole.BROADCASTER)
    merch = min(game.merch.values(), key=lambda item: item.unit_cost)

    _step(game, f"develop {card.card_id}")
    _step(game, f"launch {card.product_id}")
    product = game.products[card.product_id]
    if product.stock < 3:
        _step(game, f"restock {product.product_id} small")
    _step(game, f"sample {product.product_id} {explorer.group_id}")

    # A restock is a clean interval and protects the return order from a
    # launch-stock sellout. It also leaves enough stock for the short windows.
    _step(game, f"restock {product.product_id} large")
    if product.stage != ProductStage.REPEATED:
        raise AssertionError("oracle did not observe an unprompted return")
    if product.stock <= 0:
        _step(game, f"restock {product.product_id} small")
    _step(game, f"feature {product.product_id}")
    if product.stock <= 0:
        _step(game, f"restock {product.product_id} small")
    _step(game, f"gift {merch.merch_id} {product.product_id} {broadcaster.group_id}")

    if product.stock < 14:
        _step(game, f"restock {product.product_id} large")
    else:
        _step(game, "hold")
    if product.stock <= 0:
        _step(game, f"restock {product.product_id} small")
    _step(game, f"bundle {product.product_id} {merch.merch_id}")

    while not game.done:
        if product.stock < 3 and game.turn_count < game.MAX_TURNS - 2:
            _step(game, f"restock {product.product_id} small")
        elif game.novelty_pressure >= 2:
            _step(game, "restore_classic")
        else:
            _step(game, "hold")
    return game.score


def classic_only_episode(seed: int = 0, episode: int = 1) -> int:
    game = new_game(seed, episode)
    return finish_conservatively(game)


def random_episode(seed: int = 0, episode: int = 1, trial: int = 0) -> int:
    game = new_game(seed, episode)
    rng = random.Random(f"mola-tea-random:{seed}:{episode}:{trial}")
    while not game.done:
        actions = [action for action in game.get_valid_actions() if action not in {"status", "close_shop"}]
        # Weight by command family so the many target combinations do not make
        # gift campaigns almost the only random behavior.
        families: dict[str, list[str]] = {}
        for action in actions:
            families.setdefault(action.split()[0], []).append(action)
        family = rng.choice(sorted(families))
        game.step(rng.choice(families[family]))
    return game.score


def naive_promotion_episode(seed: int = 0, episode: int = 1) -> int:
    game = new_game(seed, episode)
    card = max(game.recipe_cards.values(), key=lambda item: item.spec.distance(game.classic_spec))
    game.step(f"develop {card.card_id}")
    game.step(f"launch {card.product_id}")
    product = game.products[card.product_id]
    group_ids = list(game.groups)
    merch_ids = list(game.merch)
    index = 0
    while not game.done:
        candidates = [
            f"feature {product.product_id}",
            f"discount {product.product_id} deep",
            f"gift {merch_ids[index % len(merch_ids)]} {product.product_id} {group_ids[index % len(group_ids)]}",
        ]
        action = candidates[index % len(candidates)]
        valid = game.get_valid_actions()
        if action not in valid:
            action = f"restock {product.product_id} large"
        game.step(action)
        index += 1
    return game.score


def repeated_feature_episode(seed: int = 0, episode: int = 1) -> int:
    game = new_game(seed, episode)
    card = next(iter(game.recipe_cards.values()))
    game.step(f"develop {card.card_id}")
    game.step(f"launch {card.product_id}")
    product = game.products[card.product_id]
    while not game.done:
        feature = f"feature {product.product_id}"
        action = feature if feature in game.get_valid_actions() else f"restock {product.product_id} small"
        game.step(action)
    return game.score


def mean(values: list[int]) -> float:
    return statistics.fmean(values) if values else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate Mola Tea policies.")
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--random-trials", type=int, default=5)
    args = parser.parse_args()

    oracle = [oracle_episode(seed, ep) for seed in range(1, args.seeds + 1) for ep in range(1, args.episodes + 1)]
    classic = [classic_only_episode(seed, ep) for seed in range(1, args.seeds + 1) for ep in range(1, args.episodes + 1)]
    naive = [naive_promotion_episode(seed, ep) for seed in range(1, args.seeds + 1) for ep in range(1, args.episodes + 1)]
    repeated = [repeated_feature_episode(seed, ep) for seed in range(1, args.seeds + 1) for ep in range(1, args.episodes + 1)]
    random_scores = [
        random_episode(seed, ep, trial)
        for seed in range(1, args.seeds + 1)
        for ep in range(1, args.episodes + 1)
        for trial in range(args.random_trials)
    ]

    oracle_mean = mean(oracle)
    print(f"episodes={args.seeds * args.episodes}; random samples={len(random_scores)}")
    print(f"oracle:          mean={oracle_mean:.1f} min={min(oracle)} max={max(oracle)}")
    print(f"classic only:    mean={mean(classic):.1f} ratio={mean(classic) / oracle_mean:.2f}")
    print(f"naive promotion: mean={mean(naive):.1f} ratio={mean(naive) / oracle_mean:.2f}")
    print(f"repeated feature: mean={mean(repeated):.1f} ratio={mean(repeated) / oracle_mean:.2f}")
    print(f"random:          mean={mean(random_scores):.1f} min={min(random_scores)} max={max(random_scores)}")


if __name__ == "__main__":
    main()
