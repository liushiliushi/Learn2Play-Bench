"""
Grapevine（风声）— hidden influence-network inference + synergistic influence maximization.

一座城里有 N 个市民（A..T）。谁影响谁（有向加权关系网）、谁耳根多硬（阈值）全部隐藏，
且 seed 固定、跨回合不变。你每一局只能买通 K 个源头放风（直接「已信」），然后看风声按
确定性线性阈值模型逐轮传播，得分 = 最终被说服人数。**一局只能放一次风、看一次结果**
——逼你跨局累积观察、反推整张网，学会挑出能引爆全城的协同 K 人组。

唯一隐藏物 = 关系网（边/权/阈值）。从级联结果反推（边是潜变量、不能直接观测，也无法
暴力搜索绕过）。生成期拒绝采样保证：协同必需（最优组远超最佳单点）、地板低、天花板高。

接口与其它游戏一致。网络在 __init__ 生成（跨回合固定）；reset() 只重置本局选源头状态。
"""

import random
from itertools import combinations

LETTERS = "ABCDEFGHIJKLMNOPQRST"   # 20 个


class GrapevineGame:
    MAX_TURNS = 12
    N = 20
    K = 3                 # 每局放风源头名额

    def __init__(self, seed=None, lang="zh"):
        self._lang = lang if lang in ("zh", "en") else "zh"
        self._seed = seed
        self._generate_network(seed)
        self.reset()

    # ── 隐藏网络（跨回合固定，拒绝采样）──────────────────────────────────
    def _generate_network(self, seed):
        rng = random.Random(seed)
        N = self.N
        best = None
        for _ in range(2000):
            inc = self._roll(rng)
            thr = self._roll_thr(rng)
            singles = [len(self._spread([v], inc, thr)) for v in range(N)]
            max_single = max(singles)
            # 预筛：单点别太强（逼协同），且整体能传开
            if max_single > 7 or max_single < 3:
                continue
            # 贪心组（个体最强 K 个）——它必须明显劣于最优，否则贪心就解了
            greedy = sorted(range(N), key=lambda v: -singles[v])[:self.K]
            greedy_reach = len(self._spread(greedy, inc, thr))
            opt3, optset = self._best_set(inc, thr)
            trap = opt3 - greedy_reach          # 协同陷阱：最优 − 贪心
            # 综合评分：先满足硬条件，再最大化陷阱与天花板
            meets = (opt3 >= 16 and trap >= 6 and max_single <= 7)
            score = (1 if meets else 0, trap, opt3)
            if best is None or score > best[0]:
                best = (score, inc, thr, opt3, greedy_reach, optset)
            if meets and trap >= 8:
                break
        _, inc, thr, self._opt3, self._greedy_reach, self._opt_set = best
        self.inc = inc          # inc[v] = [(src, weight), ...] 入边
        self.thr = thr          # thr[v] = 阈值

    def _roll(self, rng):
        """掷一组有向加权边，返回入边邻接表 inc[v]=[(src,w),...]。"""
        N = self.N
        inc = [[] for _ in range(N)]
        for u in range(N):
            outdeg = rng.choice([2, 2, 3])
            targets = rng.sample([x for x in range(N) if x != u], outdeg)
            for t in targets:
                w = rng.choice([1, 1, 2])
                inc[t].append((u, w))
        return inc

    def _roll_thr(self, rng):
        return [rng.choice([1, 1, 2, 2, 3, 4]) for _ in range(self.N)]

    def _spread(self, seeds, inc, thr):
        """确定性线性阈值传播，返回最终已信集合。"""
        active = set(seeds)
        while True:
            newly = []
            for v in range(self.N):
                if v in active:
                    continue
                s = sum(w for (src, w) in inc[v] if src in active)
                if s >= thr[v]:
                    newly.append(v)
            if not newly:
                break
            active.update(newly)
        return active

    def _spread_waves(self, seeds):
        """同上，但返回逐轮名单（用于反馈展示）。"""
        active = set(seeds)
        waves = [sorted(seeds)]
        while True:
            newly = []
            for v in range(self.N):
                if v in active:
                    continue
                s = sum(w for (src, w) in self.inc[v] if src in active)
                if s >= self.thr[v]:
                    newly.append(v)
            if not newly:
                break
            active.update(newly)
            waves.append(sorted(newly))
        return active, waves

    def _best_set(self, inc, thr):
        """暴力求最优 K 源头组（仅生成期/开发者用）。"""
        best_n, best_set = -1, None
        for combo in combinations(range(self.N), self.K):
            n = len(self._spread(combo, inc, thr))
            if n > best_n:
                best_n, best_set = n, combo
        return best_n, best_set

    # ── 本局状态 ───────────────────────────────────────────────────────────
    def reset(self):
        self.seeds = []          # 已选源头（节点下标）
        self._turn = 0
        self._score = 0
        self._done = False
        self._released = False
        self._last_waves = None
        self._last_msg = None
        return self._render(opening=True), {}

    # ── 属性 ───────────────────────────────────────────────────────────────
    @property
    def score(self):
        return self._score

    @property
    def turn_count(self):
        return self._turn

    @property
    def done(self):
        return self._done

    # ── 行动接口 ───────────────────────────────────────────────────────────
    def get_all_actions(self):
        return [f"seed_{L}" for L in LETTERS] + ["release", "status"]

    def get_valid_actions(self):
        if self._done:
            return ["status"]
        acts = []
        if len(self.seeds) < self.K:
            acts += [f"seed_{LETTERS[v]}" for v in range(self.N) if v not in self.seeds]
        acts += [f"unseed_{LETTERS[v]}" for v in self.seeds]
        acts += ["release", "status"]
        return acts

    def step(self, action):
        action = (action or "").strip()
        L = self._lang

        if action == "status":
            return self._render(), 0, self._done, self._info()
        if self._done:
            return self._render(), 0, True, self._info()

        if action == "release":
            self._do_release()
            return self._render(), self._score, True, self._info()

        if action.startswith("seed_"):
            v = self._node(action[5:])
            self._turn += 1
            if v is None:
                self._last_msg = ("没有这个市民。" if L == "zh" else "No such citizen.")
            elif v in self.seeds:
                self._last_msg = (f"{LETTERS[v]} 已经是源头了。" if L == "zh" else f"{LETTERS[v]} already a seed.")
            elif len(self.seeds) >= self.K:
                self._last_msg = (f"名额已满（{self.K} 个）。先 unseed 再换。"
                                  if L == "zh" else f"Seed budget full ({self.K}).")
            else:
                self.seeds.append(v)
                self._last_msg = (f"买通 {LETTERS[v]} 放风。" if L == "zh" else f"Recruited {LETTERS[v]}.")

        elif action.startswith("unseed_"):
            v = self._node(action[7:])
            self._turn += 1
            if v in self.seeds:
                self.seeds.remove(v)
                self._last_msg = (f"放弃 {LETTERS[v]}。" if L == "zh" else f"Dropped {LETTERS[v]}.")
            else:
                self._last_msg = (f"{LETTERS[v] if v is not None else action} 不是源头。"
                                  if L == "zh" else "Not a seed.")
        else:
            self._last_msg = (f"看不懂的指令：{action}" if L == "zh" else f"Unknown command: {action}")
            return self._render(), 0, self._done, self._info()

        # 回合上限：自动放风结算
        if self._turn >= self.MAX_TURNS and not self._released:
            self._do_release()
            return self._render(), self._score, True, self._info()

        return self._render(), 0, self._done, self._info()

    def _do_release(self):
        active, waves = self._spread_waves(self.seeds)
        self._score = len(active)
        self._last_waves = waves
        self._released = True
        self._done = True

    def _node(self, s):
        s = s.strip().upper()
        return LETTERS.index(s) if (len(s) == 1 and s in LETTERS) else None

    def _info(self):
        return {"valid": self.get_valid_actions()}

    # ── 渲染 ───────────────────────────────────────────────────────────────
    def _render(self, opening=False):
        L = self._lang
        lines = []
        if opening:
            if L == "zh":
                lines.append(f"【风声】城里有 {self.N} 个市民（A–T）。谁影响谁、谁耳根多硬全看不见。"
                             f"你最多买通 {self.K} 个源头放风（seed_X），release 后风声按隐藏关系网逐轮传开，"
                             f"得分=最终被说服人数。**一局只放一次风**，靠多局摸清这张网、挑出能引爆全城的 {self.K} 人组。")
            else:
                lines.append(f"[Grapevine] {self.N} citizens (A–T). Who sways whom and how stubborn each is "
                             f"is hidden. Recruit up to {self.K} seeds (seed_X), then release: the rumor spreads "
                             f"wave by wave through the hidden network. Score = #persuaded. One release per game; "
                             f"learn the network across games to find the {self.K} who ignite the whole town.")

        if self._last_msg and not self._released:
            lines.append(self._last_msg)

        if self._released:
            persuaded = set()
            for w in self._last_waves:
                persuaded.update(w)
            if L == "zh":
                lines.append("风声传开：")
                for i, w in enumerate(self._last_waves):
                    names = " ".join(LETTERS[v] for v in w)
                    tag = "你放风" if i == 0 else f"第{i}轮"
                    lines.append(f"  {tag}：{names}")
                missed = [LETTERS[v] for v in range(self.N) if v not in persuaded]
                lines.append(f"止息，共说服 {len(persuaded)} 人。未被说服：{' '.join(missed) if missed else '（无）'}")
            else:
                lines.append("The rumor spreads:")
                for i, w in enumerate(self._last_waves):
                    names = " ".join(LETTERS[v] for v in w)
                    tag = "your seeds" if i == 0 else f"wave {i}"
                    lines.append(f"  {tag}: {names}")
                missed = [LETTERS[v] for v in range(self.N) if v not in persuaded]
                lines.append(f"Settled. Persuaded {len(persuaded)}. Unmoved: {' '.join(missed) if missed else '(none)'}")
        else:
            # 市民一览 + 已选源头
            row = " ".join((f"[{LETTERS[v]}]" if v in self.seeds else LETTERS[v]) for v in range(self.N))
            lines.append((f"市民：{row}" if L == "zh" else f"Citizens: {row}"))
            chosen = " ".join(LETTERS[v] for v in self.seeds) or ("（无）" if L == "zh" else "(none)")
            if L == "zh":
                lines.append(f"已选源头：{chosen}　|　名额 {len(self.seeds)}/{self.K}　|　[X]=已选")
            else:
                lines.append(f"Seeds: {chosen}  |  budget {len(self.seeds)}/{self.K}  |  [X]=chosen")
        return "\n".join(lines)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))
