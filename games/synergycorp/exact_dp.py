"""SynergyCorp 精确上限 DP（新校准引擎）。

确定性引擎 + 固定上司流 → 30 步动作序列的真最优可用逐步 DP 求出。
状态 = (boss_idx, influence(0.1 定点), prev_action, streak(capped 3), drifted)
值   = 已得奖分 − 8×记过。终局加上当前上司的 partial credit。
求出后把最优动作序列回放进真实引擎核对分数（防浮点/语义偏差）。
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from games.synergycorp.synergy_corp import (
    SynergyCorpGame, ACTIONS, ACTION_PROPS, MODALITIES,
)

NONE_PREV = 8  # prev_action=None 的编码


def episode_game(seed, ep):
    g = SynergyCorpGame(seed=seed)
    for _ in range(ep - 1):
        g.reset()
    return g


def delta_deci(game, active_pref, action, streak, prev):
    props = ACTION_PROPS[action]
    result = props["base"] * game._mult[active_pref][props["modality"]]
    if streak == 2:
        result *= 0.6
    elif streak >= 3:
        result *= 0.3
    if result > 0 and prev is not None and (ACTIONS[prev] == game._combo[0]) and action == game._combo[1]:
        result *= 2.5
    return int(round(round(result, 1) * 10))


def exact_max(seed, ep, max_bosses=24, want_seq=False):
    g = episode_game(seed, ep)
    return exact_max_for_game(g, max_bosses=max_bosses, want_seq=want_seq)


def exact_max_for_game(g, max_bosses=24, want_seq=False):
    """对一个「已 reset、上司流已定」的 game 求 30 步动作序列的真最优。
    与 exact_max 共用同一 DP；供离线按 forced salt 扫描候选流用（跳过贪心拒绝采样，快很多）。"""
    bosses = [g._make_boss(i) for i in range(max_bosses)]
    combo_a, combo_b = g._combo

    # 预取每个 boss 的常量
    binfo = []
    for b in bosses:
        binfo.append({
            "thr10": b["threshold"] * 10,
            "half10x2": b["threshold"] * 10,   # 2*inf >= thr*10 即 inf >= thr/2
            "prize": b["prize"],
            "pref": b["pref"],
            "drift": b["drift_pref"],
            "taboo": g._taboo_trait in b["traits"],
        })

    start = (0, 0, NONE_PREV, 0, False)
    frontier = {start: (0, None, None)}   # state -> (value, parent_state, action_idx)
    layers = [frontier]

    for turn in range(SynergyCorpGame.MAX_TURNS):
        nxt = {}
        for state, (val, _, _) in layers[-1].items():
            bi, inf, prev, streak, drifted = state
            bb = binfo[bi]
            for ai, action in enumerate(ACTIONS):
                nstreak = streak + 1 if ai == prev else 1
                if nstreak > 3:
                    nstreak = 3
                if bb["taboo"] and action == g._taboo_action:
                    ns = (bi, 0, ai, nstreak, drifted)
                    nv = val - SynergyCorpGame.DEMERIT_COST
                else:
                    apref = bb["drift"] if drifted else bb["pref"]
                    d = delta_deci(g, apref, action, nstreak, prev if prev != NONE_PREV else None)
                    ninf = inf + d
                    ndrift = drifted
                    if bb["drift"] and not drifted and 2 * ninf >= bb["thr10"]:
                        ndrift = True
                    if ninf >= bb["thr10"]:
                        nv = val + bb["prize"]
                        ns = (bi + 1, 0, NONE_PREV, 0, False)
                    else:
                        nv = val
                        ns = (bi, ninf, ai, nstreak, ndrift)
                cur = nxt.get(ns)
                if cur is None or nv > cur[0]:
                    nxt[ns] = (nv, state, ai)
        layers.append(nxt)

    # 终局：加 partial credit
    best_score, best_state = None, None
    for state, (val, _, _) in layers[-1].items():
        bi, inf, _, _, _ = state
        b = bosses[bi]
        ratio = max(0.0, inf / 10.0) / b["threshold"]
        partial = round(min(1.0, ratio) * b["prize"] * 0.5)
        score = max(0, val + partial)
        if best_score is None or score > best_score:
            best_score, best_state = score, state

    if not want_seq:
        return best_score, None, max(len(l) for l in layers)

    seq, st = [], best_state
    for turn in range(len(layers) - 1, 0, -1):
        _, parent, ai = layers[turn][st]
        seq.append(ACTIONS[ai])
        st = parent
    return best_score, list(reversed(seq)), max(len(l) for l in layers)


def replay_check(seed, ep, seq):
    g = episode_game(seed, ep)
    for a in seq:
        g.step(a)
    return g.score


if __name__ == "__main__":
    for seed in [1, 2]:
        per_ep = []
        for ep in range(1, 11):
            t0 = time.time()
            score, seq, width = exact_max(seed, ep, want_seq=(ep == 1))
            if seq is not None:
                real = replay_check(seed, ep, seq)
                assert real == score, f"回放不符: DP={score} engine={real}"
                tag = f"(回放核对通过, 状态宽度~{width}, {time.time()-t0:.1f}s)"
            else:
                tag = f"({time.time()-t0:.1f}s)"
            per_ep.append(score)
            print(f"seed{seed} ep{ep}: exact_max={score} {tag}", flush=True)
        print(f"seed{seed} 十局: {per_ep} 恒定={len(set(per_ep))==1}")
