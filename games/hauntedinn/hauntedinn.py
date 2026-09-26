"""Haunted Inn (闹鬼客栈) — hidden-taboo discovery through inn management.

You run an inn for a SEASON of N_NIGHTS. Each night a queue of guests (visible
type + mark) arrives; you seat each in one of N_ROOMS (each room has a visible
fixed feature) or turn them away, then `open` for the night. An invisible ghost
holds a small set of HIDDEN TABOOS — relational/spatial conditions on the
night's arrangement (a guest-type in a feature-room, two types adjacent, a type
beside an empty room, too many of one type…). Each taboo violated scares the
involved guests away (their fee is lost) and leaves a LOCALIZED clue (which
room / which guest). Score = fees of guests who stayed.

The taboos are fixed across episodes (per seed); the guests vary per night, so
memorizing one night doesn't help — you must INDUCE the general taboo rules from
the haunting clues and then seat guests to avoid them. Learning is pure
hypothesis-and-falsification: there is no optimization to compute (once you know
the taboos, avoiding them is trivial), and the rules generalize (not a table).
"""

import random


class HauntedInnGame:
    MAX_TURNS = 120         # generous cap (≈ season length × placements + queries)
    N_ROOMS = 8
    N_NIGHTS = 1

    # guest types → nightly room fee
    FEES = {"商人": 30, "书生": 20, "孩童": 10, "老妇": 15, "戏子": 25}
    TYPES = list(FEES)
    TYPE_EN = {"商人": "merchant", "书生": "scholar", "孩童": "child",
               "老妇": "crone", "戏子": "actor"}
    MARKS = ["提灯", "无"]          # carries-a-lantern, or nothing
    MARK_EN = {"提灯": "lantern", "无": "—"}

    SPECIAL_FEATURES = ["镜子", "临窗", "阴暗", "佛龛"]   # mirror / window / dark / shrine
    FEATURE_EN = {"镜子": "mirror", "临窗": "window", "阴暗": "dark",
                  "佛龛": "shrine", "普通": "plain"}

    def __init__(self, seed=None, lang="zh"):
        self._lang = lang if lang in ("zh", "en") else "zh"
        self._seed = seed if seed is not None else 0
        rng = random.Random(seed)
        self._generate(rng)
        self._episode = 0        # 第几局（0-based）；客人随局变、忌讳只随 seed 变
        self.reset()

    # ── hidden-structure generation (seed-fixed) ────────────────────────────────

    def _generate(self, rng):
        # room features: exactly one of each special feature + plain filler, shuffled
        feats = list(self.SPECIAL_FEATURES) + ["普通"] * (self.N_ROOMS - len(self.SPECIAL_FEATURES))
        rng.shuffle(feats)
        self._features = feats                          # index = room (0-based)

        # hidden taboos: exactly 3, always including the two HARD-to-dodge /
        # hard-to-disentangle kinds — `adjacent` (forced on a packed inn, and
        # confounded: many adjacencies exist, so which pair is taboo needs a
        # deliberate experiment to isolate) and `count` (a common-that-night type
        # housed 3+ times) — plus one feature-room taboo for a clean early clue.
        # (empty-neighbor / single-room-only sets were dropped: a dense-fill
        # default trivially dodges them → no learning gradient.)
        feature_builder = rng.choice([self._mk_type_feature, self._mk_mark_feature])
        self._taboos = [self._mk_adjacent(rng), self._mk_count(rng), feature_builder(rng)]
        rng.shuffle(self._taboos)

    def _special_rooms(self):
        return [f for f in self.SPECIAL_FEATURES if f in self._features]

    def _mk_type_feature(self, rng):
        return {"kind": "type_feature", "type": rng.choice(self.TYPES),
                "feature": rng.choice(self._special_rooms())}

    def _mk_mark_feature(self, rng):
        return {"kind": "mark_feature", "mark": "提灯",
                "feature": rng.choice(self._special_rooms())}

    def _mk_adjacent(self, rng):
        a = rng.choice(self.TYPES)
        b = rng.choice(self.TYPES)
        return {"kind": "adjacent", "a": a, "b": b}

    def _mk_count(self, rng):
        return {"kind": "count", "type": rng.choice(self.TYPES), "n": 3}

    # ── per-night guest queue (固定：同一 seed 的 10 夜永远相同) ──────────────────
    # 客人只由 (seed, 夜) 决定 → 选同一个 seed，每次都是一模一样的一季；换 seed 才换内容。

    def _night_guests(self, night):
        rng = random.Random(self._seed * 1000 + night)
        n = rng.randint(6, 8)
        guests = []
        for i in range(n):
            t = rng.choice(self.TYPES)
            mark = "提灯" if rng.random() < 0.35 else "无"
            guests.append({"id": i, "type": t, "mark": mark, "fee": self.FEES[t]})
        return guests

    # ── episode state ───────────────────────────────────────────────────────────

    def reset(self):
        self._night = 1
        self._rooms = [None] * self.N_ROOMS            # each: guest dict or None
        self._queue = self._night_guests(self._episode + 1)   # 客人由 (seed, 局号) 决定，忌讳只随 seed 变
        self._qpos = 0                                 # index of guest at the door
        self._turns = 0
        self._score = 0
        self._done = False
        # Advance the round counter, the way every other reshuffled game does
        # (cf. poisoner/plague/hezu). Without this, `_episode` stayed 0 forever
        # and main.py — which builds the game ONCE and only calls reset() per
        # episode — replayed the identical guest lineup all 10 rounds, so the
        # one game in the suite that is meant to reshuffle its surface was in
        # fact a fixed world for every classic method. play.py is unaffected: it
        # sets _episode explicitly before reset() and uses a fresh object.
        self._episode += 1
        return self._intro_obs() + "\n\n" + self._situation(), {}

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
        return ([f"room_{i+1}" for i in range(self.N_ROOMS)] + ["turn_away"]
                + [f"empty_{i+1}" for i in range(self.N_ROOMS)] + ["open"])

    def get_action_label(self, action):
        zh = self._lang == "zh"
        if action == "turn_away":
            return "🚪 婉拒" if zh else "🚪 Turn away"
        if action == "open":
            return "🌙 打烊迎夜" if zh else "🌙 Open for the night"
        if action.startswith("room_"):
            return (f"🛏 第{action[5:]}号房" if zh else f"🛏 Room {action[5:]}")
        if action.startswith("empty_"):
            return (f"🧹 腾空第{action[6:]}号房" if zh else f"🧹 Empty room {action[6:]}")
        return action

    def get_valid_actions(self):
        if self._done:
            return []
        acts = []
        if self._cur_guest() is not None:
            for i in range(self.N_ROOMS):
                if self._rooms[i] is None:
                    acts.append(f"room_{i+1}")
            acts.append("turn_away")
        # 已住客的房间可随时腾空（打烊前），把客人退回门口重排——点错哪间直接清哪间
        for i in range(self.N_ROOMS):
            if self._rooms[i] is not None:
                acts.append(f"empty_{i+1}")
        acts.append("open")
        acts.append("status")
        return acts

    def _cur_guest(self):
        return self._queue[self._qpos] if self._qpos < len(self._queue) else None

    # ── step ──────────────────────────────────────────────────────────────────

    def step(self, action):
        action = (action or "").strip().lower()
        info = {"valid": self.get_valid_actions()}

        if action == "status":
            return self._situation(), 0, self._done, info
        if self._done:
            return (("本局已结束。" if self._lang == "zh" else "This round is over."),
                    0, True, info)

        if action == "open":
            return self._resolve_night(info)

        if action == "turn_away":
            if self._cur_guest() is None:
                return self._need_open_msg(), 0, False, info
            self._qpos += 1
            self._turns += 1
            return self._after_seat(info, turned_away=True)

        if action.startswith("room_"):
            return self._seat(action, info)

        if action.startswith("empty_"):
            return self._empty(action, info)

        msg = ("无效行动。可用：room_1..room_8 / turn_away / open"
               if self._lang == "zh" else
               "Invalid action. Use: room_1..room_8 / turn_away / open")
        return msg, 0, False, info

    def _seat(self, action, info):
        zh = self._lang == "zh"
        g = self._cur_guest()
        if g is None:
            return self._need_open_msg(), 0, False, info
        try:
            r = int(action[5:]) - 1
        except ValueError:
            r = -1
        if not (0 <= r < self.N_ROOMS):
            return (("没有这间房。" if zh else "No such room."), 0, False, info)
        if self._rooms[r] is not None:
            return (("那间房已经住了人。" if zh else "That room is taken."), 0, False, info)
        self._rooms[r] = g
        self._qpos += 1
        self._turns += 1
        return self._after_seat(info, seated_room=r)

    def _empty(self, action, info):
        """腾空任意一间已住客的房间（打烊结算前可用）：把那位客人退回门口队列、
        重新成为待安排的客人。点错哪间房直接清哪间，不必逐步撤销。结算才不可逆。"""
        zh = self._lang == "zh"
        try:
            r = int(action[6:]) - 1
        except ValueError:
            r = -1
        if not (0 <= r < self.N_ROOMS):
            return (("没有这间房。" if zh else "No such room."), 0, False, info)
        g = self._rooms[r]
        if g is None:
            return (("那间房本来就空着。" if zh else "That room is already empty."),
                    0, False, info)
        self._rooms[r] = None
        self._queue.insert(self._qpos, g)          # 退回门口，成为当前待安排的客人
        self._turns = max(0, self._turns - 1)
        msg = (f"🧹 把客人从第 {r+1} 号房请回门口，重新安排。" if zh
               else f"🧹 Guest moved out of room {r+1}, back at the door.")
        info["valid"] = self.get_valid_actions()
        return msg + "\n\n" + self._situation(), 0, False, info

    def _after_seat(self, info, seated_room=None, turned_away=False):
        # forced resolution if out of turns
        if self._turns >= self.MAX_TURNS:
            return self._resolve_night(info, forced=True)
        info["valid"] = self.get_valid_actions()
        return self._situation(), 0, self._done, info

    def _need_open_msg(self):
        return ("今晚的客人都安置完了，输入 open 打烊迎夜。" if self._lang == "zh"
                else "All of tonight's guests are handled — type open for the night.")

    # ── night resolution ──────────────────────────────────────────────────────

    def _resolve_night(self, info, forced=False):
        zh = self._lang == "zh"
        fled, cause = self._evaluate()
        revenue = sum(g["fee"] for i, g in enumerate(self._rooms)
                      if g is not None and i not in fled)
        self._score += revenue

        lines = [self._night_report(fled, cause, revenue)]

        self._night += 1
        if self._night > self.N_NIGHTS:
            self._done = True
            lines.append("")
            lines.append((f"本局结束,进账 {self._score} 文。" if zh
                          else f"Round over. Takings: {self._score}."))
            info["valid"] = []
            return "\n".join(lines), 0, True, info

        # set up next night (same season, same taboos)
        self._rooms = [None] * self.N_ROOMS
        self._queue = self._night_guests(self._night)
        self._qpos = 0
        lines.append("")
        lines.append(self._situation())
        info["valid"] = self.get_valid_actions()
        return "\n".join(lines), 0, False, info

    def _evaluate(self):
        """Return (fled, cause) where fled = set of room-indices whose guest left,
        and cause = {room: taboo_kind} for the rooms that DIRECTLY triggered a
        taboo. A haunting also panics the immediate neighbours, who flee too
        (one-hop cascade) — so triggering a taboo is costly, but the clue still
        points at the cause room."""
        rooms = self._rooms
        fled, cause = set(), {}

        def occ(i):
            return rooms[i] if 0 <= i < self.N_ROOMS else None

        def trigger(i, k):
            fled.add(i)
            cause.setdefault(i, k)

        for tb in self._taboos:
            k = tb["kind"]
            if k == "type_feature":
                for i, g in enumerate(rooms):
                    if g and self._features[i] == tb["feature"] and g["type"] == tb["type"]:
                        trigger(i, k)
            elif k == "mark_feature":
                for i, g in enumerate(rooms):
                    if g and self._features[i] == tb["feature"] and g["mark"] == tb["mark"]:
                        trigger(i, k)
            elif k == "adjacent":
                for i in range(self.N_ROOMS - 1):
                    g1, g2 = rooms[i], rooms[i + 1]
                    if not (g1 and g2):
                        continue
                    if tb["a"] != tb["b"]:
                        match = {g1["type"], g2["type"]} == {tb["a"], tb["b"]}
                    else:
                        match = g1["type"] == tb["a"] and g2["type"] == tb["a"]
                    if match:
                        trigger(i, k); trigger(i + 1, k)
            elif k == "count":
                idxs = [i for i, g in enumerate(rooms) if g and g["type"] == tb["type"]]
                if len(idxs) >= tb["n"]:
                    for i in idxs:
                        trigger(i, k)

        # panic cascade: a haunting empties the whole contiguous block of occupied
        # rooms it sits in — packing guests wall-to-wall is risky; an empty room
        # acts as a firebreak that stops the panic from spreading further.
        for i in list(fled):
            for step in (-1, 1):
                j = i + step
                while 0 <= j < self.N_ROOMS and rooms[j] is not None:
                    fled.add(j)
                    j += step
        return fled, cause

    # ── observation text ──────────────────────────────────────────────────────

    def _gname(self, g):
        if self._lang == "zh":
            return f"{g['type']}" + (f"·提灯" if g["mark"] == "提灯" else "")
        return f"{self.TYPE_EN[g['type']]}" + (" w/lantern" if g["mark"] == "提灯" else "")

    def _fname(self, i):
        f = self._features[i]
        return f if self._lang == "zh" else self.FEATURE_EN[f]

    def _room_map(self):
        zh = self._lang == "zh"
        cells = []
        for i in range(self.N_ROOMS):
            occ = self._rooms[i]
            who = (self._gname(occ) if occ else ("空" if zh else "empty"))
            cells.append(f"[{i+1}:{self._fname(i)}|{who}]")
        return " ".join(cells)

    def _situation(self):
        zh = self._lang == "zh"
        g = self._cur_guest()
        remaining = len(self._queue) - self._qpos
        lines = []
        lines.append((f"—— 第 {self._episode + 1} 局 ——" if zh
                      else f"—— Round {self._episode + 1} ——"))
        lines.append(("客房：" if zh else "Rooms: ") + self._room_map())
        if g is not None:
            if zh:
                lines.append(f"门口客人：{self._gname(g)}（房费 {g['fee']} 文）。"
                             f"队列还剩 {remaining} 位。安排哪间房？(room_N / turn_away)")
            else:
                lines.append(f"At the door: {self._gname(g)} (fee {g['fee']}). "
                             f"{remaining} left in queue. Which room? (room_N / turn_away)")
        else:
            lines.append(("客人都安置完了，输入 open 打烊迎夜。" if zh
                          else "All guests handled — type open for the night."))
        lines.append((f"本局进账：{self._score} 文" if zh else f"Round takings: {self._score}"))
        return "\n".join(lines)

    def _intro_obs(self):
        zh = self._lang == "zh"
        if zh:
            return ("\n".join([
                f"你接手了一家便宜得可疑的客栈。每局一队新客人上门,你把他们安排进 {self.N_ROOMS} 间客房"
                f"(每间有看得见的特征)或婉拒,然后打烊结算——结算即本局结束、可接着开下一局。",
                "可这店里有个看不见的恶灵——某些住宿安排会惹它作祟,把当晚牵涉的客人吓跑"
                "(房费泡汤)。它的忌讳是隐藏的,只能从'哪间房闹了鬼、谁被吓跑'里慢慢摸清。",
                "客越满、钱越多。目标:整局总房费最大化。同一 seed 的恶灵忌讳固定不变;"
                "每局客人重新洗牌(同套忌讳、不同客人)——多玩几局、对比着把它的忌讳摸出来。"]))
        return ("\n".join([
            f"You take over a suspiciously cheap inn. Each round a fresh queue of guests arrives; seat each "
            f"in one of {self.N_ROOMS} rooms (each with a visible feature) or turn them away, then open — "
            "that settles the round; then play the next.",
            "An invisible ghost haunts the place — certain arrangements provoke it and scare the "
            "involved guests away (their fee lost). Its taboos are hidden; infer them from which "
            "room was haunted and who fled.",
            "Fuller rooms = more money. Goal: maximize total fees for the round. The ghost's taboos are "
            "fixed per seed; guests are reshuffled each round (same taboos, new guests) — play several "
            "rounds and compare to infer them."]))

    def _night_report(self, fled, cause, revenue):
        zh = self._lang == "zh"
        head = (f"【第 {self._episode + 1} 局】" if zh
                else f"[Round {self._episode + 1}]")
        if not fled:
            body = ("夜深人静,客人安睡。" if zh else "A quiet night; all guests sleep soundly.")
            return f"{head} {body} " + (f"本局进账 {revenue} 文。" if zh
                                        else f"Tonight's takings: {revenue}.")
        # clue = WHICH room (feature) + WHO was the disturbance's origin — but NOT
        # why (the taboo kind is for the player to induce across nights). Cascade
        # victims are marked as merely panicked, so cause vs spread is legible.
        lines = [f"{head} " + ("子时阴风骤起——" if zh else "At midnight a cold wind rises —")]
        for i in sorted(fled):
            g = self._rooms[i]
            if i in cause:                              # the room that triggered a taboo
                if zh:
                    lines.append(f"  {i+1}号房({self._fname(i)})的{self._gname(g)}处骚动骤起,惊惶逃走!")
                else:
                    lines.append(f"  Room {i+1} ({self._fname(i)}): the disturbance erupts around the {self._gname(g)}, who flees!")
            else:                                       # panicked neighbour
                if zh:
                    lines.append(f"  {i+1}号房({self._fname(i)})的{self._gname(g)}被隔壁骚动惊到,也跟着逃了。")
                else:
                    lines.append(f"  Room {i+1} ({self._fname(i)}): the {self._gname(g)} panics at the commotion next door and flees too.")
        lines.append((f"本局进账 {revenue} 文。" if zh else f"Tonight's takings: {revenue}."))
        return "\n".join(lines)
