#!/usr/bin/env python3
"""
PrimordialSoup 精确理论最高分求解器（基于源码）

逻辑
----
穷举所有可行的「最终分子组合」，返回最高分。

决策变量：
    n[L1i] = 最终 portfolio 保留的 L1i 分子数（各类型分别枚举）
    n[L2j] = 最终 portfolio 保留的 L2j 分子数
    n[L3]  = 最终 portfolio 保留的 L3 分子数

约束（原料用量 ≤ 初始库存）：
    每种分子的原料成本 = 递归展开到原始化合物层面
    L1 成本 = 配方中两种化合物各 1 单位
    L2 成本 = 展开(反应物1) + 展开(反应物2)   ← 反应物可以是 L1 分子或化合物
    L3 成本 = 展开(反应物1) + 展开(反应物2)
    催化剂成本 = cat_compound × cat_level

总原料用量 = sum(每种分子数量 × 该分子成本)  ≤ stock

得分 = L1数量×10 + L2数量×25 + L3数量×80 + (5 if cat≥2) - 步数惩罚

步数估算（最优执行顺序）：
    1. 批量生产所有 L1（不同 L1 类型可以链式共产，若原料不重叠）
    2. 最后一批 L1 的 react 顺带放入催化剂（省去单独的 cat react）
    3. 连续 synthesize（每次 1 步 + 化合物类反应物的 add 步骤）
    4. submit
"""

import sys
import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import sys as _sys
if _ROOT not in _sys.path: _sys.path.insert(0, _ROOT)

sys.path.insert(0, '.')
from games.primordialsoup.primordialsoup import PrimordialSoupGame
from itertools import product as iproduct


COMPOUNDS = list("ABCDEF")


def solve(seed: int) -> dict:
    """
    返回 {'score': int, 'plan': dict, 'steps': int}
    plan 格式: {molecule_label: count_kept}
    """
    g = PrimordialSoupGame(seed=seed)
    stock = dict(g._stock_init)
    cat = g._cat_compound

    l1_rxns = g._l1_reactions    # [(c1, c2, label), ...]
    l2_rxns = g._l2_reactions    # [(r1, r2, label), ...]  r 可以是分子或化合物
    l3_r1, l3_r2, l3_label = g._l3_reaction

    l1_labels = [r[2] for r in l1_rxns]
    l2_labels = [r[2] for r in l2_rxns]
    all_mol = set(l1_labels + l2_labels + [l3_label])

    # ── 递归展开原料成本 ─────────────────────────────────────────────────────

    def expand(reactant: str) -> dict:
        """把任意反应物展开为 {化合物: 消耗数量}。"""
        if reactant not in all_mol:
            return {reactant: 1}                          # 直接就是化合物
        for c1, c2, lbl in l1_rxns:
            if lbl == reactant:
                return {c1: 1, c2: 1}                    # L1
        for r1, r2, lbl in l2_rxns:
            if lbl == reactant:
                cost = {}
                for k, v in expand(r1).items():
                    cost[k] = cost.get(k, 0) + v
                for k, v in expand(r2).items():
                    cost[k] = cost.get(k, 0) + v
                return cost                               # L2
        if reactant == l3_label:
            cost = {}
            for k, v in expand(l3_r1).items():
                cost[k] = cost.get(k, 0) + v
            for k, v in expand(l3_r2).items():
                cost[k] = cost.get(k, 0) + v
            return cost                                   # L3
        return {}

    mol_cost = {lbl: expand(lbl)
                for lbl in l1_labels + l2_labels + [l3_label]}

    # ── 步数估算 ─────────────────────────────────────────────────────────────

    def estimate_steps(plan: dict, cat_level: int) -> int:
        """
        正确步数公式推导：

        L1 生产：所有不同 L1 类型均可在同一次 react 中链式共产——把各自所需
        化合物全部加入汤即可，即使有共享化合物也只是多加几单位，资源约束已
        确保库存足够。

        设各 L1 类型产出数为 c_1 ≥ c_2 ≥ ... ≥ c_k，最优执行（先生产多的）：
          - c_k 轮全部 k 种一起产：c_k × (2k+1) 步（2k个add + 1 react）
          - c_{k-1}-c_k 轮前 k-1 种一起产：... 以此类推
        整理得：steps_L1 = max(c_i) + 2×sum(c_i)

        cat_level 个催化剂化合物顺带放入最后一次 L1 react：额外 cat_level 个 add。
        若无 L1 react，cat 单独 react：cat_level + 1 步。

        n_synth 需计入所有 L2 产出（保留 + 被 L3 消耗的中间 L2），不只是保留数。
        """
        n3 = plan.get(l3_label, 0)

        # ── 各 L1 类型总产出数 ───────────────────────────────────────────────
        l1_tot = {lbl: 0 for lbl in l1_labels}

        for lbl, n in plan.items():            # 保留在最终汤里的 L1
            if lbl in l1_tot:
                l1_tot[lbl] += n

        # L2 总产（保留 + 被 L3 消耗）→ 其中 L1 消耗量
        def l2_tot(l2_lbl):
            n_kept  = plan.get(l2_lbl, 0)
            n_in_l3 = n3 if (l3_r1 == l2_lbl or l3_r2 == l2_lbl) else 0
            return n_kept + n_in_l3

        for r1, r2, lbl in l2_rxns:
            n = l2_tot(lbl)
            if r1 in l1_tot: l1_tot[r1] += n
            if r2 in l1_tot: l1_tot[r2] += n

        for r in [l3_r1, l3_r2]:              # L3 直接消耗的 L1
            if r in l1_tot:
                l1_tot[r] += n3

        total_l1 = sum(l1_tot.values())
        max_l1   = max(l1_tot.values()) if l1_tot else 0

        # ── L1 生产步数（含催化剂）────────────────────────────────────────────
        # 正确公式：max(c_i) + 2×sum(c_i) + cat_level（顺带放入最后一次 react）
        if total_l1 > 0:
            steps_l1 = max_l1 + 2 * total_l1 + cat_level
        elif cat_level > 0:
            steps_l1 = cat_level + 1          # 无 L1 react，cat 单独 react
        else:
            steps_l1 = 0

        # ── synthesize 步数 ───────────────────────────────────────────────────
        # n_synth = 所有 L2 总产出次数 + L3 合成次数
        # extra_adds = 每次合成前需要 add 的化合物类反应物次数
        n_synth    = n3
        extra_adds = 0
        for r1, r2, lbl in l2_rxns:
            n = l2_tot(lbl)
            n_synth += n
            if r1 not in all_mol: extra_adds += n
            if r2 not in all_mol: extra_adds += n
        if l3_r1 not in all_mol: extra_adds += n3
        if l3_r2 not in all_mol: extra_adds += n3

        return steps_l1 + extra_adds + n_synth + 1  # +1 submit

    # ── 枚举所有方案 ─────────────────────────────────────────────────────────

    best_score = 0
    best_plan  = {}
    best_steps = 0

    # 上界：每种分子最多做 stock 之和 / 2（宽松）
    cap = sum(stock.values()) // 2 + 1

    for n3 in range(cap + 1):
        for n2s in iproduct(*[range(cap + 1) for _ in l2_labels]):
            for n1s in iproduct(*[range(cap + 1) for _ in l1_labels]):
                for cat_level in [0, 1, 2]:
                    has_synth = n3 > 0 or any(n > 0 for n in n2s)
                    if n3 > 0         and cat_level < 2: continue
                    if has_synth      and cat_level < 1: continue

                    plan = {}
                    for lbl, n in zip(l1_labels, n1s):
                        if n: plan[lbl] = n
                    for lbl, n in zip(l2_labels, n2s):
                        if n: plan[lbl] = n
                    if n3: plan[l3_label] = n3

                    # 总原料用量
                    used = {c: 0 for c in COMPOUNDS}
                    for lbl, n in plan.items():
                        for k, v in mol_cost[lbl].items():
                            used[k] = used.get(k, 0) + v * n
                    used[cat] = used.get(cat, 0) + cat_level

                    if any(used.get(c, 0) > stock.get(c, 0) for c in COMPOUNDS):
                        continue

                    # 得分
                    steps   = estimate_steps(plan, cat_level)
                    penalty = max(0, (steps - 30) * 0.5)
                    base    = sum(n1s)*10 + sum(n2s)*25 + n3*80
                    score   = int(base + (5 if cat_level >= 2 else 0) - penalty)

                    if score > best_score:
                        best_score = score
                        best_plan  = dict(plan)
                        best_steps = steps

    return {'score': best_score, 'plan': best_plan, 'steps': best_steps}


if __name__ == '__main__':
    print(f"{'Seed':>4}  {'Score':>7}  {'Steps':>6}  Plan")
    print('-' * 72)
    for s in range(1, 11):
        r = solve(s)
        print(f"{s:>4}  {r['score']:>7}  {r['steps']:>6}  {r['plan']}")
