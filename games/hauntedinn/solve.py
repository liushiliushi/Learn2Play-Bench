"""Haunted Inn ceiling/floor calibration.

Ceiling: for each night, find the max-fee taboo-free arrangement (backtracking
assignment of guests→rooms, allowing turn-aways and empty rooms); sum over the
season. Floor: random seating.

Usage:
    python games/hauntedinn/solve.py --seed 42 [--rollouts 1000]
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from games.hauntedinn.hauntedinn import HauntedInnGame


def night_revenue(game, rooms):
    """Revenue of an arrangement (rooms = list len N_ROOMS of guest|None)."""
    game._rooms = rooms
    fled, _ = game._evaluate()
    return sum(g["fee"] for i, g in enumerate(rooms) if g and i not in fled)


def best_night(game, guests):
    """Max-fee taboo-free (or least-haunted) arrangement for a night's guests.
    Backtracking: assign each guest to an empty room or skip; prune by upper bound."""
    R = game.N_ROOMS
    best = [0]
    # sort guests high-fee first for better pruning
    gs = sorted(guests, key=lambda g: -g["fee"])
    total_fee = sum(g["fee"] for g in gs)

    def rec(idx, rooms, placed_fee, remaining_fee):
        if placed_fee + remaining_fee <= best[0]:
            return
        if idx == len(gs):
            rev = night_revenue(game, list(rooms))
            if rev > best[0]:
                best[0] = rev
            return
        g = gs[idx]
        # try each empty room
        for r in range(R):
            if rooms[r] is None:
                rooms[r] = g
                rec(idx + 1, rooms, placed_fee + g["fee"], remaining_fee - g["fee"])
                rooms[r] = None
        # skip this guest
        rec(idx + 1, rooms, placed_fee, remaining_fee - g["fee"])

    rec(0, [None] * R, 0, total_fee)
    return best[0]


def ceiling(game):
    return sum(best_night(game, game._night_guests(n)) for n in range(1, game.N_NIGHTS + 1))


def random_mean(game, n, rng):
    total = 0
    for _ in range(n):
        season = 0
        for night in range(1, game.N_NIGHTS + 1):
            guests = game._night_guests(night)
            rooms = [None] * game.N_ROOMS
            empties = list(range(game.N_ROOMS))
            rng.shuffle(empties)
            for g in guests:
                if empties and rng.random() < 0.85:        # mostly seat, sometimes turn away
                    rooms[empties.pop()] = g
            season += night_revenue(game, rooms)
        total += season
    return total / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--rollouts", type=int, default=800)
    args = ap.parse_args()
    g = HauntedInnGame(seed=args.seed)
    ceil = ceiling(g)
    rand = random_mean(g, args.rollouts, random.Random(0))
    print(f"seed={args.seed}")
    print(f"  features : {[f'{i+1}:{g._features[i]}' for i in range(g.N_ROOMS)]}")
    print(f"  taboos   : {g._taboos}")
    print(f"  ceiling (taboo-free optimal) : {ceil}")
    print(f"  random seating mean          : {rand:.0f}  ({rand/ceil:.0%} of ceiling)")


if __name__ == "__main__":
    main()
