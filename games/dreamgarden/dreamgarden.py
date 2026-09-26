"""
梦境花圃 (DreamGarden) — 干预式因果发现游戏

你是沉睡神明梦境的调谐者。梦里栖息着五种生灵，你无法直接触碰它们，
只能向梦境注入四种抽象悸动。每种悸动会撩动某些生灵、压抑另一些；
生灵之间也有隐藏的、滞后一回合生效的相互影响（梦境的"食物网"）。
梦境共鸣（得分）由各生灵丰度的隐藏加权决定——某些生灵和谐（正分），
某些失谐（负分）。

所有隐藏结构（悸动→生灵权重、生灵→生灵权重、共鸣权重）每个 seed 不同、
对玩家完全隐藏，且跨回合固定。玩法核心：施加干预 → 观察涟漪 → 反推隐藏
因果图 → 利用图把系统驱动到高共鸣。
"""

from random import Random

# ── 生灵（名称中性，不暗示固定关系；关系由隐藏图决定）─────────────────────────
SPECIES     = ['spores', 'moths', 'jelly', 'spiders', 'nightmares']
SPECIES_ZH  = ['念想孢子', '流光飞蛾', '梦影水母', '静默之蛛', '噩梦残影']
SPECIES_EN  = ['Thought Spores', 'Gleam Moths', 'Dream Jellyfish',
               'Silent Weavers', 'Nightmare Echoes']
SPECIES_EMO = ['💭', '🦋', '🪼', '🕷️', '🌑']
N_SP        = 5

# ── 悸动（抽象干预，不泄露结构）────────────────────────────────────────────────
STIMULI     = ['throb', 'whisper', 'tide', 'eclipse']
ACTION_ZH = {
    'throb':   '🫀 悸动',
    'whisper': '🌫️ 低语',
    'tide':    '🌊 潮汐',
    'eclipse': '🌘 蚀',
    'wait':    '⏳ 静待',
}
ACTION_EN = {
    'throb':   '🫀 Throb',
    'whisper': '🌫️ Whisper',
    'tide':    '🌊 Tide',
    'eclipse': '🌘 Eclipse',
    'wait':    '⏳ Wait',
}
ALL_ACTIONS = STIMULI + ['wait']

MAX_TURNS = 18
CAP       = 100.0     # 每种生灵丰度上限
DECAY     = 0.20      # 自然衰减率
STIM_STR  = 15.0      # 悸动强度（强可控）
START_POP = 20.0      # 各生灵初始丰度
SAT       = 35.0      # 共鸣饱和点：单个生灵超过此值不再加分（凹性，逼迫分散经营）


class DreamGardenGame:
    MAX_TURNS = MAX_TURNS

    def __init__(self, seed: int = 1, lang: str = 'zh'):
        self._seed = seed
        self._lang = lang
        self.score = 0
        self.turn_count = 0
        self.done = False
        self._gen_hidden()
        self.reset()

    # ── 隐藏结构生成（seed 决定，跨回合固定）──────────────────────────────────
    #
    # 设计核心（双重防退化）：
    #  (1) 共鸣计分有饱和点 SAT——单个生灵堆过 SAT 不再加分，于是"砸高一个"严格劣于
    #      "分散养多个"，逼迫组合多个悸动（破"狂刷单一悸动"）。
    #  (2) 两个等价高分生灵 A、B：A 由悸动直连；B 只能经一条 2 跳隐藏生态链
    #      sB → P → Q → B 间接驱动（滞后 2 回合、经两个中间物种中转）。驱动 B 的
    #      关键悸动即时共鸣≈0、回报滞后两回合才显现——"逐个试悸动刷即时最高那个"
    #      发现不了 B 的链（破"一局瞬间收敛"，把学习曲线拉长到多局）。
    #  外加失谐物种 NEG：直连悸动 sA 会顺带喂养它，需用抑制悸动 supp 清理（管理维度）。
    def _gen_hidden(self):
        rng = Random(self._seed)
        A, B, NEG, P, Q = rng.sample(range(N_SP), N_SP)

        # 1) 共鸣权重（隐藏）：A、B 等价高分；NEG 失谐；P、Q（链中转）本身不计分
        self._value = [0.0] * N_SP
        self._value[A]   = 5.0
        self._value[B]   = 5.0
        self._value[NEG] = -3.0

        # 2) 生灵→生灵：核心隐藏链 P→Q→B（强正，各滞后1回合 → 合计滞后2回合）+ 一条噪声边
        #    噪声边不得指向 A、B、Q——否则制造"超级杠杆"或缩短 B 的链，使最优退化回狂刷单一悸动。
        self._W_eco = [[0.0] * N_SP for _ in range(N_SP)]
        self._W_eco[P][Q] = 1.5
        self._W_eco[Q][B] = 1.5
        pairs = [(i, j) for i in range(N_SP) for j in range(N_SP)
                 if i != j and j not in (A, B, Q) and (i, j) != (P, Q)]
        for (i, j) in rng.sample(pairs, 1):
            self._W_eco[i][j] = rng.choice([1.0, -1.0])

        # 3) 悸动→生灵：每个悸动只有单一干净效果（无隐藏副作用，可隔离）。
        #    B、P、Q 均不直连——B 的唯一通路是隐藏链 sB→P→Q→B（这是全游戏唯一要发现的谜题）。
        self._W_stim = [[0.0] * N_SP for _ in range(len(STIMULI))]
        sA, sB, trap, supp = rng.sample(range(len(STIMULI)), len(STIMULI))
        self._W_stim[sA][A]     = STIM_STR        # 直连高分 A（最易发现）
        self._W_stim[sA][NEG]   = STIM_STR * 0.4  # 代价：拉高 A 也喂养失谐物种（delta 列可见，不再隐藏）
        self._W_stim[sB][P]     = STIM_STR        # 关键：拉高链首 P（经 P→Q→B 间接驱动 B）
        self._W_stim[trap][NEG] = STIM_STR        # 陷阱：拉高失谐物种（价值公开，学会别用）
        self._W_stim[supp][NEG] = -STIM_STR       # 抑制：压低失谐物种

    def _t(self, zh, en):
        return en if self._lang == 'en' else zh

    def _sp(self, i):
        return SPECIES_EN[i] if self._lang == 'en' else SPECIES_ZH[i]

    # ── 公开接口 ──────────────────────────────────────────────────────────────
    def reset(self):
        self._pop = [START_POP] * N_SP
        self._prev_pop = list(self._pop)
        self.score = 0
        self.turn_count = 0
        self.done = False
        self._last_res = self._resonance()
        obs = self._render_intro() + '\n\n' + self._render_status()
        return obs, {'valid': self.get_valid_actions()}

    def step(self, action):
        action = action.strip().lower()

        if action == 'status':
            return self._render_status(), 0, self.done, {'valid': self.get_valid_actions()}
        if action == 'score':
            msg = self._t(f'当前共鸣累计：{self.score}  |  回合：{self.turn_count}/{MAX_TURNS}',
                          f'Total resonance: {self.score}  |  Turn: {self.turn_count}/{MAX_TURNS}')
            return msg, 0, self.done, {'valid': self.get_valid_actions()}

        if self.done:
            return self._render_status(), 0, True, {'valid': self.get_valid_actions()}

        if action not in ALL_ACTIONS:
            msg = self._t(f'❓ 未知悸动：{action}（本回合未消耗）',
                          f'❓ Unknown stimulus: {action} (turn not consumed)')
            return msg, 0, False, {'valid': self.get_valid_actions()}

        # ── 同步更新：生态涟漪基于本回合起始丰度（→ 自然滞后 1 回合）──────────
        prev = self._pop
        stim_idx = STIMULI.index(action) if action in STIMULI else None
        new = [0.0] * N_SP
        for j in range(N_SP):
            stim = self._W_stim[stim_idx][j] if stim_idx is not None else 0.0
            eco  = sum(self._W_eco[i][j] * prev[i] / 5.0 for i in range(N_SP))
            new[j] = max(0.0, min(CAP, prev[j] + stim + eco - DECAY * prev[j]))
        self._prev_pop = prev
        self._pop = new

        res = self._resonance()
        turn_score = round(res)
        self.score += turn_score
        self.turn_count += 1
        delta = res - self._last_res
        self._last_res = res

        if self.turn_count >= MAX_TURNS:
            self.done = True

        head = ACTION_ZH[action] if self._lang == 'zh' else ACTION_EN[action]
        arrow = '↑' if delta > 0.5 else ('↓' if delta < -0.5 else '→')
        msg = self._t(
            f'你施加了「{head}」。本回合共鸣 {turn_score:+d}（{arrow} 较上回合 {delta:+.0f}）',
            f'You applied "{head}". Resonance this turn {turn_score:+d} ({arrow} vs last {delta:+.0f})')
        obs = msg + '\n\n' + self._render_status()
        if self.done:
            obs += '\n\n' + self._t(f'🌙 梦境消散。最终共鸣累计：{self.score}',
                                    f'🌙 The dream dissolves. Final resonance: {self.score}')
        return obs, turn_score, self.done, {'valid': self.get_valid_actions()}

    def get_valid_actions(self):
        return STIMULI + ['wait', 'status']

    def get_all_actions(self):
        return ALL_ACTIONS

    def get_action_label(self, a):
        d = ACTION_EN if self._lang == 'en' else ACTION_ZH
        return d.get(a, a)

    # ── 内部 ──────────────────────────────────────────────────────────────────
    def _resonance(self):
        # 饱和：单个生灵超过 SAT 的部分不再加分（凹性 → 分散经营优于砸高单一物种）
        return sum(self._value[j] * min(self._pop[j], SAT) for j in range(N_SP))

    def _render_intro(self):
        if self._lang == 'en':
            return ('=' * 52 + '\n'
                    '        DreamGarden · Resonance\n'
                    'You tune a sleeping god\'s dream. Inject abstract stirrings;\n'
                    'watch how five dream-creatures answer — but no one tells you\n'
                    'who answers what. Drive the dream toward resonance.\n'
                    + '=' * 52)
        return ('=' * 52 + '\n'
                '          梦境花圃 · 共鸣\n'
                '你调谐着沉睡神明的梦。向梦中注入抽象的悸动，\n'
                '听五种生灵如何应和——但没人告诉你谁回应谁。\n'
                '设法让梦境持续共鸣。\n'
                + '=' * 52)

    def _val_tag(self, v):
        # 公开每种生灵的价值（不再隐藏谁值钱）
        if self._lang == 'en':
            return f'+{v:.0f}' if v > 0 else (f'{v:.0f}' if v < 0 else ' 0')
        return f'价值+{v:.0f}' if v > 0 else (f'价值{v:.0f}' if v < 0 else '价值 0')

    def _render_status(self):
        if self._lang == 'en':
            header = (f'Turn {self.turn_count}/{MAX_TURNS}   Resonance {self.score}'
                      f'    (score/turn = Σ value×min(pop,{int(SAT)}))')
        else:
            header = (f'回合 {self.turn_count}/{MAX_TURNS}   共鸣累计 {self.score}'
                      f'    (每回合得分 = Σ 价值×min(数量,{int(SAT)}))')
        lines = [header, '─' * 56]
        for i in range(N_SP):
            n = round(self._pop[i])
            d = n - round(self._prev_pop[i])
            dly = f'{d:+d}' if d != 0 else '  ·'
            bar = '▪' * min(20, round(n / 5)) + '·' * max(0, 20 - round(n / 5))
            tag = self._val_tag(self._value[i])
            lines.append(f'{SPECIES_EMO[i]} {self._sp(i):<18} {tag:>7}  {n:4d} ({dly:>4})  [{bar}]')
        return '\n'.join(lines)
