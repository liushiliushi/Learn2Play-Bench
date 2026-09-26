"""
GemForge — Alchemist's Forge v6  (three-tier crafting)

Tier-1  : combine 2 raw materials  → gem  (5/15 combos valid)
Tier-2  : combine 2 tier-1 gems    → gem  (4/10 combos valid)
Tier-3  : combine 2 tier-2 gems    → gem  (2/6  combos valid)

No fixed turn limit — game ends when no productive action remains.
All recipes are seed-randomised and must be discovered through play.
Supports lang='zh' (default) and lang='en'.
"""

import random
from itertools import combinations, product as iproduct

# ── Materials ─────────────────────────────────────────────────────────────────

MATERIALS = ['sulfur', 'mercury', 'salt', 'iron', 'ash', 'vitriol']

MAT_NAME = {
    'zh': {'sulfur': '硫磺', 'mercury': '水银', 'salt': '盐晶',
           'iron': '铁矿', 'ash': '灰烬', 'vitriol': '矾石'},
    'en': {'sulfur': 'Sulfur', 'mercury': 'Mercury', 'salt': 'Salt',
           'iron': 'Iron', 'ash': 'Ash', 'vitriol': 'Vitriol'},
}

# ── Tier-1 gems ───────────────────────────────────────────────────────────────

GEM1_TYPES  = ['amber', 'jade', 'zenith', 'opal', 'ruby']
GEM1_VALUES = {'amber': 5, 'jade': 10, 'zenith': 20, 'opal': 8, 'ruby': 15}
GEM1_NAME   = {
    'zh': {'amber': '琥珀石', 'jade': '翡翠石', 'zenith': '至宝',
           'opal': '蛋白石', 'ruby': '红玉'},
    'en': {'amber': 'Amber', 'jade': 'Jade', 'zenith': 'Zenith',
           'opal': 'Opal', 'ruby': 'Ruby'},
}

# ── Tier-2 gems ───────────────────────────────────────────────────────────────

GEM2_TYPES  = ['crystal', 'prism', 'apex', 'solaris']
GEM2_VALUES = {'crystal': 40, 'prism': 65, 'apex': 90, 'solaris': 130}
GEM2_NAME   = {
    'zh': {'crystal': '晶华石', 'prism': '棱镜石', 'apex': '至极宝', 'solaris': '太阳石'},
    'en': {'crystal': 'Crystal', 'prism': 'Prism', 'apex': 'Apex', 'solaris': 'Solaris'},
}

# ── Tier-3 gems ───────────────────────────────────────────────────────────────

GEM3_TYPES  = ['nova', 'celestial']
GEM3_VALUES = {'nova': 260, 'celestial': 390}
GEM3_NAME   = {
    'zh': {'nova': '新星晶', 'celestial': '天晶'},
    'en': {'nova': 'Nova Crystal', 'celestial': 'Celestial Gem'},
}

SLAG_VALUE = 1
SLAG_NAME  = {'zh': '矿渣', 'en': 'Slag'}

ALL_GEM_TYPES  = GEM1_TYPES + GEM2_TYPES + GEM3_TYPES
ALL_GEM_VALUES = {**GEM1_VALUES, **GEM2_VALUES, **GEM3_VALUES, 'slag': SLAG_VALUE}

MAX_TURNS = 300  # effectively unlimited; game ends by resource exhaustion


class GemForgeGame:

    MAX_TURNS = MAX_TURNS

    def __init__(self, seed=None, lang='zh'):
        if seed is None:
            seed = random.randint(0, 10 ** 9)
        self.seed  = seed
        self._lang = lang if lang in ('zh', 'en') else 'zh'
        self._rng  = random.Random(seed)
        self._stocks_init, self._mat_recipes, self._gem_recipes, self._gem2_recipes = self._generate()
        self.reset()

    # ── Text helpers ──────────────────────────────────────────────────────────

    def _mat(self, m):
        return MAT_NAME[self._lang][m]

    def _gem(self, g):
        if g == 'slag':
            return SLAG_NAME[self._lang]
        for table in (GEM1_NAME, GEM2_NAME, GEM3_NAME):
            if g in table[self._lang]:
                return table[self._lang][g]
        return g

    # ── Generation ────────────────────────────────────────────────────────────

    def _generate(self):
        rng = self._rng
        stocks = {m: rng.randint(4, 5) for m in MATERIALS}

        # Tier-1: 15 material combos → 5 valid
        mat_pairs = [frozenset(p) for p in combinations(MATERIALS, 2)]
        rng.shuffle(mat_pairs)
        g1 = GEM1_TYPES[:]
        rng.shuffle(g1)
        mat_recipes = {pair: (g1[i] if i < len(GEM1_TYPES) else 'slag')
                       for i, pair in enumerate(mat_pairs)}

        # Tier-2: 10 gem-1 combos → 4 valid
        gem_pairs = [frozenset(p) for p in combinations(GEM1_TYPES, 2)]
        rng.shuffle(gem_pairs)
        g2 = GEM2_TYPES[:]
        rng.shuffle(g2)
        gem_recipes = {pair: (g2[i] if i < len(GEM2_TYPES) else 'slag')
                       for i, pair in enumerate(gem_pairs)}

        # Tier-3: 6 gem-2 combos → 2 valid
        gem2_pairs = [frozenset(p) for p in combinations(GEM2_TYPES, 2)]
        rng.shuffle(gem2_pairs)
        g3 = GEM3_TYPES[:]
        rng.shuffle(g3)
        gem2_recipes = {pair: (g3[i] if i < len(GEM3_TYPES) else 'slag')
                        for i, pair in enumerate(gem2_pairs)}

        return stocks, mat_recipes, gem_recipes, gem2_recipes

    # ── Reset ─────────────────────────────────────────────────────────────────

    def reset(self):
        self._turn       = 0
        self._stocks     = dict(self._stocks_init)
        self._crucible   = []
        self._mode       = None     # 'material' | 'gem' | 'gem2' | None
        self._collection = {g: 0 for g in ALL_GEM_TYPES + ['slag']}
        self._done       = False

        if self._lang == 'en':
            intro = (
                "You step into the alchemist's forge. Six raw materials await.\n"
                "Two materials fuse into a tier-1 gem; two tier-1 gems forge a tier-2 gem;\n"
                "two tier-2 gems can yield a rare tier-3 artifact.\n"
                "All recipes are hidden. Every experiment consumes real resources.\n\n"
            )
        else:
            intro = (
                "你走进炼金坊，面前是一座熔炉和六种原料。\n"
                "两种原料合成一阶宝石，两种一阶宝石合成二阶宝石，\n"
                "两种二阶宝石还能进一步熔炼出极为珍稀的三阶宝石。\n"
                "所有配方均属未知，每次实验都消耗真实原料。\n\n"
            )
        return intro + self._status_str(), {}

    # ── Public interface ──────────────────────────────────────────────────────

    @property
    def score(self) -> int:
        return sum(ALL_GEM_VALUES[g] * self._collection[g] for g in self._collection)

    @property
    def turn_count(self) -> int:
        return self._turn

    @property
    def done(self) -> bool:
        return self._done

    def get_all_actions(self) -> list:
        """完整行动集（固定不变，用于显示）。"""
        actions = [f'add_{m}' for m in MATERIALS]
        actions += [f'add_{g}' for g in GEM1_TYPES]
        actions += [f'add_{g}' for g in GEM2_TYPES]
        actions += ['fire', 'done']
        return actions

    def get_action_label(self, action: str) -> str:
        if self._lang == 'en':
            return action
        if action == 'fire':   return '点火熔炼'
        if action == 'done':   return '结束炼金'
        if action == 'status': return '查看状态'
        if action.startswith('add_'):
            item = action[4:]
            if item in MATERIALS:
                return f'投入{self._mat(item)}'
            return f'放入{self._gem(item)}'
        return action

    def _can_act(self) -> bool:
        # 坩埚里已有东西：允许继续加第二件或点火清空
        if self._crucible:
            if len(self._crucible) == 2:
                return True  # 可以点火
            item = self._crucible[0]
            if self._mode == 'material':
                if any(m != item and self._stocks[m] > 0 for m in MATERIALS):
                    return True
            elif self._mode == 'gem':
                if any(g != item and self._collection[g] > 0 for g in GEM1_TYPES):
                    return True
            elif self._mode == 'gem2':
                if any(g != item and self._collection[g] > 0 for g in GEM2_TYPES):
                    return True
            # 坩埚有一件但凑不出第二件，仍允许点火清空（出矿渣）
            return True

        # 坩埚为空：必须能凑出至少一对才算有意义的行动
        avail_mats = [m for m in MATERIALS if self._stocks[m] > 0]
        if len(avail_mats) >= 2:
            return True
        avail_g1 = [g for g in GEM1_TYPES if self._collection[g] > 0]
        if len(avail_g1) >= 2:
            return True
        avail_g2 = [g for g in GEM2_TYPES if self._collection[g] > 0]
        if len(avail_g2) >= 2:
            return True
        return False

    def get_valid_actions(self) -> list:
        if self._done:
            return []
        if not self._can_act():
            return ['done']
        actions = ['status', 'done']

        if len(self._crucible) < 2:
            if self._mode in (None, 'material'):
                for m in MATERIALS:
                    if self._stocks[m] > 0 and m not in self._crucible:
                        actions.append(f'add_{m}')
            if self._mode in (None, 'gem'):
                for g in GEM1_TYPES:
                    if self._collection[g] > 0 and g not in self._crucible:
                        actions.append(f'add_{g}')
            if self._mode in (None, 'gem2'):
                for g in GEM2_TYPES:
                    if self._collection[g] > 0 and g not in self._crucible:
                        actions.append(f'add_{g}')

        if self._crucible:
            actions.append('fire')
        return actions

    def step(self, action: str):
        action = action.strip().lower()

        if self._done:
            return (self._t("游戏已结束。", "Game over."), 0, True, {"score": self.score})
        if not self._can_act():
            self._done = True
            msg = self._t(f"所有原料耗尽，炼金结束。最终得分：{self.score}",
                          f"All resources exhausted. The forge falls silent. Final score: {self.score}")
            return msg, self.score, True, {}
        if action == 'status':
            return self._status_str(), 0, False, {}

        valid = self.get_valid_actions()
        if action not in valid:
            playable = [a for a in valid if a != 'status']
            msg = (self._t(f"无效行动：{action}。当前可用：{', '.join(playable)}",
                           f"Invalid action: {action}. Available: {', '.join(playable)}"))
            return msg, 0, False, {}

        self._turn += 1
        lines = []

        if action == 'done':
            self._done = True
            lines += [self._t("你封炉离去。", "You leave the forge."),
                      self._t(f"最终得分：{self.score}", f"Final score: {self.score}")]

        elif action.startswith('add_') and action[4:] in GEM2_TYPES:
            gem = action[4:]
            self._collection[gem] -= 1
            self._crucible.append(gem)
            self._mode = 'gem2'
            lines.append(self._t(f"放入{self._gem(gem)}。坩埚：{self._crucible_str()}",
                                  f"Placed {self._gem(gem)} in crucible. Crucible: {self._crucible_str()}"))

        elif action.startswith('add_') and action[4:] in GEM1_TYPES:
            gem = action[4:]
            self._collection[gem] -= 1
            self._crucible.append(gem)
            self._mode = 'gem'
            lines.append(self._t(f"放入{self._gem(gem)}。坩埚：{self._crucible_str()}",
                                  f"Placed {self._gem(gem)} in crucible. Crucible: {self._crucible_str()}"))

        elif action.startswith('add_'):
            mat = action[4:]
            self._stocks[mat] -= 1
            self._crucible.append(mat)
            self._mode = 'material'
            lines.append(self._t(f"投入{self._mat(mat)}。坩埚：{self._crucible_str()}",
                                  f"Added {self._mat(mat)} to crucible. Crucible: {self._crucible_str()}"))

        elif action == 'fire':
            lines.extend(self._do_fire())

        if not self._done and not self._can_act():
            self._done = True
            lines.append(self._t(f"\n所有原料耗尽，炼金结束。最终得分：{self.score}",
                                  f"\nAll resources exhausted. The forge falls silent. Final score: {self.score}"))

        obs_body = '\n'.join(lines)
        obs = obs_body if self._done else f"{obs_body}\n\n{self._status_str()}"
        return obs, self.score, self._done, {}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _t(self, zh, en):
        return en if self._lang == 'en' else zh

    def _do_fire(self) -> list:
        key  = frozenset(self._crucible)
        mode = self._mode
        self._crucible = []
        self._mode     = None

        if mode == 'material':
            gem = self._mat_recipes.get(key, 'slag')
            self._collection[gem] += 1
            if gem == 'slag':
                line = self._t(f"原料互斥，只得一块矿渣。(+{SLAG_VALUE})",
                               f"The materials repel each other — only Slag. (+{SLAG_VALUE})")
            else:
                line = self._t(f"熔炉中凝出一颗{self._gem(gem)}！(+{ALL_GEM_VALUES[gem]})",
                               f"A {self._gem(gem)} crystallizes! (+{ALL_GEM_VALUES[gem]})")

        elif mode == 'gem':
            gem = self._gem_recipes.get(key, 'slag')
            self._collection[gem] += 1
            if gem == 'slag':
                line = self._t("宝石碰撞归于虚无，只余矿渣。(+1)",
                               "The gems collide and collapse. (+1)")
            else:
                line = self._t(f"炉中爆发光芒，{self._gem(gem)}出世！(+{ALL_GEM_VALUES[gem]})",
                               f"A blinding flash — {self._gem(gem)} is forged! (+{ALL_GEM_VALUES[gem]})")

        else:  # gem2
            gem = self._gem2_recipes.get(key, 'slag')
            self._collection[gem] += 1
            if gem == 'slag':
                line = self._t("两颗宝石相互湮灭，化为矿渣。(+1)",
                               "The two gems annihilate each other. (+1)")
            else:
                line = self._t(
                    f"熔炉剧烈震动，传说中的{self._gem(gem)}破炉而出！(+{ALL_GEM_VALUES[gem]})",
                    f"The forge trembles — a legendary {self._gem(gem)} emerges! (+{ALL_GEM_VALUES[gem]})"
                )

        score_line = self._t(f"当前得分：{self.score}", f"Score: {self.score}")
        return [line, score_line]

    def _crucible_str(self) -> str:
        names = [self._mat(x) if x in MATERIALS else self._gem(x) for x in self._crucible]
        empty = '(empty)' if self._lang == 'en' else '（空）'
        return ' + '.join(names) if names else empty

    def _status_str(self) -> str:
        empty = '(none)' if self._lang == 'en' else '（空）'
        if self._lang == 'en':
            stocks = '  '.join(f"{self._mat(m)}×{self._stocks[m]}" for m in MATERIALS)
            g1s = '  '.join(f"{self._gem(g)}×{self._collection[g]}"
                            for g in GEM1_TYPES if self._collection[g] > 0)
            g2s = '  '.join(f"{self._gem(g)}×{self._collection[g]}"
                            for g in GEM2_TYPES if self._collection[g] > 0)
            g3s = '  '.join(f"{self._gem(g)}×{self._collection[g]}"
                            for g in GEM3_TYPES if self._collection[g] > 0)
            slag = f"Slag×{self._collection['slag']}" if self._collection['slag'] else ""
            gems = '  '.join(filter(None, [g1s, g2s, g3s, slag])) or empty
            return '\n'.join([
                f"Crucible: {self._crucible_str()}",
                f"Stockroom: {stocks}",
                f"Collection: {gems}",
                f"Score: {self.score} | Steps: {self._turn}",
            ])
        else:
            stocks = '  '.join(f"{self._mat(m)}×{self._stocks[m]}" for m in MATERIALS)
            g1s = '  '.join(f"{self._gem(g)}×{self._collection[g]}"
                            for g in GEM1_TYPES if self._collection[g] > 0)
            g2s = '  '.join(f"{self._gem(g)}×{self._collection[g]}"
                            for g in GEM2_TYPES if self._collection[g] > 0)
            g3s = '  '.join(f"{self._gem(g)}×{self._collection[g]}"
                            for g in GEM3_TYPES if self._collection[g] > 0)
            slag = f"矿渣×{self._collection['slag']}" if self._collection['slag'] else ""
            gems = '  '.join(filter(None, [g1s, g2s, g3s, slag])) or empty
            return '\n'.join([
                f"坩埚：{self._crucible_str()}",
                f"原料库：{stocks}",
                f"宝石库：{gems}",
                f"得分：{self.score} | 步数：{self._turn}",
            ])


# ── Theoretical max ───────────────────────────────────────────────────────────

def theoretical_max(seed):
    """三层枚举：原料→一阶→二阶→三阶，含可调度的单件炉渣收益。"""
    game   = GemForgeGame(seed=seed)
    stocks = dict(game._stocks_init)

    vt1 = [(sorted(p), g) for p, g in game._mat_recipes.items()  if g != 'slag']
    vt2 = [(sorted(p), g) for p, g in game._gem_recipes.items()  if g != 'slag']
    vt3 = [(sorted(p), g) for p, g in game._gem2_recipes.items() if g != 'slag']

    best_score = 0
    best_plan  = None

    mn1 = [min(stocks[ms[0]], stocks[ms[1]]) for ms, _ in vt1]

    for n1 in iproduct(*[range(m + 1) for m in mn1]):
        used = {m: 0 for m in MATERIALS}
        for i, (ms, _) in enumerate(vt1):
            used[ms[0]] += n1[i]; used[ms[1]] += n1[i]
        if any(used[m] > stocks[m] for m in MATERIALS):
            continue

        prod1 = {g: 0 for g in GEM1_TYPES}
        for i, (_, g) in enumerate(vt1):
            prod1[g] += n1[i]

        mn2 = [min(prod1.get(gc[0], 0), prod1.get(gc[1], 0)) for gc, _ in vt2]

        for n2 in iproduct(*[range(m + 1) for m in mn2]):
            used2 = {g: 0 for g in GEM1_TYPES}
            for i, (gc, _) in enumerate(vt2):
                used2[gc[0]] += n2[i]; used2[gc[1]] += n2[i]
            if any(used2[g] > prod1[g] for g in GEM1_TYPES):
                continue

            prod2 = {g: 0 for g in GEM2_TYPES}
            for i, (_, g) in enumerate(vt2):
                prod2[g] += n2[i]

            mn3 = [min(prod2.get(gc[0], 0), prod2.get(gc[1], 0)) for gc, _ in vt3]

            for n3 in iproduct(*[range(m + 1) for m in mn3]):
                used3 = {g: 0 for g in GEM2_TYPES}
                for i, (gc, _) in enumerate(vt3):
                    used3[gc[0]] += n3[i]; used3[gc[1]] += n3[i]
                if any(used3[g] > prod2[g] for g in GEM2_TYPES):
                    continue

                gem_score = (
                    sum(n3[i] * ALL_GEM_VALUES[g] for i, (_, g) in enumerate(vt3))
                    + sum((prod2[g] - used3[g]) * ALL_GEM_VALUES[g] for g in GEM2_TYPES)
                    + sum((prod1[g] - used2[g]) * ALL_GEM_VALUES[g] for g in GEM1_TYPES)
                )
                mat_left = sum(stocks[m] - used[m] for m in MATERIALS)
                # Any planned material recipe can be delayed while all surplus
                # raw materials are fired singly for +1 slag each.
                slag = mat_left if any(n1) else max(0, mat_left - 1)
                score = gem_score + slag

                if score > best_score:
                    best_score = score
                    best_plan = (
                        n1,
                        n2,
                        n3,
                        slag,
                        {m: stocks[m] - used[m] for m in MATERIALS},
                    )

    g1zh = GEM1_NAME['zh']; g2zh = GEM2_NAME['zh']; g3zh = GEM3_NAME['zh']
    mzh  = MAT_NAME['zh']
    lines = [f"Seed {seed} 理论最高分：{best_score}",
             "原料：" + "  ".join(f"{mzh[m]}×{stocks[m]}" for m in MATERIALS),
             "── 一阶合成 ──"]
    for i, (ms, g) in enumerate(vt1):
        n = best_plan[0][i]
        if n: lines.append(f"  {mzh[ms[0]]}+{mzh[ms[1]]} → {g1zh[g]} ×{n} (+{ALL_GEM_VALUES[g]*n})")
    lines.append("── 二阶合成 ──")
    for i, (gc, g) in enumerate(vt2):
        n = best_plan[1][i]
        if n: lines.append(f"  {g1zh[gc[0]]}+{g1zh[gc[1]]} → {g2zh[g]} ×{n} (+{ALL_GEM_VALUES[g]*n})")
    lines.append("── 三阶合成 ──")
    for i, (gc, g) in enumerate(vt3):
        n = best_plan[2][i]
        if n: lines.append(f"  {g2zh[gc[0]]}+{g2zh[gc[1]]} → {g3zh[g]} ×{n} (+{ALL_GEM_VALUES[g]*n})")
    if best_plan[3]:
        leftovers = "  ".join(f"{mzh[m]}×{n}" for m, n in best_plan[4].items() if n)
        lines.append(f"── 剩余原料单件点火 ──")
        lines.append(f"  {leftovers} → 矿渣 ×{best_plan[3]} (+{best_plan[3]})")

    return best_score, '\n'.join(lines)


if __name__ == '__main__':
    for s in range(1, 11):
        score, plan = theoretical_max(s)
        print(plan)
        print()
