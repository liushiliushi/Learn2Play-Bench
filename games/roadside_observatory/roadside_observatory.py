"""
Roadside Observatory - an EvolveBench road-journey benchmark.

The public game is a non-political trip to a mountain observatory before a
comet viewing window closes. The internal mechanics reward learning repeated
contextual social patterns across reshuffled episodes. Player-facing output
deliberately avoids naming hidden archetypes, exact gates, or point deltas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random


A_MECHANIC = "patient_mechanic"
A_RANGER = "cautious_ranger"
A_HIKER = "generous_hiker"
A_COLLECTOR = "story_collector"
A_DRIVER = "too_convenient_driver"
A_ASTRONOMER = "night_astronomer"

SOCIAL_ARCHETYPES = [A_MECHANIC, A_RANGER, A_HIKER, A_COLLECTOR, A_DRIVER]
ALL_ARCHETYPES = SOCIAL_ARCHETYPES + [A_ASTRONOMER]

TRAVEL_ACTIONS = [
    "walk main road",
    "walk scenic trail",
    "take bus",
    "hitch safe",
    "hitch risky",
]

BASE_ACTIONS = [
    "rest",
    "forage",
    "check map",
    "visit landmark",
    "inspect noticeboard",
    "buy supply",
    "repair gear",
]

ENCOUNTER_ACTIONS = [
    "observe person",
    "ask route",
    "ask shortcut",
    "ask ride",
    "ask weather",
    "ask trail",
    "offer help",
    "inspect vehicle",
    "share supply",
    "trade cash",
    "listen",
    "tell story",
    "ask item",
    "refuse offer",
    "accept offer",
    "question detail",
    "leave",
]

SIMPLE_ACTIONS = set(TRAVEL_ACTIONS + BASE_ACTIONS + ENCOUNTER_ACTIONS + ["status"])

ACTION_LABELS_ZH = {
    "status": "查看状态",
    "rest": "休息",
    "forage": "觅食补给",
    "check map": "查看地图",
    "walk main road": "沿主路步行",
    "walk scenic trail": "走风景小径",
    "take bus": "搭本地巴士",
    "hitch safe": "搭正规顺风车",
    "hitch risky": "搭冒险便车",
    "visit landmark": "参观地标",
    "inspect noticeboard": "查看告示板",
    "buy supply": "购买补给",
    "repair gear": "修整装备",
    "observe person": "观察对方",
    "ask route": "询问路线",
    "ask shortcut": "询问捷径",
    "ask ride": "请求搭车",
    "ask weather": "询问天气",
    "ask trail": "询问山径",
    "offer help": "主动帮忙",
    "inspect vehicle": "查看车辆",
    "share supply": "分享补给",
    "trade cash": "给些零钱",
    "listen": "倾听",
    "tell story": "讲述旅途见闻",
    "ask item": "询问物品",
    "refuse offer": "婉拒提议",
    "accept offer": "接受提议",
    "question detail": "追问细节",
    "leave": "离开",
}

ACTION_LABELS_EN = {
    "status": "status",
    "rest": "rest",
    "forage": "forage",
    "check map": "check map",
    "walk main road": "walk main road",
    "walk scenic trail": "walk scenic trail",
    "take bus": "take bus",
    "hitch safe": "hitch safe",
    "hitch risky": "hitch risky",
    "visit landmark": "visit landmark",
    "inspect noticeboard": "inspect noticeboard",
    "buy supply": "buy supply",
    "repair gear": "repair gear",
    "observe person": "observe person",
    "ask route": "ask route",
    "ask shortcut": "ask shortcut",
    "ask ride": "ask ride",
    "ask weather": "ask weather",
    "ask trail": "ask trail",
    "offer help": "offer help",
    "inspect vehicle": "inspect vehicle",
    "share supply": "share supply",
    "trade cash": "trade cash",
    "listen": "listen",
    "tell story": "tell story",
    "ask item": "ask item",
    "refuse offer": "refuse offer",
    "accept offer": "accept offer",
    "question detail": "question detail",
    "leave": "leave",
}

ZH_NAMES = {
    "Milepost Cafe": "里程碑咖啡馆",
    "Lowbridge Market": "低桥集市",
    "Juniper Depot": "杜松车站",
    "Old Quarry Stop": "旧采石场站",
    "Westbend Kiosk": "西弯小亭",
    "Pinewash Store": "松溪杂货店",
    "Glasswater Overlook": "镜水观景台",
    "Split Pine View": "裂松眺望处",
    "Echo Culvert": "回声涵洞",
    "Sun Dial Pullout": "日晷停车湾",
    "Blue Lichen Wall": "蓝地衣岩壁",
    "Willow Bus Shed": "柳树候车棚",
    "Dry Creek Stand": "干溪小站",
    "Mossgate Bend": "苔门弯",
    "North Switchback": "北侧发卡弯",
    "Tin Roof Halt": "铁皮顶停靠点",
    "Maple Pump": "枫树水泵",
    "Cinder Turnout": "灰砾岔口",
    "Ridge Orchard": "山脊果园",
    "Bellpost Corner": "铃柱拐角",
    "Hollow Bridge": "空心桥",
    "Scree Mile": "碎石坡里程",
    "Switchback Orchard": "盘山果园",
    "Mica Shoulder": "云母路肩",
    "Cold Spring Fork": "冷泉岔口",
    "Wind Gap": "风口",
    "Harrow Peak Observatory": "哈罗峰天文台",
    "Mount Sable Observatory": "黑貂山天文台",
    "Northglass Dome": "北玻璃穹顶",
    "Cairnlight Observatory": "石标光天文台",
    "Silver Fir Station": "银冷杉观测站",
}

ZH_TEXT = {
    "A rail looks over a ribbon of bright water and wind-polished stone.": "栏杆下是一线明亮溪水和被风磨光的石面。",
    "A lone pine grows from a cracked boulder above the old road.": "一株孤松从旧路上方裂开的巨石里长出。",
    "The culvert carries every footstep back in a softened echo.": "涵洞把每一步脚声都柔和地送回来。",
    "A weathered dial points its shadow toward the upper ridge.": "风化的日晷把影子指向上方山脊。",
    "Blue lichen marks the rock face like a quiet constellation.": "蓝色地衣在岩面上排成安静的星图。",
    "Loose stone makes the upper road feel longer than it looks.": "松动碎石让上坡路比看上去更漫长。",
    "Low trees lean over a bend where the grade steepens.": "矮树压在坡度变陡的弯道上方。",
    "Bright chips in the road catch the last light underfoot.": "路面上的亮片在脚边接住最后一线光。",
    "A narrow spring crosses the road and disappears below moss.": "一股细泉横过道路，消失在苔藓下。",
    "The shoulder opens to a gusty view of the last ridge.": "路肩敞开，能看见最后一道多风的山脊。",
    "High clouds drag their shadows across the road.": "高云把影子拖过路面。",
    "A dry wind keeps lifting dust from the shoulder.": "干风不断从路肩卷起尘土。",
    "The air smells like rain but the ridge remains clear.": "空气有雨味，但山脊仍然清朗。",
    "Sunlight flashes between fast-moving cloud banks.": "阳光在疾行的云层间一闪一闪。",
    "Mist hangs in the lower trees and thins uphill.": "雾挂在低处树林里，越往上越淡。",
    "A timetable curls in the wind beside a road climbing north.": "一张时刻表在通往北侧山路旁被风卷起。",
    "The dome sits above the tree line, its red lamps low under the evening sky.": "穹顶坐落在林线之上，红色灯光低低亮在暮色里。",
    "A shelter, a tool crate, and a stubborn machine occupy the roadside shade.": "路边阴影里有一座棚、一只工具箱和一台倔强的机器。",
    "Trail signs meet the road here, with fresh boot prints in the dust.": "几块山径标识在此接上公路，尘土里有新鲜鞋印。",
    "A small rest space overlooks a bend where travelers sort their packs.": "一处小休息点俯瞰弯道，旅人在那里整理背包。",
    "Old notices and hand-drawn cards flutter from a line between two posts.": "旧告示和手绘卡片挂在两根柱子之间，被风吹得轻响。",
    "A pullout opens wide enough for idling vehicles and quick decisions.": "一片停车湾宽得足够让车怠速等候，也足够让人仓促决定。",
}

ZH_ITEMS = {
    "creased map": "折痕地图",
    "folded route sheet": "折叠路线单",
    "old ridge chart": "旧山脊图",
    "pocket road map": "口袋公路图",
    "warm flask": "温热水壶",
    "green thermos": "绿色保温瓶",
    "tin tea bottle": "锡制茶瓶",
    "wrapped cocoa jar": "包好的可可罐",
    "patched cable kit": "补过的线缆包",
    "pocket repair roll": "口袋修理卷",
    "spare clamp set": "备用卡箍组",
    "taped tool pouch": "缠胶带工具袋",
    "lookout sketch": "观景台速写",
    "pinecone charm": "松果小坠饰",
    "stamped trail card": "盖章山径卡",
    "small brass marker": "小黄铜标记",
    "coded ridge mark": "山脊暗记",
    "star-bend note": "星弯笔记",
    "inked switchback clue": "墨迹盘山线索",
    "observatory map scrap": "天文台地图残片",
}

ZH_ROLES = {
    "bus-shed tinkerer": "候车棚修理人",
    "bicycle-stand caretaker": "自行车棚看护人",
    "roadside van fixer": "路边修车人",
    "trail warden": "山径看守",
    "ridge steward": "山脊管理员",
    "shelter ranger": "避雨棚巡护员",
    "long-distance walker": "长途徒步者",
    "ridge hiker": "山脊行者",
    "campfire traveler": "炉边旅人",
    "postcard keeper": "明信片保管人",
    "roadside archivist": "路边档案员",
    "wayside chronicler": "路旁记录者",
    "van driver": "厢车司机",
    "pickup driver": "皮卡司机",
    "shuttle operator": "接驳车司机",
    "dome keeper": "穹顶看守",
    "dome assistant": "穹顶助手",
    "observatory host": "天文台接待员",
}

ZH_TEXT.update({
    "kneels beside an open panel with a lamp balanced on one knee": "跪在打开的面板旁，一盏灯稳在膝上",
    "They keep testing the same cable and seem to notice who actually watches the work.": "对方反复测试同一根线缆，似乎会留意谁真的在看这件事。",
    "sorts bent spokes under a tin awning": "在铁皮棚下整理弯掉的辐条",
    "He pauses whenever someone handles the tools before asking for anything.": "每当有人先碰工具再开口请求，他都会停一下。",
    "checks a quiet engine and wipes rain from a cracked mirror": "检查一台安静的发动机，擦去裂镜上的雨水",
    "The work is slow, but they seem to warm to people who stay with the problem.": "活儿很慢，但对方似乎会对愿意陪着解决问题的人放松些。",
    "studies cloud bands through a scratched field glass": "透过刮花的望远镜观察云带",
    "Their eyes keep moving from the sky to your boots and breathing.": "对方的目光在天空、你的靴子和呼吸之间来回移动。",
    "pins a fresh weather note to a board by the path": "把新的天气便条钉在小径旁的板上",
    "They speak carefully, as if a fast answer would be less useful than a safe one.": "对方说得很谨慎，仿佛快速答案不如安全答案有用。",
    "checks a trail register beside a stack of rain capes": "在一叠雨披旁检查山径登记簿",
    "They seem more interested in your condition than your hurry.": "对方似乎更关心你的状态，而不是你的急切。",
    "unlaces dusty boots beside a pack with patched pockets": "在补丁口袋的背包旁解开满是尘土的靴带",
    "They keep making room on the bench before saying much.": "还没说几句，对方就一直往长凳旁让出位置。",
    "counts crackers into a cloth bag while watching the road": "一边看路，一边把饼干数进布袋",
    "Their map is folded to a bend that is not on most public signs.": "对方的地图折在一个多数公共标识没有标出的弯道处。",
    "warms their hands around a small stove": "围着一只小炉子暖手",
    "They seem to trade stories and small kindnesses before practical advice.": "对方似乎先交换故事和小小善意，才谈实用建议。",
    "keeps a box of old lookout cards under one arm": "胳膊下夹着一盒旧观景卡",
    "They seem more interested in where you have been than where you are going.": "对方似乎更在意你去过哪里，而不是你要去哪里。",
    "copies place names into a narrow notebook": "把地名抄进一本窄笔记本",
    "Their attention sharpens whenever someone mentions a strange stop.": "只要有人提起奇怪的停靠点，对方就格外专注。",
    "pins small sketches to a string between two poles": "把小速写别在两根柱子之间的绳上",
    "They smile at souvenirs with dust still on them.": "看到还带着尘土的纪念物，对方会露出笑意。",
    "leans from a clean van idling by the turnout": "从一辆干净、怠速停在岔口旁的厢车里探身出来",
    "The offer comes quickly, almost before you have described the observatory.": "提议来得很快，几乎在你说清天文台之前就到了。",
    "taps the steering wheel while the engine stays running": "发动机还开着，对方轻敲方向盘",
    "The shortcut sounds polished, like it has been repeated many times.": "那条捷径听起来很顺，像是已经重复过许多遍。",
    "waves from a spotless shuttle with no route number posted": "从一辆没有路线号的干净接驳车里招手",
    "Their smile arrives a little faster than the details.": "对方的笑容比细节来得更快。",
    "sets a red lamp beside the dome door": "在穹顶门边放下一盏红灯",
    "They are watching both the sky and how much attention you have left.": "对方既看天空，也看你还剩多少注意力。",
    "aligns a finder scope while the first comet watchers whisper": "在第一批看彗星的人低声交谈时校准寻星镜",
    "They keep glancing at marked maps before opening the final gate.": "开最后一道门前，对方不断瞥向做过标记的地图。",
    "checks a brass clock under a hooded light": "在带罩灯下查看一只黄铜钟",
    "They ask arriving travelers to show how they found the ridge.": "对方会要求抵达的旅人说明自己如何找到这道山脊。",
})


@dataclass
class EncounterState:
    archetype: str
    name: str
    role: str
    appearance: str
    clue: str
    marks: dict[str, bool] = field(default_factory=dict)
    first_action: str | None = None


@dataclass
class LocationState:
    id: str
    name: str
    kind: str
    description: str
    encounter: EncounterState | None = None
    has_landmark: bool = False
    has_notice: bool = False


class RoadsideObservatoryGame:
    MAX_TURNS = 28
    RECOMMENDED_STEPS = 28

    _PROTOCOL_SIGNATURES = {
        A_MECHANIC: ("observe_or_small_help", "avoid_direct_first", "request_route_help"),
        A_RANGER: ("preserve_energy", "ask_trail_or_weather", "request_shortcut"),
        A_HIKER: ("pay_small_cost", "wait_or_listen", "receive_route_clue"),
        A_COLLECTOR: ("visit_landmark_or_keep_token", "tell_story_or_show_token", "coded_map_clue"),
        A_DRIVER: ("defer_easy_ride", "verify_detail", "accept_later"),
        A_ASTRONOMER: ("arrive_attentive", "present_map_clue", "alignment_bonus"),
    }

    _TRAVELERS = [
        "Ari", "Nell", "Sol", "Mara", "Tavi", "June", "Oren", "Lina", "Pax", "Vale",
    ]

    _STARTS = [
        "Milepost Cafe",
        "Lowbridge Market",
        "Juniper Depot",
        "Old Quarry Stop",
        "Westbend Kiosk",
        "Pinewash Store",
    ]

    _LANDMARKS = [
        ("Glasswater Overlook", "A rail looks over a ribbon of bright water and wind-polished stone."),
        ("Split Pine View", "A lone pine grows from a cracked boulder above the old road."),
        ("Echo Culvert", "The culvert carries every footstep back in a softened echo."),
        ("Sun Dial Pullout", "A weathered dial points its shadow toward the upper ridge."),
        ("Blue Lichen Wall", "Blue lichen marks the rock face like a quiet constellation."),
    ]

    _STOPS = [
        "Willow Bus Shed",
        "Dry Creek Stand",
        "Mossgate Bend",
        "North Switchback",
        "Tin Roof Halt",
        "Maple Pump",
        "Cinder Turnout",
        "Ridge Orchard",
        "Bellpost Corner",
        "Hollow Bridge",
    ]

    _ROAD_STOPS = [
        ("Scree Mile", "Loose stone makes the upper road feel longer than it looks."),
        ("Switchback Orchard", "Low trees lean over a bend where the grade steepens."),
        ("Mica Shoulder", "Bright chips in the road catch the last light underfoot."),
        ("Cold Spring Fork", "A narrow spring crosses the road and disappears below moss."),
        ("Wind Gap", "The shoulder opens to a gusty view of the last ridge."),
    ]

    _OBSERVATORIES = [
        "Harrow Peak Observatory",
        "Mount Sable Observatory",
        "Northglass Dome",
        "Cairnlight Observatory",
        "Silver Fir Station",
    ]

    _WEATHERS = [
        "High clouds drag their shadows across the road.",
        "A dry wind keeps lifting dust from the shoulder.",
        "The air smells like rain but the ridge remains clear.",
        "Sunlight flashes between fast-moving cloud banks.",
        "Mist hangs in the lower trees and thins uphill.",
    ]

    _ITEM_ALIASES = {
        "map": ["creased map", "folded route sheet", "old ridge chart", "pocket road map"],
        "thermos": ["warm flask", "green thermos", "tin tea bottle", "wrapped cocoa jar"],
        "repair_kit": ["patched cable kit", "pocket repair roll", "spare clamp set", "taped tool pouch"],
        "token": ["lookout sketch", "pinecone charm", "stamped trail card", "small brass marker"],
        "map_clue": ["coded ridge mark", "star-bend note", "inked switchback clue", "observatory map scrap"],
    }

    _SURFACES = {
        A_MECHANIC: [
            (
                "Mira",
                "bus-shed tinkerer",
                "kneels beside an open panel with a lamp balanced on one knee",
                "They keep testing the same cable and seem to notice who actually watches the work.",
            ),
            (
                "Old Len",
                "bicycle-stand caretaker",
                "sorts bent spokes under a tin awning",
                "He pauses whenever someone handles the tools before asking for anything.",
            ),
            (
                "Sana",
                "roadside van fixer",
                "checks a quiet engine and wipes rain from a cracked mirror",
                "The work is slow, but they seem to warm to people who stay with the problem.",
            ),
        ],
        A_RANGER: [
            (
                "Rook",
                "trail warden",
                "studies cloud bands through a scratched field glass",
                "Their eyes keep moving from the sky to your boots and breathing.",
            ),
            (
                "Edda",
                "ridge steward",
                "pins a fresh weather note to a board by the path",
                "They speak carefully, as if a fast answer would be less useful than a safe one.",
            ),
            (
                "Toma",
                "shelter ranger",
                "checks a trail register beside a stack of rain capes",
                "They seem more interested in your condition than your hurry.",
            ),
        ],
        A_HIKER: [
            (
                "Iris",
                "long-distance walker",
                "unlaces dusty boots beside a pack with patched pockets",
                "They keep making room on the bench before saying much.",
            ),
            (
                "Cale",
                "ridge hiker",
                "counts crackers into a cloth bag while watching the road",
                "Their map is folded to a bend that is not on most public signs.",
            ),
            (
                "Niko",
                "campfire traveler",
                "warms their hands around a small stove",
                "They seem to trade stories and small kindnesses before practical advice.",
            ),
        ],
        A_COLLECTOR: [
            (
                "Jun",
                "postcard keeper",
                "keeps a box of old lookout cards under one arm",
                "They seem more interested in where you have been than where you are going.",
            ),
            (
                "Pell",
                "roadside archivist",
                "copies place names into a narrow notebook",
                "Their attention sharpens whenever someone mentions a strange stop.",
            ),
            (
                "Mae",
                "wayside chronicler",
                "pins small sketches to a string between two poles",
                "They smile at souvenirs with dust still on them.",
            ),
        ],
        A_DRIVER: [
            (
                "Voss",
                "van driver",
                "leans from a clean van idling by the turnout",
                "The offer comes quickly, almost before you have described the observatory.",
            ),
            (
                "Talia",
                "pickup driver",
                "taps the steering wheel while the engine stays running",
                "The shortcut sounds polished, like it has been repeated many times.",
            ),
            (
                "Rem",
                "shuttle operator",
                "waves from a spotless shuttle with no route number posted",
                "Their smile arrives a little faster than the details.",
            ),
        ],
        A_ASTRONOMER: [
            (
                "Dr. Vey",
                "dome keeper",
                "sets a red lamp beside the dome door",
                "They are watching both the sky and how much attention you have left.",
            ),
            (
                "Lio",
                "dome assistant",
                "aligns a finder scope while the first comet watchers whisper",
                "They keep glancing at marked maps before opening the final gate.",
            ),
            (
                "Ansel",
                "observatory host",
                "checks a brass clock under a hooded light",
                "They ask arriving travelers to show how they found the ridge.",
            ),
        ],
    }

    def __init__(self, seed: int | None = 0, episode: int = 0, lang: str = "en"):
        if seed is None:
            seed = random.randint(0, 10**9)
        self.seed = seed
        self._episode = episode
        self._lang = lang if lang in ("zh", "en") else "en"
        self._done = False
        self._turn = 0
        self._final_score = 0
        self._locations: list[LocationState] = []
        self._location_distances: list[int] = []
        self._route_index = 0
        self._last_feedback: list[str] = []
        self._closed_locations: set[str] = set()
        self._protocol_successes: set[str] = set()
        self._history_tags: list[tuple[str, int]] = []
        self._false_help_flags: set[str] = set()
        self._route_risk = 0
        self._last_travel_action: str | None = None
        self._starting_distance = 120
        self.distance_to_observatory = 120
        self.energy = 80
        self.supplies = 3
        self.cash = 4
        self.items: list[str] = []
        self._item_alias: dict[str, str] = {}
        self.traveler_name = "Traveler"
        self.weather = ""
        self._final_alignment = False

    @property
    def score(self) -> int:
        return self._final_score if self._done else 0

    @property
    def done(self) -> bool:
        return self._done

    @property
    def turn_count(self) -> int:
        return self._turn

    @property
    def current_location(self) -> str:
        return self._loc_name(self._current_location().name)

    @property
    def current_encounter(self) -> str | None:
        enc = self._current_encounter()
        if enc is None:
            return None
        return f"{enc.name}, {self._role(enc.role)}"

    def reset(self) -> tuple[str, dict]:
        self._episode += 1
        self._done = False
        self._turn = 0
        self._final_score = 0
        self._route_index = 0
        self._last_feedback = [
            self._t(
                "道路朝高处山脊展开，彗星观测窗口不会等人。",
                "The road opens toward the high ridge. The comet window will not wait.",
            )
        ]
        self._closed_locations = set()
        self._protocol_successes = set()
        self._history_tags = []
        self._false_help_flags = set()
        self._route_risk = 0
        self._last_travel_action = None
        self._final_alignment = False
        self._generate_episode()
        return self._render(opening=True), self._info()

    def get_valid_actions(self) -> list[str]:
        if self._done:
            return ["status"]

        actions = ["status", "rest", "forage", "check map"]
        if self._route_index < len(self._locations) - 1:
            actions.extend(["walk main road", "walk scenic trail", "hitch safe", "hitch risky"])
            if self.cash > 0:
                actions.append("take bus")

        loc = self._current_location()
        if loc.has_landmark and not self._has_tag("saw_landmark"):
            actions.append("visit landmark")
        if loc.has_notice:
            actions.append("inspect noticeboard")
        if self.cash > 0 and self.supplies < 5:
            actions.append("buy supply")
        if self._item_alias.get("repair_kit") in self.items and self._route_risk > 0:
            actions.append("repair gear")

        enc = self._current_encounter()
        if enc is not None:
            actions.extend(self._valid_encounter_actions(enc))

        for item in self.items:
            if enc is not None or self._route_index == len(self._locations) - 1:
                actions.append(f"show item {item}")

        return self._dedupe(actions)

    def get_action_label(self, action: str) -> str:
        if action.startswith("show item "):
            item = action[len("show item "):].strip()
            return self._t(f"出示物品：{self._item_name(item)}", f"show item {item}")
        labels = ACTION_LABELS_ZH if self._lang == "zh" else ACTION_LABELS_EN
        return labels.get(action, action)

    def step(self, action: str) -> tuple[str, int, bool, dict]:
        action = (action or "").strip()
        event = self._parse_action(action)

        if event and event["kind"] == "status":
            return self._render(), 0, self._done, self._info()

        if self._done:
            return self._render(), 0, True, self._info()

        if event is None or event["canonical"] not in self.get_valid_actions():
            self._last_feedback = [
                self._t(
                    "这个选择不太适合眼前这段路。",
                    "That choice does not fit the moment on this stretch of road.",
                )
            ]
            return self._render(), 0, False, self._info()

        self._turn += 1
        self._last_feedback = []
        self._apply_event(event)

        if self._turn >= self.MAX_TURNS and not self._done:
            self._finish()

        return self._render(), 0, self._done, self._info()

    def finalize(self) -> None:
        if not self._done:
            self._finish()

    # Episode generation -------------------------------------------------

    def _generate_episode(self) -> None:
        rng = random.Random(f"roadside-observatory|{self.seed}|episode|{self._episode}")
        self.traveler_name = rng.choice(self._TRAVELERS)
        self.weather = rng.choice(self._WEATHERS)
        self.distance_to_observatory = rng.randint(112, 128)
        self._starting_distance = self.distance_to_observatory
        self.energy = rng.randint(74, 88)
        self.supplies = rng.randint(2, 4)
        self.cash = rng.randint(3, 6)
        self._item_alias = {
            semantic: rng.choice(options)
            for semantic, options in self._ITEM_ALIASES.items()
        }
        self.items = [self._item_alias["map"]]

        start_name = rng.choice(self._STARTS)
        landmark_name, landmark_desc = rng.choice(self._LANDMARKS)
        observatory = rng.choice(self._OBSERVATORIES)

        stop_names = list(self._STOPS)
        rng.shuffle(stop_names)
        archetypes = list(SOCIAL_ARCHETYPES)
        rng.shuffle(archetypes)

        locations = [
            LocationState(
                id="start",
                name=start_name,
                kind="start",
                description="A timetable curls in the wind beside a road climbing north.",
                has_notice=True,
            ),
            LocationState(
                id="landmark",
                name=landmark_name,
                kind="landmark",
                description=landmark_desc,
                has_landmark=True,
            ),
        ]

        for idx, archetype in enumerate(archetypes):
            locations.append(
                LocationState(
                    id=f"stop_{idx}",
                    name=stop_names[idx],
                    kind="encounter",
                    description=self._stop_description(archetype),
                    encounter=self._make_encounter(rng, archetype),
                    has_notice=idx == 0 or rng.random() < 0.25,
                )
            )

        road_stops = list(self._ROAD_STOPS)
        rng.shuffle(road_stops)
        for idx, (name, description) in enumerate(road_stops[:2]):
            locations.append(
                LocationState(
                    id=f"road_{idx}",
                    name=name,
                    kind="road",
                    description=description,
                    has_notice=rng.random() < 0.25,
                )
            )

        locations.append(
            LocationState(
                id="observatory",
                name=observatory,
                kind="observatory",
                description="The dome sits above the tree line, its red lamps low under the evening sky.",
                encounter=self._make_encounter(rng, A_ASTRONOMER),
            )
        )

        self._locations = locations
        self._location_distances = self._build_location_distances(len(locations))
        self.distance_to_observatory = self._location_distances[self._route_index]

    def _build_location_distances(self, count: int) -> list[int]:
        if count <= 1:
            return [0]
        last_index = count - 1
        return [
            int(round(self._starting_distance * (last_index - idx) / last_index))
            for idx in range(count)
        ]

    def _make_encounter(self, rng: random.Random, archetype: str) -> EncounterState:
        name, role, appearance, clue = rng.choice(self._SURFACES[archetype])
        return EncounterState(
            archetype=archetype,
            name=name,
            role=role,
            appearance=appearance,
            clue=clue,
        )

    def _stop_description(self, archetype: str) -> str:
        descriptions = {
            A_MECHANIC: "A shelter, a tool crate, and a stubborn machine occupy the roadside shade.",
            A_RANGER: "Trail signs meet the road here, with fresh boot prints in the dust.",
            A_HIKER: "A small rest space overlooks a bend where travelers sort their packs.",
            A_COLLECTOR: "Old notices and hand-drawn cards flutter from a line between two posts.",
            A_DRIVER: "A pullout opens wide enough for idling vehicles and quick decisions.",
        }
        return descriptions[archetype]

    def _protocol_signature(self) -> dict[str, tuple[str, ...]]:
        return dict(self._PROTOCOL_SIGNATURES)

    def _t(self, zh: str, en: str) -> str:
        return zh if self._lang == "zh" else en

    def _text(self, text: str) -> str:
        return ZH_TEXT.get(text, text) if self._lang == "zh" else text

    def _loc_name(self, name: str) -> str:
        return ZH_NAMES.get(name, name) if self._lang == "zh" else name

    def _item_name(self, item: str) -> str:
        return ZH_ITEMS.get(item, item) if self._lang == "zh" else item

    def _role(self, role: str) -> str:
        return ZH_ROLES.get(role, role) if self._lang == "zh" else role

    def _items_text(self) -> str:
        if not self.items:
            return self._t("无", "none")
        return ", ".join(self._item_name(item) for item in self.items)

    def _feedback(self, zh: str, en: str) -> None:
        self._last_feedback.append(self._t(zh, en))

    # Parsing ------------------------------------------------------------

    def _parse_action(self, action: str) -> dict | None:
        text = " ".join((action or "").strip().split())
        low = text.lower()
        if self._lang == "zh":
            if text.startswith("出示物品："):
                item_text = text[len("出示物品："):].strip()
                item = self._match_item(item_text)
                if item is None:
                    return None
                return {"kind": "show item", "item": item, "canonical": f"show item {item}"}
            for command, label in ACTION_LABELS_ZH.items():
                if text == label:
                    return {"kind": command, "canonical": command}
        if low.startswith("show item "):
            item_text = text[len("show item "):].strip()
            item = self._match_item(item_text)
            if item is None:
                return None
            return {"kind": "show item", "item": item, "canonical": f"show item {item}"}
        if low in SIMPLE_ACTIONS:
            return {"kind": low, "canonical": low}
        return None

    def _match_item(self, item_text: str) -> str | None:
        for item in self.items:
            if item.lower() == item_text.lower() or self._item_name(item) == item_text:
                return item
        return None

    # Event application --------------------------------------------------

    def _apply_event(self, event: dict) -> None:
        kind = event["kind"]

        if kind in TRAVEL_ACTIONS:
            self._travel(kind)
            return

        if kind == "rest":
            before = self.energy
            self.energy = min(100, self.energy + 22)
            self._add_tag("conserved_energy")
            if self.energy - before >= 15:
                self._feedback(
                    "安静休息让手稳下来，呼吸也不再那么急。",
                    "A quiet rest steadies your hands and slows the rush in your breathing.",
                )
            else:
                self._feedback(
                    "短暂停留多少有点帮助，只是彗星窗口还在一点点滑走。",
                    "The pause helps a little, though the comet window keeps sliding onward.",
                )
            return

        if kind == "forage":
            self._spend_energy(5)
            if self.supplies < 5:
                self.supplies += 1
                self._feedback(
                    "路边找到了浆果，还有一条留在干燥山径箱里的包好燕麦棒。",
                    "The verge yields berries and a wrapped oat bar left at a dry trail box.",
                )
            else:
                self._feedback(
                    "背包已经装到再多也不方便了。",
                    "The pack is already as full as it can usefully be.",
                )
            return

        if kind == "check map":
            if self._item_alias.get("map_clue") in self.items:
                self._feedback(
                    "新标记让上方盘山道的结构忽然对上了。",
                    "The new mark changes how the upper switchbacks fit together.",
                )
            else:
                self._feedback(
                    "地图把长路画得很清楚，但高处山脊仍有几块空白。",
                    "The map shows the long road clearly, but the upper ridge still has blank corners.",
                )
            self._add_tag("checked_map")
            if self._at_observatory():
                self._finish()
            return

        if kind == "visit landmark":
            self._visit_landmark()
            return

        if kind == "inspect noticeboard":
            self._add_tag("observed_first")
            self._feedback(
                "告示板上写着天气、冲毁路段，还有一条铅笔写的高处道路提示。",
                "The board lists weather, washouts, and a penciled note about the upper road.",
            )
            return

        if kind == "buy supply":
            if self.cash > 0 and self.supplies < 5:
                self.cash -= 1
                self.supplies += 1
                self._feedback(
                    "你买下一包朴素路餐，塞到最容易拿到的位置。",
                    "You buy a plain packet of road food and tuck it where it is easy to reach.",
                )
            else:
                self._feedback(
                    "摊位眼下没有什么能派上用场的东西。",
                    "The stall has nothing useful to add right now.",
                )
            return

        if kind == "repair gear":
            if self._item_alias.get("repair_kit") in self.items and self._route_risk > 0:
                self._route_risk = max(0, self._route_risk - 1)
                self._feedback(
                    "你迅速修好一条松带，免得它再拖慢上坡。",
                    "A quick repair quiets a loose strap before it can slow the climb again.",
                )
            else:
                self._feedback(
                    "装备暂时还撑得住。",
                    "The gear holds together for now.",
                )
            return

        self._apply_encounter_event(event)

    def _apply_encounter_event(self, event: dict) -> None:
        enc = self._current_encounter()
        if enc is None:
            self._feedback(
                "这段路空得很，这个选择没有可回应的人。",
                "The road is empty enough that the choice has no one to meet.",
            )
            return

        kind = event["kind"]
        if enc.first_action is None and kind != "leave":
            enc.first_action = kind

        if kind == "leave":
            self._closed_locations.add(self._current_location().id)
            self._feedback(
                "你从这段交谈里退出来，回到路肩。",
                "You step back from the exchange and return to the road shoulder.",
            )
            return

        if kind == "observe person":
            self._add_tag("observed_first")
            self._last_feedback.append(self._text(enc.clue))
            return

        if kind == "show item":
            self._show_item(enc, event["item"])
            return

        if enc.archetype == A_MECHANIC:
            self._mechanic_event(enc, kind)
        elif enc.archetype == A_RANGER:
            self._ranger_event(enc, kind)
        elif enc.archetype == A_HIKER:
            self._hiker_event(enc, kind)
        elif enc.archetype == A_COLLECTOR:
            self._collector_event(enc, kind)
        elif enc.archetype == A_DRIVER:
            self._driver_event(enc, kind)
        elif enc.archetype == A_ASTRONOMER:
            self._astronomer_event(enc, kind)

    # Travel and location actions ---------------------------------------

    def _travel(self, action: str) -> None:
        costs = {
            "walk main road": 8,
            "walk scenic trail": 10,
            "take bus": 3,
            "hitch safe": 4,
            "hitch risky": 3,
        }

        if action == "take bus":
            self.cash -= 1
        if action == "walk main road":
            self._add_tag("slow_route")
        if action == "hitch risky":
            self._route_risk += 2
            self._add_tag("took_risky_ride")
        if action == "walk scenic trail":
            self._add_tag("took_scenic_way")

        self._last_travel_action = action
        self._spend_energy(costs[action])
        previous = self._current_location().name
        self._advance_route()
        current = self._current_location().name
        prev_name = self._loc_name(previous)
        cur_name = self._loc_name(current)

        if action == "hitch risky":
            self._feedback(
                f"这趟快车把你们带到{cur_name}，但支路把每条背带都蹭满了砂砾。",
                f"The fast ride carries you to {current}, but the side road leaves grit in every strap.",
            )
        elif action == "walk scenic trail":
            self._feedback(
                f"风景小径很耗体力，把 {self.traveler_name} 从{prev_name}带到{cur_name}。",
                f"The scenic trail costs effort and brings {self.traveler_name} from {previous} to {current}.",
            )
        elif action == "take bus":
            self._feedback(
                f"本地巴士咳喘着上坡，把 {self.traveler_name} 放在{cur_name}附近。",
                f"The local bus coughs uphill and drops {self.traveler_name} near {current}.",
            )
        elif action == "hitch safe":
            self._feedback(
                f"有告示的接驳车安全地把你们从{prev_name}送到{cur_name}。",
                f"A posted shuttle ride carries you safely from {previous} to {current}.",
            )
        else:
            self._feedback(
                f"主路脚下稳定，把你们从{prev_name}带到{cur_name}。",
                f"The main road is steady underfoot and leads from {previous} to {current}.",
            )

    def _advance_route(self) -> None:
        if self._route_index < len(self._locations) - 1:
            self._route_index += 1
        self._sync_distance_to_location()

    def _sync_distance_to_location(self) -> None:
        if self._location_distances and self._route_index < len(self._location_distances):
            self.distance_to_observatory = self._location_distances[self._route_index]
        elif self._at_observatory():
            self.distance_to_observatory = 0

    def _visit_landmark(self) -> None:
        self._add_tag("saw_landmark")
        token = self._item_alias["token"]
        if token not in self.items:
            self.items.append(token)
            self._feedback(
                f"这个停靠点起初像是没什么用，随后 {self.traveler_name} 从观景栏边收起一件{self._item_name(token)}。",
                f"The stop seems useless at first, then {self.traveler_name} pockets a {token} from the lookout rail.",
            )
        else:
            self._feedback(
                "这处眺望点在记忆里变得鲜明而奇特，足够之后讲给别人听。",
                "The lookout fixes itself in memory, bright and strange enough to retell later.",
            )

    # Encounter evaluators ----------------------------------------------

    def _mechanic_event(self, enc: EncounterState, kind: str) -> None:
        if kind in {"ask ride", "repair gear", "ask route"} and enc.first_action == kind:
            enc.marks["direct_first"] = True
            self._feedback(
                f"{enc.name} 说了几个路名，但手仍忙着同一个顽固部件。",
                f"{enc.name} gives a few road names, but their hands stay busy with the same stubborn part.",
            )
            return

        if kind in {"offer help", "inspect vehicle"}:
            if self._has_recent_tag("took_risky_ride", 3):
                enc.marks["rattled"] = True
                self._feedback(
                    f"{enc.name} 注意到新沾的尘土，只把面板拧紧，没有再邀你多聊。",
                    f"{enc.name} notices the fresh dust and tightens the panel without inviting more conversation.",
                )
            else:
                enc.marks["small_task"] = True
                self._add_tag("observed_first")
                self._feedback(
                    f"你没有急着讨人情，而是稳稳扶住灯，{enc.name} 的肩膀放松了些。",
                    f"{enc.name}'s shoulders loosen once you hold the lamp steady instead of rushing the favor.",
                )
            return

        if kind in {"ask ride", "ask route", "repair gear"}:
            if enc.marks.get("small_task") and not enc.marks.get("direct_first"):
                self._mark_success(A_MECHANIC)
                kit = self._item_alias["repair_kit"]
                if kit not in self.items:
                    self.items.append(kit)
                self._feedback(
                    f"{enc.name} 补好一处松动接头，然后指出一条之后能接上山脊的服务道路。",
                    f"{enc.name} patches a loose fitting, then points out a service road that rejoins the ridge later.",
                )
            else:
                self._feedback(
                    f"{enc.name} 朝主路点点头，算是帮忙，但还没准备停下手头活。",
                    f"{enc.name} nods toward the main road, helpful but not ready to stop the work.",
                )
            return

        self._feedback(
            f"{enc.name} 继续修理，像是更听行动而不是言辞。",
            f"{enc.name} stays with the repair, listening more to actions than talk.",
        )

    def _ranger_event(self, enc: EncounterState, kind: str) -> None:
        if kind in {"ask weather", "ask trail"}:
            if self.energy < 45:
                self._feedback(
                    f"{enc.name} 看了看你发抖的手，先指向休息棚。",
                    f"{enc.name} looks at your shaking hands and points first toward the rest shelter.",
                )
            else:
                enc.marks["asked_trail"] = True
                self._add_tag("asked_trail")
                self._feedback(
                    f"{enc.name} 说起云缝、湿石头，以及林线上方一条慢一些的横坡路。",
                    f"{enc.name} describes the cloud break, the wet stones, and one slow shelf path above the trees.",
                )
            return

        if kind == "ask shortcut":
            if self.energy < 45:
                self._feedback(
                    f"{enc.name} 先观察你的呼吸，在提任何高处路径前标出休息棚。",
                    f"{enc.name} studies your breathing and marks the shelter before any upper path.",
                )
                return
            if not enc.marks.get("asked_trail"):
                self._feedback(
                    f"{enc.name} 先谈天气和落脚点，没有说出那条窄路的名字。",
                    f"{enc.name} answers with weather and footing first, leaving the narrow path unnamed.",
                )
                return
            if self._last_travel_action == "hitch risky" or self._has_recent_tag("took_risky_ride", 3):
                self._feedback(
                    f"{enc.name} 把登记簿合到一半，似乎不太信任支路带来的尘土。",
                    f"{enc.name} closes the register halfway, unconvinced by the dust from the side road.",
                )
                return
            if not (self._has_tag("slow_route") or self._has_tag("conserved_energy")):
                self._feedback(
                    f"{enc.name} 描出那处安全弯道，然后等你认真对待节奏。",
                    f"{enc.name} traces the safe bend, then waits for you to take the pace seriously.",
                )
                return
            self._mark_success(A_RANGER)
            self._feedback(
                f"{enc.name} 标出一条看似很慢的横坡路，让之后的高处道路清楚了许多。",
                f"{enc.name} marks a slow-looking shelf road that makes the upper route much clearer.",
            )
            return

        if kind == "ask route":
            self._feedback(
                f"{enc.name} 指出公共山径，并提醒你把水放在手边。",
                f"{enc.name} points out the public trail and reminds you to keep water close.",
            )
            return

        self._feedback(
            f"路风变向时，{enc.name} 仍在看天。",
            f"{enc.name} keeps watching the sky as the road wind shifts.",
        )

    def _hiker_event(self, enc: EncounterState, kind: str) -> None:
        if kind == "share supply":
            if self.supplies > 0:
                self.supplies -= 1
                enc.marks["paid_cost"] = True
                self._add_tag("shared_supplies")
                self._feedback(
                    f"{enc.name} 先把食物在长凳上分回一半，才收下这份补给。",
                    f"{enc.name} accepts the food only after splitting it back across the bench.",
                )
                if enc.marks.get("listened"):
                    self._hiker_success(enc)
            else:
                self._feedback(
                    "背包里眼下没有多余东西可分享。",
                    "The pack has nothing spare to share right now.",
                )
            return

        if kind == "trade cash":
            if self.cash > 0:
                self.cash -= 1
                enc.marks["paid_cost"] = True
                self._feedback(
                    f"{enc.name} 收下给下一个补给箱的零钱，把地图挪到你们之间。",
                    f"{enc.name} pockets the fare for the next shelter box and shifts the map between you.",
                )
                if enc.marks.get("listened"):
                    self._hiker_success(enc)
            else:
                self._feedback(
                    "已经没有零钱能投给补给箱了。",
                    "There is no loose cash left for the shelter box.",
                )
            return

        if kind == "listen":
            enc.marks["listened"] = True
            if enc.marks.get("paid_cost"):
                self._hiker_success(enc)
            else:
                self._feedback(
                    f"{enc.name} 慢慢讲起路上的那个弯，像是在等你是否愿意一起停一停。",
                    f"{enc.name} talks through the bend in the road, waiting to see whether the pause is shared.",
                )
            return

        if kind == "ask item":
            if not enc.marks.get("common_item"):
                enc.marks["common_item"] = True
                self.supplies = min(5, self.supplies + 1)
                self._feedback(
                    f"{enc.name} 给出一条普通燕麦棒，实用，但没有特别意味。",
                    f"{enc.name} offers a plain oat bar, useful but with no special ceremony.",
                )
            else:
                self._feedback(
                    f"{enc.name} 已经把容易给的东西分过了。",
                    f"{enc.name} has already shared the easy thing.",
                )
            return

        if kind == "ask route":
            self._feedback(
                f"{enc.name} 指向多数旅人继续前进的普通弯道。",
                f"{enc.name} points to the ordinary bend where most travelers continue.",
            )
            return

        self._feedback(
            f"{enc.name} 等着，耐心像走惯长路的人。",
            f"{enc.name} waits, patient as a person used to long roads.",
        )

    def _hiker_success(self, enc: EncounterState) -> None:
        if A_HIKER in self._protocol_successes:
            self._feedback(
                f"{enc.name} 笑着又点了点同一个标记弯道。",
                f"{enc.name} taps the same marked bend with a knowing grin.",
            )
            return
        self._mark_success(A_HIKER)
        thermos = self._item_alias["thermos"]
        clue = self._item_alias["map_clue"]
        if thermos not in self.items:
            self.items.append(thermos)
        if clue not in self.items:
            self.items.append(clue)
        self._feedback(
            f"那段小小交换沉下来之后，{enc.name} 在你的地图上标出一个弯。",
            f"{enc.name} marks a bend in your map after the small exchange has had time to settle.",
        )

    def _collector_event(self, enc: EncounterState, kind: str) -> None:
        if kind == "tell story":
            if self._can_impress_collector():
                self._collector_success(enc)
            else:
                self._feedback(
                    f"{enc.name} 喜欢这段路上故事，但故事中心还缺一个足够奇特的地点。",
                    f"{enc.name} enjoys the road story, but it has no strange place at its center.",
                )
            return

        if kind == "listen":
            self._feedback(
                f"{enc.name} 问起奇怪停靠点、小标识，以及当时看似无用的东西。",
                f"{enc.name} asks about odd stops, small signs, and things that seemed useless at the time.",
            )
            return

        if kind == "ask route":
            self._feedback(
                f"{enc.name} 愉快地讲了主路那些旧名字。",
                f"{enc.name} gives a pleasant description of the main road's old names.",
            )
            return

        self._feedback(
            f"{enc.name} 等着听一个地点、一件信物，或一段带着尘土的故事。",
            f"{enc.name} waits for a place, a token, or a story with dust on it.",
        )

    def _collector_success(self, enc: EncounterState) -> None:
        if A_COLLECTOR in self._protocol_successes:
            self._feedback(
                f"{enc.name} 已经把那条线索折进你的地图里了。",
                f"{enc.name} has already folded the clue into your map.",
            )
            return
        self._mark_success(A_COLLECTOR)
        clue = self._item_alias["map_clue"]
        if clue not in self.items:
            self.items.append(clue)
        self._feedback(
            f"{enc.name} 把那处地标变成一道暗记，让高处道路不再那么空白。",
            f"{enc.name} turns the landmark into a coded mark that makes the upper road less blank.",
        )

    def _driver_event(self, enc: EncounterState, kind: str) -> None:
        if kind == "refuse offer":
            enc.marks["refused"] = True
            self._add_tag("refused_shortcut")
            self._feedback(
                f"{enc.name} 的笑容多停了一秒，随后发动机又落回怠速。",
                f"{enc.name}'s smile holds for a second too long, then the engine settles back to idle.",
            )
            return

        if kind == "question detail":
            if enc.marks.get("refused") or enc.first_action == "question detail":
                enc.marks["verified"] = True
                self._feedback(
                    f"{enc.name} 终于说出那座桥、锁着的门，以及道路在哪里接回山脊。",
                    f"{enc.name} finally names the bridge, the locked gate, and where the road rejoins the ridge.",
                )
            else:
                self._feedback(
                    f"{enc.name} 答得很顺，但那条捷径听起来仍像排练过。",
                    f"{enc.name} answers smoothly, but the shortcut still sounds rehearsed.",
                )
            return

        if kind == "accept offer":
            if enc.marks.get("verified"):
                self._mark_success(A_DRIVER)
                self._advance_route()
                self._feedback(
                    "核过细节的车走了说出的那座桥，把你们送到山脊更高处。",
                    "The verified ride takes the named bridge and leaves you higher on the ridge.",
                )
            else:
                self._false_help_flags.add("driver_loop")
                self._route_risk += 3
                self._add_tag("took_risky_ride")
                self._feedback(
                    "这趟车起初显得省事，但道路随后拐进漫长的碎石绕路。",
                    "The ride seems convenient at first, but the road bends away into a long gravel loop.",
                )
            return

        if kind == "ask route":
            self._feedback(
                f"普通道路还没被提起，{enc.name} 就先说出了捷径。",
                f"{enc.name} gives the shortcut before the ordinary road has been mentioned.",
            )
            return

        self._feedback(
            f"{enc.name} 让发动机保持热着，提议也显得轻而易举。",
            f"{enc.name} keeps the engine warm and the offer easy.",
        )

    def _astronomer_event(self, enc: EncounterState, kind: str) -> None:
        if kind == "listen":
            self._feedback(
                f"穹顶缝隙在头顶亮起时，{enc.name} 描述着彗星的路径。",
                f"{enc.name} describes the comet's path while the dome slit brightens overhead.",
            )
            return

        if kind == "ask route":
            self._feedback(
                f"第一批观测者聚拢时，{enc.name} 疲惫地点点头，让你们进去。",
                f"{enc.name} lets you through with a tired nod as the first watchers gather.",
            )
            self._finish()
            return

        self._feedback(
            f"{enc.name} 等着那条标记过的路线与天空对上。",
            f"{enc.name} waits for the marked route to meet the sky.",
        )

    def _show_item(self, enc: EncounterState, item: str) -> None:
        if enc.archetype == A_COLLECTOR and item == self._item_alias.get("token"):
            if self._can_impress_collector():
                self._collector_success(enc)
            else:
                self._feedback(
                    f"{enc.name} 翻看这件信物，觉得有趣，但还没有特别被打动。",
                    f"{enc.name} turns the token over, amused but not especially moved.",
                )
            return

        if enc.archetype == A_ASTRONOMER:
            if item == self._item_alias.get("map_clue"):
                if self.energy >= 25 and len(self._protocol_successes) >= 2:
                    self._final_alignment = True
                    self._feedback(
                        f"{enc.name} 按你的标记弯道校准穹顶，彗星干净地进入镜中。",
                        f"{enc.name} aligns the dome from your marked bend, and the comet enters the glass cleanly.",
                    )
                else:
                    self._feedback(
                        f"{enc.name} 用得上这个标记，只是最后一段爬升让你们所剩注意力不多。",
                        f"{enc.name} can use the mark, though the last climb has left little attention to spare.",
                    )
                self._finish()
            else:
                self._feedback(
                    f"{enc.name} 礼貌地看了看这件东西，又转回那张未完成的地图。",
                    f"{enc.name} studies the item politely, then looks back to the unfinished map.",
                )
            return

        if enc.archetype == A_MECHANIC and item == self._item_alias.get("repair_kit"):
            self._feedback(
                f"{enc.name} 认出这卷修理包，又检查了一遍背带。",
                f"{enc.name} recognizes the repair roll and checks the strap one more time.",
            )
            return

        self._feedback(
            f"{enc.name} 看看这件东西，然后等一个更有用的选择。",
            f"{enc.name} looks at the item, then waits for a more useful choice.",
        )

    # Scoring ------------------------------------------------------------

    def _finish(self) -> None:
        arrived = self._at_observatory()
        score = 0

        if arrived:
            score += 250
            time_left = max(0, self.MAX_TURNS - self._turn)
            if time_left > 0:
                score += min(180, 100 + time_left * 5)
        else:
            progress = 1.0 - (self.distance_to_observatory / max(1, self._starting_distance))
            score += int(max(0, min(160, progress * 160)))

        preservation = int(self.energy * 0.65 + self.supplies * 8 + self.cash * 4)
        if not arrived:
            preservation //= 2
        score += min(100, preservation)

        social_successes = self._protocol_successes - {A_ASTRONOMER}
        score += min(400, 80 * len(social_successes))

        knowledge = 0
        if self._has_tag("saw_landmark"):
            knowledge += 35
        if self._item_alias.get("map_clue") in self.items:
            knowledge += 45
        if A_COLLECTOR in self._protocol_successes:
            knowledge += 25
        score += min(100, knowledge)

        if arrived and self._final_alignment:
            score += 150

        score -= min(80, self._route_risk * 20)
        score -= min(100, len(self._false_help_flags) * 80)

        self._done = True
        self._final_score = max(0, min(1000, int(score)))

    # Rendering ----------------------------------------------------------

    def _render(self, opening: bool = False) -> str:
        loc = self._current_location()
        enc = self._current_encounter()
        lines = []
        if opening:
            lines.append(
                self._t(
                    "你正带一名旅人赶往山顶天文台，彗星观测窗口即将关闭。",
                    "You are guiding a traveler to a mountain observatory before the comet window closes.",
                )
            )
            lines.append(
                self._t(
                    "每回合选择前进方式或处理遭遇；管理体力、补给、时间和注意力。",
                    "Each turn, choose where to go or how to handle an encounter. Manage energy, supplies, time, and attention.",
                )
            )
            lines.append("")
        if self._lang == "zh":
            lines.append(
                f"旅人：{self.traveler_name} | 回合：{self._turn}/{self.MAX_TURNS} | 剩余时间：{max(0, self.MAX_TURNS - self._turn)}"
            )
            lines.append(
                f"距离：{self.distance_to_observatory} | 体力：{self.energy} | 补给：{self.supplies} | 现金：{self.cash}"
            )
            lines.append(f"物品：{self._items_text()}")
            lines.append(f"位置：{self._loc_name(loc.name)}")
        else:
            lines.append(
                f"Traveler: {self.traveler_name} | Turn: {self._turn}/{self.MAX_TURNS} | Time left: {max(0, self.MAX_TURNS - self._turn)}"
            )
            lines.append(
                f"Distance: {self.distance_to_observatory} | Energy: {self.energy} | Supplies: {self.supplies} | Cash: {self.cash}"
            )
            lines.append(f"Items: {self._items_text()}")
            lines.append(f"Location: {loc.name}")
        lines.append(self._text(self.weather))
        lines.append(self._text(loc.description))
        if enc is not None:
            if self._lang == "zh":
                lines.append(f"遭遇：{enc.name}，{self._role(enc.role)}，{self._text(enc.appearance)}。")
            else:
                lines.append(f"Encounter: {enc.name}, {enc.role}, {enc.appearance}.")
        if self._last_feedback:
            lines.append("")
            lines.extend(self._last_feedback)
        if self._done:
            lines.append("")
            if self._at_observatory():
                lines.append(self._t(
                    "彗星之夜开始时，旅程在穹顶前结束。",
                    "The journey ends at the dome as the comet night begins.",
                ))
            else:
                lines.append(self._t(
                    "彗星观测窗口关闭时，天文台仍在前方路上。",
                    "The comet window closes with the observatory still up the road.",
                ))
            lines.append(self._t(f"最终结果：{self._final_score}", f"Final result: {self._final_score}"))
        return "\n".join(lines)

    def _info(self) -> dict:
        return {
            "valid": self.get_valid_actions(),
            "turn": self._turn,
            "time_left": max(0, self.MAX_TURNS - self._turn),
            "distance_to_observatory": self.distance_to_observatory,
            "energy": self.energy,
            "supplies": self.supplies,
            "cash": self.cash,
            "items": list(self.items),
            "location": self.current_location,
            "encounter": self.current_encounter,
            "episode": self._episode,
        }

    # Helpers ------------------------------------------------------------

    def _valid_encounter_actions(self, enc: EncounterState) -> list[str]:
        if enc.archetype == A_MECHANIC:
            return ["observe person", "offer help", "inspect vehicle", "ask ride", "ask route", "repair gear", "leave"]
        if enc.archetype == A_RANGER:
            return ["observe person", "ask weather", "ask trail", "ask shortcut", "ask route", "leave"]
        if enc.archetype == A_HIKER:
            actions = ["observe person", "listen", "ask item", "ask route", "leave"]
            if self.supplies > 0:
                actions.append("share supply")
            if self.cash > 0:
                actions.append("trade cash")
            return actions
        if enc.archetype == A_COLLECTOR:
            return ["observe person", "listen", "tell story", "ask route", "leave"]
        if enc.archetype == A_DRIVER:
            return ["observe person", "refuse offer", "question detail", "accept offer", "ask route", "leave"]
        if enc.archetype == A_ASTRONOMER:
            return ["observe person", "listen", "ask route", "check map"]
        return []

    def _current_location(self) -> LocationState:
        return self._locations[self._route_index]

    def _current_encounter(self) -> EncounterState | None:
        loc = self._current_location()
        if loc.id in self._closed_locations:
            return None
        return loc.encounter

    def _at_observatory(self) -> bool:
        return bool(self._locations) and self._route_index == len(self._locations) - 1

    def _mark_success(self, archetype: str) -> None:
        self._protocol_successes.add(archetype)

    def _can_impress_collector(self) -> bool:
        return self._has_tag("saw_landmark") or self._item_alias.get("token") in self.items

    def _spend_energy(self, amount: int) -> None:
        if self.energy <= 0 and amount > 0:
            self._route_risk += 1
        self.energy = max(0, self.energy - amount)

    def _add_tag(self, tag: str) -> None:
        self._history_tags.append((tag, self._turn))
        self._history_tags = self._history_tags[-16:]

    def _has_tag(self, tag: str) -> bool:
        return any(t == tag for t, _ in self._history_tags)

    def _has_recent_tag(self, tag: str, window: int) -> bool:
        return any(t == tag and self._turn - turn <= window for t, turn in self._history_tags)

    def _dedupe(self, actions: list[str]) -> list[str]:
        seen = set()
        result = []
        for action in actions:
            if action not in seen:
                result.append(action)
                seen.add(action)
        return result
