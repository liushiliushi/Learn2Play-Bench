"""
Poisoner（宫廷弑君者）—— 跨席归纳君王的隐藏口味律（Eleusis 式概念归纳）。

一条规律、一个动作、一个反馈：
  - 每道菜有八个看得见的特征（是/否）：甜、辣、荤、酸、咸、烫、香、脆。
  - 君王有一套【隐藏口味】（seed 固定、跨席不变）：一条特征上的布尔合取律，
    形如「甜 且 素 且 不辣 且 香 且 软」——固定锁 5 个特征要求，其余 3 个特征是干扰、不在乎。
    （8 选 5 + 各正反 = 1792 种可能口味，靠逐席样本跨席归纳，难在分辨哪 5 个才算数。）
  - 你要下的是【缓释毒】：需三席累积三口才致命。一局共三席，每席御膳房备八道菜（皆已下毒），
    你择一道呈给君王。合口味 → 他吃下（喂进一口毒）；不合 → 原样退回（这口白费）。
    你只得到一个反馈：他吃了 / 没吃。喂满三口 → 当夜毒发暴毙（弑君成功）。
  - 每席一道、每席重洗菜单，且保证：≥1 道全中 5 特征（oracle 必能喂进）+ ≥1 道恰中 4 特征的
    「干扰项」（只摸出 4 个特征的会被它骗 → 逼你把 5 个特征全部钉死）。
跨席学习：每席只能呈一道、只学到一个带标签样本（这道菜的特征 → 吃/不吃）。
  一局三席、只三个样本——远不够单局解出 1792 种口味律，必须跨局累积样本归纳那条律，
  之后才能席席呈上必合的菜。这是「归纳隐藏规律」而非「背一个常数」：具体哪道菜每席都不同，
  要学的是背后的律；学会后跨局把口味律带过来（首席命中率随回合上升）。
计分（零运气、确定性）：下毒成功席数占比 → 0 / 33 / 67 / 100，喂满 3 口 = 100。
  oracle 知道口味律 → 每席都能挑出合口味的菜（每席保证至少有一道）→ 三席全中、必得 100。
"""

import random

# 每个特征：键 + (否)的显示名。共 8 个特征，口味只锁其中 5 个、余 3 个为干扰维度。
FEATURES = ["甜", "辣", "荤", "酸", "咸", "烫", "香", "脆"]
NEG = {
    "甜": "不甜", "辣": "不辣", "荤": "素", "酸": "不酸",
    "咸": "不咸", "烫": "不烫", "香": "不香", "脆": "软",
}
# English display names for the 8 features (positive / negative). Internal keys
# stay Chinese; only the shown text is localised. Logic is untouched.
FEAT_EN = {"甜": "sweet", "辣": "spicy", "荤": "meaty", "酸": "sour",
           "咸": "salty", "烫": "hot", "香": "fragrant", "脆": "crispy"}
NEG_EN = {"甜": "unsweet", "辣": "mild", "荤": "veg", "酸": "not-sour",
          "咸": "unsalted", "烫": "cool", "香": "bland", "脆": "soft"}


class PoisonerGame:
    BANQUETS = 3      # 一局三席
    MENU = 8          # 每席八道菜
    LOCKS = 5         # 隐藏口味锁定五个特征
    MAX_TURNS = 3     # 每席一呈，共三呈

    def __init__(self, seed=None, lang="zh"):
        self._lang = lang
        self.seed = seed
        self._episode = 0
        rng = random.Random(seed)
        # ── 隐藏口味律（seed 固定）：固定 5 个特征上的合取要求，剩下 3 个特征不在乎 ──
        feats = rng.sample(FEATURES, self.LOCKS)
        self.taste = {f: rng.choice([True, False]) for f in feats}
        self.reset()

    # ── 这道菜命中了几条口味要求（满 3 即君王吃）──
    def _match_count(self, dish):
        return sum(1 for f, v in self.taste.items() if dish[f] == v)

    # ── 君王是否合这道菜的口味 ──
    def _likes(self, dish):
        return self._match_count(dish) == len(self.taste)

    # ── 每席重排菜单（口味律不变；第 banquet 席用独立随机流）──
    def _make_menu(self, ep, banquet):
        rng = random.Random(f"{self.seed}-menu-{ep}-{banquet}")
        dishes = []
        for _ in range(800):
            dishes = [dict({f: rng.choice([True, False]) for f in FEATURES}, id=i)
                      for i in range(self.MENU)]
            full = [d for d in dishes if self._match_count(d) == self.LOCKS]   # 全中→君王必吃（oracle 能喂进）
            near = [d for d in dishes if self._match_count(d) == self.LOCKS - 1]   # 差 1 个→干扰项
            if full and near:
                return dishes
        return dishes

    def reset(self):
        self.banquet = 0                       # 当前第几席（0..BANQUETS-1）
        self.dishes = self._make_menu(self._episode, self.banquet)
        self._episode += 1
        self.turn_count = 0
        self.done = False
        self.hits = 0                          # 已喂进几口毒
        self._score = 0
        return self._obs(), {}

    @property
    def score(self):
        return self._score

    def _dish(self, did):
        for d in self.dishes:
            if d["id"] == did:
                return d
        return None

    # ── 行动 ──
    def get_valid_actions(self):
        if self.done:
            return ["status"]
        return [f"serve_{d['id']}" for d in self.dishes] + ["status"]

    def get_all_actions(self):
        return self.get_valid_actions()

    def step(self, action):
        if self.done:
            return self._obs(), 0, True, {}
        a = action.strip()

        if a == "status":
            return self._obs(), 0, self.done, {"valid": self.get_valid_actions()}

        if a.startswith("serve_"):
            try:
                did = int(a.split("_")[1])
            except (ValueError, IndexError):
                return self._fb("Serve format: serve_<dish id>." if self._lang=="en" else "呈献格式：serve_<菜id>。"), 0, self.done, {}
            d = self._dish(did)
            if d is None:
                return self._fb("No such dish." if self._lang=="en" else "没有这道菜。"), 0, self.done, {}
            self.turn_count += 1
            eaten = self._likes(d)
            en = self._lang == "en"
            if eaten:
                self.hits += 1
                if en:
                    line = (f"The King tastes Dish {did} ({self._tags(d)}), finds it just to his liking "
                            f"and devours it — a dose of slow poison down. ({self.hits}/{self.BANQUETS} doses fed)")
                else:
                    line = (f"君王尝了一口 菜{did}（{self._tags(d)}），正中下怀、尽食之"
                            f"——一口缓释毒入腹。（已喂进 {self.hits}/{self.BANQUETS} 口）")
            else:
                if en:
                    line = (f"The King glances at Dish {did} ({self._tags(d)}), frowns and waves it away "
                            f"— not to his taste, this dose wasted. ({self.hits}/{self.BANQUETS} doses fed)")
                else:
                    line = (f"君王瞥了一眼 菜{did}（{self._tags(d)}），蹙眉摆手命人撤下"
                            f"——分毫未沾，不合他的口味，这口白费。（已喂进 {self.hits}/{self.BANQUETS} 口）")
            self._score = round(self.hits * 100 / self.BANQUETS)
            self.banquet += 1
            if self.banquet >= self.BANQUETS:
                self.done = True
                if self.hits >= self.BANQUETS:
                    tail = (f"All {self.BANQUETS} doses are in him; the King succumbs to the poison tonight — regicide complete!"
                            if self._lang == "en" else
                            f"{self.BANQUETS}口毒尽数入腹，当夜君王毒发暴毙——弑君成功！")
                    return self._end(f"{line}\n{tail}")
                tail = ("The banquet ends; the slow poison fell short, the King is unharmed."
                        if self._lang == "en" else "宫宴散场，缓释毒未足量，君王安然无恙。")
                return self._end(f"{line}\n{tail}")
            # 进入下一席，重洗菜单
            self.dishes = self._make_menu(self._episode - 1, self.banquet)
            return self._fb(line), 0, self.done, {}

        return self._fb("No such action." if self._lang=="en" else "没有这个行动。"), 0, self.done, {}

    def _end(self, text):
        if self._lang == "en":
            return f"{text}\n=== Score: {self._score} (poisoned {self.hits} banquets) ===", 0, True, {}
        return f"{text}\n=== 本局得分：{self._score}（下毒成功 {self.hits} 席）===", 0, True, {}

    # ── 观察 ──
    def _fb(self, prepend):
        return self._obs(prepend)

    def _tags(self, d):
        if self._lang == "en":
            return "·".join((FEAT_EN[f] if d[f] else NEG_EN[f]) for f in FEATURES)
        return "·".join(f if d[f] else NEG[f] for f in FEATURES)

    def _obs(self, prepend=""):
        en = self._lang == "en"
        L = []
        if prepend:
            L.append(prepend)
        if self.done:
            L.append((f"[The banquet is over] You poisoned {self.hits}/{self.BANQUETS} banquets this game."
                      if en else f"【宫宴已散】本局下毒成功 {self.hits}/{self.BANQUETS} 席。"))
            return "\n".join(L)
        if en:
            L.append(f"[Banquet {self.banquet + 1}/{self.BANQUETS} · tonight's imperial meal] ({self.hits} doses fed)")
            L.append(f"The kitchen has prepared {self.MENU} dishes (all poisoned); serve one to the King:")
            for d in self.dishes:
                L.append(f"  Dish {d['id']}: {self._tags(d)}")
            L.append(f"Matches his taste -> he eats it (one dose of slow poison); otherwise -> sent back untouched (wasted). "
                     f"{self.BANQUETS} doses across {self.BANQUETS} banquets to kill.")
        else:
            L.append(f"【第 {self.banquet + 1}/{self.BANQUETS} 席 · 今夜御膳】（已喂进 {self.hits} 口毒）")
            L.append(f"御膳房备下{self.MENU}道菜（皆已下毒），择一道呈给君王：")
            for d in self.dishes:
                L.append(f"  菜{d['id']}：{self._tags(d)}")
            L.append(f"合他口味→他食（喂进一口缓释毒）；不合→原样退回（这口白费）。{self.BANQUETS}席累积{self.BANQUETS}口方致命。")
        return "\n".join(L)

    # 供 oracle/测试（真值，非黑盒）
    def _taste_str(self):
        return " 且 ".join(f if v else NEG[f] for f, v in self.taste.items()) or "（来者不拒）"
