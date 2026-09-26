# Modelkeeper: The Console

A black-box sequential-learning game for EvolveBench. The player is a **Model
Auditor** at a console wired to a hidden **clocked machine**. They feed it input
signals, watch the readouts, and must figure out the machine's behavior well
enough to **predict** the readouts of an unseen exam sequence. Rules are never
stated — they are discovered by probing.

See `modelkeeper_game_design.md` for the full design.

## How to play

```bash
python play.py modelkeeper --seed 42            # zh (default)
python play.py modelkeeper --seed 42 --lang en  # en
python play.py modelkeeper_hard --seed 42       # hard variant (depth-2, hidden nodes)
python play.py modelkeeper_expert --seed 42     # expert variant (shared depth-3 state)
```

Three phases per episode:
1. **Probe** — `probe <v1..vm>` sets inputs, advances one tick, shows readouts
   (costs 1 of the probe budget). `reset` clears the machine's state (free).
   `exam` ends probing. `status` is free.
2. **Exam** — a fresh, un-probed input sequence is revealed; predict every readout
   for every step with `predict_<value>` (one cell per turn, no feedback).
3. **Score** — `round(100 × normalized)`, where
   `normalized = (raw_fraction − chance)/(1 − chance)` clipped to `[-1, 1]`
   (0 = blind guessing, 100 = perfect). Probes used is reported alongside.

## The four mechanisms (universal "physics", fixed forever)

GATE (threshold), MIX (sum mod k / parity), HOLD (saturating up/down counter),
ECHO (one-tick delay). Each episode wires a **fresh** machine from these; the
mechanisms never change, only the instance does — so the game is *learnable but
not memorizable*.

## Frozen standard config

```python
Config(k=2, n_inputs_range=(2, 2), n_nodes_range=(3, 4), depth=1,
       hidden_allowed=False, probe_budget=20, exam_len=8, hold_caps=(2, 3))
MAX_TURNS = 80   # safety cap; status is free, RESET is free-but-turn-counted
```
- Exam answer menu is a **constant** `predict_0..predict_3` for every instance
  (`Config.answer_max()`), so it leaks nothing about a machine's mechanisms.
- Distinct machines for this config ≈ **54,000**; distinct exam sequences = 65,536.

## Verification results (see `CHANGELOG_VERIFICATION.md`, `../../results/modelkeeper/REPORT.md`)

Run the suites (cover both the standard and hard configs):
```bash
python games/modelkeeper/tests/run_all.py    # §2/§3/§6 [MUST] + §7 feedback variants — 35/35 green
python games/modelkeeper/baselines.py         # §4 [CALIBRATE] standard — green
python games/modelkeeper/baselines.py hard    # §4 [CALIBRATE] hard incl. headroom — green
python games/modelkeeper/baselines.py expert  # expert ladder incl. human anchor proxy
python games/modelkeeper/solve.py             # standard heuristic self-test — 1.000
python games/modelkeeper/solve.py hard        # hard heuristic self-test — 1.000
python games/modelkeeper/solve.py expert      # expert heuristic self-test — 1.000
python -m unittest games.modelkeeper.tests.test_expert
```

Baseline ladder (50 seeds, mean normalized accuracy):

| Player | Normalized | Probes | Meaning |
|---|---|---|---|
| `random` | −0.01 | — | floor (≈ chance) |
| `constant` | +0.05 | 0 | a fixed answer loses (non-triviality holds) |
| `single_sweep` (naive one-pass) | +0.46 | 3 | can't capture HOLD/ECHO/combos |
| `heuristic` (full routine) | +1.00 | 18 | ceiling, within budget |

`single_sweep / heuristic = 0.46 ≤ 0.70` → the **temporal mechanisms are binding**:
a naive one-pass is well below ceiling. Floor↔ceiling gap = 1.01.

### Episode-1 headroom and the hard variant

A strong LLM player solved the standard (depth-1) game at normalized **1.000** in a
single cold episode (8–20 probes). Because the four mechanisms are universal rather
than a seed-hidden secret, a capable reasoner can fully model a fresh depth-1 machine
in one episode, leaving little cross-episode **accuracy** headroom (only an
**efficiency** signal — probe count drops with skill). The **hard variant**
restores accuracy headroom.

## Hard variant (`modelkeeper_hard`)

Same interface (`probe` / `reset` / `exam` / `predict_<value>`, `--lang zh/en`) but a
**depth-2** machine with **hidden intermediate nodes**: every visible readout is a
GATE/MIX composed over a subset of inputs **plus one hidden, stateful (HOLD/ECHO)
helper** that is never directly observable — so each readout is the downstream shadow
of something you can only infer. Composition is non-collapsible to a depth-1 (memoryless)
model, so an "easy" mental model cannot solve it.

```python
HARD_CONFIG = Config(k=3, n_inputs_range=(3, 3), n_nodes_range=(4, 6), depth=2,
                     hidden_allowed=True, probe_budget=32,
                     exam_len=10, hold_caps=(2, 3))
```
- 3 inputs (0..2), 4–6 nodes, 2–3 visible readouts (mostly hidden-composite), 10-step exam.
- Exam answer menu is a **constant** `predict_0..predict_3` (`answer_max()`), leaking nothing.
- The player gets **32 probes**, matching the curated reference battery (ramps + pulses
  + a small combo set). This is enough to identify the served hard instance with the
  intended diagnostic routine, while still far below exhaustive black-box mapping.
- Distinct machines ≈ **6.7×10⁸**; distinct exam sequences ≈ **2.1×10¹⁴**.
- Every served episode is certified solvable: generation only keeps a machine whose hard
  solver predicts the exam exactly **and** that the plain depth-1 solver cannot reproduce
  (the hidden node is load-bearing every episode).

Baseline ladder — hard config (50 seeds, mean normalized accuracy):

| Player | Normalized | Probes | Meaning |
|---|---|---|---|
| `random` | −0.02 | — | floor (≈ chance) |
| `constant` | +0.02 | 0 | a fixed answer loses |
| `single_sweep` (naive one-pass) | +0.13 | 4 | memoryless can't touch hidden state |
| `depth1_solver` (easy mental model) | +0.24 | 20 | depth-1 understanding leaves headroom |
| `heuristic` (certification routine) | +1.00 | 32 | white-box solvability ceiling, above player budget |

Restored-headroom gate: `depth1_solver = 0.24 ≤ 0.60` while `heuristic = 1.00`, so the
**accuracy headroom (heur − depth1_solver) = 0.76** is the room a strong learner can climb
across episodes. `single_sweep / heuristic = 0.13`.

## Expert variant (`modelkeeper_expert`)

The expert game keeps the human-facing surface compact — 3 ternary inputs, exactly 2
readouts, 40 probes, and a 10-step final-only exam — while adding a controlled shared
depth-3 structure. A hidden GATE/MIX driven by two inputs feeds a hidden HOLD/ECHO state
that affects both readouts. One readout is a reversible MIX view (an undisclosed anchor
for human reasoning); the other is a second GATE/MIX view and, in 40% of machines, also
uses one direct hidden HOLD/ECHO helper.

The topology is deliberately bounded: no arbitrary DAGs, state-to-state chains, negative
hidden gates, or more than one extra state helper. The 40-probe reference battery combines
single-input and paired-input ramp/pulse experiments and certifies joint predictions across
both readouts. Generation never falls back to the hard or depth-1 family.

```python
EXPERT_CONFIG = Config(family="expert", k=3, n_inputs_range=(3, 3),
                       n_nodes_range=(4, 5), depth=3, hidden_allowed=True,
                       probe_budget=40, exam_len=10, hold_caps=(2, 3))
```

**Follow-up (not part of the offline gate):** an LLM with-memory vs no-memory run
(`compare_memory.py --backend main`, needs `OPENROUTER_API_KEY`) to confirm strong models
no longer saturate at episode 1.

## Diagnostic feedback-ablation variants (NOT official benchmark games)

Two extra game IDs exist purely as an **A/B diagnostic** to test *why* strong models
may fail to show a learning curve on `modelkeeper_hard` — is the hidden depth-2 rule
intrinsically too hard, or is **final-only exam feedback too sparse** for learning? They
are **identical to `modelkeeper_hard`** in every measured respect — same `HARD_CONFIG`,
same machine generation per `(seed, episode)`, same scoring formula, same probe budget,
same `predict_0..predict_3` exam menu — and differ **only in EXAM-phase feedback text**:

```bash
python play.py modelkeeper_hard_dense   --seed 42 --episode 1   # row-score feedback
python play.py modelkeeper_hard_teacher --seed 42 --episode 1   # teacher feedback (reveals correct row)
```

| Game ID | `feedback_mode` | After each completed exam row (one step's readouts) shows |
|---|---|---|
| `modelkeeper_hard` | `final_only` | nothing (official: feedback only at finalize) |
| `modelkeeper_hard_dense` | `row_score` | `row_correct` for this step + `cumulative_correct` so far |
| `modelkeeper_hard_teacher` | `row_answer` | the above **plus** the correct readout values for the step |

The feedback is **additional text only** — it does not change reward, final score, `done`,
`turn_count`, `MAX_TURNS`, instance generation, or valid actions. The **probe phase is
untouched** and score stays hidden during probing. `row_score` never reveals the correct
answers or which output was wrong, and neither variant ever names a mechanism, hidden node,
wiring, range, or cause; `row_answer` is allowed to reveal the correct numeric row only,
because it is an explicit teacher/supervised upper bound. The last exam row goes straight to
the unchanged finalize (its final report already reports cumulative correctness). These IDs
are **not** benchmark candidates and are excluded from the official calibration ladder.
`feedback_mode` is selected by the game ID via `ModelkeeperGame(mode="hard", feedback_mode=…)`;
gates are in `tests/test_feedback_modes.py` (§7).
