"""
PrimordialSoup — 原始汤游戏引擎

规则：
- 在深海热泉旁向"原始汤"中投入化学原料，触发反应，催化有机分子
- 6 种化合物（A~F），其中 1 种为隐藏催化剂
- 通过 react 触发基础反应（L1），synthesize 合成高级分子（L2/L3）
- 50 步上限，主动 submit 或原料耗尽时结算
"""

import random


# ── 行动列表 ──────────────────────────────────────────────────────────────────

COMPOUNDS = ["A", "B", "C", "D", "E", "F"]

# 行动名称使用小写，与 step() 中 action.lower() 保持一致
ADD_ACTIONS = [f"add_{c.lower()}" for c in COMPOUNDS]

ACTIONS = ADD_ACTIONS + ["react", "synthesize", "submit", "status"]


# ── 游戏主类 ──────────────────────────────────────────────────────────────────

class PrimordialSoupGame:
    MAX_TURNS = 50

    def __init__(self, seed=None, lang="zh"):
        self._lang = lang
        if seed is None:
            seed = random.randint(0, 10 ** 9)
        self.seed = seed
        self._rng = random.Random(seed)
        self._generate_hidden()
        self.reset()

    # ── i18n helper（只本地化显示文本，不改任何游戏逻辑/标签/token） ──
    def _t(self, zh, en):
        return en if self._lang == "en" else zh

    def _generate_hidden(self):
        """生成所有隐藏变量（只在 __init__ 调用一次）"""
        rng = self._rng

        # 1. 催化剂化合物（A~F 中随机 1 种）
        self._cat_compound = rng.choice(COMPOUNDS)

        # 2. 原料初始数量（每种 3~6 单位）
        self._stock_init = {c: rng.randint(3, 6) for c in COMPOUNDS}

        # 3. 生成基础反应网络
        #    L1 反应：非催化剂化合物中任意 2 种 → L1 分子（生成 2~3 个 L1 反应）
        non_cat = [c for c in COMPOUNDS if c != self._cat_compound]
        rng.shuffle(non_cat)

        # L1 分子标签：L1a, L1b, L1c（最多 3 种）
        # 每个 L1 反应由 2 种非催化剂化合物生成
        num_l1 = rng.randint(2, 3)
        used_pairs = set()
        self._l1_reactions = []  # list of (compound1, compound2, label)
        l1_labels = ["L1a", "L1b", "L1c"]

        available = list(non_cat)
        for i in range(num_l1):
            label = l1_labels[i]
            # 选取不重复的两种化合物组合
            attempts = 0
            while attempts < 20:
                c1, c2 = rng.sample(available, 2)
                pair = tuple(sorted([c1, c2]))
                if pair not in used_pairs:
                    used_pairs.add(pair)
                    self._l1_reactions.append((c1, c2, label))
                    break
                attempts += 1

        # 4. L2 反应：L1+L1 或 L1+化合物 → L2 分子（1~2 个 L2 反应）
        l1_labels_used = [r[2] for r in self._l1_reactions]
        num_l2 = rng.randint(1, 2)
        self._l2_reactions = []  # list of (reactant1, reactant2, label)
        l2_labels = ["L2a", "L2b"]
        l2_used_pairs = set()

        for i in range(num_l2):
            label = l2_labels[i]
            attempts = 0
            while attempts < 20:
                # 随机选择：L1+L1 或 L1+化合物
                mode = rng.choice(["l1l1", "l1c"]) if len(l1_labels_used) >= 2 else "l1c"
                if mode == "l1l1" and len(l1_labels_used) >= 2:
                    r1, r2 = rng.sample(l1_labels_used, 2)
                else:
                    r1 = rng.choice(l1_labels_used)
                    r2 = rng.choice(non_cat)
                pair = tuple(sorted([r1, r2]))
                if pair not in l2_used_pairs:
                    l2_used_pairs.add(pair)
                    self._l2_reactions.append((r1, r2, label))
                    break
                attempts += 1

        # 5. L3 反应：至少 1 个 L2 参与 → L3 分子（1 个）
        l2_labels_used = [r[2] for r in self._l2_reactions]
        if len(l2_labels_used) >= 2:
            r1, r2 = rng.sample(l2_labels_used, 2)
        elif len(l2_labels_used) == 1:
            r1 = l2_labels_used[0]
            r2 = rng.choice(l1_labels_used) if l1_labels_used else rng.choice(non_cat)
        else:
            r1 = rng.choice(l1_labels_used) if l1_labels_used else non_cat[0]
            r2 = rng.choice(non_cat)
        self._l3_reaction = (r1, r2, "L3")

    def reset(self):
        """重置回合状态，不重新生成隐藏变量"""
        self._turn = 0
        self._done = False

        # 原料库存（从初始值复制）
        self._stock = dict(self._stock_init)

        # 汤中内容：化合物 + 有机分子
        self._soup_compounds = {c: 0 for c in COMPOUNDS}
        self._soup_molecules = {}  # label -> count

        # 催化剂浓度（由上一次 react 计算得出，持续到下次 react）
        self._cat_level = 0

        # 本局是否曾达到催化剂浓度 >= 2
        self._cat_bonus_triggered = False

        # 得分缓存
        self._cached_score = 0

        obs = self._render_status_text()
        sep = "=" * 52
        intro = "\n".join([
            sep,
            self._t("【原始汤实验室】", "[Primordial Soup Lab]"),
            self._t("前寒武纪深海热泉旁，六种化学原料静待你的投入。",
                    "Beside a Precambrian deep-sea hydrothermal vent, six chemical reagents await your input."),
            self._t("催化生命之火，在混沌中涌现秩序。",
                    "Kindle the spark of life, and let order emerge from chaos."),
            sep,
            "",
        ]) + obs
        return intro, {"valid": self.get_valid_actions()}

    # ── 对外接口 ──────────────────────────────────────────────────────────────

    @property
    def score(self) -> int:
        return self._compute_score()

    @property
    def turn_count(self) -> int:
        return self._turn

    @property
    def done(self) -> bool:
        return self._done

    def get_valid_actions(self) -> list:
        if self._done:
            return []
        return list(ACTIONS)

    def get_action_label(self, action: str) -> str:
        """返回行动的简短标签"""
        action = action.strip().lower()
        if action.startswith("add_"):
            compound = action[4:].upper()
            return self._t(f"投入化合物{compound}", f"Add compound {compound}")
        labels = {
            "react":     self._t("触发基础反应", "Trigger base reaction"),
            "synthesize":self._t("合成高级分子", "Synthesize higher molecule"),
            "submit":    self._t("提交实验结果", "Submit experiment result"),
            "status":    self._t("查看实验状态", "View experiment status"),
        }
        return labels.get(action, action)

    def step(self, action: str):
        action = action.strip().lower()

        if self._done:
            return self._t("实验已结束。", "The experiment has ended."), 0, True, {"score": self.score}

        if action == "status":
            return self._render_status_text(), 0, False, {"valid": self.get_valid_actions()}

        if action not in [a for a in ACTIONS if a != "status"]:
            avail = ' | '.join(a for a in ACTIONS if a != 'status')
            return self._t(f"无效指令。可用行动：{avail}",
                           f"Invalid command. Available actions: {avail}"), 0, False, {"valid": self.get_valid_actions()}

        self._turn += 1
        obs = ""
        reward = 0

        if action.startswith("add_"):
            compound = action[4:].upper()
            obs = self._do_add(compound)
        elif action == "react":
            obs = self._do_react()
        elif action == "synthesize":
            obs = self._do_synthesize()
        elif action == "submit":
            obs = self._do_submit()
            self._done = True

        # 检查是否达到步数上限
        if not self._done and self._turn >= self.MAX_TURNS:
            self._done = True
            obs += self._t("\n\n步数上限已达，实验自动结算。\n",
                           "\n\nStep limit reached; the experiment settles automatically.\n") + self._render_ending()

        # 检查原料耗尽且汤为空且无分子可合成
        elif not self._done and self._is_exhausted():
            self._done = True
            obs += self._t("\n\n原料耗尽，汤中空空荡荡，实验自动结算。\n",
                           "\n\nReagents depleted and the soup is empty; the experiment settles automatically.\n") + self._render_ending()

        if self._done:
            reward = self._compute_score()
        else:
            obs += "\n\n" + self._render_status_text()

        info = {"valid": self.get_valid_actions(), "score": self.score}
        return obs, reward, self._done, info

    # ── 行动逻辑 ──────────────────────────────────────────────────────────────

    def _do_add(self, compound: str) -> str:
        if compound not in COMPOUNDS:
            return self._t(f"未知化合物 {compound}。", f"Unknown compound {compound}.")

        if self._stock[compound] <= 0:
            return self._t(f"化合物 {compound} 库存已耗尽，无法继续投入。",
                           f"Compound {compound} is out of stock; no more can be added.")

        self._stock[compound] -= 1
        self._soup_compounds[compound] += 1

        in_soup = self._soup_compounds[compound]
        if in_soup > 6:
            return self._t(
                f"化合物 {compound} 已大量积聚在汤中（{in_soup} 单位），继续投入的效果可能有限。",
                f"Compound {compound} has accumulated heavily in the soup ({in_soup} units); adding more may have limited effect.")

        return self._t(
            f"你将化合物 {compound} 缓缓加入热泉汤中。汤面微微波动。（库存剩余：{self._stock[compound]}）",
            f"You slowly add compound {compound} to the vent soup. The surface ripples faintly. (Stock left: {self._stock[compound]})")

    def _do_react(self) -> str:
        # 检查汤中是否有内容物
        total_compounds = sum(self._soup_compounds.values())
        total_molecules = sum(self._soup_molecules.values())

        if total_compounds == 0 and total_molecules == 0:
            return self._t("热泉沸腾，但汤中空空荡荡，什么反应都没有发生。",
                           "The vent boils, but the soup is empty; no reaction occurs.")

        # 1. 统计催化剂浓度
        cat_in_soup = self._soup_compounds.get(self._cat_compound, 0)
        self._cat_level = min(3, cat_in_soup)

        if self._cat_level >= 2:
            self._cat_bonus_triggered = True

        # 2. 移除催化剂化合物
        self._soup_compounds[self._cat_compound] = 0

        # 3. 如果汤中只有催化剂化合物
        if total_compounds - cat_in_soup == 0 and total_molecules == 0:
            return self._t(
                f"催化剂在汤中弥漫开来，浓度升至 {self._cat_level}。其他化合物尚未投入，无法驱动反应。",
                f"The catalyst spreads through the soup, concentration rising to {self._cat_level}. No other compounds are present, so no reaction can be driven.")

        # 4. 遍历 L1 反应
        triggered = set()
        l1_generated = 0
        for (c1, c2, label) in self._l1_reactions:
            key = label
            if key in triggered:
                continue
            if self._soup_compounds.get(c1, 0) >= 1 and self._soup_compounds.get(c2, 0) >= 1:
                # 消耗化合物，生成 L1 分子
                self._soup_compounds[c1] -= 1
                self._soup_compounds[c2] -= 1
                self._soup_molecules[label] = self._soup_molecules.get(label, 0) + 1
                triggered.add(key)
                l1_generated += 1

        # 反馈
        cat_str = self._t(f"催化剂浓度：{self._cat_level}", f"Catalyst concentration: {self._cat_level}")
        if l1_generated == 0:
            return self._t(
                f"加热后，化合物剧烈震荡，但彼此间缺乏化学亲和力，汤变得混浊，无分子产生。{cat_str}。",
                f"On heating, the compounds churn violently but lack chemical affinity for one another; the soup turns murky and no molecule forms. {cat_str}.")
        elif l1_generated == 1:
            return self._t(
                f"汤面泛起涟漪——某种有机结构正在成形。你观察到 1 个初级有机分子涌现。{cat_str}。",
                f"Ripples spread across the soup — an organic structure is taking shape. You observe 1 primary organic molecule emerge. {cat_str}.")
        else:
            return self._t(
                f"反应链激活！汤面翻腾，你观察到 {l1_generated} 个初级有机分子相继涌现。{cat_str}。",
                f"Reaction chain activated! The soup roils, and you observe {l1_generated} primary organic molecules emerge one after another. {cat_str}.")

    def _do_synthesize(self) -> str:
        # 1. 检查催化剂浓度
        if self._cat_level < 1:
            return self._t(
                "分子在汤中游荡，但环境太过平静——它们相遇却无法融合。也许需要更强的催化活性。",
                "The molecules drift through the soup, but the environment is too calm — they meet yet cannot fuse. Perhaps stronger catalytic activity is needed.")

        # 2. 尝试所有合成组合
        # 先尝试 L3 合成（优先级高），再尝试 L2 合成
        # L3 需要催化剂浓度 >= 2
        if self._cat_level >= 2:
            r1, r2, label = self._l3_reaction
            if self._has_reactant(r1) and self._has_reactant(r2):
                self._consume_reactant(r1)
                self._consume_reactant(r2)
                self._soup_molecules[label] = self._soup_molecules.get(label, 0) + 1
                return self._t(
                    "奇迹发生——两种有机分子在强催化场中相互识别，折叠成一个精妙的高级结构。生命的雏形出现了！",
                    "A miracle unfolds — two organic molecules recognize each other in the strong catalytic field and fold into an intricate higher structure. The rudiment of life appears!")

        # 尝试 L2 合成（需催化剂浓度 >= 1）
        for (r1, r2, label) in self._l2_reactions:
            # 检查是否满足 L3 阈值导致失败（此处已通过 cat_level >= 1 检查）
            if self._has_reactant(r1) and self._has_reactant(r2):
                self._consume_reactant(r1)
                self._consume_reactant(r2)
                self._soup_molecules[label] = self._soup_molecules.get(label, 0) + 1
                return self._t(
                    "两种分子在催化剂作用下缓慢靠近，链接成更复杂的结构。一个中级有机分子形成了！",
                    "Under the catalyst, two molecules slowly draw together and link into a more complex structure. An intermediate organic molecule has formed!")

        # 尝试高级合成但催化剂不足
        if self._cat_level < 2:
            r1, r2, _ = self._l3_reaction
            if self._has_reactant(r1) and self._has_reactant(r2):
                return self._t(
                    "分子相遇，但高级合成所需的能量壁垒太高——需要更强的催化场。",
                    "The molecules meet, but the energy barrier for advanced synthesis is too high — a stronger catalytic field is needed.")

        return self._t(
            "汤中的分子结构相互排斥，无法组合。也许需要不同类型的分子搭档。",
            "The molecular structures in the soup repel one another and cannot combine. Perhaps a different kind of molecular partner is needed.")

    def _do_submit(self) -> str:
        score = self._compute_score()
        ending = self._render_ending()
        return self._t("你主动提交了本次实验结果。\n\n",
                       "You have submitted this experiment's results.\n\n") + ending

    # ── 辅助方法 ──────────────────────────────────────────────────────────────

    def _has_reactant(self, reactant: str) -> bool:
        """检查汤中是否存在某种反应物（化合物或分子）"""
        if reactant in COMPOUNDS:
            return self._soup_compounds.get(reactant, 0) >= 1
        else:
            return self._soup_molecules.get(reactant, 0) >= 1

    def _consume_reactant(self, reactant: str):
        """消耗一单位反应物"""
        if reactant in COMPOUNDS:
            self._soup_compounds[reactant] -= 1
        else:
            self._soup_molecules[reactant] -= 1
            if self._soup_molecules[reactant] <= 0:
                del self._soup_molecules[reactant]

    def _compute_score(self) -> int:
        """计算当前得分"""
        # 统计分子数量
        l1_labels = {r[2] for r in self._l1_reactions}
        l2_labels = {r[2] for r in self._l2_reactions}
        l3_label = self._l3_reaction[2]

        l1_count = sum(self._soup_molecules.get(lb, 0) for lb in l1_labels)
        l2_count = sum(self._soup_molecules.get(lb, 0) for lb in l2_labels)
        l3_count = self._soup_molecules.get(l3_label, 0)

        base_score = l1_count * 10 + l2_count * 25 + l3_count * 80

        # 催化剂运用奖励
        cat_bonus = 5 if self._cat_bonus_triggered else 0

        # 步数惩罚
        step_penalty = max(0, (self._turn - 30) * 0.5)

        score = base_score + cat_bonus - step_penalty
        return max(0, int(score))

    def _is_exhausted(self) -> bool:
        """判断原料耗尽且汤为空且无分子可合成"""
        stock_empty = all(v == 0 for v in self._stock.values())
        soup_empty = (all(v == 0 for v in self._soup_compounds.values()) and
                      not self._soup_molecules)
        return stock_empty and soup_empty

    def _render_status_text(self) -> str:
        """生成状态观察文字"""
        # 原料库
        stock_str = "  ".join(f"{c}×{self._stock[c]}" for c in COMPOUNDS)

        # 汤中内容
        soup_c = [f"{c}×{self._soup_compounds[c]}"
                  for c in COMPOUNDS if self._soup_compounds[c] > 0]
        soup_m = [f"[{lb}]×{cnt}" for lb, cnt in sorted(self._soup_molecules.items()) if cnt > 0]
        soup_content = "  ".join(soup_c + soup_m) if (soup_c or soup_m) else self._t("（空）", "(empty)")

        # 有机分子分级显示
        l1_labels = {r[2] for r in self._l1_reactions}
        l2_labels = {r[2] for r in self._l2_reactions}
        l3_label = self._l3_reaction[2]

        p1 = self._t("初级", "L1 ")
        p2 = self._t("中级", "L2 ")
        p3 = self._t("高级", "L3 ")
        l1_parts = [f"{p1}[{lb}]×{self._soup_molecules[lb]}"
                    for lb in sorted(l1_labels) if self._soup_molecules.get(lb, 0) > 0]
        l2_parts = [f"{p2}[{lb}]×{self._soup_molecules[lb]}"
                    for lb in sorted(l2_labels) if self._soup_molecules.get(lb, 0) > 0]
        l3_parts = [f"{p3}[{l3_label}]×{self._soup_molecules[l3_label]}"]  if self._soup_molecules.get(l3_label, 0) > 0 else []

        mol_str = "  ".join(l1_parts + l2_parts + l3_parts) if (l1_parts or l2_parts or l3_parts) else self._t("（无）", "(none)")

        lines = [
            self._t("【实验状态】", "[Experiment Status]"),
            self._t(f"原料库：{stock_str}", f"Reagent stock: {stock_str}"),
            self._t(f"汤中内容：{soup_content}（催化剂浓度：{self._cat_level}）",
                    f"Soup contents: {soup_content} (catalyst concentration: {self._cat_level})"),
            self._t(f"有机分子：{mol_str}", f"Organic molecules: {mol_str}"),
            self._t(f"当前得分：{self._compute_score()} | 步数：{self._turn}/{self.MAX_TURNS}",
                    f"Current score: {self._compute_score()} | Steps: {self._turn}/{self.MAX_TURNS}"),
        ]
        return "\n".join(lines)

    def _render_ending(self) -> str:
        """生成结算文字"""
        score = self._compute_score()

        l1_labels = {r[2] for r in self._l1_reactions}
        l2_labels = {r[2] for r in self._l2_reactions}
        l3_label = self._l3_reaction[2]

        l1_count = sum(self._soup_molecules.get(lb, 0) for lb in l1_labels)
        l2_count = sum(self._soup_molecules.get(lb, 0) for lb in l2_labels)
        l3_count = self._soup_molecules.get(l3_label, 0)

        if l3_count >= 1:
            summary = self._t("生命的雏形在你手中成形，原始汤中涌现出高级有机结构。",
                              "The rudiment of life takes shape in your hands; a higher organic structure emerges from the primordial soup.")
        elif l2_count >= 1:
            summary = self._t("中级有机分子已初步形成，但生命的完整链条尚未构建。",
                              "Intermediate organic molecules have begun to form, but the complete chain of life is not yet built.")
        elif l1_count >= 1:
            summary = self._t("你发现了初步的有机化学反应，但距离真正的生命还很遥远。",
                              "You have discovered rudimentary organic chemistry, but true life remains far off.")
        else:
            summary = self._t("这次实验未能催化出任何有机分子，混沌依旧混沌。",
                              "This experiment failed to catalyze any organic molecule; chaos remains chaos.")

        penalty = max(0, (self._turn - 30) * 0.5)
        lines = [
            "=" * 52,
            self._t("实验结算", "Experiment Settlement"),
            "=" * 52,
            "",
            self._t(f"初级有机分子（L1）：{l1_count} 个 × 10 分",
                    f"Primary organic molecules (L1): {l1_count} × 10 pts"),
            self._t(f"中级有机分子（L2）：{l2_count} 个 × 25 分",
                    f"Intermediate organic molecules (L2): {l2_count} × 25 pts"),
            self._t(f"高级有机分子（L3）：{l3_count} 个 × 80 分",
                    f"Higher organic molecules (L3): {l3_count} × 80 pts"),
            self._t(f"催化剂运用奖励：{'+5' if self._cat_bonus_triggered else '0'} 分",
                    f"Catalyst-use bonus: {'+5' if self._cat_bonus_triggered else '0'} pts"),
            self._t(f"步数惩罚：-{penalty:.1f} 分",
                    f"Step penalty: -{penalty:.1f} pts"),
            "",
            self._t(f"最终得分：{score} 分", f"Final score: {score} pts"),
            self._t(f"用时：{self._turn} / {self.MAX_TURNS} 步",
                    f"Steps used: {self._turn} / {self.MAX_TURNS}"),
            "",
            summary,
        ]
        return "\n".join(lines)
