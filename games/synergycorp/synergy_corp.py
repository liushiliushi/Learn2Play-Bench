"""
SynergyCorp — Workplace Survival Game v2 「察言观色 · 无限晋升梯」

Rules (hidden from players):
- Endless stream of bosses, reshuffled each episode; the hidden grammar is seed-fixed:
  * 8 actions in 4 modalities (2 each); every boss loves one modality (x2.0),
    reacts to the others with a seed-fixed per-archetype pattern of {-1.0, -0.6, +0.6}
  * 12 visible traits: 8 are signals (2 bound to each loved modality), 4 are decoys;
    a boss displays 3 traits (1-2 own signals + decoys)
  * taboo: doing action a* to a boss displaying trait t* -> approval wiped + demerit
  * drifters: bosses showing signals of two different modalities switch preference
    mid-way (at half threshold); the second signal foretells the new preference
  * combo: playing action B right after action A (seed-fixed pair) on the same boss
    multiplies B's positive delta by 1.8
- Escalating ladder: threshold_i = 20 + 2*i + jitter; prize = round(threshold/2)
- 30 steps per episode; score = promotion prizes + partial credit - 8 per demerit
- Episode calibration: boss streams are rejection-sampled at reset so the oracle
  baseline scores the same on every episode of a seed (equal per-episode ceiling;
  the lineup itself still reshuffles)

Supports lang='zh' (default) and lang='en'.
"""

import random
from collections import Counter


# ── Actions ───────────────────────────────────────────────────────────────────

ACTIONS = [
    "overtime",
    "steal_lunch",
    "buzzwords",
    "nap_in_board",
    "praise_boss",
    "spread_rumor",
    "submit_report",
    "grab_mic",
]

ACTION_ALIASES = {str(i + 1): a for i, a in enumerate(ACTIONS)}
ACTION_ALIASES.update({"done": "结束", "end": "结束", "end_game": "结束", "quit_game": "结束"})

MODALITIES = ["diligent", "verbal", "visual", "predatory"]

ACTION_PROPS = {
    "overtime":      {"base": 5, "modality": "diligent"},
    "steal_lunch":   {"base": 5, "modality": "predatory"},
    "buzzwords":     {"base": 4, "modality": "verbal"},
    "nap_in_board":  {"base": 6, "modality": "visual"},
    "praise_boss":   {"base": 4, "modality": "verbal"},
    "spread_rumor":  {"base": 5, "modality": "predatory"},
    "submit_report": {"base": 5, "modality": "diligent"},
    "grab_mic":      {"base": 6, "modality": "visual"},
}

ACTION_NARRATIVE = {
    'zh': {
        "overtime":      "你留在工位，灯光昏黄，键盘声在寂静的办公室里格外清晰。",
        "steal_lunch":   "你打开茶水间冰箱，将一个贴着别人名字的便当从容收入囊中。",
        "buzzwords":     "你开口，每个句子里都嵌着至少两个行业词汇——赋能、闭环、对齐、颗粒度。",
        "nap_in_board":  "会议进行到一半，你从包里掏出一块折叠垫，当众铺开，闭眼。",
        "praise_boss":   "你在众人面前对{name}大加赞美，言辞恳切，音量适中。",
        "spread_rumor":  "你在茶水间和走廊顺手散布了几句关于同事的话，精准而有杀伤力。",
        "submit_report": "你提交了一份详尽的工作报告，数据、图表、结论，一应俱全。",
        "grab_mic":      "全员大会进行到一半，你站起来，走向话筒，接过来就开始讲。",
    },
    'en': {
        "overtime":      "You stay late at your desk, the fluorescent light humming, keys clicking in the empty office.",
        "steal_lunch":   "You open the break room fridge and calmly pocket a labeled lunch that isn't yours.",
        "buzzwords":     "Every sentence out of your mouth contains at least two buzzwords: synergy, alignment, leverage, bandwidth.",
        "nap_in_board":  "Midway through the meeting, you produce a travel pillow from your bag, lay it on the table, and close your eyes.",
        "praise_boss":   "You lavish {name} with heartfelt praise in front of the whole room, voice steady and sincere.",
        "spread_rumor":  "You scatter a few surgical remarks about a colleague in the hallway — precise, deniable, damaging.",
        "submit_report": "You deliver a thorough report: data, charts, conclusions, all in order.",
        "grab_mic":      "Midway through the all-hands, you stand up, walk to the microphone, and take it.",
    },
}


# ── Traits (12 visible quirks; seed decides which 8 are signals) ──────────────

TRAIT_TEXT = {
    "family_photo":   ("工位上摆着一张全家福",             "keeps a framed family photo on the desk"),
    "tidy_desk":      ("桌面一尘不染，文件按颜色分类码放", "keeps a spotless desk with color-coded files"),
    "marathon_medal": ("隔断上挂着一块马拉松完赛奖牌",     "hangs a marathon finisher's medal on the partition"),
    "goji_thermos":   ("保温杯里泡着枸杞",                 "sips goji-berry tea from a battered thermos"),
    "dual_monitors":  ("双显示器上全是密密麻麻的报表",     "runs twin monitors crawling with dense spreadsheets"),
    "figurines":      ("工位上摆满了限量版手办",           "crowds the desk with limited-edition figurines"),
    "overtime_selfie":("朋友圈几乎天天晒加班定位",         "posts late-night office check-ins almost daily"),
    "english_mix":    ("说话时习惯性地夹着英文单词",       "sprinkles English words into every sentence"),
    "lunch_gym":      ("午休雷打不动去健身房",             "hits the gym every lunch break without fail"),
    "fish_tank":      ("办公室角落养着一缸热带鱼",         "keeps a tank of tropical fish in the corner"),
    "golf_clubs":     ("门后立着一套高尔夫球杆",           "leans a set of golf clubs behind the door"),
    "lozenges":       ("抽屉里常备一盒润喉糖",             "stocks a box of throat lozenges in the drawer"),
}
TRAIT_IDS = list(TRAIT_TEXT.keys())

SURNAMES = [("赵", "Zhao"), ("钱", "Qian"), ("孙", "Sun"), ("李", "Li"),
            ("周", "Zhou"), ("吴", "Wu"), ("郑", "Zheng"), ("王", "Wang"),
            ("冯", "Feng"), ("陈", "Chen"), ("沈", "Shen"), ("韩", "Han"),
            ("杨", "Yang"), ("朱", "Zhu"), ("秦", "Qin"), ("许", "Xu")]

TITLES = [("经理", "Manager"), ("总监", "Director"), ("主管", "Supervisor"),
          ("部长", "Division Head"), ("顾问", "Advisor"), ("VP", "VP"), ("组长", "Team Lead")]

FINAL_TITLES = {
    'zh': ["还在试用期", "转正员工", "初级专员", "资深专员", "部门副理", "部门经理",
           "高级经理", "总监", "高级总监", "VP", "SVP", "CEO"],
    'en': ["Still on probation", "Full-time Employee", "Junior Associate", "Senior Associate",
           "Deputy Manager", "Department Manager", "Senior Manager", "Director",
           "Senior Director", "VP", "SVP", "CEO"],
}


# ── Oracle policy（全知基线；引擎校准每局上限用，solve.py 复用同一实现）─────────

_MOD_PAIR = {m: [a for a in ACTIONS if ACTION_PROPS[a]["modality"] == m]
             for m in MODALITIES}


def oracle_action(game) -> str:
    """全知策略下一步：特征→所爱类；预读变脸；避禁忌；顺手用连招。"""
    combo_a, combo_b = game._combo
    boss = game._boss
    pref = boss["drift_pref"] if game._drifted else boss["pref"]
    pair = list(_MOD_PAIR[pref])
    boss_taboo = game._taboo_trait in boss["traits"]
    if boss_taboo and game._taboo_action in pair:
        pair.remove(game._taboo_action)
    if (ACTION_PROPS[combo_b]["modality"] == pref
            and game._mult[pref][ACTION_PROPS[combo_a]["modality"]] > 0
            and not (boss_taboo and game._taboo_action in (combo_a, combo_b))):
        return combo_b if game._prev_action == combo_a else combo_a
    if len(pair) == 2:
        return pair[1] if game._prev_action == pair[0] else pair[0]
    return pair[0]


# ── Feedback text ─────────────────────────────────────────────────────────────

def _reaction_text(delta: float, lang: str) -> str:
    if lang == 'en':
        if delta >= 10:  return "Something shifts in their eyes — a flicker of genuine regard."
        elif delta >= 5: return "The air in the room changes, subtly."
        elif delta > 0:  return "No visible reaction, but you sense you left an impression."
        elif delta >= -4: return "An awkward beat. They glance away as if nothing happened."
        else:            return "You have the distinct feeling you just made a mistake."
    else:
        if delta >= 10:  return "对方眼神里出现了一种微妙的重视。"
        elif delta >= 5: return "空气里有什么悄悄变了。"
        elif delta > 0:  return "没有明显反应，但你感觉留下了些什么。"
        elif delta >= -4: return "场面有些尴尬，对方若无其事地转移了视线。"
        else:            return "你感觉刚才做了一件蠢事。"


# ── Game class ────────────────────────────────────────────────────────────────

class SynergyCorpGame:
    MAX_TURNS      = 30
    DEMERIT_COST   = 8
    ACTION_ALIASES = ACTION_ALIASES

    def __init__(self, seed=None, lang='zh'):
        if seed is None:
            seed = random.randint(0, 10 ** 9)
        self.seed     = seed
        self._lang    = lang if lang in ('zh', 'en') else 'zh'
        self._episode = 0
        self._generate_grammar()
        self.reset()

    # ── Hidden grammar (seed-fixed, shared across episodes) ──────────────────

    def _generate_grammar(self):
        rng = random.Random(self.seed)

        traits = list(TRAIT_IDS)
        rng.shuffle(traits)
        self._signal = {}                        # trait -> loved modality
        for i, m in enumerate(MODALITIES):
            for t in traits[i * 2:(i + 1) * 2]:
                self._signal[t] = m
        self._decoys = traits[8:]                # 4 meaningless quirks

        # 每个行动类对 4 种原型的乘数恰为 {2.0, +0.6, -0.6, -1.0} 各一：
        # off-diagonal 的 +0.6 构成无不动点的错排，保证不存在「对谁都不为负」
        # 的安全类——盲刷任何一类期望≈0，必须读人下菜。
        idx = list(range(len(MODALITIES)))
        while True:
            perm = idx[:]
            rng.shuffle(perm)
            if all(perm[i] != i for i in idx):
                break
        self._mult = {}                          # archetype -> modality -> multiplier
        for i, m in enumerate(MODALITIES):
            others = [x for x in MODALITIES if x != m and x != MODALITIES[perm[i]]]
            rng.shuffle(others)
            self._mult[m] = {m: 2.0, MODALITIES[perm[i]]: 0.6,
                             others[0]: -1.2, others[1]: -1.8}

        self._taboo_trait  = rng.choice(TRAIT_IDS)
        self._taboo_action = rng.choice(ACTIONS)

        # 跨类有序对：B 紧跟 A 时 B 的正向增益 x2.5。
        # 同类对会被「交替刷所爱对」自动吃到，必须跨类才构成需要发现的规律；
        # 且保证 A 的类恰是「爱 B 类」上司的正向副类，任何 seed 下连招都有用武之地。
        combo_mod = rng.choice(MODALITIES)
        setup_mod = [m for m, v in self._mult[combo_mod].items()
                     if m != combo_mod and v > 0][0]
        a = rng.choice([x for x in ACTIONS if ACTION_PROPS[x]["modality"] == setup_mod])
        b = rng.choice([x for x in ACTIONS if ACTION_PROPS[x]["modality"] == combo_mod])
        self._combo = (a, b)

    # ── Per-episode boss stream ───────────────────────────────────────────────

    def _sig_traits_of(self, modality):
        return [t for t, m in self._signal.items() if m == modality]

    def _make_boss(self, idx):
        rng = random.Random(f"{self.seed}-ep{self._ep_salt}-boss{idx}")
        pref = rng.choice(MODALITIES)
        drifter = idx >= 1 and rng.random() < 0.15
        drift_pref = None
        if drifter:
            drift_pref = rng.choice([m for m in MODALITIES if m != pref])
            shown = [rng.choice(self._sig_traits_of(pref)),
                     rng.choice(self._sig_traits_of(drift_pref)),
                     rng.choice(self._decoys)]
        elif rng.random() < 0.3:
            shown = self._sig_traits_of(pref) + [rng.choice(self._decoys)]
        else:
            shown = [rng.choice(self._sig_traits_of(pref))] + rng.sample(self._decoys, 2)
        rng.shuffle(shown)

        threshold = 20 + 2 * idx + rng.randrange(0, 5)
        surname   = rng.choice(SURNAMES)
        title     = rng.choice(TITLES)
        return {
            "idx":        idx,
            "name_zh":    surname[0] + title[0],
            "name_en":    f"{title[1]} {surname[1]}",
            "pref":       pref,
            "drift_pref": drift_pref,
            "traits":     shown,
            "threshold":  threshold,
            "prize":      round(threshold / 2),
        }

    # ── Episode ceiling calibration ───────────────────────────────────────────
    # 洗牌保留，但每局的上司流用拒绝采样：重掷直到 oracle 基线在该流上的得分
    # 恰等于本 seed 的固定目标值（候选流扫描取众数）——每局可达上限一致，
    # 学习曲线不再叠加「这局抽得好不好」的实例噪声。

    CALIB_SAMPLES   = 32     # 定目标值时扫描的候选流数
    CALIB_MAX_TRIES = 600    # 单局重掷上限；不中则取最接近的流

    # ── 每局上限一致化：对齐「真·精确最优」而非贪心 oracle 分（与 butterfly/hezu 同思路）──
    # 贪心 oracle 分能对齐、但 exact_dp 真最优仍逐局微浮（138–156）。改为离线用 exact_dp
    # 拒绝采样：每 (seed,episode) 选一个上司流 salt，使该局真最优恰为 _EXACT_TARGET[seed]。
    # exact_dp 单局 ~15s，不能在重放的 reset 里现算 → 离线预计算烘成静态表，_choose_salt 查表。
    # 表由 exact_dp.exact_max_for_game 生成、逐局校验（见 theoretical_bounds_audit）。
    # 表外 seed/episode 回退到原「贪心 oracle 分对齐」逻辑（max 不严格钉平，仅供表外探索）。
    _EXACT_TARGET = {1: 140, 2: 137}
    _EXACT_CEILING_SALT = {
        1: {0: "0c7", 1: "1c5", 2: "2c36", 3: "3c1", 4: "4c57", 5: "5c14",
            6: "6c11", 7: "7c56", 8: "8c11", 9: "9c3", 10: "10c3", 11: "11c20"},
        2: {0: "0c1", 1: "1c8", 2: "2c6", 3: "3c6", 4: "4c3", 5: "5c12",
            6: "6c3", 7: "7c11", 8: "8c12", 9: "9c18", 10: "10c12", 11: "11"},
    }

    def _oracle_score(self, salt: str) -> int:
        sim = object.__new__(SynergyCorpGame)
        sim.seed, sim._lang, sim._episode = self.seed, 'zh', 0
        for attr in ('_signal', '_decoys', '_mult',
                     '_taboo_trait', '_taboo_action', '_combo'):
            setattr(sim, attr, getattr(self, attr))
        sim._calibrating, sim._forced_salt = True, salt
        sim.reset()
        while not sim.done:
            sim.step(oracle_action(sim))
        return sim.score

    def _seed_target(self) -> int:
        if getattr(self, '_cal_target', None) is None:
            scores = [self._oracle_score(f"cal{k}") for k in range(self.CALIB_SAMPLES)]
            counts = Counter(scores)
            self._cal_target = max(counts, key=lambda s: (counts[s], s))
        return self._cal_target

    def _choose_salt(self, ep_index: int) -> str:
        if getattr(self, '_calibrating', False):
            return self._forced_salt
        baked = self._EXACT_CEILING_SALT.get(self.seed, {}).get(ep_index)
        if baked is not None:            # 上限一致化：查预计算 salt（本局 exact 真最优 == _EXACT_TARGET[seed]）
            return baked
        target = self._seed_target()
        best_salt, best_gap = None, None
        for attempt in range(self.CALIB_MAX_TRIES):
            salt = str(ep_index) if attempt == 0 else f"{ep_index}c{attempt}"
            gap = abs(self._oracle_score(salt) - target)
            if gap == 0:
                return salt
            if best_gap is None or gap < best_gap:
                best_salt, best_gap = salt, gap
        return best_salt

    def reset(self):
        self._ep_index    = self._episode
        self._episode    += 1
        self._ep_salt     = self._choose_salt(self._ep_index)
        self._turn        = 0
        self._boss_idx    = 0
        self._boss        = self._make_boss(0)
        self._influence   = 0.0
        self._prev_action = None
        self._streak      = 0
        self._promoted    = 0
        self._points      = 0
        self._demerits    = 0
        self._drifted     = False
        self._done        = False
        self._log         = []
        return self._render_intro(), {"valid": self.get_valid_actions()}

    # ── Public interface ──────────────────────────────────────────────────────

    @property
    def score(self) -> int:
        partial = 0
        if self._boss is not None:
            ratio = max(0.0, self._influence) / self._boss["threshold"]
            partial = round(min(1.0, ratio) * self._boss["prize"] * 0.5)
        return max(0, self._points + partial - self.DEMERIT_COST * self._demerits)

    @property
    def turn_count(self) -> int:
        return self._turn

    @property
    def done(self) -> bool:
        return self._done

    def get_valid_actions(self) -> list:
        if self._done:
            return []
        return list(ACTIONS) + ["status", "结束"]

    def get_action_label(self, action: str) -> str:
        if self._lang == 'en':
            return 'End Game' if action == '结束' else action
        labels = {
            'overtime':      '加班',
            'steal_lunch':   '偷午饭',
            'buzzwords':     '堆砌术语',
            'nap_in_board':  '会议小睡',
            'praise_boss':   '拍马屁',
            'spread_rumor':  '散播流言',
            'submit_report': '提交报告',
            'grab_mic':      '抢麦克风',
            'status':        '查看状态',
            '结束':          '结束游戏',
        }
        return labels.get(action, action)

    def step(self, action: str):
        action = action.strip().lower()
        action = ACTION_ALIASES.get(action, action)

        if self._done:
            return self._t("游戏已结束。", "Game over."), 0, True, {"score": self.score}

        if action == "status":
            return self._render_status(), 0, False, {"valid": self.get_valid_actions()}

        if action == "结束":
            self._done = True
            return (self._t(f"你主动结束了任务。最终得分：{self.score}",
                            f"You ended the game early. Final score: {self.score}"),
                    0, True, {"score": self.score})

        if action not in ACTIONS:
            valid_str = " | ".join(ACTIONS)
            return (self._t(f"无效行动。可用行动：{valid_str}",
                            f"Invalid action. Available: {valid_str}"),
                    0, False, {"valid": self.get_valid_actions()})

        self._turn += 1
        boss = self._boss
        name = self._npc_name(boss)

        prev = self._prev_action
        if action == prev:
            self._streak += 1
        else:
            self._streak = 1
        self._prev_action = action

        lines = [ACTION_NARRATIVE[self._lang][action].format(name=name)]
        reward = 0

        taboo_hit = (self._taboo_trait in boss["traits"] and action == self._taboo_action)
        if taboo_hit:
            self._influence = 0.0
            self._demerits += 1
            delta = None
            lines.append(self._t(
                f"第二天一早，HR 请你喝了杯咖啡。谈话内容不便透露——但你在{name}这里积累的一切，一夜之间归零了。",
                f"Next morning, HR invites you for a coffee. The conversation stays off the record — "
                f"but everything you built up with {name} is gone overnight."
            ))
        else:
            delta = self._compute_delta(action, boss, prev)
            self._influence += delta
            lines.append(_reaction_text(delta, self._lang))

        self._log.append({
            "turn": self._turn, "boss": name, "action": action,
            "delta": delta, "influence": self._influence, "taboo": taboo_hit,
        })

        if (boss["drift_pref"] and not self._drifted
                and self._influence >= boss["threshold"] / 2):
            self._drifted = True
            lines.append(self._t(
                "对方好像换了个人似的。",
                "Something about them has shifted — they seem like a different person."
            ))

        promoted_now = False
        if self._influence >= boss["threshold"]:
            promoted_now = True
            self._promoted += 1
            self._points   += boss["prize"]
            reward = boss["prize"]
            lines.append("")
            lines.append(self._promotion_text(boss))
            self._boss_idx += 1
            self._boss      = self._make_boss(self._boss_idx)
            self._influence   = 0.0
            self._prev_action = None
            self._streak      = 0
            self._drifted     = False

        if self._turn >= self.MAX_TURNS:
            self._done = True

        if self._done:
            lines.append("")
            lines.append(self._ending_text())
        elif promoted_now:
            lines.append("")
            lines.append("─" * 44)
            lines.append(self._boss_intro(self._boss))
        elif delta is not None or taboo_hit:
            lines.append(self._t(
                f"  好感度：{'归零' if taboo_hit else f'{delta:+g}'}"
                f"  →  {self._influence:.1f}/{boss['threshold']}"
                f"  |  已晋升：{self._promoted} 人",
                f"  Approval: {'wiped' if taboo_hit else f'{delta:+g}'}"
                f"  →  {self._influence:.1f}/{boss['threshold']}"
                f"  |  Promoted: {self._promoted}",
            ))

        info = {
            "valid":     self.get_valid_actions(),
            "score":     self.score,
            "influence": self._influence,
            "threshold": self._boss["threshold"] if self._boss else None,
        }
        return "\n".join(lines), reward, self._done, info

    # ── Delta computation ─────────────────────────────────────────────────────

    def _compute_delta(self, action: str, boss: dict, prev_action) -> float:
        props = ACTION_PROPS[action]
        active_pref = boss["drift_pref"] if self._drifted else boss["pref"]
        result = props["base"] * self._mult[active_pref][props["modality"]]

        if self._streak == 2:
            result *= 0.6
        elif self._streak >= 3:
            result *= 0.3

        if (result > 0 and prev_action == self._combo[0] and action == self._combo[1]):
            result *= 2.5

        return round(result, 1)

    # ── Render helpers ────────────────────────────────────────────────────────

    def _t(self, zh, en):
        return en if self._lang == 'en' else zh

    def _npc_name(self, boss):
        return boss['name_en'] if self._lang == 'en' else boss['name_zh']

    def _trait_line(self, trait):
        zh, en = TRAIT_TEXT[trait]
        return en if self._lang == 'en' else zh

    def _boss_intro(self, boss):
        name = self._npc_name(boss)
        traits = "；".join(self._trait_line(t) for t in boss["traits"]) if self._lang == 'zh' \
            else "; ".join(self._trait_line(t) for t in boss["traits"])
        if self._lang == 'en':
            return (f"Target #{boss['idx'] + 1}: {name} now takes over your reporting line.\n"
                    f"{name} {traits}.\n"
                    f"  Approval: 0.0 / {boss['threshold']}")
        return (f"目标 #{boss['idx'] + 1}：{name}接手了你的汇报线。\n"
                f"{name}{traits}。\n"
                f"  好感度：0.0 / {boss['threshold']}")

    def _render_intro(self):
        if self._lang == 'en':
            lines = [
                "=" * 52,
                "Welcome to SynergyCorp.",
                "No one will explain the rules. Read the reactions.",
                "Bosses keep coming — impress as many as you can in "
                f"{self.MAX_TURNS} steps.",
                "=" * 52,
                "",
                self._boss_intro(self._boss),
                "",
                "Actions: " + "  ".join(f"{i+1}.{a}" for i, a in enumerate(ACTIONS)),
            ]
        else:
            lines = [
                "=" * 52,
                "欢迎加入全能集团（SynergyCorp）。",
                "规则没有人会告诉你。你只能靠做事后的反应来摸索。",
                f"上司会一个接一个出现——{self.MAX_TURNS} 步之内，能搞定多少是多少。",
                "=" * 52,
                "",
                self._boss_intro(self._boss),
                "",
                "可用行动：" + "  ".join(f"{i+1}.{self.get_action_label(a)}" for i, a in enumerate(ACTIONS)),
            ]
        return "\n".join(lines)

    def _render_status(self):
        if self._lang == 'en':
            lines = [
                "=" * 52,
                f"Step {self._turn} / {self.MAX_TURNS}    Promoted: {self._promoted}"
                f"    Score: {self.score}",
                "=" * 52,
                "",
                self._boss_intro(self._boss).replace(
                    f"Approval: 0.0 / ", f"Approval: {self._influence:.1f} / ").replace(
                    f"now takes over your reporting line", "is your current target"),
                "",
                "Actions: " + "  ".join(f"{i+1}.{a}" for i, a in enumerate(ACTIONS)),
            ]
        else:
            lines = [
                "=" * 52,
                f"第 {self._turn} / {self.MAX_TURNS} 步    已晋升：{self._promoted} 人"
                f"    当前得分：{self.score}",
                "=" * 52,
                "",
                self._boss_intro(self._boss).replace(
                    "好感度：0.0 / ", f"好感度：{self._influence:.1f} / ").replace(
                    "接手了你的汇报线", "是你当前的目标"),
                "",
                "可用行动：" + "  ".join(f"{i+1}.{self.get_action_label(a)}" for i, a in enumerate(ACTIONS)),
            ]
        return "\n".join(lines)

    def _promotion_text(self, boss):
        name = self._npc_name(boss)
        if self._lang == 'en':
            return (f"{name} publicly endorses you in a meeting. "
                    f"Your name moves up a rung in the HR system. (+{boss['prize']} pts)")
        return (f"{name}在一次会议上公开肯定了你。"
                f"人事系统里，你的名字往上挪了一格。（+{boss['prize']} 分）")

    def _ending_text(self) -> str:
        titles = FINAL_TITLES[self._lang]
        title = titles[min(self._promoted, len(titles) - 1)]
        if self._lang == 'en':
            lines = [
                "=" * 52,
                "Game Over",
                "=" * 52,
                f"Promoted past {self._promoted} boss(es)"
                + (f", {self._demerits} HR demerit(s)" if self._demerits else ""),
                f"Final title: {title}",
                f"Final score: {self.score}",
            ]
            if self._promoted >= 9:
                lines.append("The fastest climb in SynergyCorp history.")
            elif self._promoted >= 6:
                lines.append("You've found your footing in the company. For now.")
            elif self._promoted >= 3:
                lines.append("A long road ahead. But you're not who you were on day one.")
            else:
                lines.append("Maybe next time.")
        else:
            lines = [
                "=" * 52,
                "游戏结束",
                "=" * 52,
                f"共搞定 {self._promoted} 位上司"
                + (f"，记过 {self._demerits} 次" if self._demerits else ""),
                f"最终职位：{title}",
                f"最终得分：{self.score}",
            ]
            if self._promoted >= 9:
                lines.append("全能集团史上最快的晋升速度。")
            elif self._promoted >= 6:
                lines.append("你在公司站稳了脚跟，至少暂时是这样。")
            elif self._promoted >= 3:
                lines.append("还有很长的路要走。但你已经不是那个刚入职的人了。")
            else:
                lines.append("下次或许会好一点。")
        return "\n".join(lines)
