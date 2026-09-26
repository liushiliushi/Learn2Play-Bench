"""
Modelkeeper: The Console — EvolveBench game.

A black-box "clocked machine" the player probes, then must PREDICT the readouts
of an unseen exam sequence. The four mechanisms (GATE / MIX / HOLD / ECHO) are
the fixed, universal "physics" of the world; each episode wires a brand-new
machine from those mechanisms. The player improves across episodes by learning
the mechanisms + an efficient probing routine, not by memorizing one answer.

See games/modelkeeper/modelkeeper_game_design.md for the full design.

EvolveBench contract (duck-typed): __init__(seed, lang), reset()->(obs, info),
step(action)->(obs, reward, done, info), get_valid_actions(), properties
score/done/turn_count, class attr MAX_TURNS, optional get_action_label().
"""

import hashlib
import os
import pickle
import random
from dataclasses import dataclass, field, replace
from itertools import product
from typing import Optional


# ── The four mechanisms (universal, hardcoded physics) ──────────────────────

GATE = "GATE"   # threshold over signed sources; instantaneous, monotone
MIX = "MIX"     # sum mod k; instantaneous, every source-flip toggles output
HOLD = "HOLD"   # internal level, +1 when driven / -1 when not, capped; stateful
ECHO = "ECHO"   # outputs a source's value from the PREVIOUS tick; stateful


# ── Machine model ───────────────────────────────────────────────────────────

@dataclass
class Node:
    kind: str
    sources: list            # list of ("in", i) or ("node", j)
    signs: Optional[list] = None       # GATE only: σ_i ∈ {+1, -1}
    threshold: Optional[int] = None    # GATE only: θ
    cap: Optional[int] = None          # HOLD only
    visible: bool = True


@dataclass
class Machine:
    k: int
    n_inputs: int
    nodes: list                        # list[Node]
    eval_order: list                   # topological order over instantaneous deps
    readout_ids: list                  # visible node ids, in display order O1, O2, ...


def readout_value_count(machine: Machine, node_id: int) -> int:
    """Number of distinct values a node can output (for chance-level scoring)."""
    node = machine.nodes[node_id]
    if node.kind == GATE:
        return 2
    if node.kind == MIX:
        return machine.k
    if node.kind == HOLD:
        return node.cap + 1
    if node.kind == ECHO:
        src = node.sources[0]
        if src[0] == "in":
            return machine.k
        return readout_value_count(machine, src[1])
    raise ValueError(f"unknown kind {node.kind}")


def _topo_order(nodes: list) -> list:
    """Topological order over instantaneous dependencies.

    GATE/MIX read their node-sources on the current tick; HOLD reads its driver
    on the current tick. ECHO reads the PREVIOUS tick, so it adds no edge.
    """
    n = len(nodes)
    deps = {i: set() for i in range(n)}
    for i, node in enumerate(nodes):
        if node.kind in (GATE, MIX):
            for s in node.sources:
                if s[0] == "node":
                    deps[i].add(s[1])
        elif node.kind == HOLD:
            s = node.sources[0]
            if s[0] == "node":
                deps[i].add(s[1])
        # ECHO: no instantaneous dependency
    order, resolved = [], set()
    while len(order) < n:
        progressed = False
        for i in range(n):
            if i in resolved:
                continue
            if deps[i] <= resolved:
                order.append(i)
                resolved.add(i)
                progressed = True
        if not progressed:
            raise ValueError("instantaneous loop in machine")
    return order


class MachineSim:
    """Live simulator: reset() to zero state, tick(inputs) -> readout row.

    val(s, t<0) = 0 (before start / just after reset) is encoded by prev_* = None.
    """

    def __init__(self, machine: Machine):
        self.m = machine
        self.reset()

    def reset(self):
        self.levels = {i: 0 for i, nd in enumerate(self.m.nodes) if nd.kind == HOLD}
        self.prev_inputs = None
        self.prev_nodes = None

    def _val_cur(self, src, inputs, cur):
        if src[0] == "in":
            return inputs[src[1]]
        return cur[src[1]]   # node already evaluated (topo order guarantees)

    def _val_prev(self, src):
        if src[0] == "in":
            return 0 if self.prev_inputs is None else self.prev_inputs[src[1]]
        return 0 if self.prev_nodes is None else self.prev_nodes[src[1]]

    def _eval(self, nid, inputs, cur):
        node = self.m.nodes[nid]
        if node.kind == GATE:
            total = sum(sg * self._val_cur(s, inputs, cur)
                        for s, sg in zip(node.sources, node.signs))
            return 1 if total >= node.threshold else 0
        if node.kind == MIX:
            return sum(self._val_cur(s, inputs, cur) for s in node.sources) % self.m.k
        if node.kind == HOLD:
            drive = self._val_cur(node.sources[0], inputs, cur)
            lvl = self.levels[nid]
            lvl = min(lvl + 1, node.cap) if drive >= 1 else max(lvl - 1, 0)
            self.levels[nid] = lvl
            return lvl
        if node.kind == ECHO:
            return self._val_prev(node.sources[0])
        raise ValueError(f"unknown kind {node.kind}")

    def tick(self, inputs) -> list:
        cur = {}
        for nid in self.m.eval_order:
            cur[nid] = self._eval(nid, inputs, cur)
        self.prev_inputs = list(inputs)
        self.prev_nodes = dict(cur)
        return [cur[rid] for rid in self.m.readout_ids]


def simulate(machine: Machine, input_seq) -> list:
    """Pure batch sim from a fresh reset; one readout row per tick."""
    sim = MachineSim(machine)
    return [sim.tick(inp) for inp in input_seq]


# ── Difficulty dials ────────────────────────────────────────────────────────

@dataclass
class Config:
    k: int = 2
    n_inputs_range: tuple = (2, 2)
    n_nodes_range: tuple = (3, 4)
    depth: int = 1                 # 1 = all nodes fed by inputs, fully visible
    hidden_allowed: bool = False
    probe_budget: int = 20
    certify_probe_budget: Optional[int] = None
    exam_len: int = 8
    hold_caps: tuple = (2, 3)
    allowed_kinds: tuple = (GATE, MIX, HOLD, ECHO)
    family: str = "standard"

    def answer_max(self) -> int:
        """Upper bound (exclusive) on any readout value reachable under this config.

        Constant across all instances of the config (GATE→2, MIX→k, HOLD→cap+1,
        ECHO→inherits), so the exam answer menu never reveals an instance's
        mechanisms. Exam answers in 0..answer_max-1; out-of-range scores as wrong.
        """
        return max(2, self.k, max(self.hold_caps) + 1)


# Standard play uses Config(); the hard variant uses HARD_CONFIG: depth-2 with a
# hidden stateful node (HOLD/ECHO) shadowing a visible instantaneous readout
# (GATE/MIX). k=3, 3 inputs, 4-6 nodes. The player budget is the 32-probe
# reference battery: enough to fully identify a served instance with the intended
# diagnostic routine, but still far below exhaustive black-box mapping. exam_len is
# long enough that a partial mental model diverges cell-by-cell. answer_max()==4
# here, so the exam menu (predict_0..3) is a config-level constant that leaks no
# mechanism.
HARD_CONFIG = Config(
    family="hard",
    k=3,
    n_inputs_range=(3, 3),
    n_nodes_range=(4, 6),
    depth=2,
    hidden_allowed=True,
    probe_budget=32,
    exam_len=10,
    hold_caps=(2, 3),
    allowed_kinds=(GATE, MIX, HOLD, ECHO),
)


# Expert keeps the public interaction surface compact for human play (three
# inputs, two readouts, ten exam ticks), but uses a controlled depth-3 grammar:
# a two-input instantaneous driver feeds a shared stateful helper, which is seen
# through two different readouts.  Some instances add one direct stateful helper
# to the non-anchor readout.  Forty probes are deliberately retained so the
# difficulty increase comes from structure rather than a tighter action budget.
EXPERT_CONFIG = Config(
    family="expert",
    k=3,
    n_inputs_range=(3, 3),
    n_nodes_range=(4, 5),
    depth=3,
    hidden_allowed=True,
    probe_budget=40,
    exam_len=10,
    hold_caps=(2, 3),
    allowed_kinds=(GATE, MIX, HOLD, ECHO),
)


# ── Reference solver (powers the solvability/certification guardrail) ────────

class ReferenceSolver:
    """Mechanizes the intended probing routine for the depth-1 fully-visible game.

    Runs a fixed probe battery (single-input ramp, single-input pulse, full input
    combination sweep), then for each readout searches a small space of candidate
    single-node mechanisms and keeps any one consistent with the whole transcript.
    Full combo coverage + ramp + pulse makes every depth-1 node identifiable up to
    prediction-equivalence, so a consistent candidate predicts the exam exactly.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.ramp_len = max(cfg.hold_caps) + 1

    def _battery(self, m: int, k: int):
        """Return ops list of ("reset",) / ("tick", inputs)."""
        on = k - 1
        zeros = [0] * m
        ops = []
        # single-input ramp (reveals HOLD + driver + cap)
        for i in range(m):
            ops.append(("reset",))
            ei = [0] * m
            ei[i] = on
            for _ in range(self.ramp_len):
                ops.append(("tick", list(ei)))
        # single-input pulse (reveals ECHO + one-tick lag)
        for i in range(m):
            ei = [0] * m
            ei[i] = on
            ops.append(("reset",))
            ops.append(("tick", list(ei)))
            ops.append(("tick", list(zeros)))
            ops.append(("tick", list(zeros)))
        # full input-combination sweep (reveals GATE vs MIX, θ, signs)
        ops.append(("reset",))
        for combo in product(range(k), repeat=m):
            ops.append(("tick", list(combo)))
        return ops

    def _candidates(self, m: int, k: int):
        """Yield candidate single-node mechanisms fed by the m inputs."""
        idxs = list(range(m))
        subsets = []
        for r in range(1, m + 1):
            from itertools import combinations
            subsets.extend(combinations(idxs, r))
        # MIX first (cheap exact), then ECHO, HOLD, GATE
        for S in subsets:
            yield Node(MIX, [("in", i) for i in S])
        for i in idxs:
            yield Node(ECHO, [("in", i)])
        for i in idxs:
            for cap in range(1, max(self.cfg.hold_caps) + 1):
                yield Node(HOLD, [("in", i)], cap=cap)
        for S in subsets:
            for signs in product((1, -1), repeat=len(S)):
                max_total = sum((k - 1) for sg in signs if sg > 0)
                min_total = sum(-(k - 1) for sg in signs if sg < 0)
                for theta in range(min_total + 1, max_total + 1):
                    yield Node(GATE, [("in", i) for i in S],
                               signs=list(signs), threshold=theta)

    def _single_machine(self, node: Node, m: int, k: int) -> Machine:
        return Machine(k=k, n_inputs=m, nodes=[node], eval_order=[0], readout_ids=[0])

    def _consistent(self, node, m, k, ops, observed_col) -> bool:
        sim = MachineSim(self._single_machine(node, m, k))
        idx = 0
        for op in ops:
            if op[0] == "reset":
                sim.reset()
            else:
                if sim.tick(op[1])[0] != observed_col[idx]:
                    return False
                idx += 1
        return True

    def solve(self, machine: Machine):
        """Return (ok, probes_used, predicted_rows)."""
        m, k = machine.n_inputs, machine.k
        ops = self._battery(m, k)
        probes_used = sum(1 for op in ops if op[0] == "tick")
        if probes_used > self.cfg.probe_budget:
            return False, probes_used, None

        # run the real machine through the battery
        sim = MachineSim(machine)
        observed = []
        for op in ops:
            if op[0] == "reset":
                sim.reset()
            else:
                observed.append(sim.tick(op[1]))

        # fit each readout independently
        R = len(machine.readout_ids)
        fitted = [None] * R
        for r in range(R):
            col = [row[r] for row in observed]
            for cand in self._candidates(m, k):
                if self._consistent(cand, m, k, ops, col):
                    fitted[r] = cand
                    break
            if fitted[r] is None:
                return False, probes_used, None

        # predict the exam from the fitted model (exam stored on machine by caller)
        return True, probes_used, fitted


# ── Hard reference solver (depth-2: hidden stateful helper → visible readout) ─

class HardReferenceSolver:
    """Reference solver for the depth-2 hard variant.

    Each visible readout is either a plain depth-1 single-node-over-inputs mechanism
    OR a GATE/MIX over (a subset of inputs + ONE hidden stateful helper, HOLD/ECHO).
    It runs a CURATED battery (per-input ramps long enough to expose a HOLD cap,
    per-input pulses for ECHO's one-tick lag, and a small combo set that separates
    the instantaneous mechanisms), then fits EACH visible readout independently:
    first try a plain single-node candidate; on failure escalate to a composite
    (top mechanism over inputs + one stateful helper). Per-readout independence is
    sound because the generator gives each helper to exactly one readout. The battery
    is small enough to fit a tight budget but too small for exhaustive black-box
    mapping. Returns per-readout mini-Machines, so prediction reuses simulate()."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        # +2 so a cap-c HOLD shows its plateau AND one extra step (no cap ambiguity).
        self.ramp_len = max(cfg.hold_caps) + 2
        self.depth1 = ReferenceSolver(cfg)   # reuse depth-1 candidates/consistency

    # — curated battery (NOT the full k^m sweep) —
    def _combos(self, m, k):
        on = k - 1
        combos = [[0] * m, [on] * m]                 # baseline + saturate-all
        for i in range(m):                           # each input pair at max
            for j in range(i + 1, m):
                v = [0] * m
                v[i] = on
                v[j] = on
                combos.append(v)
        if k > 2:                                     # graded combos separate MIX/GATE
            combos.append([1] * m)
            for shift in range(min(m, 2)):
                combos.append([(p + shift) % k for p in range(m)])
        seen, uniq = set(), []
        for v in combos:
            t = tuple(v)
            if t not in seen:
                seen.add(t)
                uniq.append(v)
        return uniq

    def _battery(self, m, k):
        on = k - 1
        zeros = [0] * m
        ops = []
        for i in range(m):                           # ramps: HOLD + cap
            ops.append(("reset",))
            ei = [0] * m
            ei[i] = on
            for _ in range(self.ramp_len):
                ops.append(("tick", list(ei)))
        for i in range(m):                           # pulses: ECHO + one-tick lag
            ei = [0] * m
            ei[i] = on
            ops.append(("reset",))
            ops.append(("tick", list(ei)))
            ops.append(("tick", list(zeros)))
            ops.append(("tick", list(zeros)))
        ops.append(("reset",))                       # curated combos: GATE vs MIX
        for combo in self._combos(m, k):
            ops.append(("tick", list(combo)))
        return ops

    # — candidate spaces for a composite readout —
    def _helper_candidates(self, m, k):
        """Stateful helpers only (HOLD/ECHO): a depth-1 GATE/MIX is memoryless, so a
        stateful helper into an instantaneous readout is non-collapsible to depth-1."""
        cands = [Node(ECHO, [("in", i)]) for i in range(m)]
        for i in range(m):
            for cap in range(1, max(self.cfg.hold_caps) + 1):
                cands.append(Node(HOLD, [("in", i)], cap=cap))
        return cands

    def _top_candidates(self, m, k, helper_max):
        """Top GATE/MIX over (a subset of inputs) + the helper as one extra source."""
        from itertools import combinations
        idxs = list(range(m))
        subsets = [()]
        for r in range(1, m + 1):
            subsets.extend(combinations(idxs, r))
        for S in subsets:
            yield ("MIX", tuple(S))
        for S in subsets:
            src_max = [k - 1] * len(S) + [helper_max]
            for signs in product((1, -1), repeat=len(S) + 1):
                if not any(s > 0 for s in signs):
                    continue
                max_total = sum(mx for mx, sg in zip(src_max, signs) if sg > 0)
                min_total = sum(-mx for mx, sg in zip(src_max, signs) if sg < 0)
                for theta in range(min_total + 1, max_total + 1):
                    yield ("GATE", tuple(S), tuple(signs), theta)

    def _sim_col(self, node, m, k, ops):
        """Output column of a single hypothetical helper node over the battery."""
        sim = MachineSim(self.depth1._single_machine(node, m, k))
        out = []
        for op in ops:
            if op[0] == "reset":
                sim.reset()
            else:
                out.append(sim.tick(op[1])[0])
        return out

    def _top_consistent(self, top, tick_inputs, hcol, col, k):
        if top[0] == "MIX":
            S = top[1]
            for t, inp in enumerate(tick_inputs):
                if (sum(inp[i] for i in S) + hcol[t]) % k != col[t]:
                    return False
            return True
        _, S, signs, theta = top
        for t, inp in enumerate(tick_inputs):
            vals = [inp[i] for i in S] + [hcol[t]]
            total = sum(sg * v for sg, v in zip(signs, vals))
            if (1 if total >= theta else 0) != col[t]:
                return False
        return True

    def _composite_machine(self, helper, top, m, k):
        h = Node(helper.kind, list(helper.sources), signs=helper.signs,
                 threshold=helper.threshold, cap=helper.cap, visible=False)
        if top[0] == "MIX":
            S = top[1]
            tn = Node(MIX, [("in", i) for i in S] + [("node", 0)])
        else:
            _, S, signs, theta = top
            tn = Node(GATE, [("in", i) for i in S] + [("node", 0)],
                      signs=list(signs), threshold=theta)
        nodes = [h, tn]
        return Machine(k=k, n_inputs=m, nodes=nodes,
                       eval_order=_topo_order(nodes), readout_ids=[1])

    def _fit_composite(self, m, k, ops, tick_inputs, col):
        for helper in self._helper_candidates(m, k):
            hcol = self._sim_col(helper, m, k, ops)        # memoize per helper
            helper_max = helper.cap if helper.kind == HOLD else (k - 1)
            for top in self._top_candidates(m, k, helper_max):
                if self._top_consistent(top, tick_inputs, hcol, col, k):
                    return self._composite_machine(helper, top, m, k)
        return None

    def solve(self, machine: Machine):
        """Return (ok, probes_used, fitted) where fitted is a list of per-readout
        mini-Machines (each single-readout) reproducing the observed column."""
        m, k = machine.n_inputs, machine.k
        ops = self._battery(m, k)
        probes_used = sum(1 for op in ops if op[0] == "tick")
        if probes_used > self.cfg.probe_budget:
            return False, probes_used, None
        sim = MachineSim(machine)
        observed = []
        for op in ops:
            if op[0] == "reset":
                sim.reset()
            else:
                observed.append(sim.tick(op[1]))
        tick_inputs = [op[1] for op in ops if op[0] == "tick"]
        R = len(machine.readout_ids)
        fitted = [None] * R
        for r in range(R):
            col = [row[r] for row in observed]
            node = None
            for cand in self.depth1._candidates(m, k):     # stage 1: plain depth-1
                if self.depth1._consistent(cand, m, k, ops, col):
                    node = cand
                    break
            if node is not None:
                fitted[r] = self.depth1._single_machine(node, m, k)
                continue
            comp = self._fit_composite(m, k, ops, tick_inputs, col)  # stage 2
            if comp is None:
                return False, probes_used, None
            fitted[r] = comp
        return True, probes_used, fitted


# ── Expert reference solver (shared latent state + controlled depth-3 chain) ─

class ExpertReferenceSolver:
    """Black-box reference solver for ``modelkeeper_expert``.

    The expert family is intentionally structured rather than an arbitrary DAG.
    A two-input instantaneous driver feeds one shared stateful helper.  One visible
    readout is a reversible MIX view of that helper; the other is a GATE/MIX view
    and may also consume one direct stateful helper.  The solver enumerates that
    public *hypothesis family*, fits the two readouts jointly, and only succeeds
    when every transcript-consistent candidate predicts the supplied exam alike.
    It never reads the real machine's nodes or wiring.
    """

    _catalog_cache = {}

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def _battery(self, m, k):
        """Forty informative ticks, grouped into reset-delimited experiments."""
        if m != 3 or k != 3:
            raise ValueError("expert solver currently requires exactly 3 ternary inputs")
        zeros = [0] * m
        vectors = []
        for i in range(m):
            v = [0] * m
            v[i] = k - 1
            vectors.append(v)
        for i in range(m):
            for j in range(i + 1, m):
                v = [0] * m
                v[i] = v[j] = k - 1
                vectors.append(v)

        ops = []
        for v in vectors:
            ops.append(("reset",))
            for _ in range(4):
                ops.append(("tick", list(v)))
            ops.append(("tick", list(zeros)))
            ops.append(("tick", list(zeros)))

        # Graded, clean-state observations disambiguate ternary MIX drivers from
        # monotone GATE drivers without extending the player-visible budget.
        for v in ([1, 1, 0], [1, 0, 1], [0, 1, 1], [0, 1, 2]):
            ops.append(("reset",))
            ops.append(("tick", list(v)))
        return ops

    @staticmethod
    def _signature(machine, ops):
        sim = MachineSim(machine)
        out = []
        for op in ops:
            if op[0] == "reset":
                sim.reset()
            else:
                out.extend(sim.tick(op[1]))
        return tuple(out)

    @staticmethod
    def _positive_top(kind, sources, threshold=None):
        if kind == MIX:
            return Node(MIX, list(sources))
        return Node(GATE, list(sources), signs=[1] * len(sources),
                    threshold=threshold)

    def _candidate_machines(self):
        """Enumerate the bounded expert grammar (about twelve thousand models)."""
        from itertools import combinations

        m, k = 3, 3
        for pair in combinations(range(m), 2):
            drivers = [Node(MIX, [("in", i) for i in pair])]
            drivers += [Node(GATE, [("in", i) for i in pair], signs=[1, 1],
                             threshold=theta)
                        for theta in range(1, 2 * (k - 1) + 1)]
            for driver in drivers:
                shared_states = [Node(ECHO, [("node", 0)], visible=False),
                                 Node(HOLD, [("node", 0)], cap=2, visible=False)]
                for shared in shared_states:
                    for anchor_input in range(m):
                        # Template A (60% at generation): shared depth-3 chain only.
                        for coupled_input in range(m):
                            for top_kind in (MIX, GATE):
                                thetas = [None] if top_kind == MIX else range(1, 5)
                                for theta in thetas:
                                    nodes = [replace(driver, visible=False), shared,
                                             Node(MIX, [("node", 1),
                                                       ("in", anchor_input)]),
                                             self._positive_top(
                                                 top_kind,
                                                 [("node", 1), ("in", coupled_input)],
                                                 theta)]
                                    for order in ([2, 3], [3, 2]):
                                        yield Machine(k=k, n_inputs=m, nodes=nodes,
                                                      eval_order=_topo_order(nodes),
                                                      readout_ids=list(order))

                        # Template B (~40% of certified instances): add one direct state helper
                        # to the coupled readout.  The anchor remains a clean second
                        # view of the shared latent state for human triangulation.
                        direct_helpers = []
                        for h_input in range(m):
                            direct_helpers.append(
                                Node(ECHO, [("in", h_input)], visible=False))
                            for cap in self.cfg.hold_caps:
                                direct_helpers.append(
                                    Node(HOLD, [("in", h_input)], cap=cap,
                                         visible=False))
                        for helper in direct_helpers:
                            helper_max = (k - 1 if helper.kind == ECHO else helper.cap)
                            for top_kind in (MIX, GATE):
                                thetas = ([None] if top_kind == MIX
                                          else range(1, 2 + helper_max + 1))
                                for theta in thetas:
                                    nodes = [replace(driver, visible=False), shared,
                                             helper,
                                             Node(MIX, [("node", 1),
                                                       ("in", anchor_input)]),
                                             self._positive_top(
                                                 top_kind,
                                                 [("node", 1), ("node", 2)],
                                                 theta)]
                                    for order in ([3, 4], [4, 3]):
                                        yield Machine(k=k, n_inputs=m, nodes=nodes,
                                                      eval_order=_topo_order(nodes),
                                                      readout_ids=list(order))

    def _catalog(self):
        key = (self.cfg.k, self.cfg.n_inputs_range, self.cfg.hold_caps)
        cached = self._catalog_cache.get(key)
        if cached is not None:
            return cached
        ops = self._battery(3, 3)
        by_signature = {}
        for machine in self._candidate_machines():
            sig = self._signature(machine, ops)
            by_signature.setdefault(sig, []).append(machine)
        self._catalog_cache[key] = by_signature
        return by_signature

    def solve(self, machine: Machine, exam=None):
        """Return a transcript-consistent expert model.

        When ``exam`` is provided, success additionally requires prediction
        consensus across every candidate consistent with the forty black-box
        observations.  Generation always uses this stronger form.
        """
        ops = self._battery(machine.n_inputs, machine.k)
        probes_used = sum(1 for op in ops if op[0] == "tick")
        if probes_used > self.cfg.probe_budget:
            return False, probes_used, None
        sig = self._signature(machine, ops)
        candidates = self._catalog().get(sig, [])
        if not candidates:
            return False, probes_used, None
        if exam is not None:
            expected = simulate(candidates[0], exam)
            if any(simulate(cand, exam) != expected for cand in candidates[1:]):
                return False, probes_used, None
        return True, probes_used, candidates[0]


# ── Instance generator ───────────────────────────────────────────────────────

class _Generator:
    def __init__(self, cfg: Config, rng: random.Random):
        self.cfg = cfg
        self.rng = rng

    def _build_node(self, kind, m):
        r = self.rng
        cand = list(range(m))   # depth-1: sources are inputs only
        if kind == MIX:
            n = r.randint(min(2, m), m) if m >= 2 else 1
            S = r.sample(cand, n)
            return Node(MIX, [("in", i) for i in S])
        if kind == HOLD:
            i = r.choice(cand)
            return Node(HOLD, [("in", i)], cap=r.choice(self.cfg.hold_caps))
        if kind == ECHO:
            i = r.choice(cand)
            return Node(ECHO, [("in", i)])
        if kind == GATE:
            n = r.randint(1, m)
            S = r.sample(cand, n)
            # at least one positive sign so a meaningful threshold exists
            while True:
                signs = [1 if r.random() < 0.75 else -1 for _ in S]
                if any(sg > 0 for sg in signs):
                    break
            k = self.cfg.k
            max_total = sum((k - 1) for sg in signs if sg > 0)
            min_total = sum(-(k - 1) for sg in signs if sg < 0)
            lo, hi = min_total + 1, max_total
            theta = r.randint(lo, hi)
            return Node(GATE, [("in", i) for i in S], signs=signs, threshold=theta)
        raise ValueError(kind)

    def _build_composite(self, kind, m, helper_id, helper_max):
        """A visible GATE/MIX readout over (a subset of inputs) + one hidden helper."""
        r = self.rng
        k = self.cfg.k
        n_in = r.randint(0, m)
        inputs = sorted(r.sample(range(m), n_in)) if n_in else []
        srcs = [("in", i) for i in inputs] + [("node", helper_id)]
        if kind == MIX:
            return Node(MIX, srcs)
        src_max = [k - 1] * len(inputs) + [helper_max]
        while True:
            signs = [1 if r.random() < 0.75 else -1 for _ in srcs]
            if any(s > 0 for s in signs):
                break
        max_total = sum(mx for mx, sg in zip(src_max, signs) if sg > 0)
        min_total = sum(-mx for mx, sg in zip(src_max, signs) if sg < 0)
        lo, hi = min_total + 1, max_total
        theta = max_total if lo > hi else r.randint(lo, hi)
        return Node(GATE, srcs, signs=signs, threshold=theta)

    def _generate_hard(self):
        """Depth-2: each visible readout is a GATE/MIX over (a subset of inputs) + ONE
        dedicated hidden HOLD/ECHO helper (no sharing), with at most one plain depth-1
        readout. Composite (hidden-dependent) columns dominate the exam so an "easy"
        (depth-1) mental model cannot score well. Helpers come first by index, so wiring
        is feed-forward (no instantaneous cycle). Node count n = H + V ∈ {4,5,6}."""
        r = self.rng
        m = r.randint(*self.cfg.n_inputs_range)
        V = r.randint(2, 3)                       # visible readouts (exam columns)
        c = 2 if V == 2 else r.choice([2, 3])    # composites; V==3 -> n=5 (1 pure) or 6
        H = c                                     # one dedicated helper per composite
        nodes = []
        helper_ids = []
        for _ in range(H):
            nd = self._build_node(r.choice([HOLD, ECHO]), m)
            nd.visible = False
            helper_ids.append(len(nodes))
            nodes.append(nd)
        specs = [("composite", helper_ids[i]) for i in range(c)]
        specs += [("pure",) for _ in range(V - c)]
        r.shuffle(specs)
        for spec in specs:
            if spec[0] == "composite":
                helper = nodes[spec[1]]
                helper_max = helper.cap if helper.kind == HOLD else (self.cfg.k - 1)
                nd = self._build_composite(r.choice([GATE, MIX]), m, spec[1], helper_max)
            else:
                nd = self._build_node(r.choice(self.cfg.allowed_kinds), m)
            nd.visible = True
            nodes.append(nd)
        machine = Machine(k=self.cfg.k, n_inputs=m, nodes=nodes,
                          eval_order=_topo_order(nodes),
                          readout_ids=[i for i, nd in enumerate(nodes) if nd.visible])
        exam = [[r.randint(0, self.cfg.k - 1) for _ in range(m)]
                for _ in range(self.cfg.exam_len)]
        return machine, exam

    def _generate_expert(self, force_extra=None):
        """Generate one controlled expert-family candidate.

        The shared state has a ternary range (ECHO or cap-2 HOLD), making the MIX
        anchor reversible.  The anchor's display position is randomized, so the
        player must discover which readout provides the cleaner latent-state view.
        """
        r = self.rng
        m, k = 3, 3
        pair = sorted(r.sample(range(m), 2))
        if r.random() < 0.5:
            driver = Node(MIX, [("in", i) for i in pair], visible=False)
        else:
            driver = Node(GATE, [("in", i) for i in pair], signs=[1, 1],
                          threshold=r.randint(1, 2 * (k - 1)), visible=False)
        if r.random() < 0.5:
            shared = Node(ECHO, [("node", 0)], visible=False)
        else:
            shared = Node(HOLD, [("node", 0)], cap=2, visible=False)

        anchor_input = r.randrange(m)
        anchor = Node(MIX, [("node", 1), ("in", anchor_input)])
        # Certification rejects the two-state template slightly more often; a
        # 47% proposal rate yields about 40% among served instances.
        extra = (r.random() < 0.47) if force_extra is None else bool(force_extra)
        nodes = [driver, shared]
        if extra:
            h_input = r.randrange(m)
            if r.random() < 0.5:
                helper = Node(ECHO, [("in", h_input)], visible=False)
                helper_max = k - 1
            else:
                cap = r.choice(self.cfg.hold_caps)
                helper = Node(HOLD, [("in", h_input)], cap=cap, visible=False)
                helper_max = cap
            nodes.append(helper)
            anchor_id = len(nodes)
            nodes.append(anchor)
            sources = [("node", 1), ("node", 2)]
            if r.random() < 0.5:
                coupled = Node(MIX, sources)
            else:
                coupled = Node(GATE, sources, signs=[1, 1],
                               threshold=r.randint(1, 2 + helper_max))
        else:
            anchor_id = len(nodes)
            nodes.append(anchor)
            coupled_input = r.randrange(m)
            sources = [("node", 1), ("in", coupled_input)]
            if r.random() < 0.5:
                coupled = Node(MIX, sources)
            else:
                coupled = Node(GATE, sources, signs=[1, 1],
                               threshold=r.randint(1, 4))
        coupled_id = len(nodes)
        nodes.append(coupled)
        readouts = [anchor_id, coupled_id]
        r.shuffle(readouts)
        machine = Machine(k=k, n_inputs=m, nodes=nodes,
                          eval_order=_topo_order(nodes), readout_ids=readouts)
        exam = [[r.randint(0, k - 1) for _ in range(m)]
                for _ in range(self.cfg.exam_len)]
        return machine, exam

    def generate_once(self):
        if self.cfg.family == "expert":
            return self._generate_expert()
        if self.cfg.depth >= 2 or self.cfg.hidden_allowed:
            return self._generate_hard()
        r = self.rng
        m = r.randint(*self.cfg.n_inputs_range)
        n = r.randint(*self.cfg.n_nodes_range)
        nodes = [self._build_node(r.choice(self.cfg.allowed_kinds), m) for _ in range(n)]
        machine = Machine(k=self.cfg.k, n_inputs=m, nodes=nodes,
                          eval_order=_topo_order(nodes),
                          readout_ids=list(range(n)))  # depth-1: all visible
        exam = [[r.randint(0, self.cfg.k - 1) for _ in range(m)]
                for _ in range(self.cfg.exam_len)]
        return machine, exam


# The expert family certifies each instance with a full rejection-sampling
# search (ExpertReferenceSolver over many candidates), ~0.5–0.7s per build. That
# search is generation-time work and is fully determined by (cfg, rng seed): the
# same seed always yields the same (machine, exam, probes). play.py rebuilds the
# game from scratch on every stateless-replay spawn, so without a cache the study
# server pays that search on EVERY UI step. Memoize the certified result on disk,
# keyed by cfg + the rng's initial state, so the search runs once per seed and
# every later spawn loads it in ~1ms. Behaviour is byte-identical to regenerating
# (deterministic); bump _GEN_CACHE_VERSION whenever the generator/solver changes
# so an old cache can never serve a stale instance.
_GEN_CACHE_VERSION = 1
_GEN_CACHE_DIR = os.path.join(os.path.dirname(__file__), "_gen_cache")


def _gen_cache_key(cfg: Config, rng: random.Random) -> str:
    payload = repr((_GEN_CACHE_VERSION, repr(cfg), rng.getstate()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _gen_cache_load(key: str):
    path = os.path.join(_GEN_CACHE_DIR, key + ".pkl")
    try:
        with open(path, "rb") as fh:
            return pickle.load(fh)
    except Exception:
        return None  # missing or unreadable → regenerate


def _gen_cache_store(key: str, value) -> None:
    try:
        os.makedirs(_GEN_CACHE_DIR, exist_ok=True)
        path = os.path.join(_GEN_CACHE_DIR, key + ".pkl")
        tmp = path + f".{os.getpid()}.tmp"
        with open(tmp, "wb") as fh:
            pickle.dump(value, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)  # atomic: concurrent spawns can't read a half file
    except Exception:
        pass  # cache is a pure optimization; never fail generation over it


def generate_instance(cfg: Config, rng: random.Random, max_attempts: int = 400):
    """Generate a machine + exam satisfying both guardrails (Section 9)."""
    if cfg.family == "expert":
        # Key must be computed BEFORE the search consumes rng (the search draws
        # from it); the caller discards rng right after, so not advancing it on a
        # cache hit is safe.
        key = _gen_cache_key(cfg, rng)
        cached = _gen_cache_load(key)
        if cached is not None:
            return cached
        result = _generate_instance_expert(cfg, rng, max_attempts)
        _gen_cache_store(key, result)
        return result
    if cfg.hidden_allowed or cfg.depth >= 2:
        return _generate_instance_hard(cfg, rng, max_attempts)
    solver = ReferenceSolver(cfg)
    last = None
    for _ in range(max_attempts):
        machine, exam = _Generator(cfg, rng).generate_once()
        last = (machine, exam)
        truth = simulate(machine, exam)
        # non-trivial: at least one readout column must vary
        if not any(len({row[c] for row in truth}) > 1 for c in range(len(machine.readout_ids))):
            continue
        # solvable within the player-facing budget
        ok, probes_used, fitted = solver.solve(machine)
        if not ok:
            continue
        predicted = _predict_with_fitted(machine, fitted, exam)
        if predicted == truth:
            return machine, exam, probes_used
    # fallback (rare): return last attempt
    machine, exam = last
    return machine, exam, cfg.probe_budget


def _predict_with_fitted(machine: Machine, fitted: list, exam: list) -> list:
    """Predict exam rows from per-readout fitted single-node candidates."""
    m, k = machine.n_inputs, machine.k
    cols = []
    for cand in fitted:
        sm = Machine(k=k, n_inputs=m, nodes=[cand], eval_order=[0], readout_ids=[0])
        cols.append([row[0] for row in simulate(sm, exam)])
    return [[cols[r][t] for r in range(len(fitted))] for t in range(len(exam))]


def _predict_with_fitted_machines(fitted: list, exam: list) -> list:
    """Predict exam rows from per-readout fitted mini-Machines (hard solver)."""
    cols = [[row[0] for row in simulate(mm, exam)] for mm in fitted]
    R = len(fitted)
    return [[cols[r][t] for r in range(R)] for t in range(len(exam))]


def _predict_with_fitted_expert(fitted: Machine, exam: list) -> list:
    """Predict an expert exam with the jointly fitted two-readout machine."""
    return simulate(fitted, exam)


def _without_source(machine: Machine, readout_id: int, source) -> Machine:
    """Return a copy with one source removed from a visible instantaneous node."""
    nodes = []
    for nid, node in enumerate(machine.nodes):
        if nid != readout_id:
            nodes.append(replace(node, sources=list(node.sources),
                                 signs=None if node.signs is None else list(node.signs)))
            continue
        kept = [i for i, src in enumerate(node.sources) if src != source]
        sources = [node.sources[i] for i in kept]
        signs = None if node.signs is None else [node.signs[i] for i in kept]
        nodes.append(replace(node, sources=sources, signs=signs))
    return Machine(k=machine.k, n_inputs=machine.n_inputs, nodes=nodes,
                   eval_order=_topo_order(nodes), readout_ids=list(machine.readout_ids))


def _expert_dependencies_are_load_bearing(machine: Machine, exam: list) -> bool:
    """Require the shared chain (and optional direct helper) to matter in the exam."""
    truth = simulate(machine, exam)
    shared_src = ("node", 1)
    for rid in machine.readout_ids:
        if shared_src not in machine.nodes[rid].sources:
            return False
        ablated = simulate(_without_source(machine, rid, shared_src), exam)
        col = machine.readout_ids.index(rid)
        if sum(ablated[t][col] != truth[t][col] for t in range(len(exam))) < 2:
            return False

    # In the five-node template, node 2 is the optional direct state helper and
    # must change the coupled readout on at least two exam cells.
    if len(machine.nodes) == 5:
        helper_src = ("node", 2)
        coupled = next((rid for rid in machine.readout_ids
                        if helper_src in machine.nodes[rid].sources), None)
        if coupled is None:
            return False
        ablated = simulate(_without_source(machine, coupled, helper_src), exam)
        col = machine.readout_ids.index(coupled)
        if sum(ablated[t][col] != truth[t][col] for t in range(len(exam))) < 2:
            return False
    return True


def _generate_instance_expert(cfg: Config, rng: random.Random, max_attempts: int):
    """Generate only certified, load-bearing expert instances.

    Unlike the legacy hard fallback, this path never degrades to an easier family.
    A compact curated expert template is used only if random candidates exhaust the
    normal attempt budget.
    """
    solver = ExpertReferenceSolver(cfg)
    old_solver = HardReferenceSolver(replace(cfg, family="hard", depth=2))
    gen = _Generator(cfg, rng)

    def acceptable(machine, exam):
        truth = simulate(machine, exam)
        if len(machine.readout_ids) != 2:
            return None
        if any(len({row[c] for row in truth}) < 2 for c in range(2)):
            return None
        if not _expert_dependencies_are_load_bearing(machine, exam):
            return None
        # The new family must not collapse back to the old one-helper-per-readout
        # hypothesis class on this exam.
        old_ok, _, old_fit = old_solver.solve(machine)
        if old_ok and _predict_with_fitted_machines(old_fit, exam) == truth:
            return None
        ok, probes, fitted = solver.solve(machine, exam)
        if ok and _predict_with_fitted_expert(fitted, exam) == truth:
            return probes
        return None

    for _ in range(max_attempts):
        machine, exam = gen._generate_expert()
        probes = acceptable(machine, exam)
        if probes is not None:
            return machine, exam, probes

    # Curated expert fallback: input roles are permuted and exams are retried, but
    # the topology remains the five-node expert grammar (never hard/depth-1).
    perm = list(range(3))
    rng.shuffle(perm)
    driver = Node(MIX, [("in", perm[0]), ("in", perm[1])], visible=False)
    shared = Node(ECHO, [("node", 0)], visible=False)
    helper = Node(HOLD, [("in", perm[2])], cap=2, visible=False)
    anchor = Node(MIX, [("node", 1), ("in", perm[0])])
    coupled = Node(MIX, [("node", 1), ("node", 2)])
    nodes = [driver, shared, helper, anchor, coupled]
    readouts = [3, 4]
    rng.shuffle(readouts)
    machine = Machine(k=3, n_inputs=3, nodes=nodes,
                      eval_order=_topo_order(nodes), readout_ids=readouts)
    for _ in range(200):
        exam = [[rng.randint(0, 2) for _ in range(3)]
                for _ in range(cfg.exam_len)]
        probes = acceptable(machine, exam)
        if probes is not None:
            return machine, exam, probes
    raise RuntimeError("unable to construct a certified modelkeeper_expert instance")


def _generate_instance_hard(cfg: Config, rng: random.Random, max_attempts: int):
    """Hard generation: accept a machine only if (a) some readout varies, (b) it is
    NOT reproducible by the plain depth-1 solver given unlimited probes (so the hidden
    helper is genuinely load-bearing), and (c) the hard solver cracks it and predicts
    the exam EXACTLY within the certification budget. The player-facing probe budget
    may be lower than this certification battery. Never serves an uncertified
    instance: if the hard family yields nothing in max_attempts, degrade to a
    depth-1-style instance that the hard solver's curated battery still certifies."""
    certify_budget = cfg.certify_probe_budget or cfg.probe_budget
    cert_cfg = replace(cfg, probe_budget=certify_budget)
    solver = HardReferenceSolver(cert_cfg)
    d1cfg = replace(cfg, depth=1, hidden_allowed=False, probe_budget=10 ** 9)
    d1 = ReferenceSolver(d1cfg)

    def varies(truth, n_read):
        return any(len({row[c] for row in truth}) > 1 for c in range(n_read))

    for _ in range(max_attempts):
        machine, exam = _Generator(cfg, rng).generate_once()
        truth = simulate(machine, exam)
        if not varies(truth, len(machine.readout_ids)):
            continue
        # load-bearing guardrail: reject anything an "easy" (depth-1) model can explain
        d1ok, _, d1fitted = d1.solve(machine)
        if d1ok and _predict_with_fitted(machine, d1fitted, exam) == truth:
            continue
        ok, probes_used, fitted = solver.solve(machine)
        if ok and _predict_with_fitted_machines(fitted, exam) == truth:
            return machine, exam, probes_used

    # Safe fallback (near-unreachable): serve a depth-1-style instance certified by the
    # hard solver's curated battery (fits the hard budget) — never an uncertified one.
    d1_family = replace(cfg, depth=1, hidden_allowed=False)
    last = None
    for _ in range(max_attempts):
        machine, exam = _Generator(d1_family, rng).generate_once()
        last = (machine, exam)
        truth = simulate(machine, exam)
        if not varies(truth, len(machine.readout_ids)):
            continue
        ok, probes_used, fitted = solver.solve(machine)
        if ok and _predict_with_fitted_machines(fitted, exam) == truth:
            return machine, exam, probes_used
    machine, exam = last
    return machine, exam, cfg.probe_budget


# ── The game ──────────────────────────────────────────────────────────────────

PHASE_PROBE, PHASE_EXAM, PHASE_DONE = "PROBE", "EXAM", "DONE"


class ModelkeeperGame:
    MAX_TURNS = 80

    def __init__(self, seed=None, lang="zh", mode="standard",
                 feedback_mode="final_only", config: Optional[Config] = None):
        if seed is None:
            seed = random.randint(0, 10 ** 9)
        self.seed = seed
        self._lang = lang if lang in ("zh", "en") else "zh"
        if mode not in ("standard", "hard", "expert"):
            raise ValueError(
                f"Unknown modelkeeper mode '{mode}'. Use 'standard', 'hard', or 'expert'.")
        self.mode = mode
        # Diagnostic feedback-ablation knob (game-level, NOT a Config dial — it does not
        # affect machine generation or scoring, only EXAM-phase observation text):
        #   final_only  — official behavior: no per-row feedback (modelkeeper / _hard)
        #   row_score   — after each completed exam row, show row + cumulative correct counts
        #   row_answer  — row_score plus the correct readout values for that row (teacher)
        if feedback_mode not in ("final_only", "row_score", "row_answer"):
            raise ValueError(
                f"Unknown modelkeeper feedback_mode '{feedback_mode}'. "
                "Use 'final_only', 'row_score', or 'row_answer'.")
        self._feedback_mode = feedback_mode
        # Explicit config wins (back-compat for baselines/solve/tests); otherwise the
        # mode selects the difficulty dials.
        if config is not None:
            self.cfg = config
        else:
            self.cfg = (EXPERT_CONFIG if mode == "expert" else
                        HARD_CONFIG if mode == "hard" else Config())
        # Turn cap must fit a maximal legitimate episode: a free reset before every
        # probe (2×budget) plus the full exam (exam_len × up to 3 readouts) plus slack.
        # The class default 80 must still fit a reset-heavy probe plan plus the full
        # exam; keep this formula tied to the player-facing budget.
        self.MAX_TURNS = max(self.MAX_TURNS,
                             2 * self.cfg.probe_budget + self.cfg.exam_len * 3 + 10)
        self._episode = 0
        self.reset()

    # ── localization helper ──
    def _t(self, zh, en):
        return zh if self._lang == "zh" else en

    # ── episode setup ──
    def reset(self):
        self._episode += 1
        ep_rng = random.Random(self.seed * 1000 + self._episode)
        self._machine, self._exam_inputs, self._ref_probes = generate_instance(self.cfg, ep_rng)
        self._exam_true = simulate(self._machine, self._exam_inputs)  # hidden truth

        self._R = len(self._machine.readout_ids)
        self._n_cells = self.cfg.exam_len * self._R
        # Config-level constant answer range, identical for EVERY instance of this
        # config, so the exam menu (predict_0..predict_{max-1}) leaks nothing about
        # which mechanisms this particular machine uses (e.g. a HOLD's cap).
        self._answer_max = self.cfg.answer_max()

        self._phase = PHASE_PROBE
        self._probes_left = self.cfg.probe_budget
        self._turn = 0
        self._exam_pred = []
        self._score = 0
        self._probes_used = 0
        self._done = False
        self._sim = MachineSim(self._machine)   # live probe state
        self._sim.reset()
        return self._render_intro(), {"valid": self.get_valid_actions()}

    # ── properties (EvolveBench contract) ──
    @property
    def score(self):
        return self._score          # 0 during play; set once at _finalize()

    @property
    def done(self):
        return self._done

    @property
    def turn_count(self):
        return self._turn

    # ── action surface ──
    def _probe_action_strings(self):
        m = self._machine.n_inputs
        return ["probe " + " ".join(str(v) for v in combo)
                for combo in product(range(self.cfg.k), repeat=m)]

    def get_valid_actions(self):
        if self._phase == PHASE_PROBE:
            return self._probe_action_strings() + ["reset", "exam", "status"]
        if self._phase == PHASE_EXAM:
            return [f"predict_{v}" for v in range(self._answer_max)] + ["status"]
        return ["status"]

    def get_action_label(self, action):
        a = action.strip()
        zh = self._lang == "zh"
        if a == "reset":
            return "重置" if zh else "reset"
        if a == "exam":
            return "开始考核" if zh else "begin exam"
        if a == "status":
            return "状态" if zh else "status"
        if a.startswith("probe"):
            vals = a.split()[1:]
            inner = ", ".join(f"I{i+1}={v}" for i, v in enumerate(vals))
            return (f"探测 ({inner})" if zh else f"probe ({inner})")
        if a.startswith("predict_"):
            v = a[len("predict_"):]
            return (f"预测值 {v}" if zh else f"predict {v}")
        return a

    # ── step dispatch ──
    def step(self, action):
        a = action.strip()
        if a.lower() == "status":
            return self._render_status(), 0, self._done, {"valid": self.get_valid_actions()}

        if self._done or self._phase == PHASE_DONE:
            return (self._t("本局已结束。", "This episode is over."),
                    0, True, {"valid": ["status"]})

        self._turn += 1
        if self._turn > self.MAX_TURNS:
            return self._force_finish()

        if self._phase == PHASE_PROBE:
            return self._step_probe(a)
        return self._step_exam(a)

    # ── probe phase ──
    def _step_probe(self, a):
        low = a.lower()
        if low == "reset":
            self._sim.reset()
            obs = self._t("已重置：机器回到零状态。", "Reset: machine back to zero state.")
            obs += "  " + self._fmt_readouts([0] * self._R) + self._fmt_left()
            return obs, 0, False, {"valid": self.get_valid_actions()}

        if low == "exam":
            return self._enter_exam(prefix=None)

        if low.startswith("probe"):
            if self._probes_left <= 0:
                return self._enter_exam(prefix=self._t(
                    "探测额度已用尽。", "Probe budget exhausted."))
            parts = a.split()[1:]
            m, k = self._machine.n_inputs, self.cfg.k
            try:
                vals = [int(x) for x in parts]
            except ValueError:
                vals = None
            if vals is None or len(vals) != m or any(not (0 <= v < k) for v in vals):
                msg = self._t(
                    f"无效探测：需要 {m} 个取值，每个在 0..{k-1} 之间。",
                    f"Invalid probe: need {m} values, each in 0..{k-1}.")
                return msg, 0, False, {"valid": self.get_valid_actions()}
            self._probes_left -= 1
            row = self._sim.tick(vals)
            obs = self._t("读数：", "Readouts: ") + self._fmt_readouts(row, prefix=False) + self._fmt_left()
            if self._probes_left <= 0:
                return self._enter_exam(prefix=obs + "\n\n" + self._t(
                    "探测额度已用尽，进入考核。", "Probe budget exhausted — entering exam."))
            return obs, 0, False, {"valid": self.get_valid_actions()}

        msg = self._t("无效命令。可用：probe <值..> / reset / exam / status。",
                      "Invalid command. Use: probe <vals..> / reset / exam / status.")
        return msg, 0, False, {"valid": self.get_valid_actions()}

    def _enter_exam(self, prefix):
        self._phase = PHASE_EXAM
        text = self._render_exam_intro()
        if prefix:
            text = prefix + "\n\n" + text
        text += "\n\n" + self._render_cell_prompt()
        return text, 0, False, {"valid": self.get_valid_actions()}

    # ── exam phase ──
    def _step_exam(self, a):
        val = self._parse_prediction(a)
        if val is None:
            msg = self._t(
                f"无效作答。用 predict_<值> 作答，可选 0..{self._answer_max-1}。",
                f"Invalid answer. Use predict_<value>, choices 0..{self._answer_max-1}.")
            return msg, 0, False, {"valid": self.get_valid_actions()}
        self._exam_pred.append(val)
        if len(self._exam_pred) >= self._n_cells:
            return self._finalize()
        ack = self._t("已记录。", "Recorded.")
        # Diagnostic variants only: once a full row (one exam step's readouts) is done,
        # surface row-level feedback. This is additional text — reward stays 0, and the
        # final-only path (official modelkeeper / _hard) is untouched.
        if self._feedback_mode != "final_only" and len(self._exam_pred) % self._R == 0:
            step = len(self._exam_pred) // self._R - 1
            ack = self._render_row_feedback(step)
        return ack + "\n\n" + self._render_cell_prompt(), 0, False, {"valid": self.get_valid_actions()}

    def _parse_prediction(self, a):
        s = a.strip().lower()
        if s.startswith("predict"):
            s = s[len("predict"):].lstrip("_ ").strip()
        if not s.isdigit():
            return None
        # Out-of-range values must RE-PROMPT, never consume a cell: replay pipelines
        # feed probe-phase menu numbers (e.g. "29" = exam) after the budget-exhausted
        # auto-enter, and silently recording one as a wrong answer shifts every
        # subsequent prediction by a cell (turns a near-perfect model into below-chance).
        # Re-prompting cannot soft-lock — the prompt states the valid range 0..max.
        val = int(s)
        if val >= self._answer_max:
            return None
        return val

    # ── finalize / scoring ──
    def _finalize(self):
        correct = sum(
            self._exam_pred[c] == self._exam_true[c // self._R][c % self._R]
            for c in range(self._n_cells))
        raw = correct / self._n_cells
        vcounts = [readout_value_count(self._machine, rid)
                   for rid in self._machine.readout_ids]
        chance = sum(1.0 / v for v in vcounts) / self._R
        # Clip to [-1, 1] (design §2.7): a below-chance predictor scores negative,
        # so a uniform-random predictor centers at 0 rather than being biased up.
        normalized = 0.0 if chance >= 1.0 else max(-1.0, min(1.0, (raw - chance) / (1 - chance)))
        self._probes_used = self.cfg.probe_budget - self._probes_left
        self._score = round(normalized * 100)
        self._done = True
        self._phase = PHASE_DONE
        info = {"valid": ["status"], "probes_used": self._probes_used,
                "raw_fraction": raw, "normalized": normalized,
                "correct": correct, "total": self._n_cells}
        return self._render_final(correct, raw), self._score, True, info

    def _force_finish(self):
        """Safety: turn cap hit. Auto-answer/zero-fill remaining and finalize."""
        if self._phase == PHASE_PROBE:
            self._phase = PHASE_EXAM
        while len(self._exam_pred) < self._n_cells:
            self._exam_pred.append(0)
        return self._finalize()

    # ── rendering ──
    def _fmt_readouts(self, row, prefix=True):
        body = "  ".join(f"O{i+1}={v}" for i, v in enumerate(row))
        if prefix:
            return ("读数：" if self._lang == "zh" else "Readouts: ") + body
        return body

    def _fmt_left(self):
        return self._t(f"  | 剩余探测：{self._probes_left}",
                       f"  | probes_left={self._probes_left}")

    def _render_intro(self):
        m, k, R, B = (self._machine.n_inputs, self.cfg.k, self._R, self.cfg.probe_budget)
        L = self.cfg.exam_len
        if self._lang == "zh":
            return (
                "【模型审计员控制台】\n"
                "你面前是一台连接着隐藏机器的控制台。机器内部封闭不可见——你只能给它输入信号、"
                "读取它产生的读数，借此推断它的行为。\n"
                f"本机有 {m} 路输入通道 (I1..I{m})，每路取值 0..{k-1}；对外显示 {R} 个读数 (O1..O{R})。\n\n"
                f"第一阶段·探测（共 {B} 次额度）：\n"
                f"  probe <v1..v{m}>  —— 设定输入、让机器走一拍并显示读数（消耗 1 次额度）\n"
                "  reset            —— 清空机器记忆，回到零状态（免费）\n"
                "  exam             —— 结束探测，进入考核\n"
                "  status           —— 查看阶段与剩余额度（免费）\n\n"
                f"探明机器行为后输入 exam 进入考核：系统会给出一段你未运行过、长 {L} 拍的输入序列，"
                "要求你从全新 reset 状态出发，逐格预测每一拍的每个读数。"
                + self._feedback_notice("考核期间没有任何反馈。",
                                        "There is NO feedback during the exam.")
            )
        return (
            "[Model Auditor Console]\n"
            "Before you is a console wired to a hidden machine. Its internals are sealed — you can "
            "only feed it input signals and read the values it produces, and from those infer how it "
            "behaves.\n"
            f"This machine has {m} input channels (I1..I{m}), each in 0..{k-1}, and exposes {R} "
            f"readouts (O1..O{R}).\n\n"
            f"Phase 1 — Probe ({B} probes):\n"
            f"  probe <v1..v{m}>  set inputs, advance ONE tick, show readouts (uses 1 probe)\n"
            "  reset            clear the machine's memory, back to zero state (free)\n"
            "  exam             stop probing, begin the exam\n"
            "  status           show phase / probes remaining (free)\n\n"
            f"When you understand the machine, type exam: the console reveals a fresh {L}-step input "
            "sequence you have not run, and asks you to predict every readout for every step, starting "
            "from a clean reset. "
            + self._feedback_notice("考核期间没有任何反馈。",
                                    "There is NO feedback during the exam.")
        )

    def _render_exam_intro(self):
        lines = []
        for t, inp in enumerate(self._exam_inputs):
            vec = ", ".join(str(v) for v in inp)
            lines.append((f"  第{t}拍: ({vec})" if self._lang == "zh"
                          else f"  step {t}: ({vec})"))
        seq = "\n".join(lines)
        if self._lang == "zh":
            return ("【考核开始】机器从全新 reset 状态运行以下输入序列（共 "
                    f"{self.cfg.exam_len} 拍）：\n{seq}\n\n"
                    "请逐格预测每一拍的每个读数。"
                    + self._feedback_notice("无任何反馈。", "No feedback."))
        return ("[Exam] The machine runs the following input sequence from a fresh reset "
                f"({self.cfg.exam_len} steps):\n{seq}\n\n"
                "Predict every readout for every step, in order. "
                + self._feedback_notice("无任何反馈。", "No feedback."))

    def _feedback_notice(self, default_zh, default_en):
        """Intro sentence describing exam-feedback density. Returns the unchanged
        default for final_only (so official modelkeeper / _hard intros are
        byte-identical); a mechanism-free description for the diagnostic variants."""
        if self._feedback_mode == "row_score":
            return self._t(
                "每预测完一拍的全部读数后，会告知本拍答对几格及累计答对几格（不显示正确答案）。",
                "After you finish all readouts for a step, you are told how many cells "
                "in that step were correct and your cumulative correct count "
                "(the correct values are not shown).")
        if self._feedback_mode == "row_answer":
            return self._t(
                "每预测完一拍的全部读数后，会告知本拍答对几格、该拍的正确读数及累计答对几格。",
                "After you finish all readouts for a step, you are told how many cells "
                "were correct, the correct readouts for that step, and your cumulative "
                "correct count.")
        return self._t(default_zh, default_en)

    def _render_row_feedback(self, step):
        """Row-level EXAM feedback for the dense/teacher diagnostic variants. `step`
        is the 0-indexed exam step whose row of readouts was just completed. Reveals
        only correctness counts (row_score) or the correct numeric row (row_answer) —
        never mechanism names, hidden structure, ranges, caps, or causes."""
        R = self._R
        pred_row = self._exam_pred[step * R:(step + 1) * R]
        true_row = self._exam_true[step]
        row_correct = sum(p == t for p, t in zip(pred_row, true_row))
        cells_done = len(self._exam_pred)
        cum_correct = sum(
            self._exam_pred[c] == self._exam_true[c // R][c % R]
            for c in range(cells_done))
        if self._lang == "zh":
            lines = ["【作答反馈】", f"拍次：{step}", f"本拍正确：{row_correct}/{R}"]
            if self._feedback_mode == "row_answer":
                lines.append("正确读数：" + self._fmt_readouts(true_row, prefix=False))
            lines += [f"累计正确：{cum_correct}/{cells_done}", "请继续预测下一拍。"]
            return "\n".join(lines)
        lines = ["ROW FEEDBACK", f"step: {step}", f"row_correct: {row_correct}/{R}"]
        if self._feedback_mode == "row_answer":
            lines.append("correct_row: " + self._fmt_readouts(true_row, prefix=False))
        lines += [f"cumulative_correct: {cum_correct}/{cells_done}",
                  "continue predicting the next step."]
        return "\n".join(lines)

    def _render_cell_prompt(self):
        c = len(self._exam_pred)
        step, r = c // self._R, c % self._R
        inp = self._exam_inputs[step]
        vec = ", ".join(str(v) for v in inp)
        maxv = self._answer_max - 1
        if self._lang == "zh":
            return (f"预测 第{step}拍 的读数 O{r+1}（该拍输入为 ({vec})）：\n"
                    f"用 predict_<值> 作答，可选 0..{maxv}。（进度 {c+1}/{self._n_cells}）")
        return (f"Predict step {step} readout O{r+1} (this step's inputs are ({vec})):\n"
                f"answer with predict_<value>, choices 0..{maxv}. (cell {c+1}/{self._n_cells})")

    def _render_status(self):
        if self._phase == PHASE_PROBE:
            if self._lang == "zh":
                return (f"阶段：探测  |  已用回合 {self._turn}/{self.MAX_TURNS}  |  "
                        f"剩余探测 {self._probes_left}/{self.cfg.probe_budget}")
            return (f"Phase: PROBE  |  turns {self._turn}/{self.MAX_TURNS}  |  "
                    f"probes_left {self._probes_left}/{self.cfg.probe_budget}")
        if self._phase == PHASE_EXAM:
            done_cells = len(self._exam_pred)
            if self._lang == "zh":
                return (f"阶段：考核  |  已作答 {done_cells}/{self._n_cells} 格  |  "
                        f"回合 {self._turn}/{self.MAX_TURNS}")
            return (f"Phase: EXAM  |  answered {done_cells}/{self._n_cells} cells  |  "
                    f"turns {self._turn}/{self.MAX_TURNS}")
        return self._t(f"阶段：结束  |  得分 {self._score}/100",
                       f"Phase: DONE  |  score {self._score}/100")

    def _render_final(self, correct, raw):
        if self._lang == "zh":
            return ("【考核结束】\n"
                    f"预测正确 {correct}/{self._n_cells} 格，原始正确率 {raw*100:.1f}%。\n"
                    f"归一化得分：{self._score}/100（0=瞎猜，100=满分）。\n"
                    f"本局共用探测 {self._probes_used}/{self.cfg.probe_budget} 次。")
        return ("[Exam complete]\n"
                f"Correct: {correct}/{self._n_cells} cells, raw accuracy {raw*100:.1f}%.\n"
                f"Normalized score: {self._score}/100 (0 = guessing, 100 = perfect).\n"
                f"Probes used this episode: {self._probes_used}/{self.cfg.probe_budget}.")
