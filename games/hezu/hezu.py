"""
合租室友（Roommates）—— 配房优化 + 跨轮归纳隐藏「相处之道」。

黑盒：你是租房中介。每轮有 9 位房客(各性格类型)要分进 3 间三人间。你决定谁和谁住;
入住一阵后,每屋反馈住得如何(屋内室友两两相处之和),总分 = 三屋之和。
谁和谁处得来、谁和谁犯冲是隐藏门道(seed 固定),只能从一轮轮的「屋内组合 → 住得如何」
里跨轮归纳出来,再把配房越做越好。

隐藏「相处之道」（seed 固定、跨轮不变;开发者参考,玩家不可见）：
  - 两两相处:5 种性格排成一条隐藏环序(随机)。环上相邻 → 合得来 +1;隔一位 → 犯冲 −1;同类型 → 0。
  - 三人组化学反应(非线性,关键难点):少数几个「三人组合」(类型多重集)有隐藏的额外效应
    (特别旺 +5 或 特别炸 −5),叠加在两两之上。光会两两算不准这些屋——必须把那仨真凑一屋
    才看得到，且要从「实际和睦 ≠ 两两预测」的偏差里发现是哪几个三人组特殊。
  - 一屋和睦度 = 屋内 3 对两两相处之和 + (若该屋类型组合是特殊三人组)其化学反应值。
  - 一轮总分 = 三屋和睦度之和。
计分（渐进）：score = 总和睦度。oracle 知全部门道→选最优分配=该轮上限(每轮随房客而变,见 best_total)。
  随机分配 ≈ 0。学会两两(快) + 发现特殊三人组(慢)后才逼近每轮上限。
"""

import random
from collections import Counter
from itertools import combinations, combinations_with_replacement

TYPES = ["夜猫子", "洁癖", "社牛", "肥宅", "吃货"]
N_TENANTS = 9
N_ROOMS = 3
ROOM_CAP = 3
ROOM_LEVELS = ["鸡飞狗跳", "摩擦不断", "平平淡淡", "还算和睦", "其乐融融"]   # by harmony

# English display names. TYPES stays the canonical (Chinese) key used everywhere in
# the hidden logic (self.pos, special-trio keys, seed determinism) — never localize
# the keys, only how they are shown.
ROOM_LEVELS_EN = ["Chaos", "Constant friction", "So-so", "Fairly cordial", "Harmonious"]
TYPE_EN = {"夜猫子": "Night Owl", "洁癖": "Neat Freak", "社牛": "Extrovert",
           "肥宅": "Homebody", "吃货": "Foodie"}


class HezuGame:
    MAX_TURNS = 40

    def __init__(self, seed=None, lang="zh"):
        self._lang = lang
        self.seed = seed
        self._episode = 0
        rng = random.Random(seed)
        cyc = TYPES[:]
        rng.shuffle(cyc)
        self.pos = {t: i for i, t in enumerate(cyc)}
        # ── 三人组化学反应：少数特殊类型组合有额外效应 ──
        all_trios = list(combinations_with_replacement(sorted(TYPES), 3))   # 35 个多重集
        rng.shuffle(all_trios)
        effs = [5, 5, -5]                                                   # 2 旺(+5) 1 炸(-5)
        self.special = {all_trios[i]: effs[i] for i in range(len(effs))}
        self.reset()

    # ── i18n helpers（TYPES/ROOM_LEVELS 的 key 不变，只本地化显示） ──
    def _t(self, zh, en):
        return en if self._lang == "en" else zh

    def _tp(self, t):
        return TYPE_EN[t] if self._lang == "en" else t

    def _lvl(self, tier):
        return (ROOM_LEVELS_EN if self._lang == "en" else ROOM_LEVELS)[tier]

    def _g(self, i):
        return f"Guest{i}" if self._lang == "en" else f"房客{i}"

    # ── 隐藏律：两人相处(对称) ──
    def _h(self, A, B):
        d = (self.pos[A] - self.pos[B]) % 5
        if d == 1 or d == 4:      # 环上相邻
            return 1
        if d == 2 or d == 3:      # 环上隔一位
            return -1
        return 0                  # 同类型

    def _trio_effect(self, types3):
        return self.special.get(tuple(sorted(types3)), 0)

    def _room_harmony(self, types3):
        return sum(self._h(a, b) for a, b in combinations(types3, 2)) + self._trio_effect(types3)

    def _room_tier(self, h):
        if h >= 3:
            return 4
        if h >= 1:
            return 3
        if h == 0:
            return 2
        if h >= -2:
            return 1
        return 0

    # ── 枚举 9→3×3 的所有分配（280 种），求最优总分（oracle / 上限）──
    def _partitions(self, ids):
        a0 = ids[0]
        rest = ids[1:]
        for g1 in combinations(rest, 2):
            r1 = [x for x in rest if x not in g1]
            b0 = r1[0]
            rr = r1[1:]
            for g2 in combinations(rr, 2):
                g3 = tuple(x for x in rr if x not in g2)
                yield ((a0,) + g1, (b0,) + g2, g3)

    def _total_of(self, partition, types=None):
        tps = self._type if types is None else types
        return sum(self._room_harmony([tps[i] for i in grp]) for grp in partition)

    def best_total(self, types=None):
        return max(self._total_of(p, types) for p in self._partitions(list(range(N_TENANTS))))

    # ── 每轮上限校准：房客照样每轮重抽，但拒绝采样保证「精确最优分配的总分」
    #    恰等于本 seed 的固定目标值（候选轮扫描取众数）——每轮 max 一致，
    #    学习曲线不叠加「这轮房客好不好排」的实例噪声。──
    CALIB_SAMPLES   = 40
    CALIB_MAX_TRIES = 400

    def _draw_types(self, rng):
        while True:
            types = [rng.choice(TYPES) for _ in range(N_TENANTS)]
            if len(set(types)) >= 3:
                return types

    def _seed_target(self):
        if getattr(self, "_cal_target", None) is None:
            scores = [self.best_total(self._draw_types(random.Random(f"{self.seed}-cal-{k}")))
                      for k in range(self.CALIB_SAMPLES)]
            scores = [s for s in scores if s >= 2]     # 该轮确有可观的最优，配房才有意义
            counts = Counter(scores)
            self._cal_target = max(counts, key=lambda s: (counts[s], s))
        return self._cal_target

    def _make_round(self, ep):
        target = self._seed_target()
        best_types, best_gap = None, None
        for attempt in range(self.CALIB_MAX_TRIES):
            key = f"{self.seed}-round-{ep}" if attempt == 0 else f"{self.seed}-round-{ep}-try{attempt}"
            types = self._draw_types(random.Random(key))
            gap = abs(self.best_total(types) - target)
            if gap == 0:
                self._type = types
                return types
            if best_gap is None or gap < best_gap:
                best_types, best_gap = types, gap
        self._type = best_types
        return best_types

    def reset(self):
        self._make_round(self._episode)
        self._episode += 1
        self.turn_count = 0
        self.done = False
        self._score = 0
        self.room_of = {}          # tenant id -> room (0..2)
        return self._obs(), {}

    @property
    def score(self):
        return self._score

    # ── 行动 ──
    def _rooms(self):
        r = {0: [], 1: [], 2: []}
        for tid, rm in self.room_of.items():
            r[rm].append(tid)
        return r

    def get_valid_actions(self):
        if self.done:
            return ["status"]
        acts = []
        rooms = self._rooms()
        for i in range(N_TENANTS):
            for rm in range(N_ROOMS):
                if self.room_of.get(i) != rm and len(rooms[rm]) < ROOM_CAP:
                    acts.append(f"assign_{i}_{rm + 1}")
        acts.append("move_in")
        acts.append("status")
        return acts

    def get_all_actions(self):
        return self.get_valid_actions()

    def step(self, action):
        if self.done:
            return self._obs(), 0, True, {}
        a = action.strip()

        if a == "status":
            return self._obs(), 0, self.done, {"valid": self.get_valid_actions()}

        if a.startswith("assign_"):
            parts = a.split("_")
            if len(parts) != 3:
                return self._fb(self._t("格式：assign_<房客0-8>_<屋1-3>。",
                                        "Format: assign_<guest 0-8>_<room 1-3>.")), 0, self.done, {}
            try:
                tid = int(parts[1]); rm = int(parts[2]) - 1
            except ValueError:
                return self._fb(self._t("看不懂的分配指令。", "Unrecognized assign command.")), 0, self.done, {}
            if not (0 <= tid < N_TENANTS) or not (0 <= rm < N_ROOMS):
                return self._fb(self._t("房客 0–8、屋 1–3。", "Guest 0–8, room 1–3.")), 0, self.done, {}
            rooms = self._rooms()
            if self.room_of.get(tid) == rm:
                return self._fb(self._t(f"房客{tid} 已在 屋{rm + 1}。",
                                        f"Guest{tid} is already in Room{rm + 1}.")), 0, self.done, {}
            if len(rooms[rm]) >= ROOM_CAP:
                return self._fb(self._t(f"屋{rm + 1} 已住满 3 人，先把人挪走。",
                                        f"Room{rm + 1} is full (3). Move someone out first.")), 0, self.done, {}
            self.room_of[tid] = rm
            self.turn_count += 1
            return self._fb(self._t(f"已把 房客{tid}({self._type[tid]}) 安排进 屋{rm + 1}。",
                                    f"Assigned Guest{tid} ({self._tp(self._type[tid])}) to Room{rm + 1}.")), 0, self.done, {"valid": self.get_valid_actions()}

        if a == "move_in":
            rooms = self._rooms()
            if len(self.room_of) < N_TENANTS or any(len(rooms[r]) != ROOM_CAP for r in range(N_ROOMS)):
                return self._fb(self._t("还没排满——9 人须正好每屋 3 位，才能入住。",
                                        "Not full yet — all 9 must be exactly 3 per room to move in.")), 0, self.done, {}
            return self._resolve()

        return self._fb(self._t("没有这个行动。", "No such action.")), 0, self.done, {}

    def _resolve(self):
        self.done = True
        rooms = self._rooms()
        total = 0
        L = [self._t("入住一阵后，各屋住得如何——",
                     "After a while, here is how each room is getting along —")]
        sep = ", " if self._lang == "en" else "、"
        for r in range(N_ROOMS):
            ids = rooms[r]
            tps = [self._type[i] for i in ids]
            h = self._room_harmony(tps)
            total += h
            who = sep.join(f"{self._g(i)}({self._tp(self._type[i])})" for i in ids)
            L.append(self._t(
                f"  屋{r + 1}：{who} → {self._lvl(self._room_tier(h))}（和睦 {h:+d}）",
                f"  Room{r + 1}: {who} → {self._lvl(self._room_tier(h))} (harmony {h:+d})"))
        self._score = total
        L.append(self._t(f"=== 本轮总和睦：{total} ===",
                         f"=== Round total harmony: {total} ==="))
        return "\n".join(L), 0, True, {}

    # ── 观察（黑盒：不透露相处法则）──
    def _fb(self, prepend):
        return self._obs(prepend)

    def _obs(self, prepend=""):
        L = []
        if prepend:
            L.append(prepend)
        L.append(self._t("【租房中介】今轮 9 位房客，排进 3 间三人间：",
                         "[Rental agent] This round: 9 guests into 3 triple rooms:"))
        sep = ", " if self._lang == "en" else "、"
        L.append(self._t("  房客：", "  Guests: ")
                 + "  ".join(f"{self._g(i)}={self._tp(self._type[i])}" for i in range(N_TENANTS)))
        rooms = self._rooms()
        empty = "(empty)" if self._lang == "en" else "（空）"
        for r in range(N_ROOMS):
            occ = rooms[r]
            shown = sep.join(f"{self._g(i)}({self._tp(self._type[i])})" for i in occ) if occ else empty
            L.append(self._t(f"  屋{r + 1}（{len(occ)}/3）：{shown}",
                             f"  Room{r + 1} ({len(occ)}/3): {shown}"))
        unplaced = [i for i in range(N_TENANTS) if i not in self.room_of]
        if unplaced:
            L.append(self._t("  待安排：", "  Unplaced: ") + sep.join(self._g(i) for i in unplaced))
        L.append(self._t("用 assign_<房客0-8>_<屋1-3> 排房；排满每屋 3 人后 move_in 入住结算。",
                         "Use assign_<guest 0-8>_<room 1-3> to place; once every room has 3, move_in to settle."))
        return "\n".join(L)
