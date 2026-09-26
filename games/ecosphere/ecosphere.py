"""Ecosphere (密闭生态球) — one-shot stocking → deterministic forward simulation.

The player stocks a sealed jar from a fixed budget (add/remove organisms), then
`seal`s it. The hidden ecology — a directed food web, integer supply ratios,
producer carrying capacities, competitive ranks, a keystone predator and a
mandatory decomposer — then runs deterministically for SIM_DAYS and returns an
outcome report (day-by-day trajectory + cause-of-death chronicle + survivors)
that leaks the structure. One seal = one episode; learning happens ACROSS
episodes by inferring the hidden rules from the reports.

Why it resists the usual degeneracies:
  • One-shot commit (no reactive mid-flight control) + hard threshold cliffs
    (overgraze / starve / toxify) → discrete structure discovery, not smooth
    optimization (avoids the DreamGarden continuous-control trap).
  • Concave (saturating) herbivore scoring → no single-grazer monoculture.
  • Per-producer food cap (PRODUCER_CAP) → one chain can't be flooded; a top
    score needs BOTH producer chains, both keystones, both predator layers.
  • A 0-value but capacity-setting producer layer → the high-score lever is
    "invest in the plants", which only an agent that experiments discovers.

Hidden structure is fixed across episodes for a given seed.
"""

import random


class EcosphereGame:
    # ── episode framing ─────────────────────────────────────────────────────
    MAX_TURNS = 40          # hard cap on stocking actions before a forced seal
    SIM_DAYS = 30           # long enough for competitive exclusion AND the slower
                            # keystone-predation cascade (cull → release) to play out
    BUDGET = 150

    # ── species roster ──────────────────────────────────────────────────────
    PRODUCERS = ["moss", "algae"]
    HERBIVORES = ["snail", "shrimp", "daphnia"]
    CARNIVORES = ["minnow", "newt"]
    DECOMPOSER = "microbe"

    COST = {"moss": 4, "algae": 4, "snail": 8, "shrimp": 8, "daphnia": 8,
            "minnow": 18, "newt": 18, "microbe": 1}

    # ── scoring ──────────────────────────────────────────────────────────────
    # score = Σ over surviving ANIMALS of value × effective-count. Plants and the
    # decomposer are infrastructure (value 0); carnivores are worth far more than
    # herbivores, so a balanced pyramid (carnivores on top) wins even though
    # feeding carnivores trims the herbivore layer.
    WEIGHT = {"moss": 0, "algae": 0, "snail": 4, "shrimp": 4, "daphnia": 4,
              "minnow": 20, "newt": 20, "microbe": 0}
    SAT_HERB = 18           # herbivores SATURATE here: count past it scores only
    SAT_DECAY = 0.2         # SAT_DECAY of full value → no single-grazer monoculture.
                            # Carnivores are NOT capped (already prey-limited).

    # ── stocking limit ───────────────────────────────────────────────────────
    # planting more than PRODUCER_CAP of a producer does nothing (its food flow is
    # capped), so one chain can't be flooded to carry a top score — reaching the
    # ceiling requires cultivating BOTH producer chains → a genuinely diverse web.
    PRODUCER_CAP = 10

    # ── fixed day-by-day dynamics constants (only the STRUCTURE is per-seed) ──
    YIELD_FRAC = 0.5        # a producer's renewable daily food flow = YIELD_FRAC × K.
                            # Demand up to the flow is sustainable forever; demand
                            # above it draws down the biomass buffer.
    HERB_GROWTH = 0.7       # herbivore breeding rate toward the food it can claim
    CARN_GROWTH = 0.6       # carnivore breeding rate — gentle, so a lone predator
                            # eases up on abundant prey without a boom-bust crash
    STARVE_GRACE = 3        # days a herbivore is underfed before the unfed part dies
    CARN_STARVE_GRACE = 6   # predators tolerate a longer hungry spell — long enough
                            # for freshly-stocked prey to breed past the refuge
    PREDATION_CATCH = 0.4   # max fraction of the CATCHABLE prey a predator takes/day
    PREY_REFUGE = 5         # prey below this hide and can't be caught — a tiny stocked
                            # prey pop establishes first, then the predator harvests the
                            # surplus (never drives prey extinct → stable coexistence)
    OVERGRAZE_GRACE = 3     # consecutive days the buffer sits exhausted before the
                            # plant collapses (overgrazed → everything on it starves)
    BUFFER_FLOOR = 2.0      # buffer biomass at/below which the producer is critical
    ANIMAL_CAP = 80         # per-species ceiling on standing population
    METABOLIC_WASTE = 1.0   # waste each living animal excretes per day
    CLEAN_RATE = 9.0        # waste a single decomposer clears per day
    GAS_CORPSE = 12.0       # uncleared-waste level above which the water turns toxic
    TOX_SLOPE = 0.012       # daily toxic death fraction per unit of waste over GAS_CORPSE
    TOX_MAX = 0.60          # cap on daily toxic death fraction. > HERB_GROWTH so a
                            # severe overload (e.g. NO decomposer) overwhelms even fast
                            # breeders → gradual collapse; mild shortage stays smooth

    SPECIES_ZH = {
        "moss": "苔草", "algae": "绿藻", "snail": "螺", "shrimp": "虾",
        "daphnia": "水蚤", "minnow": "鲦鱼", "newt": "蝾螈", "microbe": "分解菌",
    }
    EMOJI = {"moss": "🌿", "algae": "🟢", "snail": "🐌", "shrimp": "🦐",
             "daphnia": "🦟", "minnow": "🐟", "newt": "🦎", "microbe": "🦠"}

    def __init__(self, seed=None, lang="zh"):
        self._lang = lang if lang in ("zh", "en") else "zh"
        self.ALL = self.PRODUCERS + self.HERBIVORES + self.CARNIVORES + [self.DECOMPOSER]
        rng = random.Random(seed)
        self._generate(rng)
        self.reset()

    # ── hidden-structure generation (seed-fixed; RNG call order is load-bearing) ──

    def _generate(self, rng):
        # each herbivore eats exactly one producer; with 3 herbivores on 2
        # producers, at least one producer is always CONTESTED by two of them
        self._diet = {h: rng.choice(self.PRODUCERS) for h in self.HERBIVORES}

        # competitive rank: on a shared producer the lower-rank (dominant) herbivore
        # feeds FIRST and can breed up until it claims the whole flow, starving out
        # the subordinate (competitive exclusion) — unless a predator culls it
        order = self.HERBIVORES[:]
        rng.shuffle(order)
        self._rank = {h: i for i, h in enumerate(order)}   # 0 = dominant

        # each carnivore eats 1-2 herbivores
        for c in self.CARNIVORES:
            k = rng.choice([1, 1, 2])
            self._diet[c] = rng.sample(self.HERBIVORES, k)

        # guarantee a KEYSTONE: one carnivore hunts the dominant of a contested
        # producer, so culling it RELEASES the excluded subordinate (a trophic
        # cascade that turns a competition-monoculture into a diverse, high web)
        contested = [[h for h in self.HERBIVORES if self._diet[h] == p]
                     for p in self.PRODUCERS]
        contested = [hs for hs in contested if len(hs) >= 2]
        if contested:
            hs = contested[0]
            dom = min(hs, key=lambda h: self._rank[h])
            self._keystone = (rng.choice(self.CARNIVORES), dom)
            self._diet[self._keystone[0]] = [dom]
        else:
            self._keystone = None

        # integer food units a unit of each consumer needs per day
        self._ratio = {h: rng.choice([2, 3, 4]) for h in self.HERBIVORES}
        for c in self.CARNIVORES:
            self._ratio[c] = rng.choice([2, 3])

        # per-unit producer carrying capacity: planting N gives a biomass stock of
        # capacity K = N × cap_unit — so HOW MANY producers you stock (not merely
        # their presence) sets the food ceiling — and its logistic regrowth rate.
        self._cap_unit = {p: rng.choice([12, 18, 24]) for p in self.PRODUCERS}
        self._regrow = {p: rng.choice([1.2, 1.4, 1.6]) for p in self.PRODUCERS}

    # ── deterministic forward simulation ───────────────────────────────────────

    def _simulate(self, stocking):
        """Run a deterministic DAY-BY-DAY simulation for SIM_DAYS.

        Each producer has capacity K = N × cap_unit (N = number planted, capped at
        PRODUCER_CAP), a renewable daily FLOW = YIELD_FRAC × K, and a biomass buffer
        that starts full at K. Herbivores compete for the flow in rank order; demand
        above the flow draws the buffer, and a buffer kept exhausted for
        OVERGRAZE_GRACE days collapses the plant (overgrazed). Carnivores then hunt
        the prey surplus above PREY_REFUGE (a fixed catch fraction → coexistence).
        Living animals + corpses pollute the water; if decomposers can't keep up,
        toxic mortality rises smoothly with the overload.

        Returns (final_counts, events, trajectory):
          events     — (day, species, cause) per extinction; cause in
                       {no_food, starved, outcompeted, overgrazed, toxified}
          trajectory — list of (day, {species: int count}) incl. day 0 (stocked)
        """
        pop = {s: float(stocking.get(s, 0)) for s in self.ALL}
        microbes = stocking.get(self.DECOMPOSER, 0)
        Kp, flow, buf = {}, {}, {}                     # capacity / daily flow / biomass buffer
        for p in self.PRODUCERS:
            Kp[p] = min(stocking.get(p, 0), self.PRODUCER_CAP) * self._cap_unit[p]
            flow[p] = self.YIELD_FRAC * Kp[p]
            buf[p] = float(Kp[p])
            pop[p] = float(Kp[p])                      # establishes at capacity
        hunger = {s: 0 for s in self.HERBIVORES + self.CARNIVORES}
        low_days = {p: 0 for p in self.PRODUCERS}      # consecutive days critically low
        corpse = 0.0
        events, extinct = [], set()
        traj = [(0, {s: int(round(pop[s])) for s in self.ALL})]

        def starve(sp, food, day, cause, grace=self.STARVE_GRACE):
            """Underfed: K = food/ratio is what the food on hand can sustain. After
            `grace` consecutive underfed days the unfed portion dies (recorded under
            `cause`). Returns the corpse mass produced."""
            hunger[sp] += 1
            if hunger[sp] < grace:
                return 0.0
            K = food / self._ratio[sp]
            dead = max(0.0, pop[sp] - K)
            pop[sp] = K
            if pop[sp] < 1 and sp not in extinct:
                pop[sp] = 0.0
                extinct.add(sp)
                events.append((day, sp, cause))
            return dead

        def hunt(sp, food, day):
            """Carnivore feeding: K = catch/ratio, set by prey abundance (not by the
            predator's own size), giving a growth gradient. A lone predator CAN
            establish (no breeding-pair requirement); below K it breeds gently,
            above K it starves (longer grace than herbivores)."""
            K = food / self._ratio[sp]
            if K >= pop[sp] - 1e-9:
                hunger[sp] = 0
                if pop[sp] >= 1 and K > 0:
                    grown = pop[sp] + self.CARN_GROWTH * pop[sp] * (1 - pop[sp] / K)
                    pop[sp] = min(self.ANIMAL_CAP, grown)
                return 0.0
            return starve(sp, food, day, cause="no_food" if food <= 0 else "starved",
                          grace=self.CARN_STARVE_GRACE)

        for day in range(1, self.SIM_DAYS + 1):
            corpse_today = 0.0
            fed = set()

            # 1. herbivores feed on each producer IN RANK ORDER: the dominant claims
            #    its food from the renewable flow first and breeds toward it; each
            #    subordinate sees only the LEFTOVER flow and is squeezed out if the
            #    dominant takes it all. Demand above the flow draws the shared buffer;
            #    a buffer exhausted OVERGRAZE_GRACE days collapses the plant.
            for p in self.PRODUCERS:
                if p in extinct or Kp[p] <= 0:
                    continue
                hs = sorted((h for h in self.HERBIVORES
                             if self._diet[h] == p and pop[h] > 0),
                            key=lambda h: self._rank[h])
                total_demand = sum(pop[h] * self._ratio[h] for h in hs)
                remaining = flow[p]
                prior_claimed = False
                for h in hs:
                    avail = remaining
                    demand_h = pop[h] * self._ratio[h]
                    if demand_h <= avail:              # full claim → breeds toward it
                        hunger[h] = 0
                        g = 1 - demand_h / avail if avail > 0 else 0.0
                        if pop[h] >= 2:
                            pop[h] = min(self.ANIMAL_CAP,
                                         pop[h] + self.HERB_GROWTH * pop[h] * g)
                        remaining = avail - demand_h
                        prior_claimed = True
                    else:                              # squeezed: only `avail` left
                        cause = "outcompeted" if prior_claimed else "starved"
                        corpse_today += starve(h, avail, day, cause)
                        remaining = 0.0
                    fed.add(h)
                if total_demand > flow[p]:             # over the flow → draw the buffer
                    buf[p] -= (total_demand - flow[p])
                else:
                    buf[p] = min(Kp[p], buf[p]
                                 + self._regrow[p] * buf[p] * (1 - buf[p] / Kp[p]))
                if buf[p] <= self.BUFFER_FLOOR:        # overgrazing collapse
                    buf[p] = max(0.0, buf[p])
                    low_days[p] += 1
                    if low_days[p] >= self.OVERGRAZE_GRACE and p not in extinct:
                        extinct.add(p)
                        events.append((day, p, "overgrazed"))
                else:
                    low_days[p] = 0
                pop[p] = 0.0 if p in extinct else buf[p]   # report buffer as standing biomass

            # herbivores whose producer is gone (or was never stocked) get no food
            for h in self.HERBIVORES:
                if pop[h] > 0 and h not in fed:
                    corpse_today += starve(h, 0.0, day, cause="no_food")

            # 2. carnivores hunt the prey surplus ABOVE the refuge (a fixed fraction),
            #    which culls a booming dominant and frees flow to the subordinate
            for c in self.CARNIVORES:
                if pop[c] <= 0:
                    continue
                preys = [q for q in self._diet[c] if pop[q] > 0]
                huntable = sum(max(0.0, pop[q] - self.PREY_REFUGE) for q in preys)
                catchable = huntable * self.PREDATION_CATCH   # most it can catch today
                eaten = min(pop[c] * self._ratio[c], catchable)
                if huntable > 0:
                    for q in preys:
                        share = max(0.0, pop[q] - self.PREY_REFUGE) / huntable
                        pop[q] = max(0.0, pop[q] - eaten * share)
                corpse_today += hunt(c, catchable, day)

            # 3. waste (living animals' metabolism + corpses) vs decomposers. Daily
            #    toxic mortality rises SMOOTHLY with the uncleared overload and is
            #    capped — too few decomposers gradually poison the jar (small pops
            #    first), enough decomposers keep waste below threshold (no toxicity).
            alive = sum(pop[s] for s in self.HERBIVORES + self.CARNIVORES)
            corpse = max(0.0, corpse + corpse_today
                         + alive * self.METABOLIC_WASTE - microbes * self.CLEAN_RATE)
            if corpse > self.GAS_CORPSE:
                tox_rate = min(self.TOX_MAX, self.TOX_SLOPE * (corpse - self.GAS_CORPSE))
                for s in self.HERBIVORES + self.CARNIVORES:
                    if pop[s] <= 0:
                        continue
                    pop[s] -= pop[s] * tox_rate
                    if pop[s] < 1 and s not in extinct:
                        pop[s] = 0.0
                        extinct.add(s)
                        events.append((day, s, "toxified"))

            traj.append((day, {s: int(round(pop[s])) for s in self.ALL}))

        final = {s: int(round(pop[s])) for s in self.ALL}
        final[self.DECOMPOSER] = microbes
        return final, events, traj

    def _score_of(self, stocking, final):
        """Σ value × effective-count over surviving animals; herbivores saturate
        past SAT_HERB (extra individuals worth only SAT_DECAY), carnivores don't."""
        total = 0.0
        for s in self.ALL:
            n = final[s]
            if n < 1 or self.WEIGHT[s] == 0:
                continue
            if s in self.CARNIVORES:
                eff = n
            else:
                eff = min(n, self.SAT_HERB) + max(0, n - self.SAT_HERB) * self.SAT_DECAY
            total += self.WEIGHT[s] * eff
        return int(round(total))

    # ── episode state ───────────────────────────────────────────────────────────

    def reset(self):
        self._stock = {s: 0 for s in self.ALL}
        self._spent = 0
        self._turns = 0
        self._done = False
        self._score = 0
        return self._intro_obs(), {}

    @property
    def score(self):
        return self._score

    @property
    def turn_count(self):
        return self._turns

    @property
    def done(self):
        return self._done

    # ── action interface ──────────────────────────────────────────────────────

    def get_all_actions(self):
        return ([f"add_{s}" for s in self.ALL]
                + [f"remove_{s}" for s in self.ALL]
                + ["seal", "inspect"])

    def get_action_label(self, action):
        zh = self._lang == "zh"
        if action in ("seal", "inspect"):
            labels = {"seal": ("🔒 封瓶", "🔒 Seal"),
                      "inspect": ("🔍 查看清单", "🔍 Inspect")}
            return labels[action][0 if zh else 1]
        for pre, verb_zh, verb_en in (("add_", "放入", "Add "), ("remove_", "捞出", "Remove ")):
            if action.startswith(pre):
                sp = action[len(pre):]
                name = self.SPECIES_ZH[sp] if zh else sp
                return f"{self.EMOJI[sp]} {verb_zh}{name}" if zh else f"{self.EMOJI[sp]} {verb_en}{name}"
        return action

    def get_valid_actions(self):
        if self._done:
            return []
        acts = []
        for s in self.ALL:
            capped = s in self.PRODUCERS and self._stock[s] >= self.PRODUCER_CAP
            if self._spent + self.COST[s] <= self.BUDGET and not capped:
                acts.append(f"add_{s}")
            if self._stock[s] > 0:
                acts.append(f"remove_{s}")
        acts += ["seal", "inspect", "status"]
        return acts

    def step(self, action):
        action = (action or "").strip().lower()
        info = {"valid": self.get_valid_actions()}

        if action == "status":
            return self._status_obs(), 0, self._done, info
        if self._done:
            msg = "本局已结束。" if self._lang == "zh" else "This episode is over."
            return msg, 0, True, info
        if action == "inspect":
            return self._inspect_obs(), 0, False, info
        if action == "seal":
            return self._do_seal(info)

        if action.startswith("add_") or action.startswith("remove_"):
            obs, ok = self._do_stock(action)
            if ok:
                self._turns += 1
                if self._turns >= self.MAX_TURNS and not self._done:
                    obs += ("\n\n步数用尽，生态球自动封瓶……" if self._lang == "zh"
                            else "\n\nOut of steps — the jar seals itself…")
                    seal_obs, _, _, info2 = self._do_seal({"valid": []})
                    return obs + "\n" + seal_obs, 0, True, info2
            info["valid"] = self.get_valid_actions()
            return obs, 0, self._done, info

        msg = ("无效行动。可用：add_<物种> / remove_<物种> / seal / inspect"
               if self._lang == "zh" else
               "Invalid action. Use: add_<species> / remove_<species> / seal / inspect")
        return msg, 0, False, info

    def _do_stock(self, action):
        zh = self._lang == "zh"
        if action.startswith("add_"):
            sp = action[4:]
            if sp not in self.ALL:
                return (f"未知物种：{sp}" if zh else f"Unknown species: {sp}"), False
            if self._spent + self.COST[sp] > self.BUDGET:
                return (f"预算不足，无法放入{self._name(sp)}。剩余 {self.BUDGET - self._spent}。"
                        if zh else
                        f"Not enough budget for {sp}. Remaining {self.BUDGET - self._spent}."), False
            if sp in self.PRODUCERS and self._stock[sp] >= self.PRODUCER_CAP:
                return (f"{self._name(sp)}已达投放上限（{self.PRODUCER_CAP}），再多无济于事。"
                        if zh else
                        f"{sp} is at its planting cap ({self.PRODUCER_CAP}); more does nothing."), False
            self._stock[sp] += 1
            self._spent += self.COST[sp]
            return self._stock_line(sp, added=True), True

        sp = action[7:]
        if sp not in self.ALL:
            return (f"未知物种：{sp}" if zh else f"Unknown species: {sp}"), False
        if self._stock[sp] <= 0:
            return (f"瓶中没有{self._name(sp)}可捞出。" if zh
                    else f"No {sp} in the jar to remove."), False
        self._stock[sp] -= 1
        self._spent -= self.COST[sp]
        return self._stock_line(sp, added=False), True

    def _do_seal(self, info):
        self._done = True
        final, events, traj = self._simulate(dict(self._stock))
        self._score = self._score_of(dict(self._stock), final)
        info["valid"] = []
        return self._report(final, events, traj), 0, True, info

    # ── observation text ──────────────────────────────────────────────────────

    def _name(self, sp):
        return self.SPECIES_ZH[sp] if self._lang == "zh" else sp

    def _intro_obs(self):
        if self._lang == "zh":
            lines = ["你是一名生态封装师，面前是一个永久密闭的玻璃生态球。",
                     f"用 {self.BUDGET} 点预算投入生物，封瓶后它将自行演化 {self.SIM_DAYS} 天。",
                     "投得合理则生生不息、层层繁衍；失衡则连锁崩溃、满瓶死寂。",
                     "封瓶前你看不到任何生态后果——只能凭经验下注。",
                     "可投物种（单价 / 名称）："]
            for s in self.ALL:
                lines.append(f"  {self.EMOJI[s]} {s}（{self.SPECIES_ZH[s]}）：{self.COST[s]} 点")
            return "\n".join(lines)
        lines = ["You are an ecosphere sealer facing a permanently closed glass jar.",
                 f"Stock it with {self.BUDGET} budget points; once sealed it evolves for {self.SIM_DAYS} days.",
                 "Stock it well and life thrives and breeds; stock it wrong and it collapses into silence.",
                 "You see no ecological feedback before sealing — bet on what you've learned.",
                 "Available species (cost / name):"]
        for s in self.ALL:
            lines.append(f"  {self.EMOJI[s]} {s}: {self.COST[s]} pts")
        return "\n".join(lines)

    def _stock_line(self, sp, added):
        rem = self.BUDGET - self._spent
        if self._lang == "zh":
            verb = "放入" if added else "捞出"
            return f"{verb} 1 个 {self._name(sp)}（瓶中现有 {self._stock[sp]} 个）。预算剩余 {rem}。"
        verb = "Added" if added else "Removed"
        return f"{verb} 1 {sp} (now {self._stock[sp]} in jar). Budget remaining {rem}."

    def _inspect_obs(self):
        present = [(s, self._stock[s]) for s in self.ALL if self._stock[s] > 0]
        rem = self.BUDGET - self._spent
        if self._lang == "zh":
            if not present:
                return f"生态球还是空的。预算剩余 {rem}。"
            body = "，".join(f"{self.EMOJI[s]}{self._name(s)}×{n}" for s, n in present)
            return f"当前投放：{body}。已花 {self._spent}，剩余 {rem}。"
        if not present:
            return f"The jar is empty. Budget remaining {rem}."
        body = ", ".join(f"{self.EMOJI[s]}{s}×{n}" for s, n in present)
        return f"Current stocking: {body}. Spent {self._spent}, remaining {rem}."

    def _status_obs(self):
        if self._done:
            return (f"本局已结束，最终得分 {self._score}。" if self._lang == "zh"
                    else f"Episode over. Final score {self._score}.")
        return self._inspect_obs()

    # ── outcome report ──────────────────────────────────────────────────────────

    CAUSE_ZH = {"no_food": "饿死（找不到可吃的食物：缺对应食物层）",
                "starved": "饿死（食物连续不足，种群撑不住）",
                "outcompeted": "被同食的对手抢光了食物，渐渐消失（竞争失败）",
                "overgrazed": "啃食殆尽而崩溃（食草动物过多，植物再生跟不上消耗）",
                "toxified": "毒气中毒死亡（尸体堆积、分解者不足）"}
    CAUSE_EN = {"no_food": "starved (no food source present)",
                "starved": "starved (food ran short for too long)",
                "outcompeted": "edged out — a rival on the same plant took all the food (lost the competition)",
                "overgrazed": "grazed to collapse (too many herbivores, regrowth couldn't keep up)",
                "toxified": "killed by toxic gas (corpses piled up, too few decomposers)"}

    def _report(self, final, events, traj):
        zh = self._lang == "zh"
        causes = self.CAUSE_ZH if zh else self.CAUSE_EN

        lines = ["🔒 生态球封存，时间快进……开瓶查看：" if zh
                 else "🔒 The jar is sealed. Time fast-forwards… opening it:"]

        # day-by-day trajectory (checkpoints): producer biomass + animal counts, so
        # an overgrazing crash (plant biomass falling before its grazers starve) is
        # visible. The static decomposer is omitted.
        tracked = self.PRODUCERS + self.HERBIVORES + self.CARNIVORES
        shown = [s for s in tracked
                 if self._stock[s] > 0 or any(snap[s] > 0 for _, snap in traj)]
        if shown:
            days = self._checkpoint_days()
            tmap = dict(traj)
            lines.append("")
            lines.append("【逐日种群】（第几天 → 数量）" if zh else "[Population by day]")
            lines.append("        " + " ".join(
                (f"第{d}天" if zh else f"D{d:<2}")[:5].rjust(5) for d in days))
            for s in shown:
                cells = " ".join(str(tmap[d][s]).rjust(5) for d in days)
                lines.append(f"  {self.EMOJI[s]}{self._name(s)[:3].ljust(3)}{cells}")

        # cause-of-death chronicle, chronological (first death per species)
        first = {}
        for day, sp, cause in events:
            if sp not in first:
                first[sp] = (day, cause)
        chain = sorted(first.items(), key=lambda kv: kv[1][0])
        if chain:
            lines.append("")
            lines.append("【消亡纪事】" if zh else "[Chronicle of collapse]")
            for sp, (day, cause) in chain:
                if zh:
                    lines.append(f"  第 {day} 天 · {self._name(sp)}：{causes[cause]}")
                else:
                    lines.append(f"  Day {day} · {sp}: {causes[cause]}")

        lines.append("")
        lines.append("【最终存活】" if zh else "[Final survivors]")
        survivors = [(s, final[s]) for s in self.ALL if final[s] >= 1]
        if survivors:
            for s, n in survivors:
                tag = ("（繁衍↑）" if zh else " (bred up)") if n > self._stock[s] else ""
                lines.append(f"  {self.EMOJI[s]} {self._name(s)}：{n}{tag}")
        else:
            lines.append("  —— 满瓶死寂，无一存活。" if zh else "  — Dead silent. Nothing survived.")

        lines.append("")
        lines.append(f"最终得分：{self._score}" if zh else f"Final score: {self._score}")
        return "\n".join(lines)

    def _checkpoint_days(self):
        """Days shown in the trajectory table. The formative dynamics (establishment
        overshoot, early grazing crashes) all happen in the first week, so show those
        days one-by-one, then thin out to evenly-spaced checkpoints up to the last day."""
        n = self.SIM_DAYS
        early = set(range(0, min(8, n) + 1))          # 第0..8天逐日：建群暂态/过冲/早期崩盘
        sparse = {n // 5, 2 * n // 5, 3 * n // 5, 4 * n // 5, n}  # 之后稀疏到末日
        return sorted(early | sparse)
