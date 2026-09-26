"""With-memory vs no-memory comparison for Modelkeeper (plus generic N-condition
comparison via --analyze-only).

The EvolveBench thesis: a *learning* agent that carries memory of past episodes
should improve across episodes, while a memoryless agent stays flat. This driver
runs both conditions, collects each one's per-episode `scores.jsonl`, and emits a
comparison (`comparison.json` + `COMPARISON.md` + a curve plot) with slope /
half-split / CI metrics (via metrics.py) and multi-seed aggregation (aggregate.py).

Three backends so it runs with or without an API key:

  --backend baseline   No API. Drives episodes with baselines.py reference players
                       as proxies: with_memory ≈ player_heuristic (oracle / full
                       understanding), no_memory ≈ player_single_sweep (memoryless).
                       Fully reproducible; emits probes. NOTE: these are FIXED
                       strategies, so each condition's curve is flat by construction
                       — this exercises the pipeline and shows the with/no *level
                       gap*, it is not an LLM learning curve.

  --backend main       Needs OPENROUTER_API_KEY (or the harness's Anthropic
                       fallback). Subprocess `main.py --agent memory` (with_memory)
                       vs `--agent naive` (no_memory). main.py's scores.jsonl has
                       NO probes, so the efficiency axis is unavailable on this path.

  --analyze-only G...  No running. Aggregate + metric existing scores.jsonl (e.g.
                       the committed seed-42 model_compare data). Conditions are the
                       parent dir names unless remapped with --label-map.

Run:
    python games/modelkeeper/compare_memory.py --backend baseline --seeds 0,1,2,3,4,5,6,7,8,9 --episodes 8 --plot
    python games/modelkeeper/compare_memory.py --backend main --seeds 42 --episodes 10 --model anthropic/claude-... --plot
    python games/modelkeeper/compare_memory.py --analyze-only "results/modelkeeper/model_compare/**/scores.jsonl" --plot
"""

import argparse
import glob as globmod
import json
import os
import re
import subprocess
import sys
import time

THIS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(THIS, "..", ".."))
sys.path.insert(0, THIS)    # metrics, aggregate (siblings)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)  # games.modelkeeper.baselines
import metrics      # noqa: E402
import aggregate    # noqa: E402

WITH, NO = "with_memory", "no_memory"
PALETTE = ["#2a7ae2", "#e8833a", "#3aa657", "#c0392b", "#8e44ad", "#16a085"]


# ── small io helpers ─────────────────────────────────────────────────────────

def _write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _read_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    rows.sort(key=lambda r: r["episode"])
    return rows


def _pool(per_ep):
    """per_ep: {episode: [row,...]} -> pooled mean rows (score, probes if all present)."""
    pooled = []
    for ep in sorted(per_ep):
        group = per_ep[ep]
        ms = sum(r["score"] for r in group) / len(group)
        row = {"episode": ep, "score": round(ms, 2)}
        if all("probes" in r for r in group):
            row["probes"] = round(sum(r["probes"] for r in group) / len(group), 2)
        pooled.append(row)
    return pooled


# ── backend: baseline (no API) ───────────────────────────────────────────────

def run_baseline(seeds, episodes, out_dir):
    """with_memory ≈ heuristic oracle, no_memory ≈ memoryless single-sweep."""
    import random
    from games.modelkeeper.baselines import (  # lazy: only this backend needs game internals
        player_heuristic, player_single_sweep, _instance, _normalized_for, Config)
    cfg = Config()
    mapping = {WITH: player_heuristic, NO: player_single_sweep}
    conditions, runs_by_label = {}, {}
    for label, player in mapping.items():
        runs, per_ep = [], {}
        for seed in seeds:
            rng = random.Random(12345)  # matches baselines.py; these players are deterministic
            rows = []
            for ep in range(1, episodes + 1):
                machine, exam = _instance(seed, cfg, ep)
                pred, probes = player(machine, exam, rng)
                score = round(_normalized_for(seed, cfg, ep, pred) * 100)
                rows.append({"episode": ep, "score": score, "probes": probes})
                per_ep.setdefault(ep, []).append({"score": score, "probes": probes})
            seed_path = os.path.join(out_dir, label, f"s{seed}", "scores.jsonl")
            _write_jsonl(seed_path, rows)
            runs.append((f"s{seed}", seed_path))
        pooled = _pool(per_ep)
        _write_jsonl(os.path.join(out_dir, label, "pooled.jsonl"), pooled)
        conditions[label] = pooled
        runs_by_label[label] = runs
    return conditions, runs_by_label


# ── backend: main (LLM harness) ──────────────────────────────────────────────

def _locate_run_dir(stdout, agent, seed):
    m = re.search(r"Results\s*(?:→|->)\s*(.+)", stdout)
    if m:
        d = m.group(1).strip()
        if os.path.isdir(d):
            return d
    pat = os.path.join(ROOT, "results", "modelkeeper", agent, f"*_s{seed}_*")
    cands = [d for d in globmod.glob(pat) if os.path.isdir(d)]
    if not cands:
        raise RuntimeError(f"could not locate main.py run dir for agent={agent} seed={seed}")
    return max(cands, key=os.path.getmtime)


def run_main(seeds, episodes, model, out_dir):
    """`--agent memory` (with_memory) vs `--agent naive` (no_memory). No probes."""
    mapping = {WITH: "memory", NO: "naive"}
    conditions, runs_by_label = {}, {}
    for label, agent in mapping.items():
        runs, per_ep = [], {}
        for seed in seeds:
            cmd = [sys.executable, "main.py", "--game", "modelkeeper",
                   "--agent", agent, "--seed", str(seed), "--episodes", str(episodes)]
            if model:
                cmd += ["--model", model]
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"main.py failed (agent={agent}, seed={seed}); likely missing "
                    f"OPENROUTER_API_KEY.\n--- stderr tail ---\n{proc.stderr[-1500:]}")
            run_dir = _locate_run_dir(proc.stdout, agent, seed)
            rows = _read_jsonl(os.path.join(run_dir, "scores.jsonl"))  # {episode, score}
            seed_path = os.path.join(out_dir, label, f"s{seed}", "scores.jsonl")
            _write_jsonl(seed_path, rows)
            runs.append((f"s{seed}", seed_path))
            for r in rows:
                per_ep.setdefault(r["episode"], []).append(r)
        pooled = _pool(per_ep)
        _write_jsonl(os.path.join(out_dir, label, "pooled.jsonl"), pooled)
        conditions[label] = pooled
        runs_by_label[label] = runs
    return conditions, runs_by_label


# ── analyze-only (no running) ────────────────────────────────────────────────

def run_analyze_only(inputs, out_dir, label_map):
    runs = aggregate.discover_runs(inputs)
    if not runs:
        raise RuntimeError("no scores.jsonl matched the --analyze-only globs")
    runs_by_label = {}
    for autolabel, path in runs:
        parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
        label = label_map.get(parent) or label_map.get(autolabel) or parent
        runs_by_label.setdefault(label, []).append((autolabel, path))
    conditions = {}
    for label, lst in runs_by_label.items():
        sc = aggregate.aggregate_by_episode(lst, "score")
        pr = aggregate.aggregate_by_episode(lst, "probes")
        pr_mean = {r["episode"]: r["mean"] for r in pr["per_episode"]} if pr else {}
        pooled = []
        for r in sc["per_episode"]:
            row = {"episode": r["episode"], "score": round(r["mean"], 2)}
            if r["episode"] in pr_mean:
                row["probes"] = round(pr_mean[r["episode"]], 2)
            pooled.append(row)
        _write_jsonl(os.path.join(out_dir, label, "pooled.jsonl"), pooled)
        conditions[label] = pooled
    return conditions, runs_by_label


# ── shared assembly: comparison.json / COMPARISON.md / plot / metrics ─────────

def build_comparison(conditions):
    out = {}
    for label, rows in conditions.items():
        scores = [r["score"] for r in rows]
        has_probes = bool(rows) and all("probes" in r for r in rows)
        probes = [r["probes"] for r in rows] if has_probes else []
        out[label] = {
            "scores": scores,
            "probes": probes,
            "first_score": scores[0] if scores else None,
            "last_score": scores[-1] if scores else None,
            "delta_score": (scores[-1] - scores[0]) if scores else None,
            "mean_score": round(sum(scores) / len(scores), 2) if scores else None,
            "first_probes": probes[0] if probes else None,
            "last_probes": probes[-1] if probes else None,
            "delta_probes": (probes[-1] - probes[0]) if probes else None,
        }
    return out


def _cell(x):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:g}"
    return str(x)


def write_comparison_md(comparison, out_path, title):
    lines = [f"# {title}", "", "![curves](learning_curves.png)", "",
             "| Condition | Score first | Score last | dScore | Mean score | "
             "Probes first | Probes last | dProbes |",
             "|---|---|---|---|---|---|---|---|"]
    for label, e in comparison.items():
        lines.append(
            f"| {label} | {_cell(e['first_score'])} | {_cell(e['last_score'])} | "
            f"{_cell(e['delta_score'])} | {_cell(e['mean_score'])} | "
            f"{_cell(e['first_probes'])} | {_cell(e['last_probes'])} | "
            f"{_cell(e['delta_probes'])} |")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def plot_curves(conditions, out_path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax1 = plt.subplots(figsize=(9, 5.5))
    ax2 = ax1.twinx()
    any_probes = False
    for i, (label, rows) in enumerate(conditions.items()):
        color = PALETTE[i % len(PALETTE)]
        eps = [r["episode"] for r in rows]
        ax1.plot(eps, [r["score"] for r in rows], marker="o", linewidth=2,
                 color=color, label=f"{label} score")
        if rows and all("probes" in r for r in rows):
            any_probes = True
            ax2.plot(eps, [r["probes"] for r in rows], marker="s", linewidth=1.4,
                     linestyle="--", color=color, alpha=0.7, label=f"{label} probes")
    ax1.set_xlabel("Episode")
    ax1.set_ylabel("Normalized score (0-100)")
    ax1.grid(alpha=0.3)
    if conditions:
        ax1.set_xticks([r["episode"] for r in next(iter(conditions.values()))])
    ax2.set_ylabel("Probes used (dashed)" if any_probes else "")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="best", fontsize=8)
    plt.title(title)
    fig.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def append_metrics(conditions, runs_by_label, out_dir, bootstrap=False):
    out = {}
    for label, rows in conditions.items():
        eps = [r["episode"] for r in rows]
        score_m = metrics.compute_metrics(eps, [r["score"] for r in rows],
                                          metric="score", bootstrap=bootstrap)
        if rows and all("probes" in r for r in rows):
            probe_m = metrics.compute_metrics(eps, [r["probes"] for r in rows],
                                              metric="probes", bootstrap=bootstrap)
        else:
            probe_m = None
        agg = aggregate.aggregate_metrics(runs_by_label.get(label, []), "score") \
            if runs_by_label.get(label) else None
        out[label] = {"score": score_m, "probes": probe_m, "aggregate": agg}
        # also write a per-condition multi-seed aggregate.json
        if runs_by_label.get(label):
            full = aggregate.build_aggregate(runs_by_label[label])
            with open(os.path.join(out_dir, f"aggregate_{label}.json"), "w") as f:
                json.dump(full, f, indent=2)
    with open(os.path.join(out_dir, "metrics.json"), "w") as f:
        json.dump(out, f, indent=2)
    return out


def _render(comparison, metrics_json):
    lines = ["Condition           score f→l  Δ    mean   probe f→l  Δ    score-slope (95% CI)"]
    for label, e in comparison.items():
        m = metrics_json[label]["score"]
        ci = m["slope_ci"]
        slope = m["ols"]["slope"]
        sl = (f"{slope:+.2f}/ep" if slope is not None else "n/a")
        if ci["ci_low"] is not None:
            sig = "*" if ci["significant"] else " "
            sl += f" [{ci['ci_low']:+.2f},{ci['ci_high']:+.2f}]{sig}"
        pf = _cell(e["first_probes"]); pl = _cell(e["last_probes"]); dp = _cell(e["delta_probes"])
        lines.append(f"  {label:<18s} {_cell(e['first_score']):>4}→{_cell(e['last_score']):<4} "
                     f"{_cell(e['delta_score']):>4} {_cell(e['mean_score']):>6} "
                     f"  {pf:>3}→{pl:<3} {dp:>4}   {sl}")
    lines.append("  (* = slope CI excludes 0)")
    return "\n".join(lines)


def run_assembly(conditions, runs_by_label, out_dir, title, plot, bootstrap):
    comparison = build_comparison(conditions)
    with open(os.path.join(out_dir, "comparison.json"), "w") as f:
        json.dump(comparison, f, indent=2)
    write_comparison_md(comparison, os.path.join(out_dir, "COMPARISON.md"), title)
    metrics_json = append_metrics(conditions, runs_by_label, out_dir, bootstrap=bootstrap)
    png = None
    if plot:
        png = plot_curves(conditions, os.path.join(out_dir, "learning_curves.png"), title)
    return comparison, metrics_json, png


# ── CLI ──────────────────────────────────────────────────────────────────────

def _parse_label_map(items):
    out = {}
    for it in items or []:
        if "=" in it:
            k, v = it.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Modelkeeper with-memory vs no-memory comparison.")
    ap.add_argument("--backend", choices=["baseline", "main"],
                    help="how to generate episodes (omit with --analyze-only)")
    ap.add_argument("--analyze-only", nargs="+", metavar="GLOB",
                    help="aggregate existing scores.jsonl instead of running")
    ap.add_argument("--label-map", nargs="+", default=[], metavar="NAME=LABEL",
                    help="(analyze-only) remap a parent-dir name to a condition label")
    ap.add_argument("--seeds", default="42", help="comma-separated seeds (run backends)")
    ap.add_argument("--episodes", type=int, default=10)
    ap.add_argument("--model", default=None, help="(main backend) model id passed to main.py")
    ap.add_argument("--out", default=None, help="output dir (default: auto under results/modelkeeper/memory_compare)")
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--bootstrap", action="store_true")
    args = ap.parse_args(argv)

    if bool(args.backend) == bool(args.analyze_only):
        ap.error("provide exactly one of --backend or --analyze-only")

    ts = time.strftime("%Y%m%d-%H%M%S")
    if args.analyze_only:
        out_dir = args.out or os.path.join(ROOT, "results", "modelkeeper",
                                           "memory_compare", f"analyze_{ts}")
        os.makedirs(out_dir, exist_ok=True)
        conditions, runs_by_label = run_analyze_only(
            args.analyze_only, out_dir, _parse_label_map(args.label_map))
        title = "Modelkeeper — analysis of existing runs"
    else:
        seeds = [int(s) for s in args.seeds.split(",") if s.strip() != ""]
        stag = "-".join(map(str, seeds)) if len(seeds) <= 6 else f"{seeds[0]}-{seeds[-1]}_n{len(seeds)}"
        out_dir = args.out or os.path.join(ROOT, "results", "modelkeeper",
                                           "memory_compare", f"s{stag}_{args.backend}_{ts}")
        os.makedirs(out_dir, exist_ok=True)
        if args.backend == "baseline":
            conditions, runs_by_label = run_baseline(seeds, args.episodes, out_dir)
            title = (f"Modelkeeper — with-memory(oracle) vs no-memory(memoryless), "
                     f"baseline proxies, {len(seeds)} seeds")
        else:
            conditions, runs_by_label = run_main(seeds, args.episodes, args.model, out_dir)
            title = (f"Modelkeeper — with-memory(--agent memory) vs no-memory(--agent naive), "
                     f"{len(seeds)} seeds")

    comparison, metrics_json, png = run_assembly(
        conditions, runs_by_label, out_dir, title, args.plot, args.bootstrap)
    print(_render(comparison, metrics_json))
    print(f"\nwrote {out_dir}/ : comparison.json, COMPARISON.md, metrics.json"
          + (", learning_curves.png" if png else "")
          + (", aggregate_<condition>.json" if any(runs_by_label.values()) else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
