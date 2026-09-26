"""Learning-curve metrics for a single per-episode series (score or probes).

This module is game-agnostic: it consumes a `scores.jsonl` (one JSON object per
line, e.g. `{"episode": 1, "score": 48, "probes": 18}`) and reports, for a chosen
metric, the signals that distinguish a *learner* (improving across episodes) from
a *non-learner* (flat):

  * OLS linear slope vs episode index (+ R^2, standard error),
  * a t-based 95% confidence interval on that slope (the PRIMARY signal — a
    learner's slope CI excludes 0),
  * first-half-mean vs second-half-mean and their difference,
  * an optional seeded bootstrap CI on the half-split difference.

Stdlib only (no numpy/scipy). Run:

    python games/modelkeeper/metrics.py PATH/scores.jsonl [--metric score|probes]
                                        [--bootstrap] [--json-only]

It is an analysis tool, not a gate: it always exits 0.
"""

import argparse
import json
import math
import random
import statistics
import sys


# ── input ───────────────────────────────────────────────────────────────────

def load_series(path, metric="score"):
    """Read a scores.jsonl and return (episodes, values) sorted by episode.

    `metric` is "score" or "probes". `probes` is optional in the schema; if the
    requested metric is missing on any row, raise ValueError (the caller decides
    whether a series has that metric).
    """
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    rows.sort(key=lambda r: r["episode"])
    episodes, values = [], []
    for r in rows:
        if metric not in r:
            raise ValueError(f'metric "{metric}" not present in {path}')
        episodes.append(int(r["episode"]))
        values.append(float(r[metric]))
    return episodes, values


def has_metric(path, metric):
    """True iff every non-empty row in `path` carries `metric`."""
    try:
        load_series(path, metric)
        return True
    except (ValueError, KeyError):
        return False


# ── ordinary least squares (hand-rolled) ─────────────────────────────────────

def ols_fit(x, y):
    """Least-squares fit y = intercept + slope*x.

    Returns a dict with slope/intercept/r_squared/slope_stderr/residual_se/n.
    Slope/CI fields are None when undefined (n < 2, or all x equal).
    """
    n = len(x)
    out = {"n": n, "slope": None, "intercept": None, "r_squared": None,
           "slope_stderr": None, "residual_se": None}
    if n < 2:
        return out
    xbar = sum(x) / n
    ybar = sum(y) / n
    sxx = sum((xi - xbar) ** 2 for xi in x)
    syy = sum((yi - ybar) ** 2 for yi in y)
    sxy = sum((xi - xbar) * (yi - ybar) for xi, yi in zip(x, y))
    if sxx == 0:                      # all episode indices identical — no slope
        return out
    slope = sxy / sxx
    intercept = ybar - slope * xbar
    out["slope"] = slope
    out["intercept"] = intercept
    out["r_squared"] = (sxy * sxy) / (sxx * syy) if syy > 0 else 0.0
    # residual variance s^2 = SSE/(n-2); SSE = Syy - slope*Sxy
    if n > 2:
        sse = max(syy - slope * sxy, 0.0)
        s2 = sse / (n - 2)
        out["residual_se"] = math.sqrt(s2)
        out["slope_stderr"] = math.sqrt(s2 / sxx)
    else:                            # n == 2: line passes exactly through points
        out["residual_se"] = 0.0
        out["slope_stderr"] = 0.0
    return out


# ── two-sided 95% Student-t critical values (no scipy) ───────────────────────

_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
        8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
        14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
        20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
        26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042}


def t_crit_95(df):
    """Two-sided 95% t critical value.

    Exact (table) for df in 1..30 — the only regime this benchmark reaches
    (episodes <= ~30 -> slope df = n-2 <= 28; seed counts -> per-episode df small).
    For df > 30 falls back to the normal approx 1.96, which understates the true
    value by < 4% (e.g. df=40 truth ~2.021); documented, not silent. df < 1 -> inf.
    """
    if df < 1:
        return float("inf")
    if df <= 30:
        return _T95[df]
    return 1.96


# ── CIs ──────────────────────────────────────────────────────────────────────

def slope_ci(fit, level=0.95):
    """t-based CI on the OLS slope (PRIMARY learning signal).

    df = n - 2. `significant` is True when the interval excludes 0 (i.e. a
    statistically detectable trend at 95%). v1 fixes level at 0.95.
    """
    out = {"slope": fit["slope"], "df": None, "t_crit": None,
           "ci_low": None, "ci_high": None, "significant": False}
    n = fit["n"]
    se = fit["slope_stderr"]
    if fit["slope"] is None or se is None or n < 3:
        # n < 3 -> df < 1 -> CI undefined (a 2-point line has no residual spread)
        out["df"] = max(n - 2, 0)
        return out
    df = n - 2
    tc = t_crit_95(df)
    lo = fit["slope"] - tc * se
    hi = fit["slope"] + tc * se
    out.update(df=df, t_crit=tc, ci_low=lo, ci_high=hi,
               significant=(lo > 0 or hi < 0))
    return out


def half_split(values):
    """First-half mean vs second-half mean.

    Split rule: h = n // 2. first = values[:h], second = values[n-h:]. For odd n
    the single middle element is dropped so both halves are equal-sized (a cleaner
    difference-of-means). `diff` = second_half_mean - first_half_mean (>0 = later
    episodes better, for a "higher-is-better" metric like score).
    """
    n = len(values)
    out = {"n": n, "half_size": n // 2,
           "first_half_mean": None, "second_half_mean": None, "diff": None}
    h = n // 2
    if h < 1:
        return out
    first = values[:h]
    second = values[n - h:]
    fm = sum(first) / h
    sm = sum(second) / h
    out.update(first_half_mean=fm, second_half_mean=sm, diff=sm - fm)
    return out


def bootstrap_diff_ci(values, n_boot=2000, seed=1234, level=0.95):
    """Seeded percentile bootstrap CI on the half-split difference (SECONDARY).

    Resamples the value vector with replacement and recomputes half_split(...)
    ['diff'] each time. Reproducible (fixed `seed`). This characterizes the
    spread of the half-split gap; it is a heuristic (the split is order-dependent),
    so the slope t-CI above remains the primary inferential signal.
    """
    n = len(values)
    point = half_split(values)["diff"]
    out = {"diff_point": point, "n_boot": n_boot, "seed": seed,
           "ci_low": None, "ci_high": None}
    if n < 2 or point is None:
        return out
    rng = random.Random(seed)
    diffs = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        d = half_split(sample)["diff"]
        if d is not None:
            diffs.append(d)
    diffs.sort()
    alpha = 1.0 - level
    lo_i = int((alpha / 2) * len(diffs))
    hi_i = min(int((1 - alpha / 2) * len(diffs)), len(diffs) - 1)
    out["ci_low"] = diffs[lo_i]
    out["ci_high"] = diffs[hi_i]
    return out


# ── top-level ────────────────────────────────────────────────────────────────

def compute_metrics(episodes, values, metric="score", bootstrap=False):
    """Canonical metric dict for one per-episode series."""
    fit = ols_fit([float(e) for e in episodes], values)
    result = {
        "metric": metric,
        "n": len(values),
        "episodes": episodes,
        "values": values,
        "ols": fit,
        "slope_ci": slope_ci(fit),
        "half_split": half_split(values),
        "bootstrap_diff_ci": bootstrap_diff_ci(values) if bootstrap else None,
        "mean": statistics.mean(values) if values else None,
        "stdev": statistics.stdev(values) if len(values) >= 2 else None,
    }
    return result


# ── readable rendering + CLI ─────────────────────────────────────────────────

def _fmt(x, nd=3):
    return "n/a" if x is None else f"{x:+.{nd}f}"


def render(result):
    """A short human-readable block summarizing a metric dict."""
    lines = []
    m, n = result["metric"], result["n"]
    lines.append(f"metric: {m}   n={n}")
    mean, sd = result["mean"], result["stdev"]
    lines.append(f"  mean={_fmt(mean, 2)}   stdev={_fmt(sd, 2) if sd is not None else 'n/a'}")
    ols, ci = result["ols"], result["slope_ci"]
    if ols["slope"] is None:
        lines.append("  OLS slope: n/a (need >=2 episodes with varying index)")
    else:
        r2 = ols["r_squared"]
        lines.append(f"  OLS slope={_fmt(ols['slope'])} per episode   "
                     f"(R^2={r2:.3f}, SE={_fmt(ols['slope_stderr'])})")
        if ci["ci_low"] is None:
            lines.append("  95% slope CI: n/a (need >=3 episodes)")
        else:
            verdict = "SIGNIFICANT (excludes 0)" if ci["significant"] else "not significant (spans 0)"
            lines.append(f"  95% slope CI [{_fmt(ci['ci_low'])}, {_fmt(ci['ci_high'])}] "
                         f"(t_crit={ci['t_crit']:.3f}, df={ci['df']}) -> {verdict}")
    hs = result["half_split"]
    if hs["diff"] is None:
        lines.append("  half-split: n/a (need >=2 episodes)")
    else:
        lines.append(f"  half-split (h={hs['half_size']}): first={_fmt(hs['first_half_mean'], 2)}  "
                     f"second={_fmt(hs['second_half_mean'], 2)}  diff={_fmt(hs['diff'], 2)}")
    bs = result["bootstrap_diff_ci"]
    if bs and bs["ci_low"] is not None:
        lines.append(f"  bootstrap diff CI [{_fmt(bs['ci_low'], 2)}, {_fmt(bs['ci_high'], 2)}] "
                     f"(n_boot={bs['n_boot']}, seed={bs['seed']})")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Learning-curve metrics for one scores.jsonl series.")
    ap.add_argument("path", help="path to a scores.jsonl")
    ap.add_argument("--metric", default="score", choices=["score", "probes"])
    ap.add_argument("--bootstrap", action="store_true", help="also compute a seeded bootstrap CI on the half-split diff")
    ap.add_argument("--json-only", action="store_true", help="print only the JSON result")
    args = ap.parse_args(argv)

    episodes, values = load_series(args.path, args.metric)
    result = compute_metrics(episodes, values, metric=args.metric, bootstrap=args.bootstrap)
    if not args.json_only:
        print(render(result))
        print()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
