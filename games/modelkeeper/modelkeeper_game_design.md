# Modelkeeper: The Console — Game Design

A complete description of how the game works: its premise, the hidden world the player explores, the four mechanisms that world is built from, how a turn resolves, how the player interacts, and how a play is won and scored.

The game exists to test whether a player (human or AI agent) gets better at it across repeated plays. That single purpose shapes a few design choices, which are flagged where they come up — but this document is about the game itself, not the testing apparatus around it.

> **This document is dual-purpose.** **Part I — Agent Handoff** (below) is the canonical handoff for an independent coding/maintenance agent with zero prior context: what is built, where it lives, how it was verified, what's open, and the first step. **Part II — Game Design Specification** (§1–§14) is the unchanged, detailed rules reference that Part I points to. A *player* must not read this file at all (it states the hidden rules); it is a maintainer document.

---

# Part I — Agent Handoff

> Keep this section complete, honest, and evidence-based so the next agent can continue with zero prior context. Evidence (exact commands + observed results) lives in H5; the full rules are in Part II.

## H0. Next-Agent Summary

- **State:** **both variants of Modelkeeper are IMPLEMENTED, REGISTERED, and VERIFIED** — the standard depth-1 baseline AND the depth-2 / hidden-node **`modelkeeper_hard`** (Part II §15). All MUST gates **26/26** (incl. the §2.8 hard depth-2 gate) and all CALIBRATE gates green — standard 8/8, **hard 10/10** (incl. the two headroom gates). A 3-model learning-curve comparison ran and validated `valid` (depth-1, seed 42).
- **Most important open item:** depth-1 has **no episode-1 accuracy headroom for strong models** (a capable player solves a cold instance at normalized 1.000) — inherent to the universal-mechanism design (Part II §8), **not a bug**; the only depth-1 learning signal is **probe efficiency**. The **hard variant restores accuracy headroom** (depth1_solver +0.239 vs heuristic +1.000 → **headroom 0.761**). The remaining open item — **now ADVANCED but not closed** — is a **live multi-seed LLM learning-curve run on `modelkeeper_hard`**. Real-LLM data now covers BOTH depth-1 and hard: depth-1 (seed-42 Claude subagents **H5**; 2026-06-24 classic deepseek run **H5b**) shows **no learner curve** (learners don't beat naive), but the **first hard-variant run (2026-06-25, deepseek-v4-flash, seeds 1–2; H5c)** shows hard does **not** saturate at episode 1 and two learners (`memory`, `evotest`) **tentatively rise above the naive control** — a qualitative reversal of depth-1. Still **n=2 / descriptive only**; the open H8 work is a **multi-seed (1–10) hard run** to test it for significance. See H6 (R2), H5c.
- **Feedback-ablation A/B result (2026-06-25, H5c):** the §16 diagnostic variants `modelkeeper_hard_dense` / `_teacher` were run alongside hard. **Finding:** denser exam feedback did **not** lift the learner curves (learners' largest Δ/slopes are on plain `final_only` hard, not on dense/teacher) ⇒ **no evidence** that sparse final-only feedback is what suppresses learning. n=2, needs re-run at seeds 1–10. (`dense/memory/seed2` failed mid-run on a transient JSON-decode error ⇒ dense/memory is single-seed.)
- **Handoff hazard:** the **test suite (`tests/`) and the maintainer docs are git-ignored** (root `.gitignore` `*.md` + an ignore on `tests/`) — they exist on disk only and are MISSING in a fresh clone/worktree. See H6 (R1). **(2026-06-21: reviewed and DEFERRED by owner — R1 stays OPEN; tests/docs remain local-only.)**
- **New this session (2026-06-21):** learning-analysis tooling `metrics.py` / `aggregate.py` / `compare_memory.py` (slope+t-CI, multi-seed aggregation, with-memory-vs-no-memory) — see **H5a**. Plain `.py`, not git-ignored (they will travel once committed); currently uncommitted.
- **New this session (2026-06-24, feedback-ablation diagnostic):** added two **diagnostic, NON-official** game IDs — `modelkeeper_hard_dense` and `modelkeeper_hard_teacher` — to A/B-test whether sparse final-only exam feedback (not intrinsic difficulty) suppresses the hard learning curve. Same `HARD_CONFIG`/generation/scoring/exam/probe budget as `modelkeeper_hard`; the ONLY difference is EXAM-phase row feedback (via a new `ModelkeeperGame(feedback_mode=…)` enum: `final_only`/`row_score`/`row_answer`). `modelkeeper_hard` is **byte-identical** (proven vs `git HEAD`). See **Part II §16**. All gates green incl. 9 new §7 tests (`tests/test_feedback_modes.py`): `run_all.py` **35/35**. **Uncommitted.**
- **First command to run** (orient + confirm green):
  ```bash
  cd /home/jinhang/EvolveBench && python games/modelkeeper/tests/run_all.py
  ```
- **First files to read:** `games/modelkeeper/modelkeeper.py` (the whole game) and this handoff; the rules are Part II.

## H1. Project Goal

Build a black-box strategy game for the **EvolveBench** benchmark that measures an LLM agent's **sequential-learning ability**: a well-designed game makes a *learning* agent improve across repeated plays (score and/or efficiency) while a non-learner stays flat. Rules are hidden and discoverable only by play.

Modelkeeper concretely: the player is a **Model Auditor** at a console wired to a hidden **clocked machine** built from four universal node mechanisms — **GATE** / **MIX** / **HOLD** / **ECHO**. Each episode **probes** the machine (limited budget), then **predicts** the readouts of an unseen **exam** input sequence with no feedback. The design is *learnable but not memorizable*: mechanisms are fixed, but each episode wires a fresh machine. **The full rules are Part II (§1–§14)** — that is the authoritative goal/spec; do not water it down.

## H2. Non-Negotiable Constraints

1. **Black box / no rule leakage to players.** Nothing in the *player-visible surface* (intro + every probe/reset/status reply + exam prompt + final, in BOTH zh and en) may name or hint at the mechanisms. Forbidden tokens (case-insensitive), enforced by `tests/test_fairness.py` 3.1: `gate, mix, hold, echo, threshold, parity, saturate, saturation, ceiling, delay, lag, integrator, monotone, xor, node, wiring, topology, circuit, in-band, setpoint, cap`, plus the numeric θ/cap/sign values. Mechanism names may appear freely in engine code, tests, and **this maintainer doc** — never in player output.
2. **Probe replies carry values only.** No "no effect"/diff/change annotations; a dead input must be indistinguishable from a wired-but-inactive one and from baseline (negative result == empty). `probes_left` is the only allowed free metadata.
3. **Exam leaks no per-output range.** The answer menu is a **config-level constant** (`predict_0..predict_{Config.answer_max()-1}`), identical across instances. Exam entry is **budget-free** (efficiency metric is `probes_used`, not turns).
4. **Scoring formula (Part II §7).** `raw = correct/total`; `chance = mean(1/declared_range)`; `normalized = clip((raw−chance)/(1−chance), -1, 1)`; integer `score = round(100×normalized)` ∈ [-100,100]. **Score stays hidden (0) during PROBE/EXAM**, set once at finalize.
5. **Determinism & fresh instances.** Machine+exam are a pure function of `(seed, episode)` via `random.Random(seed*1000+episode)`; reproducible cross-process; no global RNG except the `seed=None` bootstrap. Fresh instance every episode; the 4-mechanism library is invariant.
6. **EvolveBench contract.** `ModelkeeperGame(seed, lang)` with `reset()->(obs,info)`, `step(action)->(obs,reward,done,info)`, `get_valid_actions()` (concrete strings incl. `status`), properties `score`/`done`/`turn_count`, class attr `MAX_TURNS`. One instance persists across `reset()` calls (one per episode).
7. **Calibration gates (Part II §9 guardrails + verification §4).** Every generated instance must be **non-trivial** (≥1 readout varies in the exam) AND certified solvable by the configured reference/certification solver (else regenerate). Baseline ladder must hold `random≈0 < single_sweep < heuristic≥0.95`, `single_sweep/heuristic ≤ 0.70`, floor↔ceiling gap ≥ 0.85.
8. **zh fully immersive** (project-wide): no English leakage in Chinese output — menus, options, AND prose.
9. **Verification discipline.** [MUST] failures → fix the *root cause* in code/scoring/interface, never loosen a test. [CALIBRATE] targets → tune **config knobs only** (k, inputs, nodes, depth, budget, exam_len, caps), never op semantics or the scoring formula. Precedence: **correctness > fairness/no-leak > calibration**. If a CALIBRATE target can't be met by config tuning in reasonable ranges, **stop and report** — don't invent mechanics.

## H3. Current Implementation State

Branch `game/model-keeper`. Engine committed as `5d06997 "Add modelkeeper game engine + registration"`. **Working tree is NOT fully clean:** `games/modelkeeper/modelkeeper.py` and `games/modelkeeper/README.md` each have **1 uncommitted line** — the doc-rename reference `MODELKEEPER_GAME_DESIGN.md`→`modelkeeper_game_design.md` (verified via `git diff`: no engine-logic change). Commit these (or `git add -f` the ignored docs/tests per R1) before opening the PR.

**Committed (tracked) — present in a fresh clone:**
- `games/modelkeeper/modelkeeper.py` — the whole game: `Node`/`Machine` dataclasses, `MachineSim`+`simulate` (tick sim, Part II §5), `_topo_order`, `readout_value_count`, `Config` (+`answer_max()`), `_Generator`+`generate_instance` (seeded gen + both guardrails), `ReferenceSolver` (mechanized §10 routine), `_predict_with_fitted`, and `ModelkeeperGame` (PROBE/EXAM/DONE phase machine, per-cell `predict_<value>` exam, zh/en localization).
- `games/modelkeeper/__init__.py`, `README.md`, `solve.py`, `baselines.py`.
- Registered in `play.py` `load_game` (+ unknown-game list), `main.py` `load_game` + `--game` choices, and listed in the top-level `CLAUDE.md`.

**On disk but GIT-IGNORED (missing in a fresh clone/worktree — see H6 R1):**
- `games/modelkeeper/tests/` — `test_correctness.py`, `test_fairness.py`, `test_robustness.py`, `run_all.py`, `_util.py`.
- `games/modelkeeper/{MODELKEEPER_VERIFICATION_PLAN.md, MODELKEEPER_TESTING_GUIDE.md, CHANGELOG_VERIFICATION.md}`. **(NB: `modelkeeper_game_design.md` — this file — is now TRACKED per the 2026-06-24 owner decision; see H10. The other docs + `tests/` remain local-only.)**
- `results/modelkeeper/REPORT.md` and `results/modelkeeper/model_compare/` (and `results/modelkeeper/memory_compare/` from H5a).

**On disk, TRACKABLE but UNCOMMITTED (added 2026-06-21):**
- `games/modelkeeper/{metrics.py, aggregate.py, compare_memory.py}` — learning-analysis tooling (H5a). Plain `.py`, **not** git-ignored, so `git status` shows them untracked; commit when ready. Independent of R1 (these travel once committed regardless of the tests/docs decision).

**How the abstract interface (Part II §6) maps onto EvolveBench.** The contract is one action per turn; the three-phase design is a `_phase ∈ {PROBE, EXAM, DONE}` state machine. Probe-phase actions are literal strings `probe <v1..vm>` / `reset` / `exam` / `status` (`reset`/`status` free; `exam` or budget-exhaustion enters the exam). Exam is committed **per cell** — one `predict_<value>` per (step, readout), row-major, no feedback until the last cell. Score hidden during play; the answer menu is the config constant `predict_0..predict_3` for the standard config.

**Run it:**
```bash
python play.py modelkeeper --seed 42 --episode 1 --lang en   # play one episode (zh default)
python games/modelkeeper/tests/run_all.py                    # §2/§3/§6 MUST gates
python games/modelkeeper/baselines.py                        # §4 calibration ladder
python games/modelkeeper/solve.py                            # heuristic ceiling self-test
```
`--episode N` selects episode N's machine (`seed*1000 + episode`); one `ModelkeeperGame` instance persists across `reset()` calls, one `reset()` per episode.

**Frozen standard config (depth-1 baseline):**
```python
Config(k=2, n_inputs_range=(2, 2), n_nodes_range=(3, 4), depth=1,
       hidden_allowed=False, probe_budget=20, exam_len=8, hold_caps=(2, 3))
MAX_TURNS = 80   # safety cap; status free, reset free-but-turn-counted
```
≈ 54,000 distinct machines for this config; 65,536 exam sequences.

## H4. Latest Session Changes

**Most recent session (2026-06-25) was a benchmark run + analysis write-back — NO engine/behavior change.** Ran the classic 5-agent OpenRouter path on all three hard IDs (`modelkeeper_hard` / `_dense` / `_teacher`, `deepseek/deepseek-v4-flash`, seeds 1–2, 10 ep; ~$17.4) → `results/<game>/comparison.json`. Added `tools/plot_modelkeeper_hard.py` (untracked) generating per-experiment overlaid learning-curve charts (`results/<game>/learning_curve.png` + combined `results/_analysis/modelkeeper_hard_learning_curves.png`). Wrote both results into this handoff (**H5c**) and reconciled H0 / H6 R2 / H8. One transient failure: `dense/memory/seed2` (JSON-decode mid-run) ⇒ that cell is single-seed. No source/test/config edits this session.

Prior session was **verification + documentation + a model comparison run** (the engine predates this session's commit). On disk:
- **`modelkeeper.py` — 3 root-cause fixes** (full log in `CHANGELOG_VERIFICATION.md`): (1) `_finalize()` normalized clip `[0,1]`→**`[-1,1]`** (a below-chance predictor now scores negative, random centers on 0); (2) exam menu de-leaked via `Config.answer_max()` constant (was instance-derived → leaked a HOLD's cap), parser now accepts any non-negative int (OOR scored wrong, no soft-lock); (3) removed dead `rng = self.cfg`.
- **Added** the `tests/` suite + `baselines.py`, and `solve.py` solver wrapper with a self-test.
- **Docs:** `CHANGELOG_VERIFICATION.md`, `README.md`, `results/modelkeeper/REPORT.md`, `MODELKEEPER_TESTING_GUIDE.md`, and this handoff (Part I) + resolved §14 in Part II.
- **Ran** a 3-model comparison (Haiku/Sonnet/Opus, seed 42, 10 ep each) → `results/modelkeeper/model_compare/s42_20260620-145453/` (`validation.json = valid`).

## H5. Verification and Test Results

Re-run from repo root `/home/jinhang/EvolveBench`; observed:
```bash
python games/modelkeeper/tests/run_all.py
# §2 correctness 13/13 (incl. §2.8 hard depth-2), §3 fairness 7/7, §6 robustness 6/6 -> 26/26 ; "ALL MUST GATES GREEN"

python games/modelkeeper/baselines.py
# random -0.012 | constant +0.047 | single_sweep +0.461 | heuristic +1.000
# floor↔ceiling gap 1.012 (≥0.85) ; single_sweep/heuristic 0.461 (≤0.70)
# "ALL CALIBRATE GATES GREEN"  (state space ≈54k machines; perf ~91 ep/s)

python games/modelkeeper/solve.py
# seeds 0-9 all normalized +1.000 ; "worst +1.000 -> PASS (≥0.95)"
```
**3-model learning-curve comparison** (`results/modelkeeper/model_compare/s42_20260620-145453/`, `validation.json=valid`). Run per `MODELKEEPER_TESTING_GUIDE.md`: orchestrator launched haiku/sonnet/opus as **worktree-isolated, model-pinned subagents**, 10 episodes each at seed 42 (`--episode 1..10`), each with its own `RUN_DIR` + per-episode history files; results re-verified against ground truth this session (`comparison.json` + the A4 integrity guard, which confirmed every logged score matches a saved `ep<N>_final.txt` transcript ending in `Final score:`):

| Model | Score first→last | ΔScore | Mean | Probes first→last | ΔProbes |
|---|---|---|---|---|---|
| haiku | 10→31 | +21 | 9.8 | 20→15 | −5 |
| sonnet | 48→100 | +52 | 77.9 | 18→11 | −7 |
| opus | 85→100 | +15 | 91.0 | 14→15 | +1 |

Full per-episode sequences (ep1..ep10), from `comparison.json`:
- **haiku** — score `[10, 21, -5, 7, -8, -23, 0, 10, 55, 31]`; probes `[20, 19, 15, 15, 15, 16, 16, 15, 15, 15]`.
- **sonnet** — score `[48, 64, 100, 71, 83, 59, 100, 92, 62, 100]`; probes `[18, 13, 16, 12, 11, 9, 12, 11, 10, 11]`.
- **opus** — score `[85, 100, 100, 100, 100, 25, 100, 100, 100, 100]`; probes `[14, 16, 10, 14, 20, 9, 17, 17, 15, 15]`.

Interpretation (consistent with R2): **Sonnet is the clearest learner** — it improved on *both* axes (rising score **and** falling probes), converging to repeated 100s in 9–13 probes. **Opus** is the strongest absolute performer (mean 91) but saturates near-100 from ep1, so its learning shows as *stabilization* (it recovered from a single ep6 stumble of 25 and finished 100×4), not a climbing score curve. **Haiku** is weak/volatile (mean 9.8, range −23..55) and did not master the multi-step state disambiguation; its probe drop didn't convert to accuracy. No model was flat on both axes.

Deliverable artifacts at the run dir: `learning_curves.png` (overlaid score + probe-efficiency curves), `comparison.json`, `COMPARISON.md`, `validation.json` (`overall_status=valid`); per model: `journal.md`, `scores.jsonl`, `ep1..10_final.txt`, `learning_curve.png`, `summary.json`.

**OpenRouter `agents/` harness — NOW RUN (2026-06-24):** the `main.py --agent …` harness has since been run on the **standard depth-1** game via the README "classic testing" path (5 agents × seeds 1–2 × 10 episodes, model `deepseek/deepseek-v4-flash`) → **see H5b**. *(At the time of the H5 table above, the harness had not been run — that table's learning curve used Claude Code subagents instead.)* The hard-variant harness curve is still open (H6 R2 / H8).

## H5a. Learning-analysis tooling + re-run results (2026-06-21)

Three **tracked, stdlib-only** scripts under `games/modelkeeper/` formalize the
with-memory-vs-no-memory / multi-seed / slope-CI analysis that previously lived only
as snippets in `MODELKEEPER_TESTING_GUIDE.md`. `metrics.py`/`aggregate.py` are
game-agnostic (consume any `scores.jsonl`); only `compare_memory.py`'s `baseline`
backend imports game internals (reuses `baselines.py`).

- **`metrics.py PATH/scores.jsonl [--metric score|probes] [--bootstrap]`** — OLS
  slope vs episode index + a **t-based 95% CI** on the slope (primary signal: CI
  excluding 0 ⇒ a statistically detectable trend), first-half-vs-second-half means,
  and an optional seeded bootstrap CI on the half-split diff. t critical values are a
  hard-coded two-sided 95% table (exact for df ≤ 30, the only regime here; 1.96
  fallback above, documented). Result keys: `{metric,n,episodes,values,ols,slope_ci,
  half_split,bootstrap_diff_ci,mean,stdev}`.
- **`aggregate.py [GLOB…] --dir DIR [--out OUT] [--plot]`** — multi-seed aggregation
  over **episode index**: per-episode mean ± 95% CI band, plus `pooled` (slope on the
  across-seed mean curve) and `per_seed` (mean per-seed slope + one-sample t-CI =
  *is learning consistent across seeds?*). Seed/label parsed from the path. Writes
  `aggregate.json` (+ band plot). Discovers `**/scores.jsonl`; the per-condition
  pooled file is named `pooled.jsonl` so it is **not** double-counted.
- **`compare_memory.py`** — with-memory vs no-memory comparison, three backends:
  - `--backend baseline` (no API): `with_memory ≈ player_heuristic` (oracle),
    `no_memory ≈ player_single_sweep` (memoryless). Fully reproducible; emits probes.
  - `--backend main` (needs `OPENROUTER_API_KEY`): subprocess `main.py --agent memory`
    vs `--agent naive` (memory = agent choice; there is no `--memory` flag). main.py's
    `scores.jsonl` has **no** probes, so the efficiency axis is unavailable there.
  - `--analyze-only GLOB…`: aggregate + metric existing `scores.jsonl` (e.g. the
    committed seed-42 `model_compare` data).
  Emits `comparison.json` (exact `model_compare` schema), `COMPARISON.md`,
  `learning_curves.png`, `metrics.json`, `aggregate_<condition>.json` into
  `results/modelkeeper/memory_compare/<run>/`.

**Re-ran the existing gates — all green (2026-06-21):**
```bash
python games/modelkeeper/tests/run_all.py   # 25/25  -> ALL MUST GATES GREEN
python games/modelkeeper/baselines.py        # 8/8    -> ALL CALIBRATE GATES GREEN
#   random -0.012 | constant +0.047 | single_sweep +0.461 | heuristic +1.000
#   floor↔ceiling gap 1.012 (≥0.85) ; single_sweep/heuristic 0.461 (≤0.70) ; ~54k machines
python games/modelkeeper/solve.py            # seeds 0-9 all +1.000 -> worst +1.000 PASS (≥0.95)
```

**Result 1 — metrics on the existing seed-42 `model_compare` data (real with-memory LLM runs).**
```bash
python games/modelkeeper/compare_memory.py \
  --analyze-only "results/modelkeeper/model_compare/s42_20260620-145453/*/scores.jsonl" --plot --bootstrap
```
| Model | mean | score slope (95% CI) | **probe slope (95% CI)** |
|---|---|---|---|
| haiku  | 9.8  | +2.82/ep [−2.62, +8.27] (ns) | **−0.42/ep [−0.78, −0.05] (sig)** |
| sonnet | 77.9 | +2.89/ep [−1.81, +7.59] (ns) | **−0.67/ep [−1.17, −0.17] (sig)** |
| opus   | 91.0 | +0.36/ep [−6.00, +6.73] (ns) | +0.21/ep [−0.65, +1.07] (ns) |

At n=10, **no model's *score* slope is individually significant** (score saturates —
the §8 / R2 accuracy-headroom limit), but **2 of 3 models show a statistically
significant *decline in probes used* across episodes**. This quantitatively confirms
R2: the depth-1 learning signal is **probe efficiency**, not accuracy. (Opus is already
saturated by ep1, so it shows no efficiency trend.)

**Result 2 — with-memory vs no-memory (no-API baseline proxies, 10 seeds × 8 episodes).**
```bash
python games/modelkeeper/compare_memory.py --backend baseline --seeds 0,1,2,3,4,5,6,7,8,9 --episodes 8 --plot
python games/modelkeeper/aggregate.py --dir results/modelkeeper/memory_compare/<run>/no_memory --plot  # multi-seed
```
| Condition | mean | score slope (95% CI) | probes |
|---|---|---|---|
| with_memory (heuristic oracle) | 100.0 | +0.00/ep [0, 0] | 18 (flat) |
| no_memory (memoryless sweep)   | 45.46 | +0.41/ep [−2.16, +2.98] (ns) | 3 (flat) |

This is a **pipeline + level-gap demonstration, not a learning curve**: both proxies are
*fixed* strategies, so the metrics correctly report flat slopes (CIs span 0) and surface
a **~55-point accuracy gap** between a memory-rich oracle and a memoryless strategy. A
genuine LLM with/no-memory *learning* curve requires an API key (`--backend main`, which
runs `--agent memory` vs `--agent naive`); it was **not** run here (no `OPENROUTER_API_KEY`),
consistent with H5. The real LLM learning signal this session is Result 1's probe slopes.

## H5b. Classic 5-agent OpenRouter run — standard depth-1 (deepseek-v4-flash, 2026-06-24)

This is the **first real OpenRouter `agents/` harness run** on Modelkeeper (H5 previously
recorded the harness as "NOT run … no `OPENROUTER_API_KEY`"; that line is now superseded —
see H5). It exercises the **standard depth-1** game (`--game modelkeeper`, *not* the hard
variant) across all five EvolveBench "classic" agent architectures, via the README **scripted-method
"classic testing"** path.

**How it was run** (README §"路线 A —— 经典 agent"; orchestrator `run_classic.sh` →
`tools/aggregate_classic.py`):
```bash
GAMES="modelkeeper" AGENTS="naive memory reflexion local_reflexion evotest" \
SEEDS="1 2" EPISODES=10 MODEL="deepseek/deepseek-v4-flash" PARALLEL=8 ./run_classic.sh
# expands, per agent×seed, to:
#   python main.py --game modelkeeper --agent <agent> --seed <seed> --episodes 10 \
#                  --model deepseek/deepseek-v4-flash
# then aggregates:
python tools/aggregate_classic.py modelkeeper --model deepseek/deepseek-v4-flash --episodes 10
```
Artifacts on disk: `results/modelkeeper/comparison.json`,
`results/modelkeeper/learning_curve_all_agents.png`, and per-agent
`results/modelkeeper/<agent>/benchmark.json` + `runs/.../{scores.jsonl,summary.json}`.
(The classic path emits only `benchmark.json` + `comparison.json`; the combined plot is added
separately. There is no `validation.json`/`COMPARISON.md` on this path — those belong to the
`model_compare`/`memory_compare` workflows, H5/H5a.)

**The five agents** (harness behavior only; defined under `agents/`): **naive** = memoryless
control (per-episode coherence, but state wiped between episodes — the no-learning baseline);
**memory** = full raw cross-episode transcript carried forward; **reflexion** = LLM-distilled
3–5 bullet reflections carried forward (token-efficient learner); **local_reflexion** = offline
non-LLM keyword/rule learner (`model="local"`, **0 API calls**); **evotest** = EVOTEST
tree-of-prompts evolver (most sophisticated learner).

**Results** — per-round mean across seeds 1 & 2 (`comparison.json` `avg_by_round`):

| Agent | Round 1→10 | ΔScore | Mean | Best | Calls | Cost (USD) |
|---|---|---|---|---|---|---|
| memory | 100 → 29.5 | −70.5 | 55.75 | 100 | 1092 | 1.064 |
| evotest | 100 → 49.0 | −51.0 | 54.85 | 100 | 991 | 0.581 |
| **naive (control)** | 100 → 83.0 | −17.0 | 49.80 | 100 | 1048 | 0.293 |
| reflexion | 97 → 21.5 | −75.5 | 48.00 | 100 | 1055 | 0.333 |
| local_reflexion (offline, 0 LLM) | 22 → 1.0 | −21.0 | 3.15 | 44 | 0 | 0.000 |

Full per-round means (rounds 1..10), from `comparison.json`:
- **memory** — `[100, 45, 74, 48.5, 42.5, 55.5, 62.5, 68, 32, 29.5]`
- **evotest** — `[100, 50.5, 66, 43.5, 50.5, 62.5, 30, 48.5, 48, 49]`
- **naive** — `[100, 57, 8.5, 79, -5, 7.5, 91.5, 37, 39.5, 83]`
- **reflexion** — `[97, 50, 70, 33.5, 15.5, 81, 12, 75.5, 24, 21.5]`
- **local_reflexion** — `[22, 5, -10, 17, -33.5, 5.5, -13, 12.5, 25, 1]`

**Interpretation — a clean depth-1 negative control that reconfirms R2.**
1. **No agent shows a rising score curve.** Every learner's first→last delta is negative; the
   per-round curves track per-episode machine difficulty, not accumulated learning.
2. **Round 1 ≈ 100 for all five LLM-driven agents (including naive).** The episode-1 machines
   for both seeds are solved cold — exactly the "no episode-1 accuracy headroom" symptom of R2
   on depth-1.
3. **Memory/learning buys no accuracy over naive.** memory (55.75) and evotest (54.85) only
   marginally exceed the memoryless naive control (49.80); reflexion (48.00) ties it. On a
   fully-visible depth-1 machine there is nothing for cross-episode memory to add — precisely R2.
4. **Memory is strictly worse on cost/benefit:** 29.0M tokens / $1.06 — ~3.6× naive's $0.29 —
   for statistically indistinguishable accuracy.
5. **The offline non-LLM learner collapses to near-chance** (local_reflexion mean 3.15). The
   game genuinely requires modeling the machine; keyword heuristics can't substitute — a healthy
   sign for the benchmark.
6. **Caveats.** deepseek-v4-flash is mid-tier, so unlike Opus (which saturated at 100, H5) it is
   volatile — individual-episode LLM scores span roughly −38..100 (e.g. reflexion seed-2 ep7 =
   −38; naive ep1 = 100), pulling means to ~50; the takeaway is the *absence of upward slope*, not
   the level. Only **2 seeds** (n=2 per round) ⇒ per-round means are noisy and slopes are **not**
   tested for significance here (descriptive only). The `memory` agent's seed dirs were re-run
   (`…193935` supersedes the truncated `…164606`).

**Bottom line.** First real agent-harness confirmation that the **standard depth-1 variant does
not produce a learning curve** — across five distinct learner architectures and a real
OpenRouter model — which is exactly why `modelkeeper_hard` exists (Part II §15). This run does
**not** close the open item: the genuinely open work (H6 R2 / H8) is the same classic path on
**`modelkeeper_hard`** (`--game modelkeeper_hard`), to confirm strong learners climb there.

## H5c. Classic 5-agent OpenRouter run — HARD + feedback-ablation A/B (deepseek-v4-flash, 2026-06-25)

**This run delivers the two results the prior sessions left open:** (1) the **first real-LLM
learning curve on `modelkeeper_hard`** (the open H6 R2 / H8 item — depth-1 was the only real-LLM
data before this), and (2) the **feedback-ablation A/B** that the §16 diagnostic variants
(`modelkeeper_hard_dense` / `_teacher`) were built for — does sparse final-only exam feedback,
rather than intrinsic depth-2 difficulty, suppress the hard learning curve?

**Method.** Same README "classic testing" path as H5b (`run_classic.sh` → `tools/aggregate_classic.py`),
extended to the three hard IDs:
```bash
GAMES="modelkeeper_hard modelkeeper_hard_dense modelkeeper_hard_teacher" \
AGENTS="naive memory reflexion local_reflexion evotest" \
SEEDS="1 2" EPISODES=10 MODEL="deepseek/deepseek-v4-flash" PARALLEL=8 ./run_classic.sh
```
30 (game×agent×seed) combinations × 10 episodes; ~9.5 h wall; **~$17.4 total** OpenRouter
(hard $6.21, dense $5.22, teacher $5.95). Artifacts on disk per game: `results/<game>/comparison.json`,
per-agent `<agent>/benchmark.json` + `runs/.../{scores.jsonl,summary.json}`. Learning-curve charts
generated this session (one per experiment, all 5 agents overlaid) via the new
`tools/plot_modelkeeper_hard.py`: `results/<game>/learning_curve.png` + a combined
`results/_analysis/modelkeeper_hard_learning_curves.png`.

**One failed combo.** `modelkeeper_hard_dense/memory/seed2` died mid-run on a
`json.decoder.JSONDecodeError` (a truncated/malformed LLM response — transient, NOT an env issue;
`openai` 2.43.0 + key were confirmed working, and the stale `ModuleNotFoundError` lines in
`classic_run.log` are from earlier-today runs, not this one). So **dense/memory is single-seed**
and is the least reliable row below.

**Results** — `avg_by_round` per agent: early = mean(rounds 1–3), late = mean(rounds 8–10),
Δ = late−early, slope = OLS slope per round. Sorted by Δ within each game.

*`modelkeeper_hard` (final_only — the official sparse-feedback variant):*

| Agent | early R1‑3 | late R8‑10 | Δ | slope | best | cost |
|---|--:|--:|--:|--:|--:|--:|
| memory | 1.5 | 26.7 | **+25.2** | 3.38 | 76 | $2.70 |
| evotest | 12.5 | 31.5 | +19.0 | 3.20 | 88 | $0.85 |
| local_reflexion ⚠️ | 1.7 | 15.8 | +14.2 | 2.22 | 64 | $0.00 |
| reflexion | 12.7 | 15.2 | +2.5 | 0.52 | 100 | $1.29 |
| **naive (control)** | 21.3 | 15.7 | −5.7 | −0.52 | 70 | $1.37 |

*`modelkeeper_hard_dense` (per-tick correct-count feedback):*

| Agent | early | late | Δ | slope | best | cost |
|---|--:|--:|--:|--:|--:|--:|
| local_reflexion ⚠️ | 1.7 | 15.8 | +14.2 | 2.22 | 64 | $0.00 |
| memory ⚠️ 1‑seed | −6.0 | 6.7 | +12.7 | 4.76 | 62 | $1.81 |
| reflexion | 10.3 | 21.2 | +10.8 | 2.39 | 67 | $1.23 |
| evotest | 15.5 | 20.0 | +4.5 | 0.65 | 57 | $1.15 |
| **naive (control)** | 13.2 | 16.3 | +3.2 | −0.34 | 64 | $1.03 |

*`modelkeeper_hard_teacher` (per-tick correct readings revealed — supervision upper bound):*

| Agent | early | late | Δ | slope | best | cost |
|---|--:|--:|--:|--:|--:|--:|
| evotest | 20.2 | 33.0 | +12.8 | 1.38 | 88 | $1.01 |
| local_reflexion ⚠️ | 1.7 | 15.8 | +14.2 | 2.22 | 64 | $0.00 |
| memory | 17.5 | 26.8 | +9.3 | 0.68 | 94 | $2.51 |
| reflexion | 18.3 | 20.3 | +2.0 | 0.68 | 82 | $1.25 |
| **naive (control)** | 20.8 | 10.8 | −10.0 | −1.29 | 40 | $1.18 |

**Interpretation — two qualified-positive results, both n=2 noisy.**

*Result 1 — hard shows the first sign of a real-LLM learner curve, and confirms the headroom fix.*
1. **No episode-1 saturation on hard.** Early-round scores sit at ~1.5–21 (and individual ep-1
   cells span negative→~50), nowhere near the depth-1 "round-1 ≈ 100 for all five agents" symptom
   (H5b). This is the direct real-LLM corroboration that **`modelkeeper_hard` restores accuracy
   headroom** (R2 / §8) — the thing depth-1 could not provide.
2. **Two learners rise and beat the memoryless control on final_only.** On `modelkeeper_hard`,
   `memory` (Δ+25.2, slope +3.38) and `evotest` (Δ+19.0, slope +3.20) both trend up and clear the
   `naive` control (Δ−5.7, slope −0.52) — the **opposite** of depth-1, where no learner beat naive.
   This is the first (weak) evidence that strong learners climb on hard. `reflexion` is roughly
   flat (Δ+2.5).
3. **Not significant.** Only **2 seeds**; per-round means are noisy and slopes are **descriptive,
   not significance-tested**. Treat "memory/evotest rise on hard" as a hypothesis to confirm with a
   real multi-seed run (H8), not a closed result. **R2/H8 is advanced, not closed.**

*Result 2 — the feedback-ablation A/B does NOT support "sparse feedback suppresses the curve."*
4. **Denser feedback did not lift the learner curves.** The naive hypothesis behind §16 predicts
   `final_only < dense < teacher` in learner improvement. It does not hold: the learners' **largest**
   Δ and slopes appear on plain **final_only** hard (memory Δ+25.2, evotest Δ+19.0), while `dense`
   compresses them (memory Δ+12.7 [1‑seed], evotest Δ+4.5) and `teacher` is mixed (evotest Δ+12.8
   strongest; memory Δ+9.3). No agent shows a monotone gain with feedback density.
5. **Tentative conclusion:** at this sample size there is **no evidence** that final-only feedback
   is what suppresses learning — i.e. the hard variant's flatness (where present) reads as
   *intrinsic difficulty / per-episode variance*, not feedback starvation. This is the diagnostic
   answer §16 was built to get, but it is **n=2 and must be re-run at seeds 1–10** before acting on
   it. The `dense/memory` single-seed gap weakens the dense column specifically.

**Caveats (apply to both results).**
- **`local_reflexion` is not a learner here** (⚠️ rows). It is the offline, keyword-heuristic agent
  written for the signal-station game (scan/listen/CH channels) — modelkeeper has none of those
  tokens, so it makes **0 LLM calls** and falls through to `valid_actions[0]` every tick. Its
  `avg_by_round` is **byte-identical across all three games** (it cannot even see the feedback-mode
  difference); its +14.2 "Δ" is a deterministic artifact of a fixed action sequence, not learning.
  Keep it as a non-learner floor; never read it as a feedback-density signal.
- n=2 seeds; deepseek-v4-flash is mid-tier and volatile (per-episode cells span ≈ −63..100);
  no significance test. Charts are jagged because the ep-2 spike / ep-4 dip hit every agent in
  lockstep — that is seed-level machine variance, not per-agent learning.

**Bottom line.** First real-LLM data on `modelkeeper_hard`: it does **not** saturate at episode 1
(headroom confirmed) and two learners (`memory`, `evotest`) tentatively rise above the naive
control on the official final_only variant — a qualitative reversal of depth-1. The feedback A/B
gives **no evidence** that sparse final-only feedback is the cause of suppressed learning. Both
findings are **n=2 / descriptive**; the open H8 work is now a **multi-seed (1–10) run on
`modelkeeper_hard`** to test these two hypotheses for significance.

## H6. Current Issues, Risks, and Blockers

- **R1 — Test suite & maintainer docs are git-ignored (handoff hazard).** *Evidence:* `git check-ignore -v games/modelkeeper/<doc>.md` → root `.gitignore:12 *.md`; `tests/` also ignored; `git ls-files games/modelkeeper/` lists only engine files (`README.md` is tracked only because it was force-/pre-added). *Impact:* a fresh clone or git **worktree** (the testing guide uses worktrees) lacks the tests and these docs — players still run (engine committed), but a maintainer in a worktree can't run `run_all.py`. *Next check:* decide whether to `git add -f` the tests + docs so verification travels with the repo (owner may intend them local-only). **Status (2026-06-21): reviewed and DEFERRED by owner — R1 remains OPEN.** A scoped `.gitignore` negation (`!games/modelkeeper/tests/` + `!games/modelkeeper/tests/*.py` + `!games/modelkeeper/*.md`) was drafted and **verified** (`git add --dry-run` tracked exactly the 5 test files + 4 docs; `__pycache__`/`*.pyc`/other games stayed ignored), then **reverted at owner request**; `git add -f` was also offered. Tests + maintainer docs (including this file) and `results/` therefore remain git-ignored / local-only. NB: the three new analysis scripts (`metrics.py`/`aggregate.py`/`compare_memory.py`) are plain `.py` and are **not** ignored — they travel once committed, independent of R1.
- **R2 — Depth-1 has no episode-1 *accuracy* headroom for strong models.** *Not a bug — inherent.* *Evidence:* 3/3 cold strong-LLM players scored normalized 1.000 in one episode (corroborated by Opus mean 91). *Cause (confirmed):* the 4 mechanisms are universal (Part II §8), so a capable reasoner fully models a fresh fully-visible machine in one episode; the only depth-1 learning signal is **probe efficiency**. *Resolution:* the hard variant (`modelkeeper_hard`, Part II §15) is **now built, registered, and verified** — depth1_solver +0.239 vs heuristic +1.000 (**headroom 0.761**), restoring cross-episode accuracy headroom; a depth-1-only mental model can no longer solve it. *Reconfirmed again 2026-06-24 (H5b):* a real OpenRouter classic 5-agent run on **depth-1** (`deepseek/deepseek-v4-flash`, seeds 1–2) shows **no rising score curve for any agent**, and the memory/reflexion/evotest learners fail to beat the memoryless naive control — independent agent-harness evidence for the no-headroom claim. *First hard-variant evidence, 2026-06-25 (H5c):* the same classic path on `modelkeeper_hard` (deepseek-v4-flash, seeds 1–2) shows hard does **NOT** saturate at episode 1 (early-round scores ~1.5–21, not depth-1's ≈100) and `memory` (Δ+25.2) / `evotest` (Δ+19.0) **tentatively rise above the naive control** (Δ−5.7) — the qualitative reversal the hard variant was built to produce. **This advances R2 but does not close it: n=2, descriptive only, no significance test.** *Remaining:* a **multi-seed (1–10) hard run** (README classic path `--game modelkeeper_hard`, or `compare_memory.py --backend main`) to confirm the rising learner curve for significance; for depth-1 evaluation still plot **probes-used** alongside score.
- **R3 — `generate_instance` fallback can emit an uncertified instance.** *Evidence:* after `max_attempts` (400) it returns the last attempt even if guardrails failed. *Likely cause:* defensive fallback. *Next check:* fine for the standard config (tests pass); if you widen the config and see odd scores, add a hard assert/log on fallback.

## H7. Open Questions and Assumptions

- **Assumption:** this file (`games/modelkeeper/modelkeeper_game_design.md`) is now the canonical in-repo handoff (it absorbed the prior `~/.claude/plans/` handoff). If it should be tracked, resolve R1 (`git add -f`).
- **Update:** the hard variant is **no longer deferred** — `modelkeeper_hard` (depth-2, hidden stateful nodes) is implemented, registered, and verified (Part II §15).
- **Open question:** should the git-ignored tests/docs be committed (R1)? Needs an owner decision.

## H8. Next Implementation Steps

**The hard variant has been BUILT and committed (2026-06-24, `f6c1718`).** `modelkeeper_hard` is implemented, registered, and verified (Part II §15; 26/26 MUST + hard 10/10 CALIBRATE green). Build steps 2–6 below are now **DONE** and kept as a historical record of how it was done. The genuine remaining work:
- **[done 2026-06-24] Committed the work** on `game/model-keeper` (`f6c1718`): hard-mode engine, `modelkeeper_hard` registration in `main.py`/`play.py`, `baselines.py`/`solve.py` hard additions, and the `metrics.py`/`aggregate.py`/`compare_memory.py` analysis tooling. R1 unchanged — tests + maintainer docs (incl. this file) stay git-ignored / local-only per owner.
- **[done 2026-06-24] Depth-1 classic LLM run** — the README "classic testing" path was run on the standard depth-1 game (5 agents × seeds 1–2 × 10 ep, `deepseek/deepseek-v4-flash`) → `results/modelkeeper/comparison.json`; analysis in **H5b**. It reconfirms R2 (no depth-1 learning curve; learners don't beat naive) — it does **not** substitute for the hard-variant curve below.
- **[advanced 2026-06-25, NOT closed] Live LLM learning curve on hard** — the classic path was run on `modelkeeper_hard` (+ the `_dense`/`_teacher` A/B), `deepseek/deepseek-v4-flash`, **seeds 1–2** × 10 ep → `results/modelkeeper_hard*/comparison.json`; analysis in **H5c**. **Result:** hard does not saturate at ep 1 and `memory`/`evotest` tentatively rise above the naive control — but only **n=2, descriptive**. **Still open:** re-run at **seeds 1–10** (and ideally a stronger model than mid-tier flash) to (a) confirm the rising learner curve for significance and (b) re-test the feedback A/B (H5c found no evidence denser feedback helps). Re-fill the failed `dense/memory/seed2` cell. Next concrete command: same `run_classic.sh` invocation as H5c with `SEEDS="1 2 3 4 5 6 7 8 9 10"`.

<sub>**Historical build steps (all completed):**</sub>
1. **Resolve R1 first** — `git check-ignore -v games/modelkeeper/tests/run_all.py`; if verification should travel with the repo, `git add -f games/modelkeeper/tests games/modelkeeper/*.md` and commit (else the next agent silently has no tests). *(Reviewed and DEFERRED by owner — tests/docs stay local-only.)*
2. **Extend the generator** (`_Generator`/`generate_instance`) for depth-2: allow node sources `("node", j)` with `j<id` (DAG already handled by `_topo_order`) and mark some intermediate nodes `visible=False`, excluding them from `readout_ids`; add `k=3` / more inputs.
3. **Extend `ReferenceSolver`** — it currently fits each readout independently from a full `k^m` input-combo sweep, which neither handles hidden intermediate nodes nor fits the budget at larger `k`/`m`. Implement latent-structure inference + a relaxed "near-perfect" solvability bar (Part II §9) so the solvability guardrail still certifies hard instances.
4. **Re-run the gates** on the hard config: `run_all.py` (no-leak/determinism/robustness must stay green) + a hard-config branch in `baselines.py` confirming `single_sweep/heuristic ≤ 0.70`, `heuristic ≥ 0.95`, and now **episode-1 strong-player accuracy < ceiling**.
5. **Register `modelkeeper_hard`** in `play.py`/`main.py` (mirror the `patch_reality`/`patch_reality_hard` two-entry pattern) only after step 4 passes.
6. **Re-run the learning curve** via `MODELKEEPER_TESTING_GUIDE.md` on the hard variant; confirm a rising strong-learner accuracy curve.

To merge current work: open a PR from `game/model-keeper` (resolve R1 first so reviewers see the tests).

## H9. Resolved / Historical Notes

- **Implementation (committed `5d06997`):** chose per-cell `predict_<value>` exam over free-form/bulk (fits the one-action-per-turn contract + naive substring matching); score `round(100×normalized)`; hidden during play; `MAX_TURNS=80` with free-but-turn-counted RESET. Validated against the §12 worked example, ECHO lag, MIX parity; solver hits 100% on 600 instances at 18/20 probes.
- **Part II §14 questions — RESOLVED:** (1) prediction-only objective; (2) standard game depth-1 fully visible; hidden nodes are the **`modelkeeper_hard`** variant — **now implemented** (Part II §15).
- **3 verification fixes — RESOLVED:** normalized clip `[-1,1]`; config-constant exam menu (was leaking HOLD cap); dead-line removal (H4 / `CHANGELOG_VERIFICATION.md`).
- **§5 accuracy-headroom gate — RESOLVED via the hard variant:** depth-1 couldn't meet it by config tuning (reported, not patched, per H2#9); the fix — `modelkeeper_hard` (depth-2 + hidden nodes) — is now **built and verified** (headroom 0.761; depth1_solver 0.239 vs heuristic 1.000).

## H10. Change Log

- **2026-06-25 (HARD + feedback-ablation LLM run — analysis write-back, doc + chart tooling only):** ran the README "classic testing" path (`run_classic.sh` → `tools/aggregate_classic.py`) on the three hard IDs — `modelkeeper_hard` / `modelkeeper_hard_dense` / `modelkeeper_hard_teacher` × 5 agents (`naive`/`memory`/`reflexion`/`local_reflexion`/`evotest`) × seeds 1–2 × 10 ep, model `deepseek/deepseek-v4-flash`, `PARALLEL=8`. **Verified (commands + observed):** 30 combos completed (~9.5 h wall, **~$17.4** total: hard $6.21 / dense $5.22 / teacher $5.95) → `results/<game>/comparison.json` + per-agent `benchmark.json`/`runs/`; env confirmed healthy (`python -c "import openai"` → 2.43.0, key present; a prior naive run logged 517 calls). **One failure:** `modelkeeper_hard_dense/memory/seed2` → `json.decoder.JSONDecodeError` mid-run (transient malformed LLM response; the `ModuleNotFoundError` lines in `classic_run.log` are stale from earlier-today runs) ⇒ dense/memory is single-seed. **Two results (both n=2, descriptive, no significance test):** (1) **first real-LLM curve on `modelkeeper_hard`** — does NOT saturate at ep 1 (early-round ~1.5–21 vs depth-1's ≈100) and `memory` (Δ+25.2, slope +3.38) / `evotest` (Δ+19.0, slope +3.20) tentatively rise above the naive control (Δ−5.7) — qualitative reversal of depth-1 (H5b); (2) **feedback A/B** — denser exam feedback did NOT lift learner curves (largest Δ/slopes are on plain `final_only` hard, not dense/teacher) ⇒ no evidence sparse feedback causes the suppressed curve. `local_reflexion` = offline 0-LLM keyword heuristic, byte-identical across all three games (non-learner floor, not a feedback signal). **Tooling added:** `tools/plot_modelkeeper_hard.py` → per-experiment overlaid learning-curve charts `results/<game>/learning_curve.png` + combined `results/_analysis/modelkeeper_hard_learning_curves.png` (re-runnable; stable color/marker per agent). **Doc edits:** added **H5c** (method + 3 tables + interpretation + caveats); reconciled H0 (two new summary bullets), H4 (this session), H6 R2 (hard now has real-LLM data — advanced not closed), H8 (open item retargeted to seeds 1–10 + refill failed cell). **No game-behavior change** — benchmark run + analysis + chart script only; numbers verified against `comparison.json`. Working tree otherwise carries the still-uncommitted §16 feedback variants (prior session). **Open:** R1 (tests/docs git-ignored), R2/H8 (multi-seed 1–10 hard curve for significance + refill `dense/memory/seed2`), R3 (generator fallback).
- **2026-06-24 (feedback-ablation diagnostic variants — engine + tests + docs):** added two **NON-official, diagnostic** game IDs, `modelkeeper_hard_dense` and `modelkeeper_hard_teacher`, to A/B-test whether final-only exam feedback (vs intrinsic depth-2 difficulty) suppresses the hard learning curve (**Part II §16**). `modelkeeper.py`: new `feedback_mode` enum (`final_only`/`row_score`/`row_answer`, default `final_only`) on `ModelkeeperGame`; `_render_row_feedback` + `_feedback_notice` helpers; a row-boundary branch in `_step_exam`; both intros route their "no feedback" line through `_feedback_notice` so `final_only` stays byte-identical. Registered in `play.py`/`main.py` (loaders, error lists, `--game` choices). `baselines.py`/`solve.py` unchanged (they pass `config=HARD_CONFIG`). Tests: new `tests/test_feedback_modes.py` (9 §7 gates) + `test_fairness.py` §3.1 extended to scan dense/teacher surfaces; registered in `run_all.py`. **Verified (commands + observed):** `cd games/modelkeeper/tests && python run_all.py` → **35/35 ALL MUST GATES GREEN** (26 official + 9 §7); `python games/modelkeeper/baselines.py` + `baselines.py hard` → ALL CALIBRATE GREEN (hard headroom gate intact); `python games/modelkeeper/solve.py` + `solve.py hard` → seeds 0-9 +1.000. **`modelkeeper_hard` byte-identity** proven by importing `git HEAD:games/modelkeeper/modelkeeper.py` and diffing the full player-visible surface (standard+hard × zh/en × 8 seeds) → IDENTICAL. Smoke-tested all four new ID×lang combos via `play.py` (dense shows counts only; teacher adds `correct_row:`/`正确读数:`); loader wiring + argparse-choices confirmed for both `main.py` and `play.py`. **No change** to generation, scoring, probe phase, valid actions, or `modelkeeper`/`modelkeeper_hard` behavior. Files: `modelkeeper.py`, `play.py`, `main.py`, `README.md`, this doc (tracked); `tests/test_feedback_modes.py`, `tests/run_all.py`, `tests/test_fairness.py`, `CLAUDE.md` (local/per-repo). **Uncommitted** at session end. **Did NOT run** the expensive LLM benchmark (per task). **Open (unchanged):** R1 (tests/docs git-ignored — the new test file is too), R2/H8 (live multi-seed `modelkeeper_hard` LLM curve), R3 (generator fallback). The §16 variants are diagnostics for that R2/H8 investigation, not benchmark candidates.
- **2026-06-24 (classic depth-1 LLM run write-back — doc only):** wrote back the first real OpenRouter `agents/` harness results into this handoff. A README "classic testing" run (`run_classic.sh` → `tools/aggregate_classic.py`) on the **standard depth-1** game — 5 agents (`naive`/`memory`/`reflexion`/`local_reflexion`/`evotest`) × seeds 1–2 × 10 episodes, model `deepseek/deepseek-v4-flash` — produced `results/modelkeeper/comparison.json` (+ `learning_curve_all_agents.png`, per-agent `benchmark.json`/`runs/`). **Finding:** no agent shows a rising score curve (all first→last deltas negative); learners don't beat the memoryless naive control (means: memory 55.75, evotest 54.85, naive 49.80, reflexion 48.00, local_reflexion 3.15); memory costs ~3.6× naive ($1.06 vs $0.29) for no accuracy gain; the offline non-LLM learner collapses to near-chance (3.15). This is a clean depth-1 **negative control reconfirming R2**. **Doc edits:** added **H5b** (methodology + table + per-round arrays + interpretation), superseded H5's "OpenRouter harness NOT run" line, reconciled H0 / H6 R2 / H8 (depth-1 classic run done; the `modelkeeper_hard` LLM curve remains the open item). Descriptive analysis only (n=2 seeds ⇒ no significance test). **No game-behavior change** — documentation only; numbers verified against `comparison.json`; working tree was otherwise clean.
- **2026-06-24 (hard-variant verification re-run + commit):** re-ran all gates green on the current working tree — `run_all.py` **26/26** (incl. §2.8 hard depth-2), `baselines.py` 8/8 + `baselines.py hard` **10/10** (depth1_solver +0.239, heuristic +1.000, **headroom 0.761**), `solve.py`/`solve.py hard` seeds 0-9 = +1.000 (18/32 probes). **Committed** the work as **`f6c1718`** on `game/model-keeper` (hard-mode engine, `modelkeeper_hard` registration in `main.py`/`play.py`, `baselines.py`/`solve.py` hard additions, `metrics.py`/`aggregate.py`/`compare_memory.py`, README + CLAUDE.md) — 11 files; tests + other maintainer docs + results stay git-ignored (R1 unchanged). **This design doc is now TRACKED (owner decision):** un-ignored via a root `.gitignore` negation (`!games/modelkeeper/modelkeeper_game_design.md`) and the redundant `games/modelkeeper/.gitignore` removed, committed alongside the doc so the spec + handoff travel with the repo. Reconciled Part I (H0 / H5 / H6 R2 / H7 / H8 / H9) to reflect the hard variant as **implemented & committed** rather than deferred. **No game-behavior change** this session (verification + commit + doc reconciliation only). **Remaining:** multi-seed `--backend main` LLM curve on hard (needs `OPENROUTER_API_KEY`).
- **2026-06-21 (analysis tooling + gate re-run):** added 3 tracked stdlib scripts under `games/modelkeeper/` — `metrics.py` (OLS slope + t-based 95% CI + first/second-half + seeded bootstrap), `aggregate.py` (multi-seed aggregation over episode index, per-episode mean±CI, pooled + per-seed slope), `compare_memory.py` (with-memory vs no-memory; `baseline`/`main`/`analyze-only` backends → `comparison.json`/`COMPARISON.md`/plot/`metrics.json`). See **H5a**. **Re-ran gates:** `run_all.py` 25/25, `baselines.py` 8/8 (−0.012/+0.047/+0.461/+1.000, gap 1.012, ratio 0.461), `solve.py` seeds 0-9 = +1.000. **New results:** analyze-only on seed-42 `model_compare` → **probe-efficiency slope significant for haiku (−0.42 [−0.78,−0.05]) and sonnet (−0.67 [−1.17,−0.17])**, score slopes ns (saturation) — quantitatively confirms R2; baseline with/no-memory proxy demo (10 seeds × 8 ep) → level gap 100 vs 45.46, flat slopes (CIs span 0). **R1 reviewed and DEFERRED** by owner (tests/docs stay local-only; `.gitignore` negation drafted+verified then reverted). **No game-behavior change** (only the pre-existing doc-rename line in `modelkeeper.py`).
- **2026-06-20 (results write-back + re-verification):** ran the full `MODELKEEPER_TESTING_GUIDE.md` orchestration this session — committed the engine as `5d06997`, then launched haiku/sonnet/opus as worktree-isolated model-pinned subagents (10 ep each, seed 42) → `results/modelkeeper/model_compare/s42_20260620-145453/`. **Verified:** A4 integrity guard → `validation.json overall_status=valid` (all 30 logged scores match saved `ep<N>_final.txt` transcripts); cross-checked the H5 table against `comparison.json` (exact match). Enriched H5 with full per-episode score/probe sequences + deliverable-artifact list. Corrected H3's stale "working tree clean" claim: `modelkeeper.py` + `README.md` carry 1 uncommitted doc-rename line each (no engine-logic change, per `git diff`). **Open (unchanged):** R1 (git-ignored tests/docs), R2 (no depth-1 accuracy headroom → hard variant H8), R3 (generator fallback).
- **2026-06-20 (verification + docs + comparison):** applied 3 root-cause fixes to `modelkeeper.py`; added `tests/` + `baselines.py` + `solve.py` + `README.md` + `CHANGELOG_VERIFICATION.md` + `results/modelkeeper/REPORT.md` + `MODELKEEPER_TESTING_GUIDE.md`. **Verified:** `run_all.py` 25/25, `baselines.py` 8/8 (ladder −0.01/+0.05/+0.46/+1.00), `solve.py` seeds 0-9 = 1.000. 3-model comparison (seed 42, `valid`): sonnet learns both axes, opus saturates (~91), haiku weak (9.8). **Open:** R1 (git-ignored tests/docs), R2 (no depth-1 accuracy headroom → hard variant), R3 (generator fallback).
- **2026-06-20 (doc refactor):** folded the canonical handoff into this file as **Part I** (was a brief §0 progress note); renamed the file to lowercase `modelkeeper_game_design.md` and updated its references in `modelkeeper.py` and `README.md`. No code-behavior change.

---

# Part II — Game Design Specification

> The authoritative rules (unchanged). Part I above references these by section number.

## 1. Premise

You are a **Model Auditor**. You never touch reality directly. In front of you is a console wired to a hidden machine that stands in for some slice of the world. You can feed the console signals and watch the readouts it produces, but the machine's internals — what it is, how it is wired, what each part does — are sealed. Your job is to figure out how the machine behaves well enough to **predict** what it will do next.

This keeps the original Modelkeeper idea — *you act on a model of a hidden reality, not the reality itself* — but makes that idea concrete and testable. The narrative is flavor on top of a precise machine; the flavor never tells you how the machine works. Everything you learn, you learn by poking it.

---

## 2. What a single play feels like

One play (an **episode**) has three phases:

1. **Probe.** You have a limited number of probes. Each probe sets the console's inputs and advances the machine one step, then shows you the readouts. You experiment — change inputs, repeat inputs, reset the machine — to work out how the readouts depend on what you do and on what you did before.
2. **Exam.** When you stop probing (or run out), the console reveals a fresh sequence of inputs you have *not* run, and asks: what will the readouts be for each step of this sequence? The machine starts the exam from a clean reset.
3. **Score.** You commit your prediction. The machine then actually runs the sequence, and your score is how many readout values you got right. You get no feedback during the exam, so you cannot guess-and-check; you have to commit a working theory of the machine.

That is the whole game. The interesting part is everything you have to figure out in phase 1 to do well in phase 2.

---

## 3. The hidden world: a clocked machine

The hidden machine is a small **clocked circuit**. It runs in discrete steps (ticks). On each tick it reads the inputs you set and produces a set of readouts.

- **Inputs.** A handful of input channels, `I_1 … I_m`, each holding a small integer (in the simplest setting, just 0 or 1). You set these.
- **Nodes.** Inside, a few processing units (nodes). Each node takes some sources — inputs and/or other nodes — and produces one value per tick. The number of nodes, what they do, and how they're wired is randomized and hidden.
- **Readouts.** Some nodes are wired to the console as visible **readouts** (`O_1, O_2, …`); these are all you ever see. Other nodes may be **hidden** — they shape the readouts but are never shown directly. (Hidden nodes are an advanced setting; in the simplest setting every node is a readout.)

The crucial property: the readouts are an *interpreted view* of the machine, not the machine. A hidden node sitting between an input and a readout means the thing you observe is downstream of something you can't see — exactly the Modelkeeper premise, made mechanical.

---

## 4. The four mechanisms

Every machine is built from the same small library of four node types. This library never changes from play to play — it is the stable "physics" of the world. What changes is which of them appear, how many, how they're wired, and their settings.

The four were chosen to be **distinguishable by experiment but easy to confuse if you're careless** — each one fails a naive theory in a different way.

**GATE — a threshold.**
Adds up its sources (some sources may count negatively) and outputs 1 if the total reaches a hidden threshold, otherwise 0. It reacts instantly and only ever goes up when you push its sources up. Depending on the threshold it can behave like "any input is enough," "all inputs needed," or "a majority needed." *Tell: instantaneous and monotone — more never gives you less.*

**MIX — a parity/remainder.**
Adds up its sources and outputs the remainder when divided by the alphabet size (with 0/1 inputs, this is parity — odd vs. even count of 1s). It reacts instantly, but it is **not** monotone: flipping any single source always flips the output. *Tell: every single change to an input toggles it, with no sense of "more" or "less."*

**HOLD — a memory with a ceiling.**
Carries an internal level. Each tick, if its driver is on, the level climbs by one (up to a cap); if the driver is off, the level falls by one (down to zero). The readout is the level. *Tell: it depends on history, ramps up or down gradually, and saturates at a ceiling — repeating the same input keeps changing the output until it plateaus.*

**ECHO — a delay.**
Outputs whatever one of its sources was on the previous tick. *Tell: a one-step lag — a change you make shows up one tick later, and a single pulse comes back one tick after you sent it.*

Two of these (GATE, MIX) are **instantaneous** — they depend only on the current tick. Two (HOLD, ECHO) are **stateful** — they depend on the past, which is why resetting the machine matters and why repeating an input is informative.

---

## 5. How a tick resolves (exact rules)

These are the precise behaviors, so that the same value is always produced for the same situation. Let `val(s, t)` be the value at tick `t` of a source `s`, with `val(s, t < 0) = 0` (i.e. "before the start" and "just after a reset" count as 0). Let `k` be the alphabet size (2 in the simplest setting).

```
GATE(sources, signs σ_i, threshold θ):
    total = Σ_i  σ_i · val(source_i, t)
    out   = 1 if total ≥ θ else 0          # range {0,1}

MIX(sources):
    out   = ( Σ_i val(source_i, t) ) mod k # range {0 … k-1}; parity when k=2

HOLD(driver, cap):     # has internal `level`, set to 0 by RESET
    if val(driver, t) ≥ 1:  level = min(level + 1, cap)
    else:                    level = max(level - 1, 0)
    out = level                            # range {0 … cap}

ECHO(source):          # delay of 1 tick
    out = val(source, t - 1)               # range = range of its source
```

**Order within a tick.** Instantaneous nodes must be evaluated after the sources they read, so the machine evaluates nodes in dependency order; ECHO reads the *previous* tick (from stored history) and so never causes a circular dependency. Machines are always built so this ordering exists (no instantaneous loops). After all nodes are evaluated, the tick's values are stored (so ECHO can read them next tick) and HOLD levels are kept.

**RESET.** Sets every HOLD level to 0 and clears the stored history (so ECHO sees 0 on the next tick). It does not advance the clock. It returns the readouts as they stand with zero state.

---

## 6. The player's interface

During the probe phase the console accepts three commands:

```
PROBE <v1> <v2> ... <vm>   set the inputs, advance ONE tick, show readouts. Uses 1 probe.
RESET                      clear the machine's memory, show baseline readouts. Free.
STATUS                     show probes used / probes remaining. Free.
```

A probe replies with the readouts in fixed order, e.g. `OK  O1=1 O2=2  probes_left=14`. RESET is free and unlimited on purpose — discovering *that resetting matters* (and using it to isolate the stateful parts) is part of learning the game.

When probing ends, the console presents the exam:

```
EXAM (runs from a fresh RESET)
  step 0: <inputs>
  step 1: <inputs>
  ...
  step L-1: <inputs>
Predict the readouts for every step, in order.
```

The player answers with one row of readout values per step. That answer is the play's deliverable.

---

## 7. Winning and scoring

The machine then actually runs the exam sequence and compares. The **score is the fraction of readout values predicted correctly** across all steps and all readouts. Perfect prediction is the win; there is no other objective and no luck in it — without feedback during the exam, the only way to score well is to genuinely understand the machine.

To make scores comparable across machines that have different numbers of possible readout values, the raw fraction is also reported normalized against blind guessing:

```
chance      = average over readouts of (1 / number_of_possible_values_for_that_readout)
normalized  = (raw_fraction − chance) / (1 − chance)
```

So 0 means "no better than guessing" and 1 means "perfect," regardless of how large the readout ranges are.

There is no "death" or hard failure — a play simply yields a score between guessing and perfect. A play can be *cheap* (few probes used) or *expensive* (many), and probes-used is reported alongside the score, because solving a machine in fewer probes is the better performance.

---

## 8. One game, many fresh instances

A key design choice: **every episode uses the same game, but a brand-new instance of it.** The four mechanisms and all the rules above are fixed forever. What is randomized each episode is the specific machine — how many nodes, which mechanisms, how they're wired, the thresholds and caps, which nodes are hidden, and the exam sequence.

This is deliberate. If the literal machine were identical every time, the best strategy would be to memorize one winning answer — which says nothing about understanding. By keeping the *rules* constant but the *instance* new, a player can only do better over time by abstracting the rules ("this is the kind of world made of gates, parities, memories, and delays, and here's how to tell them apart efficiently") and bringing that understanding to a machine they have never seen. The first play is expensive because you know neither the mechanisms nor how to probe for them; later plays get cheaper as you learn the mechanisms and a good probing routine — but they never become free, because each new machine's exact wiring still has to be worked out fresh.

That two-part structure — a fixed set of mechanisms to learn once, plus fresh wiring to solve every time — is what makes the game *learnable but not memorizable*, which is the whole point of using it to study improvement over repeated play.

---

## 9. How an instance is built

Each episode's machine is generated from a seed, so it is reproducible (the same seed always yields the same machine and exam). Generation:

1. Pick the number of inputs and the number of nodes (within the configured ranges).
2. For each node, pick one of the allowed mechanisms, choose its sources (from the inputs, and — in advanced settings — from earlier nodes, always wired so no instantaneous loop can form), and sample its settings (threshold, sign pattern, or cap).
3. Choose which nodes are visible readouts (in the simplest setting, all of them).
4. Generate a random exam sequence the player will not be allowed to run during probing.

Two guardrails keep instances fair and meaningful:

- **Certified solvable.** A reference solver that follows the intended probing routine (below) must be able to reach near-perfect prediction within the configured certification budget; otherwise the instance is regenerated. For variants whose player-facing budget is lower than the certification budget, this guarantees the hidden machine is identifiable in principle without making the full reference routine available inside one episode.
- **Non-trivial.** The exam's correct answer must actually vary (at least one readout changes during the exam, and isn't constant), so that a lazy "always predict the same value" strategy cannot win. This guarantees no episode is trivially easy.

---

## 10. The intended way to read the machine

The game is solvable by a clean experimental routine. A player isn't told this — discovering it is part of getting good — but it defines what "understanding the machine" means and underpins the difficulty calibration:

1. **Reset and read the baseline.**
2. **Sweep single inputs.** Reset, raise one input alone, step once. This reveals which readouts each input touches.
3. **Repeat an input.** Reset, hold an input on for several steps. A readout that ramps and then plateaus is a HOLD (and the plateau reveals its cap); readouts that stay put under repetition are instantaneous.
4. **Toggle an input on and off.** A MIX flips on every toggle; a GATE moves only in one direction as you add inputs.
5. **Send a one-step pulse.** Set an input on for a single step then off. An ECHO answers one tick late.
6. **Assemble the picture** — which mechanism each readout is, and its settings — then simulate the exam in your head and predict.

A player who internalizes this routine across episodes spends far fewer probes on each new machine, which is precisely the improvement the game is meant to surface.

---

## 11. Difficulty controls

The game has a few dials. They let it be tuned to sit in the "not too hard, not too easy" band for both humans and AI players, and to define easy/hard variants.

| Dial | What it changes | Easy → Hard |
|---|---|---|
| Alphabet size | how many values inputs/readouts can take | 2 (binary) → 3+ |
| Number of inputs | size of the space to probe | 2 → 3–4 |
| Number of nodes | how many mechanisms to untangle | 3–4 → 4–6 |
| Depth | whether nodes feed only readouts, or feed other (possibly **hidden**) nodes | all visible → hidden intermediate nodes |
| Probe budget | how much experimenting you're allowed | generous → tight |
| Exam length | how many steps you must predict | short → long |
| Noise | whether readouts are occasionally corrupted | off → small chance of corruption |

The most important of these is **depth**. At depth 1, every node is a readout and is fed directly by inputs — the machine is fully visible and the routine in Section 10 reads it cleanly. At depth 2, a node can feed another node, and the in-between node may be **hidden**, so a readout is the downstream shadow of something you can't observe. That is the hardest, most on-theme variant: you are inferring an unseen part of reality from its effects. Noise is kept off by default, since it muddies the clean "right/wrong per readout" scoring; it's reserved for an advanced variant.

A reasonable baseline instance: binary inputs, two inputs, three or four nodes, all visible, about twenty probes, an eight-step exam, no noise. This is hand-solvable by a person in a few minutes once they understand the mechanisms, which is the level we want.

---

## 12. A full worked example

A small machine to show the rules end to end.

- Inputs: `I1, I2` ∈ {0, 1}.
- `X = GATE` over (I1, I2), both counting positively, threshold 2. (So X = 1 only when both inputs are 1.)
- `Y = HOLD` driven by I2, cap 3.
- Both X and Y are visible: `O1 = X`, `O2 = Y`.

A probing run, starting from RESET (Y's level = 0):

| Inputs (I1, I2) | X | Y | why |
|---|---|---|---|
| (1, 1) | 1 | 1 | both inputs high → X=1; I2 on → level 0→1 |
| (1, 1) | 1 | 2 | level 1→2 |
| (0, 1) | 0 | 3 | not both high → X=0; I2 on → level 2→3 |
| (0, 1) | 0 | 3 | level already at cap 3 → stays |
| (0, 0) | 0 | 2 | I2 off → level 3→2 |

From this a player infers: X is instantaneous and only fires when both inputs are on (a gate); Y climbs while I2 is on, saturates at 3, and falls when I2 is off (a memory with a ceiling).

The exam (run from a fresh RESET): `(1,1), (1,1), (1,1), (1,1), (0,0), (0,0)`.

Correct readouts:

| step | inputs | X | Y |
|---|---|---|---|
| 0 | (1,1) | 1 | 1 |
| 1 | (1,1) | 1 | 2 |
| 2 | (1,1) | 1 | 3 |
| 3 | (1,1) | 1 | 3 (capped) |
| 4 | (0,0) | 0 | 2 |
| 5 | (0,0) | 0 | 1 |

A player who missed the saturation predicts Y = 4 at step 3 and loses a cell; one who thought Y was instantaneous gets Y badly wrong throughout. That is the kind of discrimination the game is built to produce: small misunderstandings of a mechanism cost specific, identifiable points.

---

## 13. Design rationale in brief

- **Black box by construction.** Nothing about the mechanisms is stated; they can only be learned by interaction. The narrative theming is kept abstract on purpose, so a clever player can't shortcut discovery by reasoning from real-world priors about "cities" or "ecosystems" — the rules are arbitrary machinery that must be probed.
- **Predict, don't steer.** The objective is to predict the machine's behavior, not to drive it to a target state, because prediction can be scored exactly and can't be brute-forced by trial and error — it forces the player to commit a real theory.
- **Compact and deterministic.** A machine is a few small integers per tick, and identical seeds give identical machines. This keeps each play short and makes the same instance reproducible — which is what lets the same game be replayed fairly to see whether a player improves.

---

## 14. Design choices (resolved)

Both originally-open questions are now settled and reflected in the implementation:

1. **Objective: prediction only.** No "reach a target readout" variant — prediction scores cleanly and can't be brute-forced. Implemented as the per-cell `predict_<value>` exam (§0.2).
2. **Standard game is fully visible (depth-1); hidden intermediate nodes are the hard variant.** The implemented baseline is depth-1, all nodes visible (§0.3). The depth-2 / hidden-node hard variant is now **implemented** as `modelkeeper_hard` (§15).

---

## 15. Hard variant — `modelkeeper_hard` (implemented)

`modelkeeper_hard` restores cross-episode **accuracy** headroom for strong models while
keeping the same black-box interface and fairness guarantees. It is the same
`ModelkeeperGame` class selected by `mode="hard"` (mirroring `patch_reality_hard`); the
simulation engine is unchanged — `MachineSim` already evaluates every node and exposes only
`readout_ids`, and `_topo_order` already rejects instantaneous cycles, so hidden nodes and
node→node wiring needed no engine edit.

**Config (`HARD_CONFIG`).** `k=3`, 3 inputs, 4–6 nodes, `depth=2`, `hidden_allowed=True`,
`probe_budget=32`, `exam_len=10`, `hold_caps=(2,3)`.
`answer_max()=4`, so the exam menu is the constant `predict_0..predict_3` for every
instance (no mechanism leak).

**The constrained hard family (key design choice).** A visible readout that uses a hidden
node is *only* built as a **GATE/MIX (instantaneous) readout over a subset of inputs + one
dedicated hidden HOLD/ECHO (stateful) helper** fed by inputs. Rationale:
- *Stateful → instantaneous is non-collapsible to depth-1* (a depth-1 GATE/MIX is
  memoryless; the composite is not), so every episode genuinely requires the hidden node —
  the "difficulty guardrail" is free. It also rules out MIX∘MIX / GATE∘GATE absorption,
  which would secretly be trivial.
- *Each helper feeds exactly one readout (no sharing)*, so the reference solver can fit each
  readout independently and remain sound + complete.
- Composite (hidden-dependent) columns dominate the exam (≥⅔), with at most one plain
  depth-1 readout, so an "easy" mental model cannot score well.

**Reference solver (`HardReferenceSolver`).** Runs a **curated ~32-tick battery** — per-input
ramps (`ramp_len = max_cap+2`, exposes HOLD + cap), per-input pulses (ECHO + one-tick lag),
and a small combo set that separates GATE/MIX — *not* the full `k^m=27` sweep, so it fits a
tight budget. Each readout is fit in two stages: first a plain depth-1 single-node candidate;
on failure, escalate to a composite (top GATE/MIX over inputs + one HOLD/ECHO helper, helper
columns memoized). It returns per-readout mini-Machines; the exam is predicted by simulating
them. The battery size (32) is both the certification budget and the player-facing budget:
enough for the intended diagnostic routine, but still ≪ exhaustive black-box mapping.

**Generation guardrails.** A machine is served only if (a) some readout varies, (b) the plain
depth-1 solver (given unlimited probes) **cannot** reproduce the exam (load-bearing hidden
node), and (c) the hard solver predicts the exam **exactly** within the 32-probe
certification budget. The fallback never serves an uncertified instance (it degrades to a
depth-1-style instance the hard battery still certifies). Acceptance ≈ 1.7 attempts/episode;
per-episode generation+solve ≈ 14 ms.

**Calibration (offline, LLM-free; `python baselines.py hard`).** 50-seed ladder:
`random −0.02 · constant +0.02 · single_sweep +0.13 · depth1_solver +0.24 · heuristic +1.00`.
Restored-headroom gate: `depth1_solver ≤ 0.60` while `heuristic ≥ 0.95` (gap **0.76**);
`single_sweep/heuristic = 0.13`. `solve.py hard` self-test = 1.000 over seeds 0–9 using the
32-probe routine exposed to player episodes.
A with-memory vs no-memory LLM run is the recommended follow-up to confirm strong models no
longer saturate at episode 1.

## 16. Diagnostic feedback-ablation variants — `modelkeeper_hard_dense` / `modelkeeper_hard_teacher` (NOT official)

**Status:** implemented + registered + gate-verified, 2026-06-24. **These are not official
benchmark variants** and are excluded from the official calibration ladder. They are a
controlled A/B instrument to answer one diagnostic question: when strong models fail to show
a learning curve on `modelkeeper_hard`, is the hidden depth-2 rule *intrinsically* too hard,
or is **final-only exam feedback too sparse** for 10-episode (and within-episode) learning?

**What is identical to `modelkeeper_hard`.** Both variants are the same `ModelkeeperGame` with
`mode="hard"` and the same `HARD_CONFIG` — same per-`(seed, episode)` machine generation, same
solvability/load-bearing guardrails, same scoring formula (§7), same probe budget (40), same
exam (10 steps), same `predict_0..predict_3` answer menu, same valid actions, same `MAX_TURNS`,
same probe-phase replies, same `reward`/`done`/`turn_count`/`info`. `modelkeeper_hard`'s entire
player-visible surface is **byte-identical** to before this change (verified: full
intro+probe+reset+status+exam+all-cells+final surface equals `git HEAD` across standard+hard ×
zh/en × 8 seeds). The probe phase is untouched and score stays hidden (0) during probing.

**The only difference — EXAM-phase feedback density.** A new game-level enum
`ModelkeeperGame(mode="hard", feedback_mode=…)` selects it (a *game* knob, not a `Config` dial —
it does not touch generation or scoring):

| Game ID | `feedback_mode` | After each completed exam row (one step's full readouts) |
|---|---|---|
| `modelkeeper_hard` | `final_only` | nothing — official behavior (feedback only at finalize) |
| `modelkeeper_hard_dense` | `row_score` | `row_correct` (this step) + `cumulative_correct` (so far) |
| `modelkeeper_hard_teacher` | `row_answer` | the above **plus** the correct readout values for the step |

Example (`row_answer`, en): a block of `ROW FEEDBACK` / `step: 3` / `row_correct: 2/4` /
`correct_row: O1=1  O2=0 …` / `cumulative_correct: 9/16` / `continue predicting the next step.`
(zh uses `【作答反馈】` / `拍次` / `本拍正确` / `正确读数` / `累计正确` / `请继续预测下一拍。`).
Feedback is **additional observation text only** — it never alters reward (stays 0 on every
non-final exam cell), score, `done`, `turn_count`, generation, or the action menu. The **last**
exam row is not given a standalone feedback block; it flows straight into the unchanged
`_finalize()` (whose report already states cumulative correctness), so the official scoring
path is untouched.

**Fairness / leakage discipline (unchanged from §13/H2).** `row_score` reveals only correctness
*counts* — never the correct values, never which output was wrong. `row_answer` may reveal the
correct numeric row **only**, because it is an explicit teacher/supervised upper bound; those
values are already in the `predict_0..predict_3` menu, so they leak nothing the menu doesn't.
Neither variant ever names a mechanism, hidden node, wiring, range, threshold, cap, sign, or
cause. The intro/exam-intro *describe* the feedback policy for these variants (so a player can
use the signal) but contain no mechanism words; for `final_only` the intro text is unchanged.

**Implementation.** `modelkeeper.py`: `feedback_mode` ctor arg (validated, default `final_only`,
stored before `reset()`); `_render_row_feedback(step)` + `_feedback_notice(default_zh, default_en)`
helpers; a row-boundary branch in `_step_exam`; the two intros route their "no feedback" sentence
through `_feedback_notice` (returns the original literal for `final_only` → byte-identical).
Registered in `play.py`/`main.py` (incl. `--game` choices) mirroring the two-entry hard pattern.
`baselines.py`/`solve.py` need no change (they pass `config=HARD_CONFIG`, so the hard ladder
already certifies these variants' machine/scoring). **Gates:** `tests/test_feedback_modes.py`
adds §7 (9 gates: final_only silent, dense shows counts/hides answers, teacher reveals row,
count accuracy, probe-phase silent + score hidden, score-equivalence across modes, menu identical,
zh no-English-leak, no forbidden tokens); `test_fairness.py` §3.1 extended to scan the dense+teacher
surfaces. `run_all.py` → **35/35 green** (26 official MUST + 9 §7 diagnostic). Like the rest of
`tests/`, `test_feedback_modes.py` is git-ignored / local-only (R1).

## 17. Expert variant — `modelkeeper_expert`

`modelkeeper_expert` is a separate, human-playable step above hard. It preserves the public
surface (3 ternary inputs, 2 readouts, 40 probes, 10 exam ticks, final-only feedback) while
using a bounded shared depth-3 grammar. A hidden two-input positive GATE/MIX driver feeds a
hidden ECHO or cap-2 HOLD state shared by both readouts. One randomly positioned readout is
a reversible MIX anchor; the other is a positive GATE/MIX view and has a 40% chance of also
using one direct hidden HOLD/ECHO helper. Arbitrary DAGs, state-to-state chains, negative
hidden gates, and multiple extra helpers remain forbidden for human tractability.

The `ExpertReferenceSolver` fits both readouts jointly from forty reset-delimited single-input,
paired-input, and graded probes. Generation accepts only instances whose transcript-consistent
expert candidates agree on the complete exam, whose complex dependencies are load-bearing,
and which do not collapse to the former hard solver. Expert generation never falls back to an
easier family. The old hard ID remains available; Webplay's lobby card points to expert while
the direct hard URL remains supported.
