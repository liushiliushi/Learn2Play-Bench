"""ButterflyGarden（蝶园）——隐藏遗传育种的序列学习游戏（循环遗传律版）。

玩家经营一座蝴蝶园。每回合给一张「悬赏图」（目标长相），玩家挑两只蝴蝶配对、
看下一代长相、再挑再配，逼近目标。蝴蝶的遗传规律全部隐藏，只能靠配种摸出来。

本版的「生物学」**刻意不是孟德尔显隐性**（那套在训练语料里、会被一眼认出而秒解），
而是四条需要「提假设→被反例证伪→归纳」才能发现的非直觉律，且后代**确定**（同样两只
永远产同一只），把难度落在「归纳发现」而非「运气」上：

  L1 触角：强弱压制——四种触角有隐藏强弱序，后代取更强的那个。            —— 暖场层
  L2 大小：融合遗传——后代大小 = 双亲平均（四舍五入），无离散等位。       —— 第一次认知冲突
  L3 翅色：非传递环形压制——五色排成隐藏的循环序，A 压 B、B 压 C…绕成圈，   —— 招牌反孟德尔
           没有「最强色」；后代取循环里胜出的那个亲本色。
  L4 花纹：跨性状上位遮盖——基础取双亲中更复杂的花纹，但若后代触角恰为隐藏  —— 末段钥匙
           的「抑制型」，则花纹被压成「无」，无视双亲。

设计要点（与 Learn2Play Bench 其它游戏对齐）：
  · 隐藏「规律」不是「数据」：确定性后代，但一次配种只是一条数据点，规律要靠对照配种归纳。
  · laws 由 seed 固定、整局所有回合不变 = 这座园子的「生物学」，要跨回合学下来；
    每回合只重洗「开局蝴蝶 + 目标」，记不住定式、只能迁移理解。
  · 紧预算（6 次配种）：单局内「边学边建」凑不齐，逼跨局积累规律（懂律者才建得出）。
  · 计分不再 100 封顶：每只新后代按接近目标的程度累计分数；精准命中只是高价值事件，
    不会提前结束本局，剩余配种仍可通过培育更多高质量/新表型继续拉开差距。

接口契约（见 play.py / main.py）：reset()->(obs,info)；step(cmd)->(obs,reward,done,info)；
get_valid_actions()；可选 get_action_label()；属性 score/turn_count/MAX_TURNS/done/_lang/_episode。
"""

import random


# ── 特征值与显示（表型直接存值，无 genotype/等位基因概念）──────────────────────
COLORS = ["赤", "橙", "黄", "绿", "青", "蓝", "紫"]  # 7 色，构成隐藏的循环压制序（非传递；环大→需更多观测才测得全）
PATS = ["无", "星点", "螺旋", "网纹"]            # 花纹，索引 = 复杂度（无最简、网纹最繁）
SIZES = ["极小", "小", "中", "大", "极大"]       # 大小，索引 = 数值（融合取平均）
ANTS = ["直", "卷", "羽", "钩"]                  # 触角，隐藏强弱序

_EN = {
    "赤": "Crimson", "橙": "Orange", "黄": "Yellow", "绿": "Green", "青": "Cyan", "蓝": "Blue", "紫": "Purple",
    "无": "Plain", "星点": "Starspot", "螺旋": "Spiral", "网纹": "Web",
    "极小": "Tiny", "小": "Small", "中": "Medium", "大": "Large", "极大": "Huge",
    "直": "Straight", "卷": "Curled", "羽": "Feathery", "钩": "Hooked",
}

TRAITS = ("color", "pattern", "size", "antenna")
_SPACE = {"color": COLORS, "pattern": PATS, "size": SIZES, "antenna": ANTS}


def _v(trait, idx, lang):
    label = _SPACE[trait][idx]
    return _EN.get(label, label) if lang == "en" else label


class Butterfly:
    """一只蝴蝶：四项可见长相（表型索引）。没有隐藏基因——遗传律直接作用在表型上。"""
    __slots__ = ("bid", "color", "pattern", "size", "antenna")

    def __init__(self, bid, color, pattern, size, antenna):
        self.bid = bid
        self.color = color
        self.pattern = pattern
        self.size = size
        self.antenna = antenna

    def pheno(self):
        return {"color": self.color, "pattern": self.pattern,
                "size": self.size, "antenna": self.antenna}


class ButterflyGardenGame:
    MAX_TURNS = 6           # 配种预算（只有 mate 消耗）：小到单局无法「学全规律+建成目标」→ 逼跨回合累积观测；
                            # 懂律者 ≤4 次即可建出（见 _build_round 接受 cost≤4），留 2 次余量
    CAPACITY = 18           # 园子容量（9 母本 + 后代空间；直线解不必被迫放生，重探索才需放生腾位）
    LITTER = 1              # 每次配种产 1 只确定性后代（同样两只永远同一只，无随机）
    _HARD_CALLS = 600       # 防空转死循环的硬上限（任何 step 都计数）
    _MATCH_POINTS = (0, 4, 18, 49, 120)
    _NOVELTY_BONUS = (0, 1, 4, 10, 25)
    _DUPLICATE_DECAY = 0.25
    _FIRST_TARGET_BONUS_PER_UNUSED_CROSS = 12

    # ── 每局上限一致化（与 hezu/synergycorp 同思路）───────────────────────────────
    # 累计计分下，本局天花板取决于「重洗出的目标/母本有多富」→ max 逐局不同、还偏高。
    # 为让学习曲线可跨局比较，用生成期拒绝采样把「本局精确最优」统一到固定值 _TARGET_CEILING：
    # 只接受「6 次配种的精确最优 == _TARGET_CEILING」的 (目标+母本) 重洗。布局仍逐局重洗，
    # 学习性不变。因重放模式下 reset() 每个动作都会重跑、精确最优（分支限界）个别局要数十秒，
    # 不能在此现算 → 离线预计算 (seed→episode→salt) 烘成静态表，reset() 查表零成本。
    # 表由 tools 侧的精确 oracle 生成并逐局用真实引擎重放校验（见 theoretical_bounds_audit）。
    # 未在表内的 seed/episode 回退到「首个可解局」（不对齐、max 仍会浮动，仅供表外探索）。
    _TARGET_CEILING = 439
    _CEILING_SALT = {
        1: {0: 12, 1: 1, 2: 194, 3: 50, 4: 7, 5: 8, 6: 15, 7: 17, 8: 88, 9: 135, 10: 39, 11: 42},
        2: {0: 15, 1: 41, 2: 36, 3: 261, 4: 76, 5: 55, 6: 127, 7: 36, 8: 1, 9: 2, 10: 19, 11: 91},
    }

    def __init__(self, seed=None, lang="zh"):
        self._seed = 0 if seed is None else int(seed)
        self._lang = lang
        self._episode = 0
        self._episode_next = 1
        self.done = False
        self.score = 0
        self.turn_count = 0
        self._calls = 0
        self._laws = self._make_laws()

    # ── 隐藏规律：由 seed 固定，整局所有回合不变（要跨回合学下来的「生物学」）──────
    def _make_laws(self):
        rng = random.Random(f"{self._seed}|laws")
        ant_strength = list(range(len(ANTS)))     # 触角强弱序（值=强度秩，越大越强）
        rng.shuffle(ant_strength)
        color_ring = list(range(len(COLORS)))     # 翅色循环压制序（隐藏排列，非彩虹序）
        rng.shuffle(color_ring)
        return {
            "ant_strength": ant_strength,          # ant_strength[antenna_idx] -> 强度
            "color_ring": color_ring,              # 色索引在环上的位置序（循环）
            "color_d": 3,                          # 每色压制环上其后 d 个；7 色 d=3 → 无平局
            "pat_suppressor": rng.randrange(len(ANTS)),  # 抑制型触角：后代触角=它则花纹被压成「无」
        }

    # ── 遗传律：确定性地由双亲表型算出后代表型 ────────────────────────────────────
    def _ant_child(self, a1, a2):
        st = self._laws["ant_strength"]
        return a1 if st[a1] >= st[a2] else a2

    def _size_child(self, s1, s2):
        return (s1 + s2 + 1) // 2               # 平均、四舍五入（half-up）

    def _color_child(self, c1, c2):
        if c1 == c2:
            return c1
        ring = self._laws["color_ring"]
        n, d = len(ring), self._laws["color_d"]
        p1, p2 = ring.index(c1), ring.index(c2)
        if (p1 - p2) % n in range(1, d + 1):    # c1 在环上领先 c2 恰 1..d 步 → c1 胜
            return c1
        return c2                                # 否则 c2 胜（5 色 d=2 下必有一方胜、无平局）

    def _pat_child(self, pt1, pt2, child_ant):
        if child_ant == self._laws["pat_suppressor"]:
            return 0                             # 抑制型触角 → 花纹被压成「无」（上位遮盖）
        return max(pt1, pt2)                      # 否则取更复杂的花纹（复杂度显性）

    def _cross_ph(self, a, b):
        """在表型元组 (color,pattern,size,antenna) 上做一次确定性配种，返回后代表型元组。"""
        ant = self._ant_child(a[3], b[3])
        return (self._color_child(a[0], b[0]),
                self._pat_child(a[1], b[1], ant),
                self._size_child(a[2], b[2]),
                ant)

    def _cross(self, p1, p2):
        c, pt, s, a = self._cross_ph((p1.color, p1.pattern, p1.size, p1.antenna),
                                     (p2.color, p2.pattern, p2.size, p2.antenna))
        child = Butterfly(self._next_id, c, pt, s, a)
        self._next_id += 1
        return child

    # ── 重洗：开局蝴蝶 + 目标（由 seed|episode 固定，可重放；保证可达且开局远离目标）──
    def reset(self):
        ep = self._episode
        salt = self._CEILING_SALT.get(self._seed, {}).get(ep)
        if salt is not None:                     # 上限一致化：查预计算 salt（本局精确最优恒 = _TARGET_CEILING）
            built = self._build_round(ep, salt)
        else:                                    # 表外 seed/episode：回退「首个可解局」（不对齐上限）
            salt = 0
            built = self._build_round(ep, salt)
            while built is None:                 # 少数目标从某开局池不可达 → 换 salt 重建，保证每局可解
                salt += 1
                built = self._build_round(ep, salt)
        self.target, self.garden = built
        self._episode_next = self._episode + 1   # 本局结束时推进（main.py 复用 game 对象→每局重洗目标）
        self._next_id = len(self.garden)
        self._founder_ids = {b.bid for b in self.garden}   # 开局母本永久保留、不可放生（稀有源不灭绝）
        self.selected = []
        self.done = False
        self.turn_count = 0
        self._calls = 0
        self._best = self._eval_garden()
        self._seen_offspring = {}
        self._first_exact_turn = None
        self.score = 0
        return self._render(intro=True), {"valid": self.get_valid_actions()}

    def _build_round(self, ep, salt):
        """构造一回合的 (target, stock)。每只母本尽量至多对上目标 1 项（开局远离目标→低起点），
        母本覆盖目标四项 + 供路由的辅料，并保证：翅色环上有 Tc 的「猎物色」、大小两端各≥2 份、
        最弱触角≥2 份（这三处是确定性律下唯一需要「同款自交」的地方，缺则某些目标不可达）。
        copy-aware 可达性校验通过才返回；否则返回 None 换 salt。"""
        rng = random.Random(f"{self._seed}|{ep}|{salt}|round")
        target = {t: rng.randrange(len(_SPACE[t])) for t in TRAITS}
        Tc, Tp, Ts, Ta = target["color"], target["pattern"], target["size"], target["antenna"]

        def other(trait, *avoid):
            opts = [i for i in range(len(_SPACE[trait])) if i not in avoid]
            return rng.choice(opts)

        ring = self._laws["color_ring"]
        prey_c = ring[(ring.index(Tc) - 1) % len(ring)]        # Tc 在环上压制的一个色（异交即得 Tc）
        weak_a = min(range(len(ANTS)), key=lambda i: self._laws["ant_strength"][i])  # 最弱触角
        lo, hi = 0, len(SIZES) - 1                              # 大小两端
        # 猎物色的一个更弱前驱（保证 prey 母本自身 color≠Tc 且可与别色异交路由）
        prey_c2 = ring[(ring.index(prey_c) - 1) % len(ring)]

        stock = []

        def add(color, pattern, size, antenna):
            # 每只母本至多对上目标 1 项（开局远离目标→低起点）：非指定项由构造避开目标值。
            # 有界兜底：万一仍 >1 匹配，微扰花纹几次压回（构造已保证，兜底几乎不触发）。
            b = Butterfly(len(stock), color, pattern, size, antenna)
            for _ in range(len(PATS)):
                if self._match_count_ph((b.color, b.pattern, b.size, b.antenna), target) <= 1:
                    break
                b.pattern = other("pattern", Tp, b.pattern)
            stock.append(b)

        # 四个「单项携带者」：各带目标某一项、其余三项避开目标值。
        # 当目标恰为极端大小/最弱触角时，对应携带者(带大小/带触角)兼任「第 2 份来源」，与下面的
        # 常驻来源凑够≥2 份，使确定性律下「同款自交」可行。
        add(Tc,                 other("pattern", Tp), other("size", Ts),      other("antenna", Ta))   # 带色
        add(other("color", Tc), Tp,                   other("size", Ts),      other("antenna", Ta))   # 带纹
        add(other("color", Tc), other("pattern", Tp), Ts,                     other("antenna", Ta))   # 带大小
        add(other("color", Tc), other("pattern", Tp), other("size", Ts),      Ta)                     # 带触角
        # 辅料：翅色猎物 + 大小两端各一份 + 最弱触角一份（非指定项都避开目标 & 避开彼此的关键值）：
        add(prey_c,             other("pattern", Tp), other("size", Ts),      other("antenna", Ta))   # Tc 的猎物色
        add(prey_c2,            other("pattern", Tp), lo,                     other("antenna", Ta, weak_a))  # 极小来源
        add(other("color", Tc), other("pattern", Tp), hi,                     other("antenna", Ta, weak_a))  # 极大来源
        add(other("color", Tc), other("pattern", Tp), other("size", Ts, lo, hi), weak_a)               # 最弱触角来源

        rng.shuffle(stock)
        for i, b in enumerate(stock):
            b.bid = i

        # copy-aware 可达性校验：自交仅当该表型≥2 份时才算数；异交(a≠b)总可行。
        # 需 2 ≤ 合成代价 ≤ 预算(6)：拒绝「一次配种即成」的送分局；上限=预算，让「弱×弱自交凑最弱触角/
        # 极端大小」这类多步目标也能过门槛（否则会被系统性筛掉、目标分布偏斜、还回避了最难的子情形）。
        cost = self._synth_cost([(b.color, b.pattern, b.size, b.antenna) for b in stock],
                                (Tc, Tp, Ts, Ta), budget=self.MAX_TURNS)
        if cost is None or cost < 2:
            return None
        return target, stock

    def _synth_cost(self, stock_phenos, target_tuple, budget):
        """目标表型的最小「合成树」配种次数（copy-aware，无复用上界）；> budget 或不可达返回 None。
        规则：异交 cross(a,b) a≠b 总可行（两只不同蝴蝶必备）；自交 cross(a,a) 仅当 a 有≥2 份可用——
        开局≥2 份，或 a 本身可由一次异交造出（则能各造一份）。合成树代价 = cost(a)+cost(b)+1
        （两棵独立子树，物理可复现）。表型空间有限（5×4×5×4=400），松弛到不动点，开销可忽略。"""
        from collections import Counter
        cnt = Counter(stock_phenos)
        INF = 10 ** 9
        cost = {ph: 0 for ph in cnt}            # 开局表型代价 0
        multi = {ph for ph, c in cnt.items() if c >= 2}   # 有≥2 份、可自交的表型
        for _ in range(budget + 3):             # 松弛到不动点
            updated = False
            cur = list(cost.keys())
            for i in range(len(cur)):
                for j in range(i, len(cur)):
                    a, b = cur[i], cur[j]
                    if a == b and a not in multi:   # 单份表型不可自交
                        continue
                    if cost[a] >= INF or cost[b] >= INF:
                        continue
                    ch = self._cross_ph(a, b)
                    nc = cost[a] + cost[b] + 1
                    if ch not in cost or nc < cost[ch]:
                        cost[ch] = min(cost.get(ch, INF), nc)
                        multi.add(ch)               # 异交造出的可反复造 → 视为≥2 份可用
                        updated = True
            if not updated:
                break
        c = cost.get(target_tuple, INF)
        return c if c <= budget else None

    # ── 计分：累计每只后代价值；4/4 不再封顶、不提前结束 ─────────────────────────
    @staticmethod
    def _match_count_ph(ph_tuple, target):
        keys = ("color", "pattern", "size", "antenna")
        return sum(1 for i, k in enumerate(keys) if ph_tuple[i] == target[k])

    @staticmethod
    def _ph_tuple(b):
        return (b.color, b.pattern, b.size, b.antenna)

    def _match_count(self, b):
        return sum(1 for k in TRAITS if getattr(b, k) == self.target[k])

    def _eval_garden(self):
        return max((self._match_count(b) for b in self.garden), default=0)

    @classmethod
    def _score_of(cls, matched):
        return cls._MATCH_POINTS[matched]

    def _child_gain(self, child, matched):
        ph = self._ph_tuple(child)
        seen = self._seen_offspring.get(ph, 0)
        base = self._score_of(matched)
        if seen == 0:
            gain = base + self._NOVELTY_BONUS[matched]
        elif base > 0:
            gain = max(1, round(base * (self._DUPLICATE_DECAY ** min(seen, 4))))
        else:
            gain = 0

        exact_bonus = 0
        if matched == len(TRAITS) and self._first_exact_turn is None:
            remaining = max(0, self.MAX_TURNS - self.turn_count)
            exact_bonus = self._FIRST_TARGET_BONUS_PER_UNUSED_CROSS * remaining
            gain += exact_bonus
            self._first_exact_turn = self.turn_count

        self._seen_offspring[ph] = seen + 1
        return gain, seen == 0, exact_bonus

    # ── 动作 ──────────────────────────────────────────────────────────────────
    def get_valid_actions(self):
        if self.done:
            return []
        acts = []
        ids = [b.bid for b in self.garden]
        if len(self.selected) < 2:
            acts += [f"pick_{i}" for i in ids if i not in self.selected]
        if self.selected:
            acts.append("clear")
        if len(self.selected) == 2:
            acts.append("mate")
        acts += [f"release_{i}" for i in ids if i not in self._founder_ids]  # 只放生后代
        return acts

    def get_action_label(self, a):
        if a in ("target", "mate", "clear"):
            return {"target": "查看悬赏图", "mate": "▶ 配对这两只", "clear": "取消选择"}[a] \
                if self._lang != "en" else {"target": "Show target", "mate": "▶ Breed the pair", "clear": "Clear selection"}[a]
        if a.startswith("pick_") or a.startswith("release_"):
            verb, sid = a.split("_", 1)
            pre = ("选 " if verb == "pick" else "放生 ") if self._lang != "en" else ("Pick " if verb == "pick" else "Release ")
            return f"{pre}{sid}"
        return a

    def _short(self, ph):
        return "·".join(_v(k, ph[k], self._lang) for k in TRAITS)

    def _short_b(self, b):
        return self._short(b.pheno())

    def _find(self, bid):
        for b in self.garden:
            if b.bid == bid:
                return b
        return None

    def step(self, command):
        self._calls += 1
        if self.done:
            return self._render(), 0, True, {"valid": []}
        if self._calls > self._HARD_CALLS:
            self.finalize()
            return self._render(closing=True), 0, True, {"valid": []}

        cmd = command.strip()
        low = cmd.lower()
        prev = self.score
        msg = ""

        if low == "status":
            return self._render(), 0, False, {"valid": self.get_valid_actions()}
        board_changed = False
        if low == "target":
            msg = self._target_line()
        elif low == "clear":
            self.selected = []
            msg = self._t("已取消选择。当前选中：无", "Selection cleared. Selected: none")
        elif low.startswith("pick_"):
            msg = self._pick(low[5:])
        elif low.startswith("release_"):
            msg = self._release(low[8:]); board_changed = True
        elif low == "mate":
            msg = self._mate(); board_changed = True
        else:
            msg = self._t(f"无法识别的指令：{cmd}", f"Unknown command: {cmd}")

        reward = self.score - prev
        info = {"valid": self.get_valid_actions()}
        out = self._render(head=msg) if (board_changed or self.done) else msg
        return out, reward, self.done, info

    def _pick(self, sid):
        if not sid.isdigit() or not self._find(int(sid)):
            return self._t(f"园里没有 #{sid}。", f"No #{sid} in the garden.")
        bid = int(sid)
        if bid in self.selected:
            return self._t(f"#{bid} 已在选中里。", f"#{bid} already selected.")
        if len(self.selected) >= 2:
            return self._t("已选了两只，先配对或取消选择。", "Two already picked — mate or clear first.")
        self.selected.append(bid)
        if len(self.selected) == 2:
            return self._t(f"已选 #{self.selected[0]} 和 #{self.selected[1]}，可以配对了。",
                           f"Picked #{self.selected[0]} and #{self.selected[1]} — ready to mate.")
        return self._t(f"已选 #{bid}，再选一只。", f"Picked #{bid} — pick one more.")

    def _release(self, sid):
        if not sid.isdigit() or not self._find(int(sid)):
            return self._t(f"园里没有 #{sid}。", f"No #{sid} in the garden.")
        bid = int(sid)
        if bid in self._founder_ids:
            return self._t(f"#{bid} 是原种母本，不能放生（只能放生你配出来的后代）。",
                           f"#{bid} is founding stock — can't be released (only bred offspring can).")
        self.garden = [b for b in self.garden if b.bid != bid]
        self.selected = [s for s in self.selected if s != bid]
        return self._t(f"放生了 #{bid}。", f"Released #{bid}.")

    def _mate(self):
        if len(self.selected) != 2:
            return self._t("先选两只蝴蝶。", "Pick two butterflies first.")
        if len(self.garden) + self.LITTER > self.CAPACITY:
            return self._t(f"园子要满了（{len(self.garden)}/{self.CAPACITY}），先放生几只。",
                           f"Garden nearly full ({len(self.garden)}/{self.CAPACITY}) — release some first.")
        p1, p2 = self._find(self.selected[0]), self._find(self.selected[1])
        child = self._cross(p1, p2)
        self.garden.append(child)
        self.selected = []
        self.turn_count += 1

        # 更新最好成绩 + 累计计分（放生不回滚已获得的育种图鉴分）
        m = self._match_count(child)
        if m > self._best:
            self._best = m
        gain, new_pheno, exact_bonus = self._child_gain(child, m)
        self.score += gain

        lines = [self._t(f"第 {self.turn_count}/{self.MAX_TURNS} 次配种，产下：",
                         f"Cross {self.turn_count}/{self.MAX_TURNS} — offspring:")]
        tags = []
        if new_pheno:
            tags.append(self._t("新表型", "new phenotype"))
        if exact_bonus:
            tags.append(self._t(f"首次精准 +{exact_bonus}", f"first exact +{exact_bonus}"))
        tag = ("  " + " / ".join(tags)) if tags else ""
        lines.append(f"  #{child.bid}  {self._short_b(child)}  [{m}/4]  +{gain}{tag}")

        if m >= 4:
            lines.append(self._t("★ 培育出了悬赏图上的蝴蝶；本局继续，剩余配种仍会计分。",
                                 "★ You bred the wanted butterfly; the round continues and remaining crosses still score."))
        if self.turn_count >= self.MAX_TURNS:
            self.done = True
            lines.append(self._t("配种次数用尽。", "Out of crosses."))
        if self.done:
            self._episode = self._episode_next
        return "\n".join(lines)

    def finalize(self):
        """EOF/quit 时定格当前最好成绩（蝶园计分本就单调，无需演完）。"""
        self.done = True
        self._episode = self._episode_next

    # ── 渲染 ──────────────────────────────────────────────────────────────────
    def _t(self, zh, en):
        return en if self._lang == "en" else zh

    def _target_line(self):
        return self._t(f"悬赏图：{self._short(self.target)}",
                       f"Wanted: {self._short(self.target)}")

    def _render(self, intro=False, head="", closing=False):
        L = []
        if intro:
            L.append(self._t(
                "【蝶园】挑两只蝴蝶配对，看下一代长相，一代代凑出悬赏图上的那一只。\n"
                "蝴蝶怎么把长相传给后代，藏着规律——只能靠配种、对照、被反例打脸后摸出来。\n"
                "· 后代是确定的：同样的两只永远产下同一只（不靠运气，靠看懂规律）。\n"
                "· 标「母本」的是开局原种，永久保留、不能放生（稀有长相不流失、目标始终配得出来）；只有你配出的后代能放生腾地方。",
                "[Butterfly Garden] Pick two butterflies to breed, watch the offspring, and breed your way\n"
                "toward the wanted butterfly. How looks pass to offspring is hidden — discover it by breeding,\n"
                "comparing, and revising when a cross defies your guess.\n"
                "· Offspring are deterministic: the same pair always yields the same child (no luck — it rewards understanding the rules).\n"
                "· Ones tagged 'founder' are your original stock: permanent, cannot be released (rare looks never vanish, target stays reachable); only offspring you breed can be released."))
        if head:
            L.append(head)
        L.append(self._target_line())
        sel = ("  " + self._t("当前选中：", "Selected: ") +
               (" ".join(f"#{s}" for s in self.selected) if self.selected else self._t("无", "none")))
        L.append(self._t(f"配种 {self.turn_count}/{self.MAX_TURNS}   园子 {len(self.garden)}/{self.CAPACITY}",
                         f"Crosses {self.turn_count}/{self.MAX_TURNS}   Garden {len(self.garden)}/{self.CAPACITY}") + sel)
        L.append(self._t("园中蝴蝶（编号 长相 [对上目标几项]）：", "Garden (id  look  [traits matched]):"))
        for b in self.garden:
            star = (" ←选中" if self._lang != "en" else " <picked") if b.bid in self.selected else ""
            fnd = ("  母本" if self._lang != "en" else "  founder") if b.bid in self._founder_ids else ""
            L.append(f"  #{b.bid}  {self._short_b(b)}  [{self._match_count(b)}/4]{fnd}{star}")
        L.append(self._t(f"最好表型：对上 {self._best}/4 项   累计得分 {self.score}",
                         f"Best phenotype: {self._best}/4 matched   Score {self.score}"))
        if closing or self.done:
            L.append(self._t(f"== 本局结束，最终得分 {self.score} ==",
                             f"== Round over, final score {self.score} =="))
        return "\n".join(L)
