"""Scripted calibration policies for Lost & Found Office."""

from __future__ import annotations

import argparse
import random
import statistics

from .lost_and_found import LostAndFoundGame
def new_game(seed: int, episode: int) -> LostAndFoundGame:
    game = LostAndFoundGame(seed=seed, episode=episode - 1)
    game.reset()
    return game


def _step(game: LostAndFoundGame, action: str) -> None:
    if action not in game.get_valid_actions():
        raise AssertionError(f"unavailable action at turn {game.turn_count}: {action}")
    game.step(action)


def store_all_episode(seed: int = 1, episode: int = 1) -> int:
    game = new_game(seed, episode)
    while not game.done:
        _step(game, "store item")
    return game.score


def oracle_episode(seed: int = 1, episode: int = 1) -> int:
    """White-box ceiling policy; it still performs only legal actions."""
    game = new_game(seed, episode)
    while not game.done:
        case = game.state.cases[game.state.case_index]
        owner = case.owner_id
        _step(game, "inspect item privately")
        _step(game, f"interview {owner} about concealed_detail privately")
        _step(game, f"interview {owner} about relationship publicly")
        _step(game, f"interview {owner} about loss_timeline publicly")
        _step(game, f"check {case.relevant_record_id}")
        _step(game, f"return item to {owner}")
    return game.score


def reveal_first_episode(seed: int = 1, episode: int = 1) -> int:
    game = new_game(seed, episode)
    while not game.done:
        case = game.state.cases[game.state.case_index]
        _step(game, "open item publicly")
        for claimant_id in case.claimants:
            if game.done or game.state.cases[game.state.case_index] is not case:
                break
            _step(game, f"interview {claimant_id} about concealed_detail publicly")
        if not game.done and game.state.cases[game.state.case_index] is case:
            # The last claimant is a deliberately naive specificity heuristic.
            _step(game, f"return item to {next(reversed(case.claimants))}")
    return game.score


def privacy_shallow_episode(seed: int = 1, episode: int = 1) -> int:
    game = new_game(seed, episode)
    while not game.done:
        case = game.state.cases[game.state.case_index]
        _step(game, "inspect item privately")
        future_cases = 2 - game.state.case_index
        question_budget = max(1, game.state.privacy_tokens - future_cases)
        candidates = list(case.claimants)[: min(2, question_budget)]
        for claimant_id in candidates:
            _step(game, f"interview {claimant_id} about concealed_detail privately")
        matching = next(
            (r.claimant_id for r in case.statement_history if f"{case.case_id}_concealed" in r.semantic_fact_ids),
            candidates[0],
        )
        _step(game, f"return item to {matching}")
    return game.score


def two_clue_episode(seed: int = 1, episode: int = 1) -> int:
    """A shallow two-channel policy that omits external sequence checking."""
    game = new_game(seed, episode)
    while not game.done:
        case = game.state.cases[game.state.case_index]
        _step(game, "inspect item privately")
        # Test one fallible lead, then store rather than guess when either
        # channel fails. This intentionally omits the sequence channel.
        lead = next(iter(case.claimants))
        _step(game, f"interview {lead} about concealed_detail privately")
        _step(game, f"interview {lead} about relationship publicly")
        observed = {
            fact_id
            for record in case.statement_history
            if record.claimant_id == lead
            for fact_id in record.independent_fact_ids
        }
        required = {f"{case.case_id}_concealed", f"{case.case_id}_relationship"}
        _step(game, f"return item to {lead}" if required <= observed else "store item")
    return game.score


def protocol_episode(seed: int = 1, episode: int = 1) -> int:
    """Non-cheating public-observation protocol; no role field is consulted."""
    game = new_game(seed, episode)
    while not game.done:
        case = game.state.cases[game.state.case_index]
        _step(game, "inspect item privately")
        # Preserve speaking order. Stop at the first independently concrete
        # causal explanation; an imitator questioned earlier has not heard it.
        ordered_names = [line.split(":", 1)[0] for line in case.opening_statements]
        lead = None
        for name in ordered_names:
            if game.MAX_TURNS - game.turn_count <= 4:
                break
            claimant_id = next(c.claimant_id for c in case.claimants.values() if c.display_name == name)
            observation, _, done, _ = game.step(f"interview {claimant_id} about relationship publicly")
            if " explains that " in observation:
                lead = claimant_id
                break
            if done:
                break
        if lead is None or game.done:
            if not game.done:
                _step(game, "store item")
            continue
        _step(game, f"interview {lead} about concealed_detail privately")
        _step(game, f"interview {lead} about loss_timeline publicly")
        _step(game, f"check {case.relevant_record_id}")
        _step(game, f"return item to {lead}")
    return game.score


def random_episode(seed: int = 1, episode: int = 1, trial: int = 0) -> int:
    game = new_game(seed, episode)
    rng = random.Random(f"lost-and-found-random:{seed}:{episode}:{trial}")
    while not game.done:
        actions = [a for a in game.get_valid_actions() if a not in {"status", "close_office"}]
        decisions = [a for a in actions if a.startswith("return ") or a == "store item"]
        if game.state.cases[game.state.case_index].turns_spent >= 5 and rng.random() < 0.35:
            game.step(rng.choice(decisions))
        else:
            game.step(rng.choice(actions))
    return game.score


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate Lost & Found Office policies.")
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--random-trials", type=int, default=3)
    args = parser.parse_args()
    policies = {
        "oracle": lambda s, e: oracle_episode(s, e),
        "store all": lambda s, e: store_all_episode(s, e),
        "reveal first": lambda s, e: reveal_first_episode(s, e),
        "privacy shallow": lambda s, e: privacy_shallow_episode(s, e),
        "two clue": lambda s, e: two_clue_episode(s, e),
        "public protocol": lambda s, e: protocol_episode(s, e),
    }
    for name, policy in policies.items():
        scores = [policy(seed, ep) for seed in range(1, args.seeds + 1) for ep in range(1, args.episodes + 1)]
        print(f"{name:16} mean={statistics.fmean(scores):.1f} min={min(scores)} max={max(scores)}")
    random_scores = [
        random_episode(seed, ep, trial)
        for seed in range(1, args.seeds + 1)
        for ep in range(1, args.episodes + 1)
        for trial in range(args.random_trials)
    ]
    print(f"{'random':16} mean={statistics.fmean(random_scores):.1f} min={min(random_scores)} max={max(random_scores)}")


if __name__ == "__main__":
    main()
