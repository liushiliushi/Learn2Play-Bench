"""Ecosphere EXACT solver & calibration tool.

Because the decision is a finite discrete stocking vector under a budget and the
simulation is deterministic, the true theoretical maximum is computable by
exhaustive enumeration over all budget-feasible stockings. Producers only need
to be present (count beyond 1 is strictly dominated — wasted budget), so they
are binary; the other species are bounded by budget and carrying capacity. This
makes the full enumeration small (~10^5 stockings) and fast (a few seconds).

Usage:
    python games/ecosphere/solve.py --seed 42 [--rollouts 2000]
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from games.ecosphere.ecosphere import EcosphereGame

def exact_max(game):
    """Exact theoretical maximum by exhaustive enumeration over EVERY
    budget-feasible stocking. The decision is a finite discrete vector and the
    simulation is deterministic, so this is the true optimum (no domination
    assumptions — producer count now sets food capacity, so producers are
    enumerated over their full affordable range). ~9.5M stockings, ~10 min/seed
    (pure-Python deterministic sim per stocking; result exact — seed1=339, seed2=200).
    Returns (best_score, best_stocking, n_evaluated)."""
    COST, BUD = game.COST, game.BUDGET
    order = game.PRODUCERS + game.HERBIVORES + game.CARNIVORES + [game.DECOMPOSER]
    st = {s: 0 for s in order}
    best = [-1, None, 0]

    def dfs(i, rem):
        if i == len(order):
            final, _, _ = game._simulate(st)
            sc = game._score_of(st, final)
            best[2] += 1
            if sc > best[0]:
                best[0] = sc
                best[1] = {k: v for k, v in st.items() if v}
            return
        s, c = order[i], COST[order[i]]
        hi = rem // c
        if s in game.PRODUCERS:          # planting past the cap does nothing
            hi = min(hi, game.PRODUCER_CAP)
        for n in range(hi + 1):
            st[s] = n
            dfs(i + 1, rem - n * c)
        st[s] = 0

    dfs(0, BUD)
    return best


def random_mean(game, n, rng):
    species = list(game.ALL)
    total = 0
    for _ in range(n):
        stock, spent = {s: 0 for s in game.ALL}, 0
        for _ in range(rng.randint(3, 18)):
            s = rng.choice(species)
            if spent + game.COST[s] <= game.BUDGET:
                stock[s] += 1
                spent += game.COST[s]
        final, _, _ = game._simulate(stock)
        total += game._score_of(stock, final)
    return total / n


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rollouts", type=int, default=2000)
    args = parser.parse_args()

    game = EcosphereGame(seed=args.seed)
    rand = random_mean(game, args.rollouts, random.Random(0))
    best_sc, best_st, n = exact_max(game)

    print(f"seed={args.seed}")
    print(f"  theoretical max (exact) : {best_sc}   [{n} stockings enumerated]")
    print(f"  random alloc mean       : {rand:.1f}  ({rand / best_sc:.0%} of max)")
    print(f"  optimal stocking        : {best_st}")
    print(f"  food web : herb={ {h: game._diet[h] for h in game.HERBIVORES} }")
    print(f"             carn={ {c: game._diet[c] for c in game.CARNIVORES} }")


if __name__ == "__main__":
    main()
