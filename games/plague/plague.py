"""
PlagueDoctor（瘟疫医师）—— 线性村庄·追猎随时间扩散的隐匿带菌者

一条街道上住着 20 户人家（村民 A..T 即位置 0..19，只与左右紧邻者往来）。怪病爆发，
你是赶来的医师。村里藏着 **2 个从不显症的带菌者**——他们看着永远健康，却是仅有的传染源。

核心机制（黑盒，靠游玩发现）：
  - 每个带菌者以自己为中心向外传病，**传染半径随他"在任(未被隔离)的天数"逐日扩大**
    （每 REACH_GROW 天 +1 格）：拖得越久，波及越广，最终会蔓延到整条街。病人本身不传人，
    疫情始终从那两个中心一圈圈往外扩。
  - 新感染当夜停在 1/4、次夜起逐格加重，> MAX_SEV 即死。**治疗**（每次 −1 severity）只能
    "治当下的病人、拖住死亡"——它压不住不断扩大的源头（每天行动点有限，半径一大就治不过来）。
  - **唯一能真正止住的办法：把带菌者隔离**（隔离者不再传病、也不被传染）。一隔离，他那圈疫情
    当夜就停止扩散——像约翰·斯诺封掉水泵。隔离得越早，冻结的半径越小、救下的人越多 → 平滑梯度。

隔离牢房只有 3 间、行动点也有限，逼你靠观察疫情**总从谁身边一圈圈扩散、而谁自己从不生病**，
辅以隔离实验，把那 2 个看似健康的人揪出来。只会埋头治病（不找带菌者）必然被扩散的源头淹没。

黑盒：谁是带菌者、各动作的作用，都要靠假设 + 干预实验跨回合归纳。带菌者**每局重洗身份**，
逼你学「搜寻方法」而非记住是谁；而"带菌者=扩散中心、隔离才能止住"这条律跨局固定=要学的东西。
接口与 Learn2Play Bench 其余游戏一致：reset / step / get_valid_actions / score / done。
"""

import random


class PlagueDoctorGame:
    MAX_TURNS = 140         # 步数上限（防拖延刷分；正常 14 天 ×4 AP ≈ 56 步）
    N = 20                  # 村民数（线性排列，位置 0..N-1，邻居 = i±1，不环绕）
    DAYS = 14               # 疫情持续天数
    AP = 4                  # 每天行动点
    QUARANTINE_CAP = 3      # 隔离牢房数（紧到无法一关了之，逼你关「对的人」）
    MAX_SEV = 3             # 病情严重度上限，过夜后 >MAX_SEV 即死亡（未治疗 3 夜即亡）
    TREAT_CURE = 1          # 一次治疗降低的严重度
    IMMUNE_DAYS = 1         # 治愈(降到 sev0)后获得的免疫夜数：其间不会被再感染
    N_CARRIERS = 2          # 隐形带菌者数量（无症状、每局重洗身份）
    REACH0 = 1              # 带菌者初始传染半径（第 1 夜只波及紧邻）
    REACH_GROW = 2          # 每 REACH_GROW 天，带菌者(未被隔离)的传染半径 +1

    def __init__(self, seed=None, lang='zh'):
        self._lang = lang if lang in ('zh', 'en') else 'zh'
        self.seed = seed
        self._episode = 0
        self.reset()

    # ── 生命周期 ────────────────────────────────────────────────────────────────
    def reset(self):
        self._ep_rng = random.Random(f"{self.seed}|{self._episode}")
        self.day = 1
        self.ap = self.AP
        self.turn_count = 0
        self.done = False
        self._last_msg = ""
        self._night_log = []

        # 村民状态（位置即编号；线性邻接）
        self.alive = [True] * self.N
        self.sev = [0] * self.N            # 0=健康，1..MAX_SEV=病情严重度
        self.immune = [0] * self.N         # >0 = 治愈后剩余免疫夜数（其间不会被感染）
        self.quar = [False] * self.N

        # 2 个隐形带菌者：无症状、永不显症/死亡；**每局重洗身份**（seed×episode 定）→ 逼学搜寻方法。
        # 位置限内部、分处两半，保证各自两侧有邻居、形成两片可分辨的疫情簇。
        crng = random.Random(f"{self.seed}|carriers|{self._episode}")
        a = crng.randint(2, self.N // 2 - 2)          # 左半：2..8
        b = crng.randint(self.N // 2 + 1, self.N - 3)  # 右半：11..17
        self.carriers = {a, b}
        self.carrier_age = {c: 0 for c in self.carriers}   # 各带菌者「在任(未隔离)夜数」→ 决定其传染半径

        self._episode_next = self._episode + 1
        return self._obs(), {}

    @property
    def score(self):
        # 存活比例换算成百分制（满分 100 = 全员存活）
        return int(round(100 * sum(self.alive) / self.N))

    def name(self, i):
        letter = chr(ord('A') + i)
        return (f"村民{letter}" if self._lang == 'zh' else f"Villager {letter}")

    # ── 行动集 ──────────────────────────────────────────────────────────────────
    def get_all_actions(self):
        acts = []
        for i in range(self.N):
            acts.append(f"treat_{i}")
        for i in range(self.N):
            acts.append(f"quarantine_{i}")
        for i in range(self.N):
            acts.append(f"release_{i}")
        acts += ["end_day", "status"]
        return acts

    def get_valid_actions(self):
        acts = []
        n_quar = sum(self.quar)
        for i in range(self.N):
            if not self.alive[i]:
                continue
            if self.sev[i] > 0:                      # 显症者可治（隔离中也能治）
                acts.append(f"treat_{i}")
            if self.quar[i]:
                acts.append(f"release_{i}")
            elif n_quar < self.QUARANTINE_CAP:
                acts.append(f"quarantine_{i}")
        acts += ["end_day", "status"]
        return acts

    def get_action_label(self, a):
        lang = self._lang
        if a == "end_day":
            return "结束本日(过夜)" if lang == 'zh' else "end day (night)"
        if a == "status":
            return "查看状态" if lang == 'zh' else "status"
        if "_" in a:
            verb, idx = a.split("_", 1)
            if idx.isdigit():
                vb = {"treat": "治疗", "quarantine": "隔离", "release": "解除隔离"} if lang == 'zh' \
                    else {"treat": "treat", "quarantine": "quarantine", "release": "release"}
                return f"{vb.get(verb, verb)} {self.name(int(idx))}"
        return a

    # ── 文本辅助 ────────────────────────────────────────────────────────────────
    def _t(self, zh, en):
        return zh if self._lang == 'zh' else en

    def _street(self):
        """把村庄一行排开，让「疫情从哪几处一圈圈往外扩」一眼可见。"""
        cells = []
        for i in range(self.N):
            letter = chr(ord('A') + i)
            if not self.alive[i]:
                sym = "x"
            elif self.quar[i]:
                sym = f"[{self.sev[i] if self.sev[i] > 0 else '·'}]"
            elif self.sev[i] > 0:
                sym = str(self.sev[i])
            else:
                sym = "·"
            cells.append(f"{letter}{sym}")
        legend = self._t("（· 健康  数字=严重度  [ ]=隔离中  x=已故）",
                         "(· healthy  digit=severity  [ ]=quarantined  x=dead)")
        return self._t("村庄街道： ", "Street: ") + " ".join(cells) + "\n  " + legend

    def _obs(self):
        alive = sum(self.alive)
        sick = sum(1 for i in range(self.N) if self.alive[i] and self.sev[i] > 0)
        disp_day = min(self.day, self.DAYS)   # 结束后 day 会越界到 DAYS+1，显示时夹住
        head = self._t(
            f"== 瘟疫医师 ==  第 {disp_day}/{self.DAYS} 天   今日行动点 {self.ap}/{self.AP}   "
            f"存活 {alive}/{self.N}（染病 {sick}）   隔离 {sum(self.quar)}/{self.QUARANTINE_CAP}   得分 {self.score}/100",
            f"== Plague Doctor ==  Day {disp_day}/{self.DAYS}   AP {self.ap}/{self.AP}   "
            f"Alive {alive}/{self.N} (sick {sick})   Quarantined {sum(self.quar)}/{self.QUARANTINE_CAP}   Score {self.score}/100")
        lines = [head]
        # 黑盒：不给任何规律提示（有无带菌者、如何止住，全靠游玩发现）。
        if self._last_msg:
            lines.append(self._last_msg)
        if self._night_log:
            lines.append("  " + "  ".join(self._night_log))
        lines.append(self._street())
        return "\n".join(lines)

    # ── 核心 ────────────────────────────────────────────────────────────────────
    def step(self, action):
        if action == "status":
            return self._obs(), 0, self.done, {"valid": self.get_valid_actions()}
        if self.done:
            return self._obs(), 0, True, {"valid": self.get_valid_actions()}

        action = action.strip()
        prev_score = self.score
        self.turn_count += 1
        self._night_log = []
        msg = []

        # 行动数超上限：剩余天数无人干预、疫情自然演完后结算（杜绝拖延不结算刷分）。
        if self.turn_count > self.MAX_TURNS:
            self.finalize(msg)
            self._last_msg = "  ".join(msg)
            return self._obs(), self.score - prev_score, self.done, {"valid": self.get_valid_actions()}

        if action == "end_day":
            self._resolve_night(msg)
        elif "_" in action:
            verb, idx = action.split("_", 1)
            if not idx.isdigit() or not (0 <= int(idx) < self.N):
                msg.append(self._t("没有这个村民。", "No such villager."))
            else:
                i = int(idx)
                if not self.alive[i]:
                    msg.append(self._t(f"{self.name(i)} 已经去世。", f"{self.name(i)} is already dead."))
                elif verb == "treat":
                    if self.sev[i] <= 0:
                        msg.append(self._t(f"{self.name(i)} 目前没有症状，无从医治。", f"{self.name(i)} shows no symptoms — nothing to treat."))
                    else:
                        self.ap -= 1
                        self.sev[i] = max(0, self.sev[i] - self.TREAT_CURE)
                        if self.sev[i] == 0:
                            self.immune[i] = self.IMMUNE_DAYS   # 康复后短暂免疫
                            msg.append(self._t(f"你诊治了 {self.name(i)}，症状消退，已康复（获得 {self.IMMUNE_DAYS} 天免疫）。",
                                               f"You treat {self.name(i)}; symptoms recede — recovered ({self.IMMUNE_DAYS}-day immunity)."))
                        else:
                            msg.append(self._t(f"你诊治了 {self.name(i)}，病情减轻至严重度 {self.sev[i]}。",
                                               f"You treat {self.name(i)}; severity down to {self.sev[i]}."))
                elif verb == "quarantine":
                    if self.quar[i]:
                        msg.append(self._t(f"{self.name(i)} 已在隔离中。", f"{self.name(i)} is already quarantined."))
                    elif sum(self.quar) >= self.QUARANTINE_CAP:
                        msg.append(self._t("隔离牢房已满（只有 3 间）。", "Quarantine is full (only 3 cells)."))
                    else:
                        self.ap -= 1
                        self.quar[i] = True
                        msg.append(self._t(f"你将 {self.name(i)} 隔离起来（不再传染、也不会被传染）。",
                                           f"You quarantine {self.name(i)} (no longer spreads or catches)."))
                elif verb == "release":
                    if not self.quar[i]:
                        msg.append(self._t(f"{self.name(i)} 并未被隔离。", f"{self.name(i)} is not quarantined."))
                    else:
                        self.ap -= 1
                        self.quar[i] = False
                        msg.append(self._t(f"你解除了 {self.name(i)} 的隔离。", f"You release {self.name(i)}."))
                else:
                    msg.append(self._t("无法执行的行动。", "Invalid action."))
            if self.ap <= 0 and not self.done:
                self._resolve_night(msg)
        else:
            msg.append(self._t("无法执行的行动。", "Invalid action."))

        self._last_msg = "  ".join(msg)
        reward = self.score - prev_score
        return self._obs(), reward, self.done, {"valid": self.get_valid_actions()}

    def _resolve_night(self, msg):
        """过夜结算：每个未隔离带菌者以自己为中心、按「随在任天数增长的半径」传染圈内健康者；
        既有病人加重/死亡；治疗只治标，唯有隔离带菌者能冻结其扩散半径。"""
        newly = set()
        # 1) 带菌者传染：半径 = REACH0 + 在任夜数 // REACH_GROW，逐日扩大 → 迟早覆盖全村。
        for c in self.carriers:
            if not self.alive[c] or self.quar[c]:
                continue
            self.carrier_age[c] += 1
            reach = self.REACH0 + self.carrier_age[c] // self.REACH_GROW
            for i in range(self.N):
                if i in self.carriers or not self.alive[i] or self.quar[i]:
                    continue
                if self.sev[i] == 0 and self.immune[i] == 0 and abs(i - c) <= reach:
                    newly.add(i)
        # 2) 既有病人病情加重 + 死亡（带菌者无症状不计；新感染者尚未落地，故第一晚停在 1/4）。
        deaths = []
        for i in range(self.N):
            if not self.alive[i] or i in self.carriers:
                continue
            if self.sev[i] > 0:
                self.sev[i] += 1
                if self.sev[i] > self.MAX_SEV:
                    self.alive[i] = False
                    self.quar[i] = False
                    deaths.append(i)
        # 3) 落地新感染（sev1，当夜不加重）
        newly = sorted(newly)
        for j in newly:
            self.sev[j] = 1
        # 免疫倒计时：本夜免疫的人已躲过这一夜，倒计时 -1（治愈当夜 immune=1 → 护一夜后归 0）。
        for i in range(self.N):
            if self.immune[i] > 0:
                self.immune[i] -= 1

        # 夜报
        if newly:
            self._night_log.append(self._t(
                f"昨夜新增染病 {len(newly)} 人：" + "、".join(self.name(i) for i in newly),
                f"{len(newly)} new infection(s) last night: " + ", ".join(self.name(i) for i in newly)))
        else:
            self._night_log.append(self._t("昨夜新增染病 0 人。", "0 new infections last night."))
        if deaths:
            self._night_log.append(self._t(
                "不幸离世：" + "、".join(self.name(i) for i in sorted(deaths)),
                "Perished: " + ", ".join(self.name(i) for i in sorted(deaths))))

        self.day += 1
        self.ap = self.AP

        if self.day > self.DAYS or sum(self.alive) == 0:
            self.done = True
            self._episode = self._episode_next
            msg.append(self._t(f">>> 疫情结束。最终存活 {sum(self.alive)}/{self.N}，得分 {self.score}/100。",
                               f">>> The outbreak ends. Final survivors: {sum(self.alive)}/{self.N}, score {self.score}/100."))

    def finalize(self, msg=None):
        """玩家提前停手（quit / 不再行动）时调用：剩余天数无人干预，疫情按当前态自然演完后结算。

        计分始终反映「第 14 天的存活数」，而非停手那一刻全员尚活的开局态——
        「开局即退出」= 放任疫情蔓延 = 低分；真正找出并隔离带菌者的解局在余下夜晚无新增感染、
        无人死亡，分数不受影响。
        """
        if msg is None:
            msg = []
        guard = 0
        while not self.done and guard <= self.DAYS + 1:
            self._resolve_night(msg)
            guard += 1
        self.done = True
        self._episode = self._episode_next
