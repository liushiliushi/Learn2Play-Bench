"""
DungeonLabyrinth — Underground Labyrinth v2

Rules:
- 20-room random directed graph (not a grid)
- Room properties (treasure, traps, monsters, items) hidden until entered
- 1-3 treasure rooms with large gold caches, require a key to enter
- Keys are pickup items; consumed automatically on treasure room entry
- Torch lasts 18 steps; forced retreat when empty
- Some passages are concealed; use 'search' in a room to reveal them
- Finding the exit and using 'exit' grants +10 bonus
- Recommended steps per episode: 18 (naturally capped by torch)

Supports lang='zh' (default) and lang='en'.
"""

import random
from collections import deque

NUM_ROOMS = 20
MAX_TORCH = 18
MAX_HP    = 10
MAX_TURNS = 50

ITEMS = ['torch_oil', 'health_potion', 'trap_boots', 'monster_charm', 'key']

ITEM_NAME = {
    'zh': {
        'torch_oil':     '油罐（？）',
        'health_potion': '红色药剂（？）',
        'trap_boots':    '厚底靴（？）',
        'monster_charm': '兽骨符（？）',
        'key':           '古铜钥匙',
    },
    'en': {
        'torch_oil':     'Oil Can (?)',
        'health_potion': 'Red Vial (?)',
        'trap_boots':    'Thick Boots (?)',
        'monster_charm': 'Beast Charm (?)',
        'key':           'Bronze Key',
    },
}


class DungeonLabyrinthGame:

    MAX_TURNS = MAX_TURNS

    def __init__(self, seed=None, lang='zh'):
        if seed is None:
            seed = random.randint(0, 10 ** 9)
        self.seed  = seed
        self._lang = lang if lang in ('zh', 'en') else 'zh'
        self._rng  = random.Random(seed)
        self._map  = self._generate()
        self.reset()

    # ── Text helpers ──────────────────────────────────────────────────────────

    def _item_name(self, item):
        return ITEM_NAME[self._lang].get(item, item)

    def _t(self, zh, en):
        return en if self._lang == 'en' else zh

    # ── Map generation ────────────────────────────────────────────────────────

    def _generate(self):
        rng = self._rng
        N   = NUM_ROOMS

        visited    = [False] * N
        tree_edges = []
        stack = [0]
        visited[0] = True
        while stack:
            u = stack[-1]
            nbrs = [v for v in range(N) if not visited[v]]
            if nbrs:
                v = rng.choice(nbrs)
                visited[v] = True
                tree_edges.append((u, v))
                stack.append(v)
            else:
                stack.pop()

        adj = {i: set() for i in range(N)}
        for a, b in tree_edges:
            adj[a].add(b)
            adj[b].add(a)

        cands = [(a, b) for a in range(N) for b in range(a + 1, N) if b not in adj[a]]
        rng.shuffle(cands)
        for a, b in cands[:rng.randint(6, 8)]:
            adj[a].add(b)
            adj[b].add(a)

        depth = [-1] * N
        depth[0] = 0
        q = deque([0])
        while q:
            u = q.popleft()
            for v in adj[u]:
                if depth[v] == -1:
                    depth[v] = depth[u] + 1
                    q.append(v)

        exit_cands = [i for i in range(1, N) if depth[i] >= 4]
        if not exit_cands:
            exit_cands = list(range(1, N))
        exit_room = rng.choice(exit_cands)

        directed = {i: set() for i in range(N)}
        one_way  = 0
        done     = set()
        for a in range(N):
            for b in list(adj[a]):
                if (a, b) in done or (b, a) in done:
                    continue
                done.add((a, b))
                if one_way < 2 and depth[b] > depth[a] + 1 and rng.random() < 0.3:
                    directed[a].add(b)
                    one_way += 1
                else:
                    directed[a].add(b)
                    directed[b].add(a)

        # Build initially-visible edges (vis) and hidden edges (hidden_edges)
        # A subset of connections are hidden in darkness until searched
        vis        = {i: set() for i in range(N)}
        hidden     = {i: set() for i in range(N)}
        for i in range(N):
            for j in directed[i]:
                # Roughly 20% of connections start hidden (searchable)
                if rng.random() < 0.2:
                    hidden[i].add(j)
                else:
                    vis[i].add(j)
        # Ensure room 0 has at least one visible exit so player can start
        if not vis[0]:
            # Move one hidden exit to visible for room 0
            if hidden[0]:
                j = next(iter(hidden[0]))
                hidden[0].discard(j)
                vis[0].add(j)

        treasure_cands = [i for i in range(1, N) if depth[i] >= 4 and i != exit_room]
        rng.shuffle(treasure_cands)
        n_treasure     = min(rng.randint(1, 3), len(treasure_cands))
        treasure_rooms = set(treasure_cands[:n_treasure])

        trap_cands = [i for i in range(1, N)
                      if depth[i] >= 2 and i != exit_room and i not in treasure_rooms]
        trap_rooms = set(rng.sample(trap_cands, min(5, len(trap_cands))))

        mon_cands = [i for i in range(1, N)
                     if i not in trap_rooms and i != exit_room and i not in treasure_rooms]
        mon_rooms = set(rng.sample(mon_cands, min(4, len(mon_cands))))

        normal_items = ['torch_oil', 'health_potion', 'trap_boots', 'monster_charm']
        item_cands   = [i for i in range(1, N)
                        if 2 <= depth[i] <= 6 and i not in trap_rooms
                        and i not in mon_rooms and i != exit_room
                        and i not in treasure_rooms]
        rng.shuffle(item_cands)
        room_to_item = {}
        for item, r in zip(normal_items, item_cands[:5]):
            room_to_item[r] = item

        key_cands = [i for i in range(1, N)
                     if 1 <= depth[i] <= 5
                     and i not in room_to_item
                     and i != exit_room
                     and i not in treasure_rooms]
        rng.shuffle(key_cands)
        for key_room in key_cands[:len(treasure_rooms)]:
            room_to_item[key_room] = 'key'

        rooms = {}
        for i in range(N):
            d = depth[i]
            if i in treasure_rooms:
                gold = rng.randint(20, 30)
            elif i == 0:
                gold = 0
            elif d <= 2:
                gold = rng.choice([0, 0, 0, 1])
            elif d <= 4:
                gold = rng.choice([0, 0, 1, 2])
            else:
                gold = rng.choice([0, 1, 2, 3])

            rooms[i] = {
                'gold':        gold,
                'trap':        i in trap_rooms,
                'trap_dmg':    rng.randint(1, 3) if i in trap_rooms else 0,
                'monster':     i in mon_rooms,
                'mon_dmg':     rng.randint(1, 3) if i in mon_rooms else 0,
                'item':        room_to_item.get(i),
                'is_exit':     (i == exit_room),
                'is_treasure': (i in treasure_rooms),
                'depth':       d,
            }

        return {
            'vis':            vis,
            'hidden':         hidden,
            'exit':           exit_room,
            'rooms':          rooms,
            'depth':          depth,
            'treasure_rooms': treasure_rooms,
        }

    # ── Reset ─────────────────────────────────────────────────────────────────

    def reset(self):
        m = self._map
        self._rooms          = m['rooms']
        self._vis            = m['vis']
        self._hidden         = m['hidden']
        self._exit           = m['exit']
        self._treasure_rooms = m['treasure_rooms']

        self._room       = 0
        self._torch      = MAX_TORCH
        self._hp         = MAX_HP
        self._gold       = 0
        self._inv        = []
        self._visited    = {0}
        self._known      = {i: set(self._vis[i]) for i in range(NUM_ROOMS)}
        self._searched   = set()
        self._dead_mon   = set()
        self._trig_trap  = set()
        self._looted     = set()
        self._gold_taken = set()
        self._done       = False
        self._boots      = False
        self._charm      = False
        self._turn       = 0
        self._log        = []

        if self._lang == 'en':
            intro = (
                "You light your torch and descend into the labyrinth.\n"
                "Room properties are hidden until entered. Some passages lie concealed\n"
                "in darkness and must be searched out.\n\n"
            )
        else:
            intro = (
                "你点燃火把，踏入地下迷宫的入口。\n"
                "迷宫中充满了未知——房间的属性只有进入后才能发现，\n"
                "部分通道也隐藏于黑暗中，需要仔细搜索才能找到。\n\n"
            )
        return intro + self._room_desc(0, first=True), {}

    # ── Public interface ──────────────────────────────────────────────────────

    @property
    def score(self) -> int:
        return self._gold

    @property
    def turn_count(self) -> int:
        return self._turn

    @property
    def done(self) -> bool:
        return self._done

    def get_action_label(self, action: str) -> str:
        if self._lang == 'en':
            return action
        labels = {
            'status': '查看状态', 'take': '拾取物品', 'exit': '离开迷宫',
            'retreat': '撤退离开', 'search': '搜索通道',
            'use_torch_oil': '使用油罐', 'use_health_potion': '使用红色药剂',
            'use_trap_boots': '使用厚底靴', 'use_monster_charm': '使用兽骨符',
            'use_key': '使用古铜钥匙',
        }
        if action.startswith('go_'):
            return f'前往房间{action[3:]}'
        return labels.get(action, action)

    def get_valid_actions(self) -> list:
        if self._done:
            return []
        actions = ['status', 'retreat']
        for nxt in sorted(self._known[self._room]):
            actions.append(f'go_{nxt}')
        r = self._rooms[self._room]
        if self._room not in self._looted and r['item']:
            actions.append('take')
        for item in self._inv:
            actions.append(f'use_{item}')
        if self._room == self._exit:
            actions.append('exit')
        # Allow search if there are any hidden passages not yet revealed in this room
        if self._hidden[self._room] and self._room not in self._searched:
            actions.append('search')
        return actions

    def step(self, action: str):
        action = action.strip().lower()

        if self._done:
            return self._t("游戏已结束。", "Game over."), 0, True, {"score": self._gold}

        if action == 'status':
            return self._status_str(), 0, False, {}

        valid = self.get_valid_actions()
        if action not in valid:
            play = [a for a in valid if a != 'status']
            if self._lang == 'en':
                msg = f"Invalid action: {action}. Available: {', '.join(play[:8])}"
            else:
                msg = f"无效行动：{action}。可用：{', '.join(play[:8])}"
            return msg, 0, False, {}

        self._turn += 1
        lines = []

        if action == 'retreat':
            self._done = True
            lines.append(self._t(
                f"你选择撤退，带着 {self._gold} 枚金币离开了迷宫。",
                f"You retreat, escaping the labyrinth with {self._gold} gold."
            ))

        elif action == 'search':
            lines += self._search()

        elif action.startswith('go_'):
            target = int(action[3:])
            if self._rooms[target]['is_treasure'] and 'key' not in self._inv:
                self._turn -= 1
                if self._lang == 'en':
                    return (f"The stone door won't budge. There's a bronze keyhole — you need a key."
                            f" (Still in room {self._room})", 0, False, {})
                else:
                    return (f"厚重的石门纹丝不动。门上有一个古铜锁孔——需要钥匙才能进入。（你仍在房间 {self._room}）",
                            0, False, {})
            self._torch -= 1
            lines += self._move(target)

        elif action == 'take':
            lines += self._take()

        elif action.startswith('use_'):
            lines += self._use(action[4:])

        elif action == 'exit':
            lines += self._exit_dungeon()
            self._done = True

        if self._torch <= 0 and not self._done:
            self._done = True
            lines.append(self._t(
                f"\n⚠ 火把熄灭，被迫撤退！带走 {self._gold} 枚金币。",
                f"\n⚠ Your torch burns out — forced retreat! You escape with {self._gold} gold."
            ))

        if self._hp <= 0 and not self._done:
            self._done = True
            penalty    = 20
            self._gold = max(0, self._gold - penalty)
            lines.append(self._t(
                f"\n💀 你在迷宫中倒下了。扣除 {penalty} 分惩罚，最终得分：{self._gold}",
                f"\n💀 You collapse in the labyrinth. -{penalty} penalty. Final score: {self._gold}"
            ))

        if self._turn >= MAX_TURNS and not self._done:
            self._done = True
            lines.append(self._t(
                f"\n时限已到，撤退。最终得分：{self._gold}",
                f"\nTime's up — retreat! Final score: {self._gold}"
            ))

        obs_body = '\n'.join(lines)
        obs = obs_body if self._done else f"{obs_body}\n\n---\n{self._status_str()}"
        self._log.append({'turn': self._turn, 'action': action, 'obs': obs})
        return obs, self._gold, self._done, {}

    # ── Action handlers ───────────────────────────────────────────────────────

    def _search(self) -> list:
        room = self._room
        self._searched.add(room)
        newly_found = self._hidden[room] - self._known[room]
        self._known[room].update(newly_found)
        if newly_found:
            exits = sorted(newly_found)
            return [self._t(
                f"你仔细搜索房间，发现了隐藏的通道！新出口：{exits}",
                f"You search carefully and find hidden passages! New exits: {exits}"
            )]
        else:
            return [self._t(
                "你仔细搜索了整个房间，没有发现隐藏的通道。",
                "You search the room carefully but find no hidden passages."
            )]

    def _move(self, target: int) -> list:
        is_first = target not in self._visited
        self._room = target
        self._visited.add(target)
        lines = []

        r = self._rooms[target]
        lines.append(self._room_desc(target, first=is_first))

        if r['is_treasure'] and 'key' in self._inv:
            self._inv.remove('key')
            lines.append(self._t(
                "古铜钥匙插入锁孔，石门缓缓开启。（钥匙已消耗）",
                "The bronze key fits the lock — the stone door swings open. (Key consumed)"
            ))

        if target not in self._gold_taken and r['gold'] > 0:
            self._gold += r['gold']
            self._gold_taken.add(target)
            lines.append(self._t(
                f"自动拾起 {r['gold']} 枚金币。（持有：{self._gold}）",
                f"Auto-collected {r['gold']} gold. (Total: {self._gold})"
            ))

        if r['trap'] and target not in self._trig_trap:
            self._trig_trap.add(target)
            if self._boots:
                self._boots = False
                lines.append(self._t(
                    "地面突然下陷——靴子吸收了冲击，安然无恙。（防陷靴已消耗）",
                    "The floor gives way — your boots absorb the impact. Unharmed. (Boots consumed)"
                ))
            else:
                self._hp -= r['trap_dmg']
                lines.append(self._t(
                    f"⚠ 机关触发！受到 {r['trap_dmg']} 点伤害。（HP：{self._hp}/{MAX_HP}）",
                    f"⚠ Trap triggered! -{r['trap_dmg']} HP. (HP: {self._hp}/{MAX_HP})"
                ))

        if r['monster'] and target not in self._dead_mon:
            self._dead_mon.add(target)
            if self._charm:
                self._charm = False
                lines.append(self._t(
                    "一个阴影扑向你——兽骨符发出白光，怪物退缩了。（兽骨符已消耗）",
                    "A shadow lunges — the charm flares white and the monster retreats. (Charm consumed)"
                ))
            else:
                self._hp -= r['mon_dmg']
                lines.append(self._t(
                    f"⚠ 遭遇怪物！受到 {r['mon_dmg']} 点伤害。（HP：{self._hp}/{MAX_HP}）",
                    f"⚠ Monster attack! -{r['mon_dmg']} HP. (HP: {self._hp}/{MAX_HP})"
                ))

        return lines

    def _take(self) -> list:
        r  = self._room
        rm = self._rooms[r]
        self._looted.add(r)
        lines = []
        if rm['gold'] > 0 and r not in self._gold_taken:
            self._gold += rm['gold']
            self._gold_taken.add(r)
            lines.append(self._t(
                f"拾起 {rm['gold']} 枚金币。（持有：{self._gold}）",
                f"Picked up {rm['gold']} gold. (Total: {self._gold})"
            ))
        if rm['item']:
            self._inv.append(rm['item'])
            lines.append(self._t(
                f"拾起物品：{self._item_name(rm['item'])}",
                f"Picked up: {self._item_name(rm['item'])}"
            ))
        if not lines:
            lines.append(self._t("这里已经没有可拿的东西了。", "Nothing left to take here."))
        return lines

    def _use(self, item: str) -> list:
        if item not in self._inv:
            return [self._t("背包里没有这件物品。", "You don't have that item.")]
        self._inv.remove(item)
        lines = []
        if item == 'torch_oil':
            added = min(8, MAX_TORCH - self._torch)
            self._torch += added
            lines.append(self._t(
                f"你往火把里加了油，火把时间 +{added}。（剩余：{self._torch}）",
                f"You pour oil into the torch. +{added} torch. (Remaining: {self._torch})"
            ))
        elif item == 'health_potion':
            heal = min(MAX_HP - self._hp, 10)
            self._hp += heal
            lines.append(self._t(
                f"你喝下药剂，恢复 {heal} 点生命。（HP：{self._hp}/{MAX_HP}）",
                f"You drink the vial. +{heal} HP. (HP: {self._hp}/{MAX_HP})"
            ))
        elif item == 'trap_boots':
            self._boots = True
            lines.append(self._t(
                "你穿上厚底靴。下次触发陷阱时免受伤害。",
                "You put on the thick boots. Next trap triggered will deal no damage."
            ))
        elif item == 'monster_charm':
            self._charm = True
            lines.append(self._t(
                "你握紧兽骨符。下次遭遇怪物时免受伤害。",
                "You grip the beast charm. Next monster encounter will deal no damage."
            ))
        elif item == 'key':
            self._turn -= 1   # 钥匙是被动道具：把玩一下不消耗步数
            lines.append(self._t(
                "古铜钥匙在手中微微发光。推开上锁的石门时它会自动插入锁孔，无需主动使用。",
                "The bronze key glows faintly. It will unlock a sealed stone door on its own "
                "when you enter — no need to use it."
            ))
            self._inv.append('key')
        return lines

    def _exit_dungeon(self) -> list:
        raw   = self._gold
        bonus = 10
        self._gold = raw + bonus
        if self._lang == 'en':
            return [
                "You find the exit and escape with your loot!",
                f"Gold {raw} + exit bonus {bonus} = {self._gold}",
            ]
        else:
            return [
                "你找到了出口，带着战利品离开了迷宫！",
                f"金币 {raw} + 出口奖励 {bonus} = {self._gold} 分",
            ]

    # ── Descriptions ──────────────────────────────────────────────────────────

    def _room_desc(self, room_id: int, first: bool = True) -> str:
        rm  = self._rooms[room_id]
        if self._lang == 'en':
            tag = "[New Room]" if first else "[Revisit]"
        else:
            tag = "【新房间】" if first else "【重访】"
        hints = []

        if rm['is_treasure']:
            if room_id in self._gold_taken:
                hints.append(self._t("💎 宝藏室（已清空）", "💎 Treasure Room (looted)"))
            else:
                hints.append(self._t("💎 宝藏室", "💎 Treasure Room"))
        else:
            adj_treasures = [n for n in self._known[room_id]
                             if self._rooms[n]['is_treasure'] and n not in self._gold_taken]
            if adj_treasures:
                hints.append(self._t("某扇门缝透出金光", "A faint golden glow seeps through one door"))

        if rm['item'] and room_id not in self._looted:
            item_hint = (self._item_name(rm['item']) if rm['item'] == 'key'
                         else self._t("墙上挂着什么东西", "Something hangs on the wall"))
            hints.append(item_hint)

        if rm['is_exit']:
            hints.append(self._t("✨ 感到一阵清风", "✨ A faint breeze — the exit is near"))

        exits = sorted(self._known[room_id])
        if self._lang == 'en':
            desc_body = ', '.join(hints) if hints else "quiet and empty"
            return f"Room {room_id} {tag}: {desc_body}.\nVisible exits: {exits}"
        else:
            desc_body = '、'.join(hints) if hints else "空荡安静"
            return f"房间 {room_id} {tag}：{desc_body}。\n可见出口：{exits}"

    def _status_str(self) -> str:
        inv = [self._item_name(i) for i in self._inv] or \
              [self._t('空', '(empty)')]
        equip = []
        if self._boots:
            equip.append(self._t('厚底靴', 'Thick Boots'))
        if self._charm:
            equip.append(self._t('兽骨符', 'Beast Charm'))
        if self._lang == 'en':
            eq = f" | Equipped: {', '.join(equip)}" if equip else ""
            return (
                f"Location: Room {self._room} | HP: {self._hp}/{MAX_HP} | "
                f"Torch: {self._torch} | Gold: {self._gold}\n"
                f"Inventory: {inv}{eq} | Turn: {self._turn}/{MAX_TURNS}"
            )
        else:
            eq = f" | 已装备：{'、'.join(equip)}" if equip else ""
            return (
                f"位置：房间 {self._room} | HP：{self._hp}/{MAX_HP} | "
                f"火把：{self._torch} | 金币：{self._gold}\n"
                f"背包：{inv}{eq} | 回合：{self._turn}/{MAX_TURNS}"
            )
