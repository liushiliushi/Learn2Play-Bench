"""
Castaway (《孤岛余生》) — a hidden-rule-discovery survival benchmark.

A real island-survival adventure: a hidden connected map of ~7 locations,
gathering, crafting, hunger/HP management, day/night threats, creature
encounters, and an escape meta-puzzle (collect 3 escape components scattered
across the island, then craft a raft at the beach to escape).

All hidden laws (map, resource placement, food properties, recipes, dangers,
creature habits, escape chain) are generated from random.Random(seed) and are
*stable across reset()* — only discoverable through play. Reset replays the
episode without regenerating the world, so a learning agent can map the island
across rounds and converge on a successful escape.
"""

import random


# ── Static vocabulary ──────────────────────────────────────────────────────────

PLACE_POOL = ["海滩", "密林", "溪谷", "枯井", "洞穴", "礁岩", "沼泽", "废墟", "竹林"]
PLACE_EN = {
    "海滩": "Beach", "密林": "Jungle", "溪谷": "Ravine", "枯井": "Dry Well",
    "洞穴": "Cave", "礁岩": "Reef", "沼泽": "Swamp", "废墟": "Ruins", "竹林": "Bamboo Grove",
}
PLACE_EMOJI = {
    "海滩": "🏖️", "密林": "🌴", "溪谷": "🏞️", "枯井": "🕳️", "洞穴": "🦇",
    "礁岩": "🪨", "沼泽": "🐸", "废墟": "🏚️", "竹林": "🎋",
}

RESOURCES = ["木头", "燧石", "藤", "浆果", "菌菇", "贝类", "兽骨", "淡水"]
RES_EN = {
    "木头": "wood", "燧石": "flint", "藤": "vine", "浆果": "berry",
    "菌菇": "mushroom", "贝类": "shellfish", "兽骨": "bone", "淡水": "freshwater",
}
RES_EMOJI = {
    "木头": "🪵", "燧石": "🪨", "藤": "🌿", "浆果": "🫐",
    "菌菇": "🍄", "贝类": "🦪", "兽骨": "🦴", "淡水": "💧",
}

FOOD_ITEMS = ["浆果", "菌菇", "贝类", "淡水"]  # candidate edibles
# food property buckets:
#   "nourish"  : edible raw, +food
#   "poison"   : -HP if eaten raw or cooked
#   "cook"     : poison raw, nourish if cooked
#   "useless"  : no effect

CREATURE_POOL = ["野猪", "巨蟹", "毒蛇", "猿群", "海鸟"]
CREATURE_EN = {"野猪": "boar", "巨蟹": "crab", "毒蛇": "snake", "猿群": "apes", "海鸟": "seabird"}
CREATURE_EMOJI = {"野猪": "🐗", "巨蟹": "🦀", "毒蛇": "🐍", "猿群": "🐒", "海鸟": "🐦"}
# creature behaviour buckets:
#   "hostile" : attacks at night / on encounter; hunt to drive off (risky), flee safe
#   "neutral" : ignores you
#   "skittish": scare drives it off; hunting yields bone
#   "guard"   : guards an escape component; must be scared/fed/hunted to pass

DANGER_POOL = ["落石", "毒雾", "暗流", "陷坑", "蚊群"]
DANGER_EN = {"落石": "rockfall", "毒雾": "toxic mist", "暗流": "undertow", "陷坑": "pit", "蚊群": "mosquitoes"}
DANGER_EMOJI = {"落石": "🪨", "毒雾": "☠️", "暗流": "🌊", "陷坑": "🕳️", "蚊群": "🦟"}

# Escape components (the meta-puzzle): out of 4 raft-looking parts scattered on the
# island, only 3 (seed-fixed) are the *real* ones the raft needs. The 4th is a decoy
# that looks identical when picked up; using it (while missing a real part) makes the
# raft fail with a vague "something's wrong" message — never naming the culprit.
COMP_POOL = ["筏架", "船帆", "罗盘", "船舵"]
ESCAPE_COMPONENTS = COMP_POOL  # full pool of raft-like parts (3 real + 1 decoy per seed)
COMP_EN = {"筏架": "raft frame", "船帆": "sail", "罗盘": "compass", "船舵": "rudder"}
COMP_EMOJI = {"筏架": "🛶", "船帆": "⛵", "罗盘": "🧭", "船舵": "🎏"}

# Crafted goods + their hidden recipes (resource -> count). Generated per seed
# from these template "kinds"; the exact ingredient set is hidden.
# kinds: fire, torch, tool, raft


class CastawayGame:
    MAX_TURNS = 56               # cap; escape needs efficient routing (+ room to route
                                 # around the 2 hidden lethal traps once you know them)
    SEGMENTS_PER_DAY = 5          # 4 day + 1 night
    NIGHT_SEGMENTS = {4}         # only the last segment of the day is night
    GATHER_YIELD = 3             # units of each resource per gather
    HUNGER_DRAIN = 6             # food lost per segment

    # scoring constants
    PTS_SURVIVE_DAY = 6
    PTS_DISCOVER_PLACE = 4
    PTS_LEARN_RECIPE = 5
    PTS_COMPONENT = 18
    PTS_ESCAPE = 60

    def __init__(self, seed=None, lang="zh"):
        self.seed = seed
        self._lang = lang if lang in ("zh", "en") else "zh"
        self._rng_seed = seed
        self._generate_world(seed)
        self.reset()

    # ── world generation (hidden laws; stable across reset) ─────────────────────

    def _generate_world(self, seed):
        rng = random.Random(seed)

        # 1) choose 7 places, beach first
        n_places = 7
        pool = [p for p in PLACE_POOL if p != "海滩"]
        rng.shuffle(pool)
        self.places = ["海滩"] + pool[: n_places - 1]

        # 2) build a connected undirected graph, each node 2~3 edges
        self.adj = {p: set() for p in self.places}
        # spanning tree first (guarantees connectivity)
        order = self.places[:]
        for i in range(1, len(order)):
            j = rng.randrange(0, i)
            a, b = order[i], order[j]
            self.adj[a].add(b)
            self.adj[b].add(a)
        # add a few extra edges (respect degree <= 3)
        candidates = [(a, b) for a in self.places for b in self.places
                      if a < b and b not in self.adj[a]]
        rng.shuffle(candidates)
        for a, b in candidates:
            if len(self.adj[a]) < 3 and len(self.adj[b]) < 3:
                if rng.random() < 0.5:
                    self.adj[a].add(b)
                    self.adj[b].add(a)
        # ensure min degree 2 where possible
        for p in self.places:
            if len(self.adj[p]) < 2:
                others = [q for q in self.places if q != p and len(self.adj[q]) < 3
                          and q not in self.adj[p]]
                if others:
                    q = rng.choice(others)
                    self.adj[p].add(q)
                    self.adj[q].add(p)

        # 3) resources per place: 1~2 each
        res_pool = RESOURCES[:]
        self.place_resources = {}
        for p in self.places:
            k = rng.randint(1, 2)
            self.place_resources[p] = rng.sample(res_pool, k)
        # guarantee the basic survival resources exist somewhere
        for must in ["木头", "燧石", "藤", "淡水"]:
            if not any(must in self.place_resources[p] for p in self.places):
                p = rng.choice([q for q in self.places if q != "海滩"])
                self.place_resources[p].append(must)

        # 4) dangers: 2~3 places have a danger active at night / unprepared
        self.place_danger = {p: None for p in self.places}
        danger_places = rng.sample([p for p in self.places if p != "海滩"],
                                    rng.randint(2, 3))
        dpool = DANGER_POOL[:]
        rng.shuffle(dpool)
        for i, p in enumerate(danger_places):
            self.place_danger[p] = dpool[i % len(dpool)]

        # 5) creatures: place 2~3 creatures
        self.place_creature = {p: None for p in self.places}
        self.creature_behaviour = {}
        creature_places = rng.sample([p for p in self.places if p != "海滩"],
                                     rng.randint(2, 3))
        cpool = CREATURE_POOL[:]
        rng.shuffle(cpool)
        for i, p in enumerate(creature_places):
            c = cpool[i % len(cpool)]
            self.place_creature[p] = c
            self.creature_behaviour[c] = rng.choice(["hostile", "skittish", "neutral"])

        # 6) food properties (hidden). Ensure at least one "cook" (food-fire coupling),
        #    at least one nourish, at least one poison.
        props = ["nourish", "cook", "poison"]
        rest = ["nourish", "cook", "poison", "useless"]
        rng.shuffle(rest)
        assigned = props + [rng.choice(rest)]
        rng.shuffle(assigned)
        self.food_property = {}
        for item, prop in zip(FOOD_ITEMS, assigned):
            self.food_property[item] = prop
        # 淡水 should always be drinkable (nourish) for realism
        self.food_property["淡水"] = "nourish"
        # but make sure constraints still hold among the solid foods
        solids = ["浆果", "菌菇", "贝类"]
        sp = [self.food_property[s] for s in solids]
        if "cook" not in sp:
            self.food_property[rng.choice(solids)] = "cook"
        if "nourish" not in sp:
            self.food_property[rng.choice(solids)] = "nourish"
        if "poison" not in sp:
            self.food_property[rng.choice(solids)] = "poison"

        # 7) recipes (hidden ingredient sets). Use resources that exist on the island.
        #    NOTE: sort everything derived from sets so world generation is fully
        #    deterministic across processes (independent of PYTHONHASHSEED).
        avail = set()
        for p in self.places:
            avail.update(self.place_resources[p])
        avail = sorted(avail)

        def pick_recipe(size, must_have=None):
            must_have = list(must_have or [])
            size = min(size, len(avail))
            chosen = list(must_have)
            remaining = [r for r in avail if r not in chosen]
            rng.shuffle(remaining)
            for r in remaining:
                if len(chosen) >= size:
                    break
                chosen.append(r)
            # counts 1~2 each (deterministic order)
            return {r: rng.randint(1, 2) for r in chosen}

        self.recipes = {
            "火堆": pick_recipe(2, must_have=["木头", "燧石"]),   # fire (camp)
            "火把": pick_recipe(2, must_have=["木头"]),            # torch (night safety while moving)
            "工具": pick_recipe(2, must_have=["燧石"]),            # stone tool (needed to gather guarded components / hunt)
        }

        # 8) escape chain: scatter ALL 4 raft-like parts on 4 distinct non-beach places,
        #    but only 3 (seed-fixed) are REAL. The 4th is a decoy that looks identical
        #    when picked up; the raft only accepts the 3 real ones. Players can't tell
        #    real from decoy by exploring/looking — only by failing craft_raft and
        #    narrowing it down across episodes.
        comps = COMP_POOL[:]
        rng.shuffle(comps)
        self.decoy_component = comps[0]
        self.real_components = sorted(comps[1:])  # the 3 genuine parts (deterministic)

        non_beach = [p for p in self.places if p != "海滩"]
        rng.shuffle(non_beach)
        # place all 4 parts (need >=4 non-beach places; we always have 6)
        comp_places = non_beach[:len(COMP_POOL)]
        self.component_place = {}
        for comp, p in zip(COMP_POOL, comp_places):
            self.component_place[comp] = p
        # some REAL components guarded: a creature on that place becomes a "guard"
        self.component_guard = {}
        for comp, p in self.component_place.items():
            if comp in self.real_components and self.place_creature.get(p) is not None \
                    and rng.random() < 0.6:
                guard = self.place_creature[p]
                self.creature_behaviour[guard] = "guard"
                self.component_guard[comp] = guard
            else:
                self.component_guard[comp] = None

        # raft recipe: needs the 3 REAL components + some material, possibly a tool
        self.raft_recipe = {c: 1 for c in self.real_components}
        self.raft_recipe["藤"] = 2  # lashing
        self.raft_needs_tool = True

        # which component each place yields (reverse map)
        self.place_component = {v: k for k, v in self.component_place.items()}

        # craft raft only at beach
        self.raft_place = "海滩"

        # 9) HIDDEN LETHAL TRAPS (the cross-episode learning signal). Pick 2 distinct
        #    (place, kind) hazards that explore / the map / action labels NEVER reveal.
        #    You only learn them by getting killed/maimed once and avoiding next episode.
        #    kinds:
        #      "night_ambush" : a creature here (shown as harmless 'neutral' by explore)
        #                       is secretly a night ambusher — spending a NIGHT segment
        #                       at this place is lethal, even with fire AND torch. Driving
        #                       the creature off (scare/feed/hunt) removes the ambush.
        #      "night_place"  : the place ITSELF is lethal at night (riptide cove, sinkhole
        #                       fog, etc.) — spending a NIGHT segment here is near-lethal
        #                       even with fire AND torch. No creature involved.
        #      "collapse"     : gathering here triggers a hidden cave-in / gas pocket —
        #                       a massive, unforeseeable HP hit on the gather action.
        #    We always try to place 2 DISTINCT lethal traps. Avoidable by knowledge:
        #    you can route around a night spot, and skip gathering at a collapse spot
        #    (real components are taken by `gather` too, so a collapse never sits on a
        #    REAL component site — see filtering below).
        self.hidden_traps = {}  # place -> kind
        real_comp_places = {self.component_place[c] for c in self.real_components}

        # Essential resources (anything a recipe needs, plus survival staples). A trap
        # must never sit on the SOLE source of one — otherwise a knowing player would be
        # FORCED to gather/linger there, making the trap unavoidable. This keeps every
        # trap fully avoidable-with-knowledge (the cross-episode learning property).
        essential = set()
        for rec in (self.recipes["火堆"], self.recipes["火把"],
                    self.recipes["工具"], self.raft_recipe):
            for r in rec:
                if r not in COMP_POOL:
                    essential.add(r)
        essential.update(["木头", "燧石", "藤", "淡水"])

        def would_strand_essential(place):
            """True if trapping `place` would leave some essential resource with NO
            trap-free source (counting traps already placed). Such a place must never be
            trapped, or a knowing player would be FORCED to gather at a trap → the trap
            stops being avoidable (and the oracle would die)."""
            for r in self.place_resources.get(place, []):
                if r not in essential:
                    continue
                trap_free = [q for q in self.places
                             if r in self.place_resources.get(q, [])
                             and q != place
                             and q not in self.hidden_traps]
                if not trap_free:
                    return True
            return False

        # A night trap must NOT sit on a corridor (cut-vertex) that the player is forced
        # to cross to reach a real-component site or the beach base. Otherwise an
        # unavoidable transit could land on a deadly night with no detour — unwinnable
        # even with full knowledge. (Day transit is fine; the risk is forced night
        # crossings on tight maps, so we just forbid trapping the sole corridor.)
        def reachable_without(blocked, src, targets):
            seen = {src}
            stack = [src]
            while stack:
                u = stack.pop()
                for v in self.adj[u]:
                    if v == blocked or v in seen:
                        continue
                    seen.add(v)
                    stack.append(v)
            return all(t in seen for t in targets)

        must_reach = set(real_comp_places) | {"海滩"}

        def is_forced_corridor(place):
            # removing `place` must still leave every real-component site + beach
            # reachable from the beach.
            others = must_reach - {place}
            return not reachable_without(place, "海滩", others)

        # --- trap 1: a NIGHT trap (ambush if a harmless-looking neutral creature is
        #     available, else a place-based night hazard). Prefer non-real-component
        #     spots so the player isn't forced to overnight there. Never on a sole
        #     essential source, and never on a forced corridor.
        guarded_places = {self.component_place[c] for c in self.real_components
                          if self.component_guard.get(c)}
        ambush_cands = sorted(
            p for p in self.places
            if p != "海滩"
            and self.place_creature.get(p) is not None
            and self.creature_behaviour.get(self.place_creature[p]) == "neutral"
            and not would_strand_essential(p)
            and not is_forced_corridor(p)
        )
        night_place_cands = sorted(
            p for p in self.places
            if p != "海滩" and self.place_creature.get(p) is None
            and not would_strand_essential(p)
            and not is_forced_corridor(p)
        )
        night_trap_place = None
        # An AMBUSH may sit on a real-component site (the player can scare the creature
        # off, which removes the ambush, then take the component safely). A place-based
        # NIGHT trap (no creature to remove) must NOT sit on a real-component site — the
        # player is forced to visit that site, so a forced overnight there would be a
        # guaranteed death the player could never route around.
        amb_pref = ambush_cands
        np_pref = [p for p in night_place_cands if p not in real_comp_places]
        if amb_pref and (not np_pref or rng.random() < 0.5):
            night_trap_place = rng.choice(amb_pref)
            self.hidden_traps[night_trap_place] = "night_ambush"
        elif np_pref:
            night_trap_place = rng.choice(np_pref)
            self.hidden_traps[night_trap_place] = "night_place"
        elif amb_pref:
            night_trap_place = rng.choice(amb_pref)
            self.hidden_traps[night_trap_place] = "night_ambush"

        # --- trap 2 (and a fallback 2nd if no night trap landed): a COLLAPSE trap on a
        #     place with gatherable resources — never a REAL-component site (else the
        #     player can't take that component), never the night-trap spot, never the
        #     sole source of an essential resource. Stays fully AVOIDABLE with knowledge.
        #     We always aim for 2 distinct lethal traps total; if no night trap could be
        #     placed (dense maps), we place a SECOND collapse so the seed still teaches
        #     two avoid-this-or-die lessons.
        want_collapses = 2 if night_trap_place is None else 1
        for _ in range(want_collapses):
            collapse_cands = sorted(
                p for p in self.places
                if p != "海滩"
                and self.place_resources.get(p)
                and p not in self.hidden_traps
                and p not in real_comp_places
                and not would_strand_essential(p)
            )
            if not collapse_cands:
                break
            nice = [p for p in collapse_cands if self.place_danger.get(p) is None]
            pick_from = nice if nice else collapse_cands
            self.hidden_traps[rng.choice(pick_from)] = "collapse"
        self._collapse_sprung = set()  # places whose collapse already fired this episode

    # ── episode reset (does NOT regenerate world) ───────────────────────────────

    def reset(self):
        self.hp = 100
        self.food = 100
        self.turn_count = 0
        self.segment = 0          # 0..4 within a day
        self.day = 1
        self.location = "海滩"
        self.score = 0
        self.done = False
        self.escaped = False

        self.inventory = {}       # item -> count
        self.discovered = {"海滩"}                # places seen
        self.explored = set()                     # places explored (resources known)
        self.known_edges = {"海滩": set()}        # adjacency known to player
        self.learned_recipes = set()              # crafted-good names learned
        self.has_fire_here = set()                # places with an active campfire
        self._scared_creatures = set()            # creatures driven off (per place, this episode)
        self._collapse_sprung = set()             # collapse traps already fired this episode
        self._msg = []

        self._reveal_edges("海滩")  # neighbours of beach are visible as exits (names hidden until explored? no—exits shown)
        obs = self._render(self._intro())
        return obs, {}

    def _reveal_edges(self, place):
        self.known_edges.setdefault(place, set())
        for nb in self.adj[place]:
            self.known_edges[place].add(nb)
            self.discovered.add(nb)

    # ── helpers ─────────────────────────────────────────────────────────────────

    def _t(self, zh, en):
        return en if self._lang == "en" else zh

    def name_place(self, p):
        if self._lang == "en":
            return PLACE_EN.get(p, p)
        return p

    def name_res(self, r):
        if self._lang == "en":
            return RES_EN.get(r, r)
        return r

    def name_creature(self, c):
        if self._lang == "en":
            return CREATURE_EN.get(c, c)
        return c

    def nearby_creature_text(self, c):
        if self._lang == "en":
            if c == "猿群":
                return "A troop of apes is nearby."
            return f"A {self.name_creature(c)} is nearby."
        if c == "猿群":
            return "有一群猿猴在附近。"
        return f"有一只{self.name_creature(c)}在附近。"

    def guarding_creature_text(self, c):
        if self._lang == "en":
            if c == "猿群":
                return "A troop of apes guards this spot; you can't reach the item."
            return f"A {self.name_creature(c)} guards this spot; you can't reach the item."
        if c == "猿群":
            return "一群猿猴守着这里，你无法靠近取物。"
        return f"一只{self.name_creature(c)}守着这里，你无法靠近取物。"

    def name_danger(self, d):
        if self._lang == "en":
            return DANGER_EN.get(d, d)
        return d

    def name_comp(self, c):
        if self._lang == "en":
            return COMP_EN.get(c, c)
        return c

    def _is_night(self):
        return self.segment in self.NIGHT_SEGMENTS

    def _has_torch(self):
        return self.inventory.get("火把", 0) > 0

    def _has_tool(self):
        return self.inventory.get("工具", 0) > 0

    def _campfire_here(self):
        return self.location in self.has_fire_here

    # ── action set ──────────────────────────────────────────────────────────────

    def get_all_actions(self):
        acts = ["explore", "gather", "rest", "make_fire", "status"]
        for nb in self.places:
            acts.append(f"go_{nb}")
        for item in FOOD_ITEMS:
            acts.append(f"eat_{item}")
            acts.append(f"cook_{item}")
        for good in ["火把", "工具"]:
            acts.append(f"craft_{good}")
        acts.append("craft_raft")
        for verb in ["hunt", "flee", "scare", "feed"]:
            acts.append(verb)
        return acts

    def get_valid_actions(self):
        if self.done:
            return ["status"]
        acts = ["status", "explore", "rest"]

        # movement: only known adjacent places
        for nb in sorted(self.known_edges.get(self.location, set())):
            acts.append(f"go_{nb}")

        # gather if explored & has resources (or component)
        if self.location in self.explored:
            if self.place_resources.get(self.location) or self.location in self.place_component:
                acts.append("gather")

        # fire
        acts.append("make_fire")

        # eat/cook for items in inventory
        for item in FOOD_ITEMS:
            if self.inventory.get(item, 0) > 0:
                acts.append(f"eat_{item}")
                if self._campfire_here():
                    acts.append(f"cook_{item}")

        # craft torch / tool always attemptable (engine judges success)
        acts.append("craft_火把")
        acts.append("craft_工具")
        # raft only at beach
        if self.location == self.raft_place:
            acts.append("craft_raft")

        # creature interactions if a (non-scared) creature is present here
        c = self.place_creature.get(self.location)
        if c is not None and (self.location, c) not in self._scared_creatures \
                and self.location in self.explored:
            acts += ["hunt", "flee", "scare", "feed"]

        # dedupe, keep order
        seen = set()
        out = []
        for a in acts:
            if a not in seen:
                seen.add(a)
                out.append(a)
        return out

    def get_action_label(self, action):
        e = self._lang == "en"
        if action == "status":
            return self._t("📋查看状态", "📋status")
        if action == "explore":
            return self._t("🔍探查", "🔍explore")
        if action == "gather":
            return self._t("⛏️采集", "⛏️gather")
        if action == "rest":
            return self._t("😴休息", "😴rest")
        if action == "make_fire":
            return self._t("🔥生火", "🔥make fire")
        if action == "craft_raft":
            return self._t("🛶造筏逃生", "🛶craft raft (escape)")
        if action.startswith("go_"):
            p = action[3:]
            return self._t(f"🧭去{p}", f"🧭go {PLACE_EN.get(p,p)}") + PLACE_EMOJI.get(p, "")
        if action.startswith("eat_"):
            it = action[4:]
            return self._t(f"🍽️生吃{it}", f"🍽️eat {RES_EN.get(it,it)}")
        if action.startswith("cook_"):
            it = action[5:]
            return self._t(f"🍳烤{it}", f"🍳cook {RES_EN.get(it,it)}")
        if action.startswith("craft_"):
            g = action[6:]
            gname = {"火把": "torch", "工具": "tool"}.get(g, g)
            return self._t(f"🔨造{g}", f"🔨craft {gname}")
        labels = {
            "hunt": self._t("🏹猎杀", "🏹hunt"),
            "flee": self._t("🏃逃开", "🏃flee"),
            "scare": self._t("📢驱赶", "📢scare"),
            "feed": self._t("🍖喂食", "🍖feed"),
        }
        return labels.get(action, action)

    # ── step ────────────────────────────────────────────────────────────────────

    def step(self, action):
        if self.done:
            return self._render(self._t("游戏已结束。", "Game already over.")), 0, True, self._info()

        action = (action or "").strip()
        self._msg = []
        prev_score = self.score

        if action == "status":
            return self._render(""), 0, self.done, self._info()

        valid = self.get_valid_actions()
        if action not in valid:
            label = self.get_action_label(action)   # 用中文名而非英文 token，避免中英夹杂
            self._msg.append(self._t(f"现在无法「{label}」。", f"Cannot do '{label}' now."))
            return self._render(""), 0, self.done, self._info()

        consume_segment = True

        # dispatch
        if action == "explore":
            self._do_explore()
        elif action == "gather":
            self._do_gather()
        elif action == "rest":
            self._do_rest()
        elif action == "make_fire":
            consume_segment = self._do_make_fire()
        elif action.startswith("go_"):
            self._do_move(action[3:])
        elif action.startswith("eat_"):
            self._do_eat(action[4:], cooked=False)
        elif action.startswith("cook_"):
            self._do_eat(action[5:], cooked=True)
        elif action == "craft_raft":
            consume_segment = self._do_craft_raft()
        elif action.startswith("craft_"):
            consume_segment = self._do_craft(action[6:])
        elif action in ("hunt", "flee", "scare", "feed"):
            self._do_creature(action)
        else:
            self._msg.append(self._t("无效行动。", "Invalid action."))
            consume_segment = False

        if not self.done and consume_segment:
            self._advance_time()

        reward = self.score - prev_score
        return self._render(""), reward, self.done, self._info()

    # ── action implementations ──────────────────────────────────────────────────

    def _do_explore(self):
        first = self.location not in self.explored
        self.explored.add(self.location)
        self._reveal_edges(self.location)
        loc = self.name_place(self.location)

        res = self.place_resources.get(self.location, [])
        if res:
            self._msg.append(self._t(
                f"你探查了{loc}，找到资源：{('、'.join(self.name_res(r) for r in res))}。",
                f"You explore {loc}. Resources here: {(', '.join(self.name_res(r) for r in res))}."))
        else:
            self._msg.append(self._t(f"{loc}没有可采集的资源。", f"{loc} has no gatherable resources."))

        comp = self.place_component.get(self.location)
        if comp and comp not in self.inventory:      # 已取走就别再提示「藏着东西」
            self._msg.append(self._t(
                f"你注意到这里似乎藏着可用的东西。",
                f"You notice something usable is hidden here."))

        d = self.place_danger.get(self.location)
        if d:
            self._msg.append(self._t(
                f"这里有危险迹象：{self.name_danger(d)}（夜里或无准备时尤其凶险）。",
                f"Signs of danger here: {self.name_danger(d)} (worse at night / unprepared)."))

        c = self.place_creature.get(self.location)
        if c and (self.location, c) not in self._scared_creatures:
            self._msg.append(self.nearby_creature_text(c))

        exits = sorted(self.known_edges.get(self.location, set()))
        self._msg.append(self._t(
            f"通往：{('、'.join(self.name_place(x) for x in exits))}。",
            f"Paths to: {(', '.join(self.name_place(x) for x in exits))}."))

        if first:
            self._msg.append(self._t("（首次探明此地 +%d）" % self.PTS_DISCOVER_PLACE,
                                     "(first survey of this place +%d)" % self.PTS_DISCOVER_PLACE))
            self.score += self.PTS_DISCOVER_PLACE

    def _do_gather(self):
        loc = self.name_place(self.location)
        got_any = False

        # HIDDEN COLLAPSE/GAS TRAP: disturbing this place by gathering triggers an
        # unforeseeable cave-in / gas pocket. Explore never warned of this. Fires once
        # per episode; brutal HP hit (can be lethal). Vague reason — no "danger sign".
        if self.hidden_traps.get(self.location) == "collapse" \
                and self.location not in self._collapse_sprung:
            self._collapse_sprung.add(self.location)
            self.hp = max(0, self.hp - 65)
            self._msg.append(self._t(
                f"你刚一动手翻找，{loc}毫无征兆地塌了下来，碎石与浊气将你吞没（HP -65）！",
                f"The moment you start digging, {loc} caves in without warning — rubble and "
                f"foul gas engulf you (HP -65)!"))
            if self.hp <= 0:
                self._die(self._t("你被埋在塌方之下。", "You are buried in the collapse."))
                return

        # component pickup (may be guarded / need tool)
        comp = self.place_component.get(self.location)
        if comp and comp not in self.inventory:
            guard = self.component_guard.get(comp)
            if guard and (self.location, guard) not in self._scared_creatures:
                self._msg.append(self.guarding_creature_text(guard))
            elif self.raft_needs_tool and not self._has_tool() and comp == "筏架":
                # the heavy frame needs a tool to free it
                self._msg.append(self._t(
                    "这里的大件物事卡得很死，徒手撬不动，似乎需要趁手的工具。",
                    "A bulky item is wedged tight; you can't pry it loose by hand — you need a tool."))
            else:
                self.inventory[comp] = 1
                got_any = True
                self._msg.append(self._t(
                    f"你取得了逃生组件：{self.name_comp(comp)}！（+{self.PTS_COMPONENT}）",
                    f"You secured an escape component: {self.name_comp(comp)}! (+{self.PTS_COMPONENT})"))
                self.score += self.PTS_COMPONENT

        res = self.place_resources.get(self.location, [])
        if res:
            for r in res:
                self.inventory[r] = self.inventory.get(r, 0) + self.GATHER_YIELD
            got_any = True
            self._msg.append(self._t(
                f"你在{loc}采到：{('、'.join(self.name_res(r) + '×' + str(self.GATHER_YIELD) for r in res))}。",
                f"You gather at {loc}: {(', '.join(self.name_res(r) + '×' + str(self.GATHER_YIELD) for r in res))}."))
        elif not comp:
            self._msg.append(self._t("这里没什么可采的。", "Nothing to gather here."))

        if not got_any and comp:
            pass  # message already given (guarded / need tool)

    def _do_rest(self):
        # resting by a campfire (or in daylight) recovers well; cold dark rest barely
        heal = 16 if (self._campfire_here() or not self._is_night()) else 4
        self.hp = min(100, self.hp + heal)
        self._msg.append(self._t(
            f"你休息了一段，恢复了一些体力（HP +{heal}）。",
            f"You rest a while and recover (HP +{heal})."))

    def _do_make_fire(self):
        if self._campfire_here():
            self._msg.append(self._t("这里已经有火堆了。", "There's already a fire here."))
            return False
        ok, missing = self._check_recipe(self.recipes["火堆"])
        if ok:
            self._consume_recipe(self.recipes["火堆"])
            self.has_fire_here.add(self.location)
            newly = "火堆" not in self.learned_recipes
            self.learned_recipes.add("火堆")
            self._msg.append(self._t("火堆燃起来了，这里成了安全的营地。",
                                     "A fire blazes up — this is now a safe camp."))
            if newly:
                self._msg.append(self._t(f"（学会了生火 +{self.PTS_LEARN_RECIPE}）",
                                         f"(learned to make fire +{self.PTS_LEARN_RECIPE})"))
                self.score += self.PTS_LEARN_RECIPE
            return True
        else:
            self._msg.append(self._t(
                "你尝试生火，但失败了——手头的材料不对。",
                "You try to make a fire but fail — wrong materials."))
            return True  # attempt costs a segment, but no resources consumed

    def _do_move(self, dest):
        if dest not in self.known_edges.get(self.location, set()):
            self._msg.append(self._t("那里没有可走的路。", "No known path there."))
            return
        self.location = dest
        self.discovered.add(dest)
        loc = self.name_place(dest)
        self._msg.append(self._t(f"你走到了{loc}。", f"You travel to {loc}."))
        if dest not in self.explored:
            self._msg.append(self._t("（这里还没探查过，试试「探查」）",
                                     "(unexplored — try 'explore')"))

    def _do_eat(self, item, cooked):
        if self.inventory.get(item, 0) <= 0:
            self._msg.append(self._t("你没有这个可吃。", "You don't have that to eat."))
            return
        if cooked and not self._campfire_here():
            self._msg.append(self._t("这里没有火，没法烤。", "No fire here to cook."))
            return
        self.inventory[item] -= 1
        if self.inventory[item] <= 0:
            del self.inventory[item]

        prop = self.food_property.get(item, "useless")
        nm = self.name_res(item)
        verb = self._t("烤熟的", "cooked ") if cooked else self._t("生", "raw ")

        if prop == "nourish":
            self.food = min(100, self.food + 30)
            self._msg.append(self._t(f"{verb}{nm}很可口，饱食度回升（+30）。",
                                     f"The {verb}{nm} is nourishing (food +30)."))
        elif prop == "poison":
            self.hp = max(0, self.hp - 25)
            self._msg.append(self._t(f"{verb}{nm}有毒！你一阵剧痛（HP -25）。",
                                     f"The {verb}{nm} is poisonous! (HP -25)."))
        elif prop == "cook":
            if cooked:
                self.food = min(100, self.food + 30)
                self._msg.append(self._t(f"烤熟的{nm}安全又顶饱（+30）。",
                                         f"Cooked {nm} is safe and filling (food +30)."))
            else:
                self.hp = max(0, self.hp - 20)
                self._msg.append(self._t(f"生的{nm}让你上吐下泻（HP -20）……也许烤熟会不同？",
                                         f"Raw {nm} makes you violently ill (HP -20)... maybe cooking helps?"))
        else:  # useless
            self._msg.append(self._t(f"{verb}{nm}没什么营养，聊胜于无。",
                                     f"The {verb}{nm} is bland and useless."))
        if self.hp <= 0:
            self._die(self._t("你中毒不治。", "You succumb to poison."))

    def _do_craft(self, good):
        recipe = self.recipes.get(good)
        if recipe is None:
            self._msg.append(self._t("不知道怎么造这个。", "Unknown craft."))
            return False
        ok, missing = self._check_recipe(recipe)
        if ok:
            self._consume_recipe(recipe)
            self.inventory[good] = self.inventory.get(good, 0) + 1
            newly = good not in self.learned_recipes
            self.learned_recipes.add(good)
            gname = self.name_good(good)
            self._msg.append(self._t(f"你造出了{gname}。", f"You craft a {gname}."))
            if newly:
                self._msg.append(self._t(f"（学会了配方 +{self.PTS_LEARN_RECIPE}）",
                                         f"(learned a recipe +{self.PTS_LEARN_RECIPE})"))
                self.score += self.PTS_LEARN_RECIPE
            return True
        else:
            self._msg.append(self._t(
                f"你试着拼凑{self.name_good(good)}，但没成——配方不对。",
                f"You try to craft a {self.name_good(good)} but fail — wrong recipe."))
            return True

    def name_good(self, good):
        m = {"火堆": ("火堆", "campfire"), "火把": ("火把", "torch"),
             "工具": ("石器工具", "stone tool")}
        zh, en = m.get(good, (good, good))
        return en if self._lang == "en" else zh

    def _do_craft_raft(self):
        if self.location != self.raft_place:
            self._msg.append(self._t("只能在海滩造筏。", "You can only build the raft at the beach."))
            return False

        # Hidden 4-choose-3: the raft only holds together with the 3 REAL parts. The
        # decoy looks identical in the pack, so if a real part is missing we give a
        # VAGUE failure ("something's wrong") and never name which part is the dud —
        # the player must narrow it down across episodes.
        held_parts = [c for c in COMP_POOL if self.inventory.get(c, 0) > 0]
        missing_real = [c for c in self.real_components if self.inventory.get(c, 0) <= 0]
        ok, missing = self._check_recipe(self.raft_recipe)  # checks real comps + lashing
        need_tool = self.raft_needs_tool and not self._has_tool()

        if missing_real or not ok or need_tool:
            hints = []
            # Lashing material + tool are ordinary, learnable mechanics — name them.
            lash_missing = {r: c for r, c in missing.items() if r not in COMP_POOL}
            if lash_missing:
                hints.append(self._t("材料不足", "not enough materials"))
            if need_tool:
                hints.append(self._t("需要工具", "need a tool"))
            # Component situation: stay VAGUE. Three buckets, none naming the culprit.
            if missing_real:
                if len(held_parts) >= len(self.real_components):
                    # they brought "enough" parts but a wrong/decoy one is among them
                    hints.append(self._t(
                        "船筏勉强搭起又散了架，某个部件就是不对劲，可你看不出是哪个",
                        "the raft half-forms then falls apart — one part is just wrong, "
                        "though you can't tell which"))
                else:
                    hints.append(self._t("船筏的部件还不齐", "the raft is still missing parts"))
            self._msg.append(self._t(
                "筏子拼不起来：" + "、".join(hints) + "。",
                "The raft won't come together: " + "; ".join(hints) + "."))
            return True

        # success! (we have all 3 real parts + lashing + tool — a stray decoy in the
        # pack is simply left behind)
        self._consume_recipe(self.raft_recipe)
        self.escaped = True
        self.score += self.PTS_ESCAPE
        parts = "、".join(self.name_comp(c) for c in self.real_components)
        self._msg.append(self._t(
            f"你把{parts}和藤索捆成一艘逃生筏，乘浪离开了孤岛！",
            "You lash the right parts and vines into a raft and ride the waves off the island!"))
        self._win()
        return True

    def _do_creature(self, action):
        c = self.place_creature.get(self.location)
        if c is None or (self.location, c) in self._scared_creatures:
            self._msg.append(self._t("这里没有生物。", "No creature here."))
            return
        behaviour = self.creature_behaviour.get(c, "neutral")
        nm = self.name_creature(c)

        if action == "flee":
            self._msg.append(self._t(f"你避开了{nm}。", f"You back away from the {nm}."))
            return

        if action == "scare":
            if behaviour in ("skittish", "guard"):
                self._scared_creatures.add((self.location, c))
                self._msg.append(self._t(f"你大声驱赶，{nm}受惊逃走了！",
                                         f"You shout and the {nm} bolts away!"))
            elif behaviour == "neutral":
                self._msg.append(self._t(f"{nm}毫不在意你的叫喊。", f"The {nm} ignores your shouting."))
            else:  # hostile
                self.hp = max(0, self.hp - 12)
                self._msg.append(self._t(f"激怒了{nm}，它扑了上来（HP -12）！",
                                         f"You enrage the {nm} and it lunges (HP -12)!"))
                if self.hp <= 0:
                    self._die(self._t(f"你被{nm}咬死了。", f"The {nm} kills you."))
            return

        if action == "feed":
            if "浆果" in self.inventory or "贝类" in self.inventory:
                food_item = "浆果" if "浆果" in self.inventory else "贝类"
                self.inventory[food_item] -= 1
                if self.inventory[food_item] <= 0:
                    del self.inventory[food_item]
                if behaviour in ("guard", "neutral", "skittish"):
                    self._scared_creatures.add((self.location, c))
                    self._msg.append(self._t(f"你扔出食物，{nm}叼着走开了，让出了路。",
                                             f"You toss food; the {nm} takes it and wanders off, clearing the way."))
                else:  # hostile — feeding doesn't fully work
                    self._msg.append(self._t(f"{nm}吃了食物却仍盯着你。",
                                             f"The {nm} eats but keeps eyeing you."))
            else:
                self._msg.append(self._t("你没有食物可喂。", "You have nothing to feed it."))
            return

        if action == "hunt":
            if not self._has_tool():
                self.hp = max(0, self.hp - 18)
                self._msg.append(self._t(f"你赤手猎{nm}，反被所伤（HP -18）。",
                                         f"You hunt the {nm} bare-handed and get hurt (HP -18)."))
                if self.hp <= 0:
                    self._die(self._t(f"你被{nm}所杀。", f"The {nm} kills you."))
                return
            # with tool
            if behaviour == "hostile":
                self.hp = max(0, self.hp - 6)
                self._scared_creatures.add((self.location, c))
                self.inventory["兽骨"] = self.inventory.get("兽骨", 0) + 1
                self._msg.append(self._t(f"一番搏斗，你制服了{nm}，得到兽骨（HP -6）。",
                                         f"After a struggle you bring down the {nm} and get bone (HP -6)."))
            else:
                self._scared_creatures.add((self.location, c))
                self.inventory["兽骨"] = self.inventory.get("兽骨", 0) + 1
                self._msg.append(self._t(f"你用工具猎得{nm}，获得兽骨。",
                                         f"You hunt the {nm} with your tool and get bone."))
            if self.hp <= 0:
                self._die(self._t(f"你伤重不治。", "You die from your wounds."))
            return

    # ── recipe helpers ──────────────────────────────────────────────────────────

    def _check_recipe(self, recipe):
        missing = {}
        for r, n in recipe.items():
            have = self.inventory.get(r, 0)
            if have < n:
                missing[r] = n - have
        return (len(missing) == 0), missing

    def _consume_recipe(self, recipe):
        for r, n in recipe.items():
            self.inventory[r] = self.inventory.get(r, 0) - n
            if self.inventory[r] <= 0:
                del self.inventory[r]

    # ── time / survival ─────────────────────────────────────────────────────────

    def _advance_time(self):
        self.turn_count += 1
        prev_day = self.day

        # hunger drain
        self.food = max(0, self.food - self.HUNGER_DRAIN)

        self.segment += 1
        if self.segment >= self.SEGMENTS_PER_DAY:
            self.segment = 0
            self.day += 1

        # survived a new day boundary
        if self.day > prev_day and not self.done:
            self.score += self.PTS_SURVIVE_DAY
            self._msg.append(self._t(f"☀️ 你活过了第 {prev_day} 天（+{self.PTS_SURVIVE_DAY}）。",
                                     f"☀️ You survived day {prev_day} (+{self.PTS_SURVIVE_DAY})."))

        # starvation
        if self.food <= 0:
            self.hp = max(0, self.hp - 10)
            self._msg.append(self._t("🍽️ 你饿得发慌，体力流失（HP -10）。",
                                     "🍽️ Starving — you lose strength (HP -10)."))

        # night threat: unsafe if night and no campfire here and no torch
        if self._is_night():
            safe = self._campfire_here() or self._has_torch()
            c = self.place_creature.get(self.location)
            night_creature = (c is not None
                              and (self.location, c) not in self._scared_creatures
                              and self.creature_behaviour.get(c) in ("hostile", "guard"))
            danger = self.place_danger.get(self.location)
            if not safe:
                dmg = 0
                why = []
                dmg += 9
                why.append(self._t("夜里没有火光", "no firelight at night"))
                if night_creature:
                    dmg += 8
                    why.append(self._t(f"{self.name_creature(c)}夜袭", f"{self.name_creature(c)} attacks"))
                if danger:
                    dmg += 6
                    why.append(f"{self.name_danger(danger)}")
                self.hp = max(0, self.hp - dmg)
                self._msg.append(self._t(
                    f"🌙 黑夜降临，{('、'.join(why))}（HP -{dmg}）。",
                    f"🌙 Night falls — {('; '.join(why))} (HP -{dmg})."))
            else:
                # safe-ish, but raw danger may still nip if no torch and danger present
                if danger and not self._campfire_here() and not self._has_torch():
                    self.hp = max(0, self.hp - 6)
                    self._msg.append(self._t(f"夜里{self.name_danger(danger)}让你受了点伤（HP -6）。",
                                             f"The {self.name_danger(danger)} nicks you at night (HP -6)."))

            # HIDDEN NIGHT TRAPS (fire/torch give NO protection):
            trap = self.hidden_traps.get(self.location)
            amb_c = self.place_creature.get(self.location)
            if trap == "night_ambush" and amb_c is not None \
                    and (self.location, amb_c) not in self._scared_creatures:
                # a creature explore reported as harmless 'neutral' is a night ambusher.
                # Driving it off (so it's in _scared_creatures) removes the threat.
                self.hp = max(0, self.hp - 70)
                self._msg.append(self._t(
                    f"🌙 夜半，本以为温驯的{self.name_creature(amb_c)}骤然扑来，獠牙撕咬，火光毫无作用（HP -70）！",
                    f"🌙 In the dead of night the {self.name_creature(amb_c)} you took for "
                    f"harmless lunges in a savage ambush — the firelight does nothing (HP -70)!"))
            elif trap == "night_place":
                # the place itself turns deadly after dark (riptide / sinkhole fog).
                self.hp = max(0, self.hp - 70)
                self._msg.append(self._t(
                    f"🌙 入夜后，{self.name_place(self.location)}骤然变得凶险致命，火光根本压不住（HP -70）！",
                    f"🌙 After dark {self.name_place(self.location)} turns suddenly, lethally "
                    f"hostile — no fire can hold it back (HP -70)!"))

        if self.hp <= 0 and not self.done:
            self._die(self._t("你没能熬过这一夜。", "You did not survive the night."))
            return

        if self.turn_count >= self.MAX_TURNS and not self.done:
            self._msg.append(self._t("⏳ 时间耗尽，救援无望……", "⏳ Time runs out, no rescue comes..."))
            self.done = True

    def _die(self, reason):
        self.done = True
        self._msg.append("💀 " + reason)

    def _win(self):
        self.done = True

    # ── observation rendering ───────────────────────────────────────────────────

    def _intro(self):
        if self._lang == "en":
            return ("You wash ashore on an unknown island, the sole survivor. "
                    "Survive, learn the island, and find a way to escape.")
        return "你是一场海难的唯一幸存者，被冲上一座陌生孤岛。活下去，摸清这座岛，想办法逃出生天。"

    def _phase_str(self):
        if self._is_night():
            return self._t("🌙夜晚", "🌙Night")
        return self._t("☀️白天", "☀️Day")

    def _render(self, header):
        lines = []
        if header:
            lines.append(header)
        for m in self._msg:
            lines.append(m)
        lines.append("─" * 40)

        loc = self.name_place(self.location)
        seg = self.segment + 1
        lines.append(self._t(
            f"📍{loc}  {PLACE_EMOJI.get(self.location,'')}  | 第{self.day}天 第{seg}/5时段 {self._phase_str()}  | 回合{self.turn_count}/{self.MAX_TURNS}",
            f"📍{loc} {PLACE_EMOJI.get(self.location,'')} | Day {self.day} seg {seg}/5 {self._phase_str()} | turn {self.turn_count}/{self.MAX_TURNS}"))
        lines.append(self._t(
            f"❤️HP {self.hp}  🍖饱食 {self.food}  | 🏆得分 {self.score}",
            f"❤️HP {self.hp}  🍖food {self.food}  | 🏆score {self.score}"))

        # campfire / safety hint
        flags = []
        if self._campfire_here():
            flags.append(self._t("🔥这里有营火", "🔥campfire here"))
        if self._has_torch():
            flags.append(self._t("🔦持火把", "🔦have torch"))
        if self._has_tool():
            flags.append(self._t("🔧持工具", "🔧have tool"))
        if flags:
            lines.append("  ".join(flags))

        # inventory
        inv = self.inventory
        if inv:
            def disp(k):
                if k in COMP_EN:
                    return f"{COMP_EMOJI.get(k,'')}{self.name_comp(k)}×{inv[k]}"
                if k in ("火把", "工具", "火堆"):
                    return f"{self.name_good(k)}×{inv[k]}"
                return f"{RES_EMOJI.get(k,'')}{self.name_res(k)}×{inv[k]}"
            lines.append(self._t("🎒背包：", "🎒inventory: ") + "  ".join(disp(k) for k in inv))
        else:
            lines.append(self._t("🎒背包：空", "🎒inventory: empty"))

        # known exits
        exits = sorted(self.known_edges.get(self.location, set()))
        if exits:
            lines.append(self._t(
                "🧭出口：" + "、".join(self.name_place(x) for x in exits),
                "🧭exits: " + ", ".join(self.name_place(x) for x in exits)))

        if self.done:
            if self.escaped:
                lines.append("=" * 40)
                lines.append(self._t(f"🎉 你成功逃离孤岛！最终得分 {self.score}",
                                     f"🎉 You escaped the island! Final score {self.score}"))
            else:
                lines.append("=" * 40)
                lines.append(self._t(f"游戏结束。最终得分 {self.score}",
                                     f"Game over. Final score {self.score}"))

        return "\n".join(lines)

    def _info(self):
        return {
            "valid": self.get_valid_actions(),
            "score": self.score,
            "hp": self.hp,
            "food": self.food,
            "day": self.day,
            "escaped": self.escaped,
        }
