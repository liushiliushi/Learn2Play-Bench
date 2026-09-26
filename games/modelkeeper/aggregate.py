"""Aggregate learning curves over the EPISODE INDEX across many seeds/runs.

Given several `scores.jsonl` files — one per seed (or per model/condition) — this
collapses them by episode index so you can see the *average* curve and whether a
trend holds across seeds rather than in a single lucky run.

Two complementary views (both reuse `metrics.py`):

  * by_episode : for each episode index, mean / stdev / n / t-based 95% CI across
                 runs (the curve with a confidence band).
  * metrics    : 'pooled'   = the slope/CI/half-split of the across-seed MEAN curve;
                 'per_seed'  = mean/stdev of each run's own slope + a one-sample
                               t-CI on the mean per-seed slope (is learning
                               *consistent* across seeds?).

The seed/label for each file is parsed from its path (the JSONL carries no seed
field): the `_s<seed>_` token used by `main.py` run dirs, else an `s<seed>` token
anywhere, else the immediate parent directory name.

Run:
    python games/modelkeeper/aggregate.py GLOB [GLOB ...] [--out DIR] [--plot]
    python games/modelkeeper/aggregate.py --dir RUN_DIR [--plot]
"""

import argparse
import glob as globmod
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import metrics  # noqa: E402  (sibling module)


# ── run discovery & labelling ────────────────────────────────────────────────

def _label_for(path):
    """Derive a seed/condition label from a scores.jsonl path."""
    parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
    m = re.search(r"_s(\d+)_", parent)          # main.py: '<slug>_s<seed>_<ts>'
    if m:
        return f"s{m.group(1)}"
    m = re.search(r"s(\d+)", parent)            # e.g. 'seed7' / 's7'
    if m:
        return f"s{m.group(1)}"
    return parent                                # e.g. model_compare '<model>'


def discover_runs(inputs, recurse_dir=None):
    """Return a sorted, de-duplicated list of (label, path) for every matched
    scores.jsonl. `inputs` may be globs or direct paths; `recurse_dir` is searched
    for **/scores.jsonl."""
    paths = []
    for pat in inputs or []:
        paths.extend(globmod.glob(pat, recursive=True))
    if recurse_dir:
        paths.extend(globmod.glob(os.path.join(recurse_dir, "**", "scores.jsonl"),
                                  recursive=True))
    seen, runs = set(), []
    for p in sorted(paths):
        ap = os.path.abspath(p)
        if ap in seen or not os.path.isfile(p):
            continue
        seen.add(ap)
        runs.append((_label_for(p), p))
    return runs


# ── per-episode aggregation ──────────────────────────────────────────────────

def aggregate_by_episode(runs, metric):
    """Collapse runs by episode index. Runs lacking `metric` contribute nothing
    (probes are optional). Returns None if no run has the metric."""
    per_ep = {}
    labels = []
    used = 0
    for label, path in runs:
        if not metrics.has_metric(path, metric):
            continue
        used += 1
        labels.append(label)
        eps, vals = metrics.load_series(path, metric)
        for e, v in zip(eps, vals):
            per_ep.setdefault(e, []).append(v)
    if used == 0:
        return None
    rows = []
    for e in sorted(per_ep):
        vals = per_ep[e]
        n = len(vals)
        mean = sum(vals) / n
        if n >= 2:
            sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))
            sem = sd / math.sqrt(n)
            tc = metrics.t_crit_95(n - 1)
            lo, hi = mean - tc * sem, mean + tc * sem
        else:
            sd = sem = None
            lo = hi = mean
        rows.append({"episode": e, "n": n, "mean": mean, "stdev": sd,
                     "sem": sem, "ci_low": lo, "ci_high": hi, "values": vals})
    return {"metric": metric, "per_episode": rows, "n_runs": used, "labels": labels}


# ── slope/half-split aggregation ─────────────────────────────────────────────

def aggregate_metrics(runs, metric):
    """'pooled' metrics on the across-seed mean curve + a 'per_seed' summary of
    each run's own slope and half-split (consistency across seeds)."""
    by_ep = aggregate_by_episode(runs, metric)
    if by_ep is None:
        return None
    # pooled: metrics on the mean-across-seeds curve
    eps = [r["episode"] for r in by_ep["per_episode"]]
    means = [r["mean"] for r in by_ep["per_episode"]]
    pooled = metrics.compute_metrics(eps, means, metric=metric)

    # per_seed: each run's own slope + half-split diff
    per_run = []
    for label, path in runs:
        if not metrics.has_metric(path, metric):
            continue
        e, v = metrics.load_series(path, metric)
        r = metrics.compute_metrics(e, v, metric=metric)
        per_run.append({"label": label,
                        "slope": r["ols"]["slope"],
                        "halfdiff": r["half_split"]["diff"],
                        "r_squared": r["ols"]["r_squared"]})
    slopes = [r["slope"] for r in per_run if r["slope"] is not None]
    halfs = [r["halfdiff"] for r in per_run if r["halfdiff"] is not None]
    summary = {"n_runs": len(per_run), "per_run": per_run,
               "slope_mean": None, "slope_stdev": None,
               "slope_ci_low": None, "slope_ci_high": None, "slope_t_crit": None,
               "halfdiff_mean": None, "halfdiff_stdev": None}
    if slopes:
        sm = sum(slopes) / len(slopes)
        summary["slope_mean"] = sm
        if len(slopes) >= 2:
            sd = math.sqrt(sum((s - sm) ** 2 for s in slopes) / (len(slopes) - 1))
            tc = metrics.t_crit_95(len(slopes) - 1)
            sem = sd / math.sqrt(len(slopes))
            summary.update(slope_stdev=sd, slope_t_crit=tc,
                           slope_ci_low=sm - tc * sem, slope_ci_high=sm + tc * sem)
    if halfs:
        hm = sum(halfs) / len(halfs)
        summary["halfdiff_mean"] = hm
        if len(halfs) >= 2:
            summary["halfdiff_stdev"] = math.sqrt(
                sum((h - hm) ** 2 for h in halfs) / (len(halfs) - 1))
    return {"pooled": pooled, "per_seed": summary}


# ── assembly + output ────────────────────────────────────────────────────────

def build_aggregate(runs, metric_list=("score", "probes")):
    out = {"n_runs": len(runs), "labels": [l for l, _ in runs]}
    for metric in metric_list:
        out[metric] = {
            "by_episode": aggregate_by_episode(runs, metric),
            "metrics": aggregate_metrics(runs, metric),
        }
    return out


def plot_aggregate(agg, out_path):
    """Mean line + shaded 95% CI band vs episode (score; twin axis for probes)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sc = agg.get("score", {}).get("by_episode")
    pr = agg.get("probes", {}).get("by_episode")
    if not sc:
        return None
    eps = [r["episode"] for r in sc["per_episode"]]
    mean = [r["mean"] for r in sc["per_episode"]]
    lo = [r["ci_low"] for r in sc["per_episode"]]
    hi = [r["ci_high"] for r in sc["per_episode"]]

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(eps, mean, marker="o", linewidth=2, color="#2a7ae2", label="score (mean)")
    ax1.fill_between(eps, lo, hi, alpha=0.2, color="#2a7ae2")
    ax1.set_xlabel("Episode")
    ax1.set_ylabel("Normalized score (mean ± 95% CI)", color="#2a7ae2")
    ax1.set_xticks(eps)
    ax1.grid(alpha=0.3)
    if pr:
        peps = [r["episode"] for r in pr["per_episode"]]
        pmean = [r["mean"] for r in pr["per_episode"]]
        plo = [r["ci_low"] for r in pr["per_episode"]]
        phi = [r["ci_high"] for r in pr["per_episode"]]
        ax2 = ax1.twinx()
        ax2.plot(peps, pmean, marker="s", linewidth=2, color="#e8833a", label="probes (mean)")
        ax2.fill_between(peps, plo, phi, alpha=0.15, color="#e8833a")
        ax2.set_ylabel("Probes used (mean ± 95% CI)", color="#e8833a")
    plt.title(f"Modelkeeper — aggregate over {sc['n_runs']} runs")
    fig.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def write_aggregate(out_dir, agg, plot=False):
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "aggregate.json")
    with open(json_path, "w") as f:
        json.dump(agg, f, indent=2)
    png = None
    if plot:
        png = plot_aggregate(agg, os.path.join(out_dir, "aggregate_curve.png"))
    return json_path, png


def _render(agg):
    lines = [f"Aggregate over {agg['n_runs']} runs: {', '.join(agg['labels'])}"]
    for metric in ("score", "probes"):
        block = agg.get(metric, {})
        be = block.get("by_episode")
        mm = block.get("metrics")
        if not be:
            lines.append(f"  [{metric}] no run carried this metric")
            continue
        lines.append(f"  [{metric}] per-episode mean (n per ep up to {be['n_runs']}):")
        lines.append("    ep " + " ".join(f"{r['episode']:>2}" for r in be["per_episode"]))
        lines.append("    mu " + " ".join(f"{r['mean']:>2.0f}" for r in be["per_episode"]))
        pooled = mm["pooled"]["ols"]["slope"]
        ps = mm["per_seed"]
        lines.append(f"    pooled-curve slope={pooled:+.3f}/ep" if pooled is not None
                     else "    pooled-curve slope=n/a")
        if ps["slope_mean"] is not None:
            ci = (f" CI[{ps['slope_ci_low']:+.3f},{ps['slope_ci_high']:+.3f}]"
                  if ps["slope_ci_low"] is not None else "")
            lines.append(f"    per-seed mean slope={ps['slope_mean']:+.3f}/ep{ci} "
                         f"(stdev={ps['slope_stdev']:.3f})" if ps["slope_stdev"] is not None
                         else f"    per-seed mean slope={ps['slope_mean']:+.3f}/ep{ci}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Aggregate scores.jsonl over episode index across seeds/runs.")
    ap.add_argument("globs", nargs="*", help="globs/paths to scores.jsonl files")
    ap.add_argument("--dir", help="a run dir to search recursively for **/scores.jsonl")
    ap.add_argument("--out", help="output dir for aggregate.json (default: --dir or CWD)")
    ap.add_argument("--plot", action="store_true", help="also write aggregate_curve.png")
    args = ap.parse_args(argv)

    runs = discover_runs(args.globs, recurse_dir=args.dir)
    if not runs:
        ap.error("no scores.jsonl matched the given globs/--dir")
    agg = build_aggregate(runs)
    out_dir = args.out or args.dir or "."
    json_path, png = write_aggregate(out_dir, agg, plot=args.plot)
    print(_render(agg))
    print(f"\nwrote {json_path}" + (f" and {png}" if png else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
