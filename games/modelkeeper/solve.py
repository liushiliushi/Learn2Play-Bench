"""Reference solver wrapper for Modelkeeper (mirrors other games' solve.py).

Exposes the intended probing routine as a heuristic that reaches near-perfect
prediction within the configured solver budget, and a __main__ self-test over
seeds 0-9 that prints per-seed normalized score + probes used.
"""

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.modelkeeper.modelkeeper import (  # noqa: E402
    ReferenceSolver, HardReferenceSolver, ExpertReferenceSolver,
    _predict_with_fitted, _predict_with_fitted_machines, _predict_with_fitted_expert,
    Config, HARD_CONFIG, EXPERT_CONFIG, ModelkeeperGame, simulate,
)


def solve_episode(seed, episode=1, cfg=None):
    """Return (normalized_score, probes_used) for the heuristic on one instance.

    Picks the depth-1 or the hard (depth-2) reference solver from the config.
    Hard-like modes may use a separate certification budget; when present, that
    path verifies instance solvability rather than the player-facing budget."""
    cfg = cfg or Config()
    g = ModelkeeperGame(seed=seed, config=cfg)
    for _ in range(episode - 1):
        g.reset()
    machine, exam = g._machine, g._exam_inputs
    if cfg.family == "expert":
        ok, probes, fitted = ExpertReferenceSolver(cfg).solve(machine, exam)
        if not ok:
            return None, probes
        pred = _predict_with_fitted_expert(fitted, exam)
    elif cfg.hidden_allowed or cfg.depth >= 2:
        solve_cfg = replace(cfg, probe_budget=cfg.certify_probe_budget) if cfg.certify_probe_budget else cfg
        ok, probes, fitted = HardReferenceSolver(solve_cfg).solve(machine)
        if not ok:
            return None, probes
        pred = _predict_with_fitted_machines(fitted, exam)
    else:
        ok, probes, fitted = ReferenceSolver(cfg).solve(machine)
        if not ok:
            return None, probes
        pred = _predict_with_fitted(machine, fitted, exam)
    # score through the real game
    g.step("exam")
    R = g._R
    info = {}
    for c in range(g._n_cells):
        _, _, _, info = g.step(f"predict_{pred[c // R][c % R]}")
    return info["normalized"], probes


def self_test(cfg, label):
    budget_note = f"player_budget={cfg.probe_budget}"
    if cfg.certify_probe_budget:
        budget_note += f", certify_budget={cfg.certify_probe_budget}"
    print(f"Modelkeeper heuristic self-test ({label}, {budget_note})")
    print(f"{'seed':>4}  {'normalized':>10}  {'probes':>6}")
    worst = 1.0
    for seed in range(10):
        norm, probes = solve_episode(seed, cfg=cfg)
        worst = min(worst, norm if norm is not None else -1)
        shown = f"{norm:+.3f}" if norm is not None else "UNSOLVED"
        print(f"{seed:>4}  {shown:>10}  {probes:>6}")
    ok = worst >= 0.95
    print(f"worst normalized = {worst:+.3f}  -> {'PASS' if ok else 'FAIL'} (target ≥ 0.95)\n")
    return ok


def main():
    # `python solve.py [hard]` -> hard config; default tests the standard config.
    mode = sys.argv[1] if len(sys.argv) > 1 else "standard"
    if mode == "expert":
        ok = self_test(EXPERT_CONFIG, "expert config")
    elif mode == "hard":
        ok = self_test(HARD_CONFIG, "hard config")
    else:
        ok = self_test(Config(), "standard config")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
