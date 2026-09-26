"""§4 Calibration — privileged reference players (the difficulty thermometer),
state-space estimate, and performance timing.

These four players MAY see the machine; they are NOT fairness-constrained agents,
they are scientific baselines that bracket floor and ceiling. Scoring always goes
through the real game (one source of truth for the normalized formula).

Run: python games/modelkeeper/baselines.py
Maps to MODELKEEPER_VERIFICATION_PLAN.md §4.
"""

import random
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.modelkeeper.modelkeeper import (  # noqa: E402
    MachineSim, ReferenceSolver, HardReferenceSolver, ExpertReferenceSolver,
    _predict_with_fitted, _predict_with_fitted_machines,
    _predict_with_fitted_expert, readout_value_count, Machine, simulate,
    _topo_order, Config, HARD_CONFIG, EXPERT_CONFIG, ModelkeeperGame,
    GATE, MIX, HOLD, ECHO,
)


# ── scoring via the real game (DRY: the game owns the formula) ──────────────

def _normalized_for(seed, cfg, episode, pred_matrix):
    """Submit a full prediction matrix to the seed/episode's game; return its
    official normalized score."""
    g = ModelkeeperGame(seed=seed, config=cfg)
    for _ in range(episode - 1):
        g.reset()
    g.step("exam")
    R = g._R
    info = {}
    for c in range(g._n_cells):
        v = pred_matrix[c // R][c % R]
        _, _, _, info = g.step(f"predict_{v}")
    return info["normalized"]


def _instance(seed, cfg, episode):
    g = ModelkeeperGame(seed=seed, config=cfg)
    for _ in range(episode - 1):
        g.reset()
    return g._machine, g._exam_inputs


# ── the players: (machine, exam, rng, cfg) -> (pred_matrix, probes_used) ─────

def player_random(machine, exam, rng, cfg):
    ranges = [readout_value_count(machine, rid) for rid in machine.readout_ids]
    pred = [[rng.randrange(ranges[r]) for r in range(len(ranges))] for _ in exam]
    return pred, rng.randint(0, 20)


def player_constant(machine, exam, rng, cfg):
    R = len(machine.readout_ids)
    pred = [[0] * R for _ in exam]
    return pred, 0


def player_single_sweep(machine, exam, rng, cfg):
    """Naive one-pass: probe baseline + each single input once from reset, then
    predict every exam step as an INSTANTANEOUS, memoryless function — using the
    Hamming-nearest swept input's response. Cannot capture HOLD/ECHO/combos."""
    m, R = machine.n_inputs, len(machine.readout_ids)
    on = machine.k - 1
    swept = []   # (input_vector, readout_row)
    sim = MachineSim(machine)
    sim.reset()
    swept.append(([0] * m, sim.tick([0] * m)))
    for i in range(m):
        sim.reset()
        ei = [0] * m
        ei[i] = on
        swept.append((ei, sim.tick(ei)))
    probes = len(swept)  # baseline + m single-input probes (resets are free)

    def nearest(v):
        best, brow = None, None
        for sv, row in swept:
            d = sum(1 for a, b in zip(sv, v) if a != b)
            if best is None or d < best:
                best, brow = d, row
        return brow

    pred = [list(nearest(v)) for v in exam]
    return pred, probes


def player_depth1_solver(machine, exam, rng, cfg):
    """An agent who only mastered the *depth-1* game: fits each readout with a single
    input-fed mechanism where one is consistent, and is left guessing (0) on the
    hidden-composition readouts it cannot explain. This is the offline, LLM-free proxy
    for "an easy mental model cannot solve hard" — its score is the headroom floor."""
    d1cfg = replace(cfg, depth=1, hidden_allowed=False, probe_budget=10 ** 9)
    solver = ReferenceSolver(d1cfg)
    m, k = machine.n_inputs, machine.k
    ops = solver._battery(m, k)
    probes = sum(1 for op in ops if op[0] == "tick")
    sim = MachineSim(machine)
    observed = []
    for op in ops:
        if op[0] == "reset":
            sim.reset()
        else:
            observed.append(sim.tick(op[1]))
    R = len(machine.readout_ids)
    cols = []
    for r in range(R):
        col = [row[r] for row in observed]
        fitted = None
        for cand in solver._candidates(m, k):
            if solver._consistent(cand, m, k, ops, col):
                fitted = cand
                break
        if fitted is None:
            cols.append([0] * len(exam))            # can't explain -> guess 0
        else:
            sm = Machine(k=k, n_inputs=m, nodes=[fitted], eval_order=[0], readout_ids=[0])
            cols.append([row[0] for row in simulate(sm, exam)])
    pred = [[cols[r][t] for r in range(R)] for t in range(len(exam))]
    return pred, min(probes, cfg.probe_budget)


def player_old_hard_solver(machine, exam, rng, cfg):
    """A player that knows the previous one-helper-per-readout hard grammar."""
    old_cfg = replace(cfg, family="hard", depth=2)
    ok, probes, fitted = HardReferenceSolver(old_cfg).solve(machine)
    if not ok or fitted is None:
        return [[0] * len(machine.readout_ids) for _ in exam], min(probes, cfg.probe_budget)
    return _predict_with_fitted_machines(fitted, exam), min(probes, cfg.probe_budget)


def player_anchor_solver(machine, exam, rng, cfg):
    """Human-style partial model: identify the reversible shared-state view only.

    It tests the expert battery, fits either visible column to the bounded
    D->S->MIX(S,input) anchor grammar, predicts that column, and guesses zero on
    the more complex coupled readout.
    """
    solver = ExpertReferenceSolver(cfg)
    ops = solver._battery(machine.n_inputs, machine.k)
    sim = MachineSim(machine)
    observed = []
    for op in ops:
        if op[0] == "reset":
            sim.reset()
        else:
            observed.append(sim.tick(op[1]))

    anchor_models = getattr(player_anchor_solver, "_catalog", None)
    if anchor_models is None:
        anchor_models = []
        seen = set()
        for cand in solver._candidate_machines():
            # In both templates, the anchor is node 2 (four-node) or node 3
            # (five-node). Extract it as a standalone chain candidate.
            anchor_id = 2 if len(cand.nodes) == 4 else 3
            nodes = [replace(cand.nodes[0], sources=list(cand.nodes[0].sources)),
                     replace(cand.nodes[1], sources=list(cand.nodes[1].sources)),
                     replace(cand.nodes[anchor_id], sources=list(cand.nodes[anchor_id].sources))]
            mini = Machine(k=machine.k, n_inputs=machine.n_inputs, nodes=nodes,
                           eval_order=_topo_order(nodes), readout_ids=[2])
            sig = tuple(row[0] for row in _run_ops(mini, ops))
            if sig not in seen:
                seen.add(sig)
                anchor_models.append((sig, mini))
        player_anchor_solver._catalog = anchor_models

    R = len(machine.readout_ids)
    pred_cols = [[0] * len(exam) for _ in range(R)]
    for r in range(R):
        col = tuple(row[r] for row in observed)
        match = next((mini for sig, mini in anchor_models if sig == col), None)
        if match is not None:
            pred_cols[r] = [row[0] for row in simulate(match, exam)]
            break
    pred = [[pred_cols[r][t] for r in range(R)] for t in range(len(exam))]
    probes = sum(1 for op in ops if op[0] == "tick")
    return pred, probes


def _run_ops(machine, ops):
    sim = MachineSim(machine)
    rows = []
    for op in ops:
        if op[0] == "reset":
            sim.reset()
        else:
            rows.append(sim.tick(op[1]))
    return rows


def player_heuristic(machine, exam, rng, cfg):
    if cfg.family == "expert":
        ok, probes, fitted = ExpertReferenceSolver(cfg).solve(machine, exam)
        if not ok or fitted is None:
            return [[0] * len(machine.readout_ids) for _ in exam], probes
        return _predict_with_fitted_expert(fitted, exam), probes
    if cfg.hidden_allowed or cfg.depth >= 2:
        solve_cfg = replace(cfg, probe_budget=cfg.certify_probe_budget) if cfg.certify_probe_budget else cfg
        ok, probes, fitted = HardReferenceSolver(solve_cfg).solve(machine)
        if not ok or fitted is None:
            R = len(machine.readout_ids)
            return [[0] * R for _ in exam], probes
        return _predict_with_fitted_machines(fitted, exam), probes
    ok, probes, fitted = ReferenceSolver(cfg).solve(machine)
    if not ok or fitted is None:
        R = len(machine.readout_ids)
        return [[0] * R for _ in exam], probes
    return _predict_with_fitted(machine, fitted, exam), probes


PLAYERS = [
    ("random", player_random),
    ("constant", player_constant),
    ("single_sweep", player_single_sweep),
    ("depth1_solver", player_depth1_solver),
    ("heuristic", player_heuristic),
]

EXPERT_PLAYERS = [
    ("random", player_random),
    ("constant", player_constant),
    ("single_sweep", player_single_sweep),
    ("depth1_solver", player_depth1_solver),
    ("old_hard", player_old_hard_solver),
    ("anchor_only", player_anchor_solver),
    ("heuristic", player_heuristic),
]


def eval_ladder(cfg, seeds, episodes_per_seed=1):
    rng = random.Random(12345)
    out = {}
    players = EXPERT_PLAYERS if cfg.family == "expert" else PLAYERS
    for name, fn in players:
        norms, probes = [], []
        for seed in seeds:
            for ep in range(1, episodes_per_seed + 1):
                machine, exam = _instance(seed, cfg, ep)
                pred, used = fn(machine, exam, rng, cfg)
                norms.append(_normalized_for(seed, cfg, ep, pred))
                probes.append(used)
        out[name] = (sum(norms) / len(norms), sum(probes) / len(probes))
    return out


# ── §4.4 state-space estimate (analytic) ────────────────────────────────────

def node_config_count(cfg):
    """Count distinct depth-1 single-node configs the generator can emit for
    m = max inputs (over-counts vs runtime but gives the right order)."""
    from itertools import combinations, product
    m, k = cfg.n_inputs_range[1], cfg.k
    idxs = list(range(m))
    subsets = [s for r in range(1, m + 1) for s in combinations(idxs, r)]
    count = 0
    # GATE: subset x sign-pattern(>=1 positive) x feasible thresholds
    for S in subsets:
        for signs in product((1, -1), repeat=len(S)):
            if not any(s > 0 for s in signs):
                continue
            mx = sum((k - 1) for s in signs if s > 0)
            mn = sum(-(k - 1) for s in signs if s < 0)
            count += max(0, mx - (mn + 1) + 1)
    # MIX: generator uses >=2 sources (or 1 if m==1)
    count += sum(1 for S in subsets if len(S) >= min(2, m))
    # HOLD: driver x cap
    count += m * len(cfg.hold_caps)
    # ECHO: source
    count += m
    return count


def estimate_state_space(cfg):
    per_node = node_config_count(cfg)
    nmin, nmax = cfg.n_nodes_range
    if cfg.hidden_allowed or cfg.depth >= 2:
        # Rough order for the hard family: each composite readout is one hidden helper
        # (HOLD m*caps + ECHO m) wired into a GATE/MIX top (~per_node configs); with up
        # to n//2 composites per machine. Lower-bound order estimate (gate is > 100).
        m = cfg.n_inputs_range[1]
        per_helper = m * len(cfg.hold_caps) + m
        machines = sum((per_helper * per_node) ** max(1, n // 2)
                       for n in range(nmin, nmax + 1))
    else:
        machines = sum(per_node ** n for n in range(nmin, nmax + 1))
    exams = (cfg.k ** cfg.n_inputs_range[1]) ** cfg.exam_len
    return per_node, machines, exams


# ── main ─────────────────────────────────────────────────────────────────────

def run_calibration(cfg, label, hard, seeds, perf_episodes=30):
    t0 = time.time()
    ladder = eval_ladder(cfg, seeds, episodes_per_seed=1)
    t_ladder = time.time() - t0

    print(f"§4.1 Baseline ladder — {label} ({len(seeds)} seeds, "
          "mean normalized / mean probes):")
    players = EXPERT_PLAYERS if cfg.family == "expert" else PLAYERS
    for name, _ in players:
        norm, pr = ladder[name]
        print(f"  {name:13s}  normalized={norm:+.3f}   probes={pr:.1f}")

    rnd = ladder["random"][0]
    const = ladder["constant"][0]
    sweep = ladder["single_sweep"][0]
    d1 = ladder["depth1_solver"][0]
    heur = ladder["heuristic"][0]
    ratio = sweep / heur if heur else float("inf")
    gap = heur - rnd
    headroom = heur - d1            # how much an "easy" (depth-1) model leaves on table

    print("\n§4.2/4.3 ordering & gaps:")
    print(f"  random≈constant < single_sweep < heuristic : "
          f"{rnd:+.3f} ≈ {const:+.3f} < {sweep:+.3f} < {heur:+.3f}")
    print(f"  floor↔ceiling gap (heur-random) = {gap:.3f}  (target ≥ 0.85)")
    print(f"  single_sweep/heuristic ratio    = {ratio:.3f}  (target ≤ 0.70)")
    if hard:
        print(f"  depth1_solver (easy model)      = {d1:+.3f}  (target ≤ 0.60)")
        print(f"  headroom (heur - depth1_solver) = {headroom:.3f}  (target ≥ 0.35)")
    if cfg.family == "expert":
        old_hard = ladder["old_hard"][0]
        anchor = ladder["anchor_only"][0]
        print(f"  old_hard solver                 = {old_hard:+.3f}  (target < 0.70)")
        print(f"  anchor-only human proxy         = {anchor:+.3f}  (target 0.45..0.80)")

    per_node, machines, exams = estimate_state_space(cfg)
    print(f"\n§4.4 state space ({label}):")
    print(f"  distinct single-node configs (m={cfg.n_inputs_range[1]}, k={cfg.k}) = {per_node}")
    print(f"  distinct machines (nodes {cfg.n_nodes_range}) ≈ {machines:,}")
    print(f"  distinct exam sequences ≈ {exams:,}")

    # §4.5 perf: seeds × perf_episodes generate+heuristic+score
    t1 = time.time()
    rng = random.Random(0)
    n = 0
    for seed in seeds:
        for ep in range(1, perf_episodes + 1):
            machine, exam = _instance(seed, cfg, ep)
            pred, _ = player_heuristic(machine, exam, rng, cfg)
            _normalized_for(seed, cfg, ep, pred)
            n += 1
    t_perf = time.time() - t1
    print(f"\n§4.5 perf: {n} generate+heuristic+score episodes in {t_perf:.1f}s "
          f"({n / t_perf:.0f}/s); {len(seeds)}-seed ladder in {t_ladder:.1f}s")

    ordering_ok = (max(rnd, const, sweep) < ladder["anchor_only"][0] < heur
                   if cfg.family == "expert" else rnd < sweep < heur)
    ordering_label = ("4.2 ordering floor trio<anchor_only<heuristic"
                      if cfg.family == "expert"
                      else "4.2 ordering random<single_sweep<heuristic")
    gates = {
        "4.1 random ≈ 0 (±0.05)": abs(rnd) <= 0.05,
        "4.1 constant < 0.3": const < 0.3,
        "4.1 heuristic ≥ 0.95": heur >= 0.95,
        ordering_label: ordering_ok,
        "4.2 floor↔ceiling gap ≥ 0.85": gap >= 0.85,
        "4.3 single_sweep/heuristic ≤ 0.70": ratio <= 0.70,
        "4.4 state space > 100": machines > 100,
        "4.5 perf ladder+sweep < 120s": (t_ladder + t_perf) < 120,
    }
    if hard:
        gates["4.6 headroom: depth1_solver ≤ 0.60"] = d1 <= 0.60
        gates["4.6 headroom: heur - depth1_solver ≥ 0.35"] = headroom >= 0.35
    if cfg.family == "expert":
        old_hard = ladder["old_hard"][0]
        anchor = ladder["anchor_only"][0]
        gates["4.7 old-hard solver < 0.70"] = old_hard < 0.70
        gates["4.7 expert-old_hard headroom ≥ 0.25"] = heur - old_hard >= 0.25
        gates["4.8 anchor-only proxy in 0.45..0.80"] = 0.45 <= anchor <= 0.80

    print(f"\n§4 GATES ({label}):")
    allok = True
    for name, ok in gates.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        allok = allok and ok
    print("RESULT:", "ALL CALIBRATE GATES GREEN" if allok else "CALIBRATION OUT OF TARGET")
    return allok


def main():
    # `python baselines.py [hard]` -> hard config; default = standard config.
    # NB: baselines.py reaches episode N by replaying N resets (the game has no seek),
    # so perf_episodes is kept small for the hard config (each hard generation is ~14ms
    # vs ~0.3ms standard); interactive per-reset latency is what actually matters.
    mode = sys.argv[1] if len(sys.argv) > 1 else "standard"
    hard = mode in ("hard", "expert")
    if mode == "expert":
        ok = run_calibration(EXPERT_CONFIG, "expert config", True, list(range(50)),
                             perf_episodes=3)
    elif hard:
        ok = run_calibration(HARD_CONFIG, "hard config", True, list(range(50)),
                             perf_episodes=3)
    else:
        ok = run_calibration(Config(), "standard config", False, list(range(50)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
