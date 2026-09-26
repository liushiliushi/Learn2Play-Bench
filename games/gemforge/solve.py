#!/usr/bin/env python3
"""
GemForge 精确理论最高分求解器（基于源码）

直接从游戏对象读取真实配方，枚举最优宝石组合，
再加上剩余原料的最大炉渣收益。

炉渣说明：
  单件点火也是合法动作，每个剩余原料可转为 +1 炉渣。
  只要先保留一个后续合成 pair，就能在终局检测前把所有未用于配方的
  原料逐个烧掉，再执行最后的合成；这正是 seed1 的 790→791 差异来源。
"""

import sys
sys.path.insert(0, '.')
from games.gemforge.gemforge import GemForgeGame, MATERIALS, GEM1_TYPES, GEM2_TYPES
from itertools import combinations, product as iproduct


def max_slag(remaining: dict, has_future_pair: bool) -> int:
    """
    从给定的剩余原料计算最大炉渣收益。

    规则（实测验证）：
      - 有后续合成 pair 时，_can_act() 一直为真，所有剩余原料都可单件点火。
      - 没有后续 pair 时，空坩埚状态只要不足两类可用物品就会自动结束，
        因而最多会剩下一件原料无法点火。
    """
    vals = [v for v in remaining.values() if v > 0]
    total = sum(vals)
    if total <= 0:
        return 0
    if has_future_pair:
        return total
    if len(vals) < 2:
        return 0
    return total - 1


def solve(seed: int) -> dict:
    """
    返回 {'score': int, 'gem_score': int, 'slag': int, 'plan': str}
    """
    game = GemForgeGame(seed=seed)
    stocks = dict(game._stocks_init)

    # 读取真实配方
    valid_t1 = [(sorted(list(pair)), gem)
                for pair, gem in game._mat_recipes.items() if gem != 'slag']
    valid_t2 = [(sorted(list(pair)), gem)
                for pair, gem in game._gem_recipes.items() if gem != 'slag']
    valid_t3 = [(sorted(list(pair)), gem)
                for pair, gem in game._gem2_recipes.items() if gem != 'slag']

    from games.gemforge.gemforge import ALL_GEM_VALUES

    best_score = 0
    best_detail = {}

    # 枚举一阶宝石生产数量
    max_n1 = [min(stocks.get(p[0], 0), stocks.get(p[1], 0)) for p, _ in valid_t1]

    for n1 in iproduct(*[range(m + 1) for m in max_n1]):
        # 检查一阶原料约束
        mat_used = {m: 0 for m in MATERIALS}
        for i, (pair, _) in enumerate(valid_t1):
            mat_used[pair[0]] = mat_used.get(pair[0], 0) + n1[i]
            mat_used[pair[1]] = mat_used.get(pair[1], 0) + n1[i]
        if any(mat_used.get(m, 0) > stocks.get(m, 0) for m in MATERIALS):
            continue

        # 一阶宝石产出
        gem1_prod = {g: 0 for g in GEM1_TYPES}
        for i, (_, gem) in enumerate(valid_t1):
            gem1_prod[gem] += n1[i]

        # 剩余原料
        mat_left = {m: stocks.get(m, 0) - mat_used.get(m, 0) for m in MATERIALS}

        # 枚举二阶宝石生产数量
        max_n2 = [min(gem1_prod.get(p[0], 0), gem1_prod.get(p[1], 0))
                  for p, _ in valid_t2]

        for n2 in iproduct(*[range(m + 1) for m in max_n2]):
            gem1_used = {g: 0 for g in GEM1_TYPES}
            for i, (pair, _) in enumerate(valid_t2):
                gem1_used[pair[0]] = gem1_used.get(pair[0], 0) + n2[i]
                gem1_used[pair[1]] = gem1_used.get(pair[1], 0) + n2[i]
            if any(gem1_used.get(g, 0) > gem1_prod.get(g, 0) for g in GEM1_TYPES):
                continue

            gem2_prod = {g: 0 for g in GEM2_TYPES}
            for i, (_, gem) in enumerate(valid_t2):
                gem2_prod[gem] += n2[i]

            # 枚举三阶宝石生产数量
            max_n3 = [min(gem2_prod.get(p[0], 0), gem2_prod.get(p[1], 0))
                      for p, _ in valid_t3]

            for n3 in iproduct(*[range(m + 1) for m in max_n3]):
                gem2_used = {g: 0 for g in GEM2_TYPES}
                for i, (pair, _) in enumerate(valid_t3):
                    gem2_used[pair[0]] = gem2_used.get(pair[0], 0) + n3[i]
                    gem2_used[pair[1]] = gem2_used.get(pair[1], 0) + n3[i]
                if any(gem2_used.get(g, 0) > gem2_prod.get(g, 0) for g in GEM2_TYPES):
                    continue

                # 宝石得分
                gem_score = (
                    sum(n3[i] * ALL_GEM_VALUES[g] for i, (_, g) in enumerate(valid_t3))
                    + sum((gem2_prod[g] - gem2_used.get(g, 0)) * ALL_GEM_VALUES[g]
                          for g in GEM2_TYPES)
                    + sum((gem1_prod[g] - gem1_used.get(g, 0)) * ALL_GEM_VALUES[g]
                          for g in GEM1_TYPES)
                )

                # 炉渣得分：配方动作可以延后执行，用作单件烧剩余原料时的
                # 活性锚点；若完全不合成，则终局检测会卡住最后一件原料。
                has_future_pair = any(n1)
                slag = max_slag(mat_left, has_future_pair)
                total_score = gem_score + slag

                if total_score > best_score:
                    best_score = total_score
                    best_detail = {
                        'gem_score': gem_score,
                        'slag': slag,
                        'mat_left': dict(mat_left),
                        'n1': n1, 'n2': n2, 'n3': n3,
                    }

    return {
        'score': best_score,
        'gem_score': best_detail.get('gem_score', 0),
        'slag': best_detail.get('slag', 0),
        'mat_left': best_detail.get('mat_left', {}),
    }


if __name__ == '__main__':
    # 游戏实测验证值（live engine replay verified）
    # Historical reference values printed alongside the live-computed optimum for
    # a quick eyeball diff; the live engine solver is authoritative. Values were
    # recomputed on 2026-08-27 after accounting for the legal single-item burn
    # ordering trick.
    report = {1:791, 2:560, 3:580, 4:753, 5:802, 6:414, 7:802, 8:546, 9:840, 10:626}

    print(f"{'Seed':>4}  {'宝石分':>7}  {'炉渣分':>6}  {'合计':>7}  {'报告':>7}  {'差异':>5}")
    print('-' * 50)
    for s in range(1, 11):
        r = solve(s)
        rep = report[s]
        diff = r['score'] - rep
        flag = f'+{diff}' if diff > 0 else (str(diff) if diff < 0 else '✓')
        print(f"{s:>4}  {r['gem_score']:>7}  {r['slag']:>6}  {r['score']:>7}  {rep:>7}  {flag:>5}")
