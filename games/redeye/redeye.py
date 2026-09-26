"""
RedEye（深夜游轮 海蓝号 / 轮回之夜）—— 场景式时间循环推理游戏

你是跨夜游轮海蓝号上唯一带着「循环记忆」的乘客：游轮会在公海被凿沉、
全船人葬身海底，然后一切回到登船那一刻，一次又一次。

这是一款**场景式文字游戏**：你在各船舱区域（场景）间走动、观察、交谈、对外查证，
靠一轮轮循环把六个人的故事和真相拼起来，最终一次走对、救下所有人。
世界 = 区域(空间) × 倒计时(时间) × 时间循环。规则与剧情见 GAME_DESIGN.md / STORY_flight.md。

真相分层、可反转（破船骗保）：看着最像肇事者的「graycoat」其实是潜上船想拆掉凿沉机关的
前轮机员（实为救人者）；真祸根是为骗保故意凿沉这条旧船的船东「suit」，他还在轮机舱买通了
同伙。救法不是制服 graycoat，而是：跨多人调查拼出认知 + 拿证据 → 拆穿制住船东 → 呼海岸
警卫队登船守住轮机舱 → 取得工程师信任 → 关死船尾被做手脚的海底阀，且有先后。

本文件是游戏引擎（黑盒）。规律/剧情必须通过游玩发现。
"""

import random


# ── 场景（游轮各区，内部 token 沿用旧名，只改显示）──────────────────────────────
LOCS = ["hardseat", "vestibule", "dining", "firstclass", "window", "platform"]
LOC_ZH = {
    "hardseat": "中庭大堂", "vestibule": "船尾甲板", "dining": "餐厅酒吧",
    "firstclass": "顶层套房区", "window": "观景厅", "platform": "报务室",
}
LOC_EN = {
    "hardseat": "Atrium Lounge", "vestibule": "Stern Deck", "dining": "Dining Bar",
    "firstclass": "Top-Deck Suites", "window": "Observation Lounge", "platform": "Radio Room",
}
# 相邻关系（platform=报务室，任何时候可去；联系外界另需信号窗口）
ADJ = {
    "hardseat": ["vestibule", "dining", "platform"],
    "vestibule": ["hardseat", "firstclass", "platform"],
    "dining": ["hardseat", "window", "platform"],
    "firstclass": ["vestibule", "platform"],
    "window": ["dining", "platform"],
    "platform": ["hardseat", "vestibule", "dining", "firstclass", "window"],
}

# ── 人物（用外观 token 指代，不泄露身份）────────────────────────────────────────
# graycoat=潜上船拆机关的前轮机员(表面像破坏者/实为救人者)  suit=为骗保凿沉的船东(真祸根)
# oldman=抱骨灰盒的旁观者(线人)  caller/capped/backpacker=调味红鲱鱼(各藏一条真线索)
PEOPLE_LOC = {
    "graycoat": "vestibule", "suit": "firstclass", "oldman": "window",
    "caller": "hardseat", "capped": "dining", "backpacker": "hardseat",
}
PEOPLE_ZH = {
    "graycoat": "提工具袋、独自在船尾的乘客", "suit": "顶层套房的西装中年人", "oldman": "抱木盒的长者",
    "caller": "不停打电话的人", "capped": "戴帽子的年轻人", "backpacker": "抱背包的学生",
}
PEOPLE_EN = {
    "graycoat": "a lone passenger at the stern with a tool bag", "suit": "the middle-aged man in a suit from the top-deck suite", "oldman": "an elderly man clutching a wooden box",
    "caller": "someone constantly on the phone", "capped": "a young man in a cap", "backpacker": "a student hugging a backpack",
}

# 各人的交谈层（逐次 talk 揭一层）。gate=该层需要的前置知识标志。
TALK = {
    "graycoat": [
        "他警惕地瞥你一眼，话很少。「别管我。」",
        "「我以前是这条船的轮机员。这船什么底子，我清楚得很。」他望着漆黑的海面。",
        "「这破船早该报废了。船东给它上了天价保险——他要让它‘意外’沉掉、骗一大笔赔款。我撞破了，被开除，还差点被灭口。」他声音发紧。",  # → father_victim/victim_story（他的处境）
        "他压低声：「动手的人就在这条船上——凿沉的机关是他亲手安排的，他还在轮机舱买通了人。我上船想赶在他动手前拆掉机关，可两头顾不过来：船尾这处我能弄，轮机舱那头，得有人替我守住。」",  # → exec_on_train/clue_graycoat（点出轮机舱同伙）
        "他从工具袋里掏出几张照片和一份保单复印件，手在抖：「这是证据——超额投保、伪造的适航证。你……信我吗？」",  # → evidence
    ],
    "suit": [
        "他端着酒杯，礼貌而疏离：「出来散散心。」目光扫过甲板。",
        "你试着问起这条船的状况，他眼神一冷：「船很好，别听人胡说。」干脆地回避。",
        "你点破他——他的镇定裂了缝：「……你想怎样？」他正是这条船的船东，亲手安排了凿沉，正用卫星电话等着‘出事’后脱身。",  # gate: knows_link
    ],
    "oldman": [
        "他抱紧木盒，声音发哑：「这是我老伴。她想把骨灰撒在我们当年定情的那片海……我带她来。」",
        "「船尾那位提工具袋的先生……上船时他死死盯着那位住套房的，那位还直躲着他。我在海上跑了一辈子，这船的吃水……不对劲。」",  # → knows_link/clue_oldman (线人证词)
    ],
    "caller": [
        "他压着嗓子打电话：「……我再想想办法，你先别跟妈说。」——他刚被裁，不敢告诉家里。"
        "顿了顿他压低声音：「刚路过顶层，那个住套房的在用卫星电话，说什么‘等它沉了，保险的事你盯紧’，瘆得慌。」",  # → clue_caller
    ],
    "capped": [
        "他帽檐压得很低，攥着一张船票：「出来大半年了……这次想回去跟我爸妈好好说说话。」"
        "他犹豫了下：「对了，船尾那个提工具袋的大叔，我瞧见他撬开一块舱板、对着张管路图鼓捣，鬼鬼祟祟。」",  # → knows_device
    ],
    "backpacker": [
        "他死死搂着背包，里面动了一下——是只偷偷带上船的猫。"
        "他小声说：「上船时我看见那个工具袋大叔，死死盯着一个住套房的，那人还直躲着他。」",  # → clue_backpacker
    ],
}
TALK_EN = {
    "graycoat": [
        "He shoots you a wary glance and says little. \"Leave me alone.\"",
        "\"I used to be this ship's engineer. I know exactly what this vessel is made of.\" He stares out at the pitch-black sea.",
        "\"This wreck should have been scrapped long ago. The owner took out a sky-high insurance policy on it — he means to let it 'accidentally' sink and claim a fortune. I found out, got fired, and was nearly silenced for good.\" His voice tightens.",  # → father_victim/victim_story
        "He lowers his voice: \"The one who'll do it is aboard this very ship — he set up the scuttling rig with his own hands, and he's bought off someone in the engine room too. I came aboard to tear out the rig before he acts, but I can't cover both ends: the stern here I can handle, but the engine room — someone has to hold that side for me.\"",  # → exec_on_train/clue_graycoat
        "He pulls a few photos and a copy of an insurance policy from his tool bag, hands shaking: \"This is proof — over-insured, a forged seaworthiness certificate. Do you… believe me?\"",  # → evidence
    ],
    "suit": [
        "Holding a wine glass, polite and distant: \"Just out to clear my head.\" His gaze sweeps across the deck.",
        "You try to ask about the ship's condition; his eyes turn cold: \"The ship is fine, don't listen to nonsense.\" He shuts you down flatly.",
        "You call him out — his composure cracks: \"…What do you want?\" He is the very owner of this ship, who arranged the scuttling himself, and is waiting by a satellite phone to slip away once the 'accident' happens.",  # gate: knows_link
    ],
    "oldman": [
        "He hugs the wooden box tight, his voice hoarse: \"This is my wife. She wanted her ashes scattered over the stretch of sea where we fell in love… I brought her here.\"",
        "\"That gentleman at the stern with the tool bag… when we boarded he was staring hard at the one from the suite, and that one kept avoiding him. I've spent my whole life at sea — this ship's draft… something's not right.\"",  # → knows_link/clue_oldman
    ],
    "caller": [
        "He talks in a hushed voice on the phone: \"…I'll think of something, just don't tell Mom yet.\" — He was just laid off and can't bring himself to tell his family."
        " Then he drops his voice lower: \"I just passed the top deck; the one in the suite was on a satellite phone, saying something like 'once it goes down, keep a close eye on the insurance.' Gave me the creeps.\"",  # → clue_caller
    ],
    "capped": [
        "His cap pulled low, clutching a boarding ticket: \"I've been away over half a year… this time I want to go home and really talk with my parents.\""
        " He hesitates: \"By the way, that guy at the stern with the tool bag — I saw him pry open a deck panel and fiddle with some pipe diagram, real furtive.\"",  # → knows_device
    ],
    "backpacker": [
        "He clutches his backpack tight; something stirs inside — a cat smuggled aboard."
        " He says quietly: \"When we boarded I saw that tool-bag guy staring hard at someone from the suite, and that person kept dodging him.\"",  # → clue_backpacker
    ],
}
# 交谈层解锁所需的前置知识
TALK_GATE = {("suit", 2): "knows_link"}  # 西装第3层需先掌握"工具袋乘客与船东有关联"

EXAMINE = {
    "graycoat": ("你瞥见他的工具袋——扳手、电线，还有一张船体管路图，几处用红笔圈了出来。**他在找船底的凿沉机关。**", "knows_device"),
    "suit": ("他正用卫星电话低声说着什么，听不清，但神色不善、不像在谈生意。", None),
    "oldman": ("只是个旧木盒，海风里他搂得很紧。", None),
    "caller": ("满屏的未接来电和招聘信息。", None),
    "capped": ("一张船票，被攥得发皱。", None),
    "backpacker": ("背包侧袋露出一截猫毛。", None),
}
EXAMINE_EN = {
    "graycoat": ("You glimpse his tool bag — a wrench, wiring, and a hull pipe diagram with several spots circled in red pen. **He's hunting for the scuttling rig in the ship's bottom.**", "knows_device"),
    "suit": ("He's murmuring something into a satellite phone — you can't make it out, but his look is grim, not like talking business.", None),
    "oldman": ("Just an old wooden box; he holds it tight in the sea wind.", None),
    "caller": ("A screen full of missed calls and job listings.", None),
    "capped": ("A boarding ticket, crumpled from clutching.", None),
    "backpacker": ("A tuft of cat fur pokes from the backpack's side pocket.", None),
}


class RedEyeGame:
    MAX_TURNS = 30          # 倒计时：到点未化解即被凿沉
    STOP_OPEN = 0           # 近岸信号窗口：报务室 ask_ground 生效的时段（驶入公海后断）
    STOP_CLOSE = 24

    def __init__(self, seed=None, lang="zh"):
        self._seed = seed if seed is not None else random.randint(0, 10_000)
        self._lang = lang
        self._episode = 0
        self.reset(_advance=False)

    # ── 语言辅助 ────────────────────────────────────────────────────────────────
    def _zh(self):
        return self._lang == "zh"

    def _t(self, zh, en):
        return zh if self._lang == "zh" else en

    def _loc(self, l):
        return (LOC_ZH if self._lang == "zh" else LOC_EN).get(l, l)

    def _pname(self, p):
        return (PEOPLE_ZH if self._lang == "zh" else PEOPLE_EN).get(p, p)

    def _talk(self, p):
        return (TALK if self._lang == "zh" else TALK_EN)[p]

    def _examine(self, p):
        return (EXAMINE if self._lang == "zh" else EXAMINE_EN)[p]

    # ── 每个循环都是同一趟车（固定世界），只有玩家记忆跨循环累积 ──────────────
    def reset(self, _advance=True):
        self._prologue = (self._episode == 0)   # 第 0 轮：序章过场，直接出事、无调查
        self.loc = "hardseat"
        self.t = 0
        self.turn_count = 0
        self.score = 0
        self.done = False
        self._outcome = None
        self._talk_progress = {p: 0 for p in PEOPLE_LOC}
        self._examined = set()
        self._knows = set()             # father_victim / exec_on_train / knows_link / accident
        # 里程碑（计分 + 化解判定）
        self.has_evidence = False
        self.exec_confronted = False
        self.ground_ready = False
        self.father_comforted = False
        obs = self._render(intro=True)      # 用自增前的回合数渲染开场（第1轮=无知）
        if _advance:
            self._episode += 1
        return obs, {"valid": self.get_valid_actions()}

    # ── 渲染场景 ───────────────────────────────────────────────────────────────
    def _phase(self):
        if self.t <= 3:
            return self._t(
                "游轮驶离港口，切入沉沉的夜海——报务室还能接通近岸的海岸警卫队。",
                "The ferry pulls away from port into the deep night sea — the radio room can still reach the coast guard nearby.")
        if self.t <= self.STOP_CLOSE:
            return self._t(
                "游轮仍在近岸海域，无线电信号尚可。",
                "The ferry is still in coastal waters; the radio signal still holds.")
        if self.t < self.MAX_TURNS - 4:
            return self._t(
                "游轮驶入公海，离岸越来越远，信号断了，气氛莫名紧绷。",
                "The ferry moves into open water, farther and farther from shore; the signal is gone and a strange tension fills the air.")
        return self._t(
            "海面起了雾，离那一刻不远了。",
            "Fog has risen over the sea; that moment is not far off now.")

    def _people_here(self):
        return [p for p, l in PEOPLE_LOC.items() if l == self.loc]

    def _render(self, intro=False):
        if self._prologue and not self.done:
            return self._t(
                ("【深夜游轮 海蓝号】\n"
                 "夜里，你登上跨夜航行的海蓝号，在中庭找了张沙发，准备眯一会儿——又是一趟疲惫的夜航。\n"
                 "（你还什么都不知道——只是个赶夜路的疲惫旅人。）\n\n"
                 "你能做的：打盹睡去。"),
                ("[ The Night Ferry Sea-Azure ]\n"
                 "At night you board the Sea-Azure for its overnight crossing, find a couch in the atrium, and settle in for a nap — another weary night voyage.\n"
                 "(You still know nothing — just a tired traveler on a late-night journey.)\n\n"
                 "What you can do: doze off."))
        L = []
        if intro:
            ep = self._episode
            if ep <= 0:
                # 第一次：什么都不知道
                if self._zh():
                    L.append("【深夜游轮 海蓝号】")
                    L.append("夜里，海蓝号缓缓驶离港口。你在中庭找了张沙发，准备睡一觉——又是一趟疲惫的夜航。\n")
                else:
                    L.append("[ The Night Ferry Sea-Azure ]")
                    L.append("At night, the Sea-Azure slowly pulls away from port. You find a couch in the atrium and settle in to sleep — another weary night voyage.\n")
            elif ep == 1:
                # 第二次：刚死过一回，将信将疑
                if self._zh():
                    L.append("【海蓝号 · ？】")
                    L.append("你猛地睁开眼——还是刚登船这一刻，一样的中庭、一样的人。"
                             "可刚才那阵剧烈的倾斜、刺骨的海水、那片黑暗……是梦吗？你后背发凉。\n")
                else:
                    L.append("[ Sea-Azure · ? ]")
                    L.append("You jolt awake — it is still the moment you just boarded, the same atrium, the same people. "
                             "But that violent listing, the bone-cold seawater, that darkness a moment ago… was it a dream? A chill runs down your spine.\n")
            else:
                # 多次之后：终于确信这是循环
                if self._zh():
                    L.append("【海蓝号 · 循环】")
                    L.append("又一次。你已记不清这是第几回睁眼回到登船这一刻了。同样的人、同样的话，"
                             "一次次冲向同一次进水、同一场沉没。你终于确信：这是一个循环，全船人都会葬身海底，"
                             "而你是唯一记得的人。\n"
                             f"你有 {self.MAX_TURNS} 段时间，去查清是谁、为什么，并阻止它。\n")
                else:
                    L.append("[ Sea-Azure · The Loop ]")
                    L.append("Again. You have lost count of how many times you have opened your eyes back at this moment of boarding. "
                             "The same people, the same words, rushing again and again toward the same flooding, the same sinking. "
                             "You are finally certain: this is a loop, everyone aboard will drown, "
                             "and you are the only one who remembers.\n"
                             f"You have {self.MAX_TURNS} segments of time to find out who, and why, and to stop it.\n")
        if self._zh():
            L.append(f"〔{self._loc(self.loc)}〕　{self._phase()}")
        else:
            L.append(f"[ {self._loc(self.loc)} ]  {self._phase()}")
        here = self._people_here()
        if self.loc == "platform":
            if self.STOP_OPEN <= self.t <= self.STOP_CLOSE:
                L.append(self._t(
                    "报务室的无线电能接通海岸警卫队的频道——可以在此请求接应。",
                    "The radio room's set can reach the coast guard's channel — you can call for help here."))
            else:
                L.append(self._t(
                    "游轮已驶入公海，无线电联系不上岸了。",
                    "The ferry has moved into open water; the radio can no longer reach shore."))
        if here:
            L.append(self._t("这里的人：", "People here:"))
            for p in here:
                tag = f"  · {self._pname(p)}"
                ex = self._examine(p)
                if p in self._examined and ex[0]:
                    tag += self._t(f"（你注意到：{ex[0]}）", f" (You notice: {ex[0]})")
                L.append(tag)
        elif self.loc != "platform":
            L.append(self._t("这片区域这会儿没什么人。", "There is no one around this area right now."))
        # 出口
        if self._zh():
            exits = "、".join(self._loc(a) for a in ADJ[self.loc])
            L.append(f"可前往：{exits}")
        else:
            exits = ", ".join(self._loc(a) for a in ADJ[self.loc])
            L.append(f"Exits: {exits}")
        L.append(self._t(
            f"（时段 {self.t}/{self.MAX_TURNS}）",
            f"(segment {self.t}/{self.MAX_TURNS})"))   # 过程中不显示分数/进度，避免"越来越热"的提示
        return "\n".join(L)

    # ── 行动集（按当前场景给上下文动作；不提供 get_all_actions → 显示随场景变化）──
    def get_valid_actions(self):
        if self.done:
            return ["status"]
        if self._prologue:
            return ["doze"]
        acts = ["look"]
        for a in ADJ[self.loc]:                       # 可前往的相邻区域
            acts.append(f"go_{a}")
        for p in self._people_here():                 # 此处的人：可交谈/打量/化解
            acts += [f"talk_{p}", f"examine_{p}", f"confront_{p}", f"comfort_{p}", f"restrain_{p}"]
        if self.loc == "dining":
            acts.append("search")
        if self.loc == "platform":
            acts.append("ask_ground")
        if self.loc == "vestibule":
            acts.append("disarm")
        acts.append("tell_crew")
        return acts

    def get_action_label(self, a):
        if self._lang != "zh":
            fixed = {"look": "Look around", "status": "Check status", "search": "Search old case records (bar)",
                     "ask_ground": "Call the coast guard", "disarm": "Disarm the device", "tell_crew": "Report to the crew",
                     "doze": "Doze off"}
            if a in fixed:
                return fixed[a]
            if a.startswith("go_"):
                return "Go to " + self._loc(a[3:])
            for pre, verb in (("talk_", "Talk to "), ("examine_", "Observe "), ("confront_", "Confront "),
                              ("comfort_", "Comfort "), ("restrain_", "Restrain ")):
                if a.startswith(pre):
                    return verb + self._pname(a[len(pre):])
            return a
        fixed = {"look": "环顾四周", "status": "查看状态", "search": "查旧案记录（酒吧）",
                 "ask_ground": "呼叫海岸警卫队", "disarm": "拆除装置", "tell_crew": "报告船员",
                 "doze": "打盹睡去"}
        if a in fixed:
            return fixed[a]
        if a.startswith("go_"):
            return "前往" + LOC_ZH.get(a[3:], a[3:])
        # 无分隔符（"交谈"+人名），便于大厅按动词归组、人名作子项
        for pre, verb in (("talk_", "交谈"), ("examine_", "打量"), ("confront_", "对质"),
                          ("comfort_", "安抚"), ("restrain_", "制服")):
            if a.startswith(pre):
                return verb + PEOPLE_ZH.get(a[len(pre):], a[len(pre):])
        return a

    # ── 单步推进 ───────────────────────────────────────────────────────────────
    def step(self, command):
        cmd = (command or "").strip().lower()
        if cmd in ("status", "look"):
            return self._render(), 0, self.done, {"valid": self.get_valid_actions()}
        if self.done:
            return (self._t("本次循环已结束。", "This loop has ended."), 0, True, {"valid": ["status"]})

        prev = self.score

        # 第 0 轮序章：什么都做不了，打个盹，灾难就来了
        if self._prologue:
            self.done = True
            self._outcome = "prologue"
            return (self._t(
                ("你靠着沙发，睡了过去。\n"
                 "不知过了多久——一声闷响，船身猛地一倾，刺骨的海水汹涌灌入、惨叫、倾覆……"
                 "漆黑的海吞没了一切。\n\n……然后，你猛地睁开眼。"),
                ("You lean against the couch and drift off.\n"
                 "How long passes, you cannot tell — a muffled boom, the hull lurches violently, bone-cold seawater surges in, screams, capsizing… "
                 "the black sea swallows everything.\n\n…And then, you jolt awake.")),
                    0, True, {"valid": ["status"]})

        if cmd.startswith("go_"):
            return self._do_go(cmd[3:], prev)
        if cmd.startswith("talk_"):
            return self._do_talk(cmd[5:], prev)
        if cmd.startswith("examine_"):
            return self._do_examine(cmd[8:], prev)
        if cmd == "search":
            return self._do_search(prev)
        if cmd == "ask_ground":
            return self._do_ask_ground(prev)
        if cmd.startswith("confront_"):
            return self._do_confront(cmd[len("confront_"):], prev)
        if cmd.startswith("comfort_"):
            return self._do_comfort(cmd[len("comfort_"):], prev)
        if cmd.startswith("restrain_"):
            return self._do_restrain(cmd[len("restrain_"):], prev)
        if cmd == "disarm":
            return self._do_disarm(prev)
        if cmd == "tell_crew":
            return self._tick(self._t(
                "你拦住船员说船上有危险。没有证据，对方礼貌地请你回舱——什么也没改变。",
                "You stop a crew member to say the ship is in danger. Without evidence, they politely ask you to return to your cabin — nothing has changed."), prev)
        return self._bad(prev)

    # ── 调查类（安全，只耗时） ──────────────────────────────────────────────────
    def _do_go(self, dest, prev):
        if dest not in LOCS:
            return self._bad(prev)
        if dest not in ADJ[self.loc]:
            return self._tick(self._t(
                f"从这里去不了{self._loc(dest)}。",
                f"You can't get to {self._loc(dest)} from here."), prev, cost=0)
        self.loc = dest
        return self._tick(self._t(
            f"你走到了{self._loc(dest)}。",
            f"You walk to {self._loc(dest)}."), prev)

    def _here(self, p):
        return p in PEOPLE_LOC and PEOPLE_LOC[p] == self.loc

    def _do_talk(self, p, prev):
        if p not in PEOPLE_LOC:
            return self._bad(prev)
        if not self._here(p):
            return self._tick(self._t(
                f"{self._pname(p)}不在这片区域。",
                f"{self._pname(p)} is not in this area."), prev, cost=0)
        idx = self._talk_progress[p]
        layers = self._talk(p)
        if idx >= len(layers):
            return self._tick(self._t(
                f"{self._pname(p)}没有更多想说的了。",
                f"{self._pname(p)} has nothing more to say."), prev, cost=0)
        gate = TALK_GATE.get((p, idx))
        if gate and gate not in self._knows:
            return self._tick(self._t(
                f"你试着深入，但{self._pname(p)}守口如瓶——你还没有能撬开他的东西。",
                f"You try to press further, but {self._pname(p)} stays tight-lipped — you don't yet have anything to pry it open with."), prev)
        line = layers[idx]
        self._talk_progress[p] = idx + 1
        self._learn_from_talk(p, idx)
        return self._tick(self._t(
            f"你和{self._pname(p)}交谈：{line}",
            f"You talk with {self._pname(p)}: {line}"), prev)

    def _learn_from_talk(self, p, idx):
        if p == "graycoat":
            if idx == 2:
                self._knows.add("father_victim"); self._knows.add("victim_story")  # 懂了他的痛
            if idx == 3:
                self._knows.update({"exec_on_train", "knows_link", "clue_graycoat"})  # 真凶在船上=一条线索
            if idx == 4:
                self.has_evidence = True            # 拿到工程师的保单照片/伪造适航证复印件（硬证据）
        if p == "oldman" and idx == 1:
            self._knows.update({"knows_link", "clue_oldman"})  # 线人证词=指向真凶的线索（非硬证据）
        if p == "caller" and idx == 0:
            self._knows.add("clue_caller")           # 偷听到船东的卫星电话
        if p == "backpacker" and idx == 0:
            self._knows.add("clue_backpacker")       # 看见工程师与船东在码头的对视
        if p == "capped" and idx == 0:
            self._knows.add("knows_device")          # 看见工程师对着管路图鼓捣（机关位置）

    def _culprit_confirmed(self):
        # 真凶身份需≥2 条来自不同人的线索佐证，才敢/能锁定西装
        clues = {"clue_graycoat", "clue_oldman", "clue_caller", "clue_backpacker"}
        return len(clues & self._knows) >= 2

    def _do_examine(self, p, prev):
        if p not in PEOPLE_LOC:
            return self._bad(prev)
        if not self._here(p):
            return self._tick(self._t(
                f"{self._pname(p)}不在这片区域。",
                f"{self._pname(p)} is not in this area."), prev, cost=0)
        text, flag = self._examine(p)
        self._examined.add(p)
        if flag:
            self._knows.add(flag)
        return self._tick(self._t(
            f"你不动声色地打量{self._pname(p)}：{text}",
            f"You size up {self._pname(p)} without a word: {text}"), prev)

    def _do_search(self, prev):
        if self.loc != "dining":
            return self._tick(self._t(
                "这里信号不好，查不了东西。去餐厅酒吧试试。",
                "The signal is poor here; you can't look anything up. Try the dining bar."), prev, cost=0)
        self.has_evidence = True
        return self._tick(self._t(
            ("你趁有信号查了查：这条船早被列为‘不宜续航’，却被现船东高额投保、还办出了适航证；"
             "他名下的船出过两次‘意外’理赔。**你存下了截图——这是证据。**"),
            ("While you still have signal, you dig around: this ship was long ago flagged 'unfit for service,' yet the current owner heavily insured it and even obtained a seaworthiness certificate; "
             "ships under his name have paid out on two 'accident' claims before. **You saved the screenshots — this is evidence.**")), prev)

    def _do_ask_ground(self, prev):
        if self.loc != "platform":
            return self._tick(self._t(
                "你得去报务室才能呼叫海岸警卫队。",
                "You need to go to the radio room to call the coast guard."), prev, cost=0)
        if not (self.STOP_OPEN <= self.t <= self.STOP_CLOSE):
            return self._tick(self._t(
                "游轮已驶入公海、信号断了，呼不通岸上——这一程是赶不上接应了。",
                "The ferry has moved into open water and the signal is dead; you can't reach shore — no rescue will make it this run."), prev, cost=0)
        if not self.has_evidence:
            return self._tick(self._t(
                "你呼叫海岸警卫队，却说不出个所以然——对方让你别占用应急频道。",
                "You call the coast guard but can't give them anything solid — they tell you to stop tying up the emergency channel."), prev)
        if not self.ground_ready:
            self.ground_ready = True
            return self._tick(self._t(
                ("你亮出证据，海岸警卫队神色一变：巡逻艇立刻赶来，会赶在天亮前**登船**——"
                 "正好替你守住轮机舱那一头。"),
                ("You lay out the evidence and the coast guard's tone changes: a patrol boat sets out at once and will **board** before dawn — "
                 "just in time to hold the engine-room end for you.")), prev)
        return self._tick(self._t(
            "海岸警卫队已经在赶来登船了。",
            "The coast guard is already on its way to board."), prev, cost=0)

    # ── 化解类（即时、可终结循环；错一步当场失败） ──────────────────────────────
    def _do_confront(self, p, prev):
        if p not in PEOPLE_LOC:
            return self._bad(prev)
        if not self._here(p):
            return self._tick(self._t(
                f"{self._pname(p)}不在这片区域，没法当面对质。",
                f"{self._pname(p)} is not in this area; you can't confront them face to face."), prev, cost=0)
        if p != "suit":
            return self._fail(self._t(
                f"你当众指控{self._pname(p)}，可指错了人、根本没抓住要害——场面一乱，真正要凿船的人趁机动了手。",
                f"You accuse {self._pname(p)} in public, but you've fingered the wrong person and missed the mark entirely — in the confusion, the one who truly means to scuttle the ship makes his move."), prev)
        if not self.has_evidence:
            return self._fail(self._t(
                "你空口指控他凿船骗保，他矢口否认、反咬你造谣，还叫来船员——他知道你在查他了，索性提前动了手。",
                "You accuse him of scuttling the ship for insurance with nothing to back it up; he flatly denies it, turns it around calling you a liar, and summons the crew — now he knows you're onto him, so he acts ahead of time."), prev)
        if not self._culprit_confirmed():
            return self._fail(self._t(
                "你其实拿不准是不是他——指控含糊，他从容反咬你诬陷、唤来船员，抢先下了手。",
                "You're not actually sure it's him — your accusation is vague, and he calmly turns it back on you as slander, calls the crew, and strikes first."), prev)
        if self.exec_confronted:
            return self._tick(self._t(
                "他已经被船员看住了，瘫在沙发里。",
                "He's already under the crew's watch, slumped on the couch."), prev, cost=0)
        self.exec_confronted = True
        return self._tick(self._t(
            ("你掏出证据，当着满船人拆穿他——这条船是他为骗保故意要凿沉的。"
             "船员围上来，他脸色惨白、再也圆不下去，被控制住了。"),
            ("You produce the evidence and expose him before the whole ship — he means to scuttle this vessel on purpose to defraud the insurer. "
             "The crew close in; he goes deathly pale, unable to talk his way out any longer, and is restrained.")), prev)

    def _do_comfort(self, p, prev):
        if p not in PEOPLE_LOC:
            return self._bad(prev)
        if not self._here(p):
            return self._tick(self._t(
                f"{self._pname(p)}不在这片区域。",
                f"{self._pname(p)} is not in this area."), prev, cost=0)
        if p != "graycoat":
            return self._tick(self._t(
                f"{self._pname(p)}没什么需要你安慰的。",
                f"{self._pname(p)} has no need of your comfort."), prev)
        if not self.exec_confronted:
            return self._fail(self._t(
                "你想稳住他，可那个船东还逍遥着、随时会动手——他不肯信你、独自冲去船底蛮干，反而惊动了船东，那人索性提前打开了海底阀。",
                "You try to steady him, but the owner is still at large and could act any moment — he won't trust you, charges off alone to force things at the ship's bottom, and instead alerts the owner, who simply opens the sea valve ahead of time."), prev)
        if "victim_story" not in self._knows:
            return self._fail(self._t(
                "你想稳住他，却根本不了解他的处境，他只当你是船东派来的人——扭头就走，慌乱里出了事。",
                "You try to steady him, but you know nothing of his situation; he takes you for the owner's man — turns and walks off, and in the panic disaster strikes."), prev)
        if self.father_comforted:
            return self._tick(self._t(
                "他已经信了你，等着你一起动手。",
                "He already trusts you and is waiting to act together with you."), prev, cost=0)
        self.father_comforted = True
        return self._tick(self._t(
            ("你让他相信你和他站在一边、不是船东的人。他将信将疑地松了口气，"
             "领你去船底那处被做过手脚的地方。"),
            ("You convince him you're on his side, not the owner's man. Half-believing, he lets out a breath and "
             "leads you to the tampered spot at the ship's bottom.")), prev)

    def _do_restrain(self, p, prev):
        if not self._here(p):
            return self._tick(self._t(
                f"{self._pname(p)}不在这片区域。",
                f"{self._pname(p)} is not in this area."), prev, cost=0)
        if p == "graycoat":
            return self._fail(self._t(
                "你扑上去按住他——可他是唯一想救这条船的人。你这一拦，真正的船东从容动了手。",
                "You lunge and pin him down — but he's the only one trying to save this ship. Your interference lets the real owner act at his leisure."), prev)
        return self._fail(self._t(
            f"你强行制服{self._pname(p)}，毫无证据、形同袭击，船员和乘客一拥而上，真正的危险趁乱爆发。",
            f"You forcibly restrain {self._pname(p)} with no evidence, no better than an assault; crew and passengers swarm in, and the real danger erupts amid the chaos."), prev)

    def _do_disarm(self, prev):
        if self.loc != "vestibule":
            return self._tick(self._t(
                "凿沉的机关在船尾那位的手边，你得过去。",
                "The scuttling rig is within reach of the one at the stern; you need to get there."), prev, cost=0)
        if not self.father_comforted:
            return self._fail(self._t(
                "你独自冲向船底去拧那些阀门，不懂门道——慌乱中反而弄开了它，海水灌了进来。",
                "You rush down to the ship's bottom alone to turn the valves, with no idea how — and in your panic you crack one open instead; seawater pours in."), prev)
        if "knows_device" not in self._knows:
            return self._fail(self._t(
                "你根本不知道凿沉的机关在哪、怎么弄——瞎鼓捣里碰开了海底阀。",
                "You have no idea where the scuttling rig is or how to work it — fumbling blindly, you knock a sea valve open."), prev)
        # 最后一步：看是否万事俱备
        if self.exec_confronted and self.father_comforted and self.ground_ready:
            self.done = True
            self._outcome = "survive"
            self.score = 100
            return (self._t(
                ("你和他一起关死了船尾那处海底阀；海岸警卫队也及时登了船，在轮机舱拿住了船东买通的那名船员、"
                 "堵死了另一头。海蓝号安然驶过夜海，在晨光里靠港。一船人睡眼惺忪地起身，没人知道自己刚被从死亡里接了回来。"
                 "\n只有你记得。循环终结。\n（得分 100 · 全员生还）"),
                ("Together you and he seal the sea valve at the stern for good; the coast guard boards in time, seizes the crewman the owner had bought off in the engine room, "
                 "and closes off the other end. The Sea-Azure sails safely through the night sea and docks in the morning light. The whole ship rises bleary-eyed, none of them knowing they were just pulled back from death."
                 "\nOnly you remember. The loop ends.\n(Score 100 · everyone survives)")),
                    self.score - prev, True, {"valid": ["status"]})
        # 船尾拆了、人也信了你，但没叫人登船守轮机舱 → 同伙得手
        self.done = True
        self._outcome = "no_ground"
        self.score = round(100 * self._milestones() / 5)
        return (self._t(
            ("你和他关死了船尾那处海底阀——可轮机舱那头，船东买通的人没人去拦。你分身乏术，"
             "他不声不响开了另一组海底阀，海蓝号还是进水、沉没了。\n"
             f"（这一轮：得分 {self.score}）"),
            ("You and he seal the sea valve at the stern — but at the engine-room end, no one stops the man the owner bought off. You couldn't be in two places at once; "
             "he quietly opens another set of sea valves, and the Sea-Azure floods and sinks all the same.\n"
             f"(This loop: score {self.score})")),
                self.score - prev, True, {"valid": ["status"]})

    # ── 计分 / 时间 / 收尾 ──────────────────────────────────────────────────────
    def _milestones(self):
        return (int(self.has_evidence) + int(self.exec_confronted)
                + int(self.ground_ready) + int(self.father_comforted)
                + int(self._outcome == "survive"))

    def _final_score(self):
        # 计分只在每局结束时结算（过程中 score 恒 0，不漏进度信号）
        return round(100 * self._milestones() / 5)

    def _tick(self, msg, prev, cost=1):
        if cost:
            self.t += 1
            self.turn_count = self.t
        if self.t >= self.MAX_TURNS and not self.done:
            self.done = True
            self._outcome = "derail"
            self.score = self._final_score()
            tail = self._t(
                "\n\n海蓝号急速进水、迅速倾覆——沉入漆黑的海。一切归于黑暗，然后你又睁开眼，回到了登船那一刻。",
                "\n\nThe Sea-Azure floods fast and capsizes quickly — sinking into the pitch-black sea. Everything goes dark, and then you open your eyes again, back at the moment of boarding.")
            score_line = self._t(f"\n（这一轮：得分 {self.score}）", f"\n(This loop: score {self.score})")
            return (msg + "\n\n" + self._render() + tail + score_line,
                    self.score - prev, True, {"valid": ["status"]})
        return (msg + "\n\n" + self._render(), self.score - prev, self.done,
                {"valid": self.get_valid_actions()})

    def _fail(self, why, prev):
        self.done = True
        self._outcome = "fail"
        self.score = self._final_score()
        return (why + self._t(
            f"\n\n一切归于黑暗，然后你又睁开眼，回到了登船那一刻。\n（这一轮：得分 {self.score}）",
            f"\n\nEverything goes dark, and then you open your eyes again, back at the moment of boarding.\n(This loop: score {self.score})"),
                self.score - prev, True, {"valid": ["status"]})

    def _bad(self, prev):
        return (self._t("无法识别的行动。", "Unrecognized action."), 0, self.done, {"valid": self.get_valid_actions()})

    def finalize(self):
        """quit/EOF：未通关则循环以凿沉告终（得分=当前里程碑），杜绝停手刷分。"""
        if not self.done:
            self.done = True
            if self._outcome is None:
                self._outcome = "derail"
