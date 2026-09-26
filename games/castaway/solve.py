"""
Castaway calibration + self-proof.

- An ORACLE that knows every hidden law (map, recipes, food, escape chain) and
  plays optimally: explore -> learn fire/tool -> collect 3 components (handling
  guards) -> bring to beach -> craft raft -> escape. Prints the ceiling score and
  PROVES the island is escapable. If a seed cannot be escaped, the world generator
  has a bug.
- A RANDOM agent baseline: floor mean (% of ceiling), mean survival days, escape rate.
- A seed-42 summary dump of all hidden laws.

Run:  python games/castaway/solve.py
"""

import os
import sys
import random
from collections import deque

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from games.castaway.castaway import (
    CastawayGame, ESCAPE_COMPONENTS, COMP_POOL, FOOD_ITEMS,
)


# ── pathfinding over the (known-to-oracle) full map ────────────────────────────

def bfs_path(game, src, dst, avoid=None):
    """Shortest path of place names src->dst over the true adjacency.

    `avoid`: a set of places not to step ONTO as an intermediate node (the dst is
    always allowed even if in `avoid`). Used to route around hidden night-trap places
    where merely passing through near nightfall can be lethal."""
    avoid = avoid or set()
    if src == dst:
        return [src]
    prev = {src: None}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in sorted(game.adj[u]):
            if v in prev:
                continue
            if v in avoid and v != dst:
                continue
            prev[v] = u
            if v == dst:
                path = [v]
                while prev[path[-1]] is not None:
                    path.append(prev[path[-1]])
                return list(reversed(path))
            q.append(v)
    return None


def oracle_play(seed, verbose=False, transcript=False, max_survival=False):
    """Play the island with full knowledge of every hidden law and play optimally.

    Strategy (a competent learner's converged plan):
      explore beach -> stockpile fire materials -> light a home campfire ->
      learn tool + craft a portable torch (so night travel is always safe) ->
      keep food topped with the right (raw-nourish or cooked) foods ->
      route through the 3 component sites, clearing any guards ->
      bring everything home -> craft the raft -> escape.

    If `max_survival` is True, the oracle instead plays the SCORE-MAXIMISING line
    (the search lower bound on the true ceiling): it also picks up the DECOY part
    (every component pickup is +PTS_COMPONENT, decoy included), then STALLS safely
    at the beach campfire — resting/eating to hold HP & food — burning turns to bank
    the per-day survival bonus all the way to the turn cap, and only crafts the raft
    on the very last available action. This banks BOTH the full survival bonus AND
    the escape bonus in one episode.
    Returns (escaped, score, days, log).
    """
    from games.castaway.castaway import RESOURCES

    game = CastawayGame(seed=seed)
    log = []

    def act(a):
        obs, r, done, info = game.step(a)
        if transcript:
            log.append((a, obs))
        return done

    # ── world facts (oracle knows everything) ──────────────────────────────────
    fire_recipe = game.recipes["火堆"]
    tool_recipe = game.recipes["工具"]
    torch_recipe = game.recipes["火把"]
    raft_recipe = game.raft_recipe
    comp_place = game.component_place
    comp_guard = game.component_guard
    real_components = list(game.real_components)            # the 3 GENUINE raft parts
    hidden_traps = dict(game.hidden_traps)                  # place -> trap kind
    collapse_places = {p for p, k in hidden_traps.items() if k == "collapse"}
    night_trap_places = {p for p, k in hidden_traps.items()
                         if k in ("night_ambush", "night_place")}

    # The oracle knows the collapse spots and refuses to gather there if any other
    # source of a resource exists. Resources are picked from the *safe* sources.
    def safe_sources(r):
        srcs = [p for p in game.places if r in game.place_resources.get(p, [])]
        safe = [p for p in srcs if p not in collapse_places and p not in night_trap_places]
        return safe if safe else srcs   # fall back only if a resource is trap-only

    res_at = {r: safe_sources(r) for r in RESOURCES}

    # only consider foods that actually exist somewhere on the island
    def obtainable(f):
        return len(res_at.get(f, [])) > 0

    def safely_obtainable(f):
        # has at least one source that is NOT a collapse-trap place
        return any(p not in collapse_places
                   for p in game.places if f in game.place_resources.get(p, []))

    # Prefer foods we can gather WITHOUT walking into a collapse trap. Put safely
    # obtainable foods first so food_target avoids collapse-only sources.
    nourish_raw = sorted(
        [f for f in FOOD_ITEMS
         if game.food_property.get(f) == "nourish" and obtainable(f)],
        key=lambda f: 0 if safely_obtainable(f) else 1)
    cook_food = sorted(
        [f for f in FOOD_ITEMS
         if game.food_property.get(f) == "cook" and obtainable(f)],
        key=lambda f: 0 if safely_obtainable(f) else 1)
    # prefer a raw-nourish food (no fire needed); else a cook-food (must be cooked)
    food_target = nourish_raw[0] if nourish_raw else (cook_food[0] if cook_food else None)
    food_target_is_cook = bool(food_target) and game.food_property.get(food_target) == "cook"

    def path_to(dst):
        """Trap-aware shortest path: route AROUND hidden night-trap places (passing
        through one near nightfall can be lethal). Fall back to the plain shortest path
        only if every route must cross a night-trap place."""
        p = bfs_path(game, game.location, dst, avoid=night_trap_places)
        return p if p else bfs_path(game, game.location, dst)

    def night_safe_here():
        # safe at night if campfire here OR carrying a torch
        return game._campfire_here() or game._has_torch()

    def night_soon(steps=1):
        # will the segment after `steps` actions be night?
        return (game.segment + steps) % game.SEGMENTS_PER_DAY in game.NIGHT_SEGMENTS

    def safe_neighbor():
        """A KNOWN neighbouring place that is NOT a night-trap (prefer the beach). Only
        already-known edges — we must NOT explore here (exploring burns the segment and
        could tip us into the lethal night at this very spot)."""
        nbrs = sorted(game.known_edges.get(game.location, set()))
        cand = [p for p in nbrs if p not in night_trap_places]
        if not cand:
            return None
        if "海滩" in cand:
            return "海滩"
        expl = [p for p in cand if p in game.explored]
        return expl[0] if expl else cand[0]

    def flee_night_trap():
        """If we're standing on a hidden NIGHT-trap place and night is here/imminent,
        step away to a safe neighbour first. The oracle knows these spots; fire/torch
        do not help, so the only safe play is to not be here at night. We only ever step
        onto a KNOWN safe edge — never explore here. (Trap-aware path_to routing means
        we normally never transit a night-trap place at all; this is a safety net.)"""
        if game.done:
            return
        if game.location not in night_trap_places:
            return
        if not (game._is_night() or night_soon(1)):
            return
        nb = safe_neighbor()
        if nb is not None:
            act(f"go_{nb}")

    def shelter_until_day(hp_floor=40):
        """Ride out the night safely *only when HP is getting low*. A torch makes
        nights free, so this is a pre-torch fallback. We don't bounce home every
        night (that wastes the trip) — only when HP would otherwise get dangerous.
        Retreat to the beach (the only danger/creature-free place; mildest nights),
        rest there (HP regen if a campfire exists) until morning and a bit beyond."""
        if game._has_torch() or game.done:
            return
        if game.hp > hp_floor:
            return
        if not (game._is_night() or night_soon(1)):
            return
        _goto_raw("海滩")
        # rest through the night only (heals if campfire; avoids danger/creature dmg).
        # Do NOT burn daylight resting — daylight is for progress.
        while game._is_night() and not game.done:
            eat_if_hungry(threshold=80)
            if game.done:
                return
            act("rest")

    def heal_if_critical(floor=25, target=70):
        """If HP is dangerously low and a campfire exists somewhere we've built (the
        beach), retreat there and rest back up. Prevents a slow HP death-spiral on
        seeds where early creature/danger chip damage accumulates."""
        if game.done or game.hp > floor:
            return
        if "海滩" not in game.has_fire_here:
            return
        goto("海滩")
        while game.hp < target and not game.done and game._campfire_here():
            eat_if_hungry(threshold=70)
            if game.done:
                return
            act("rest")

    def eat_if_hungry(threshold=45):
        if game.done or game.food > threshold:
            return
        # raw-nourish first (no fire needed, portable)
        for f in nourish_raw:
            if game.inventory.get(f, 0) > 0:
                act(f"eat_{f}")
                return
        # cooked food if we have a fire here
        if game._campfire_here():
            for f in cook_food:
                if game.inventory.get(f, 0) > 0:
                    act(f"cook_{f}")
                    return

    def _goto_raw(dst):
        """Walk to dst over the true map, exploring new places en route. No night
        sheltering (used by the shelter routine itself to avoid recursion)."""
        guard = 0
        while game.location != dst and not game.done and guard < 60:
            guard += 1
            flee_night_trap()
            if game.done:
                return
            if game.location not in game.explored:
                act("explore")
                if game.done:
                    return
            path = path_to(dst)
            if not path or len(path) < 2:
                break
            nxt = path[1]
            if nxt not in game.known_edges.get(game.location, set()):
                act("explore")
            act(f"go_{nxt}")
            eat_if_hungry()

    def goto(dst):
        """Walk to dst, but ride out unprotected nights at the home campfire first."""
        guard = 0
        while game.location != dst and not game.done and guard < 80:
            guard += 1
            shelter_until_day()
            if game.done:
                return
            flee_night_trap()
            if game.done:
                return
            if game.location == dst:
                return
            if game.location not in game.explored:
                act("explore")
                if game.done:
                    return
            path = path_to(dst)
            if not path or len(path) < 2:
                break
            nxt = path[1]
            # If the next hop is a hidden NIGHT-trap place (sometimes unavoidable — e.g.
            # it's the only corridor to a component site), make sure we step ONTO it in
            # DAYLIGHT with room to leave before dark. If moving now would land us there
            # at night, wait out the night safely where we are (protected) or shelter,
            # so the transit happens early next morning.
            if nxt in night_trap_places and nxt != dst:
                tip_guard = 0
                while not game.done and night_soon(1) and tip_guard < 8:
                    tip_guard += 1
                    if night_safe_here():
                        act("rest")
                    else:
                        shelter_until_day()
                        break
            if nxt not in game.known_edges.get(game.location, set()):
                act("explore")
            act(f"go_{nxt}")
            eat_if_hungry()

    def gather_until(resource, count):
        """Travel to the nearest source of `resource` and gather until we hold `count`."""
        srcs = res_at.get(resource, [])
        if not srcs:
            return
        srcs = sorted(srcs, key=lambda p: len(bfs_path(game, game.location, p) or [99]))
        dst = srcs[0]
        guard = 0
        while game.inventory.get(resource, 0) < count and not game.done and guard < 40:
            guard += 1
            goto(dst)
            if game.done:
                return
            shelter_until_day()
            if game.done or game.location != dst:
                continue
            if game.location not in game.explored:
                act("explore")
            act("gather")
            eat_if_hungry()

    def have(item, n=1):
        return game.inventory.get(item, 0) >= n

    def restock_food(target_units=4):
        """Keep a buffer of edible food. Raw-nourish is carried as-is; cook-food is
        gathered then cooked at the beach fire when we pass through."""
        if not food_target or game.done:
            return
        if game.inventory.get(food_target, 0) >= target_units:
            return
        gather_until(food_target, target_units)

    def gather_manifest(manifest):
        """Efficiently gather a {resource: count} manifest in as few place-visits as
        possible: at each chosen place, `gather` grabs ALL co-located resources, so
        we greedily pick the place that covers the most still-needed resources, walk
        there, and gather (repeating if one harvest isn't enough). Also opportunistic
        food top-ups when we pass a food source."""
        manifest = {r: n for r, n in manifest.items() if r not in ESCAPE_COMPONENTS}

        def remaining():
            return {r: n - game.inventory.get(r, 0)
                    for r, n in manifest.items() if game.inventory.get(r, 0) < n}

        guard = 0
        while remaining() and not game.done and guard < 30:
            guard += 1
            need = remaining()
            # A needed resource is "trap-only" if its only sources are trap places —
            # collapse never gates an essential (world-gen guarantees this), so this set
            # is effectively always empty, but we keep the guard for robustness.
            def has_safe_source(r):
                return any(p not in collapse_places and p not in night_trap_places
                           for p in game.places if r in game.place_resources.get(p, []))
            forced = {r for r in need if not has_safe_source(r)}
            # score each place by how many still-needed resources it supplies. Skip BOTH
            # collapse spots (cave-in on gather) and night-trap spots (gathering takes a
            # segment and may tip into a lethal night) unless they're the only source.
            best, best_cover, best_cost = None, -1, 1e9
            for p in game.places:
                if (p in collapse_places or p in night_trap_places) and not any(
                        r in forced for r in need if r in game.place_resources.get(p, [])):
                    continue
                cover = sum(1 for r in need if r in game.place_resources.get(p, []))
                if cover == 0:
                    continue
                cost = len(bfs_path(game, game.location, p) or [99])
                if cover > best_cover or (cover == best_cover and cost < best_cost):
                    best, best_cover, best_cost = p, cover, cost
            if best is None:
                break
            # If we must brave a known collapse trap (only source of a forced resource),
            # heal to near-full at the beach campfire first — the cave-in deals ~65 HP.
            if best in collapse_places and best not in game._collapse_sprung \
                    and game.hp < 90:
                goto("海滩")
                while game.hp < 90 and not game.done and game._campfire_here():
                    eat_if_hungry(threshold=70)
                    if game.done:
                        return
                    act("rest")
            goto(best)
            if game.done:
                return
            shelter_until_day()
            flee_night_trap()
            if game.done or game.location != best:
                continue
            if game.location not in game.explored:
                act("explore")
            act("gather")
            eat_if_hungry()

    def craft_at_beach(craft_action):
        goto("海滩")
        if not game.done:
            act(craft_action)

    # ── Plan ────────────────────────────────────────────────────────────────────
    # 1) survey beach
    if game.location not in game.explored:
        act("explore")

    def need_for(*recipes):
        # SUM ingredient counts across all goods we plan to craft in this tour — each
        # craft consumes its own materials, so overlapping ingredients add up (e.g. fire
        # AND torch both want wood). (Using max here was a latent under-gather bug.)
        m = {}
        for rec in recipes:
            for r, n in rec.items():
                if r in ESCAPE_COMPONENTS:
                    continue
                m[r] = m.get(r, 0) + n
        return m

    # 2) Gather FIRE + TORCH materials in ONE tour (they overlap heavily) plus a food
    #    buffer, then return home, light the fire, and craft the torch right away.
    #    Fire = safe nights now; torch = the big unlock (every night safe afterwards,
    #    so no more sheltering detours). Doing both in one tour saves a whole circuit.
    boot_need = need_for(fire_recipe, torch_recipe)
    if food_target:
        boot_need[food_target] = boot_need.get(food_target, 0) + 4
    gather_manifest(boot_need)
    goto("海滩")
    if not game.done:
        act("make_fire")
    if not game.done:
        act("craft_火把")
    eat_if_hungry(threshold=75)

    # 4) TOOL + raft lashing in one tour (night travel now free), craft tool.
    heal_if_critical()
    gather_manifest(need_for(tool_recipe, raft_recipe))
    craft_at_beach("craft_工具")
    eat_if_hungry(threshold=75)

    # 4) tour the 3 REAL component sites in a nearest-neighbour route (tool + torch in
    #    hand). The oracle KNOWS which 3 of the 4 raft-like parts are genuine and skips
    #    the decoy entirely (carrying the decoy would still let the raft work, but the
    #    extra trip is wasted — and a naive player who can't tell them apart pays for it).
    remaining_comps = list(real_components)
    if max_survival:
        # also grab the DECOY (every component pickup banks +PTS_COMPONENT, decoy too).
        # the decoy can never sit on a real-component site, so add it to the tour.
        for c in COMP_POOL:
            if c not in remaining_comps:
                remaining_comps.append(c)
    while remaining_comps and not game.done:
        heal_if_critical()
        if game.done:
            break
        # next = component whose place is closest to where we are
        nxt = min(remaining_comps,
                  key=lambda c: len(bfs_path(game, game.location, comp_place[c]) or [99]))
        remaining_comps.remove(nxt)
        p = comp_place[nxt]
        # If this component site is also a hidden NIGHT trap (an ambush creature, OR a
        # place that itself turns lethal after dark — e.g. the decoy at a night_place),
        # we must ARRIVE in daylight with room to explore + clear any guard + gather, then
        # LEAVE before night (fire/torch don't help). So: walk to a SAFE neighbour first,
        # wait for fresh morning there, then make the final hop in — whole day ahead.
        if hidden_traps.get(p) in ("night_ambush", "night_place"):
            safe_adj = sorted(q for q in game.adj[p] if q not in night_trap_places)
            staging = "海滩" if "海滩" in safe_adj else (safe_adj[0] if safe_adj else "海滩")
            tries = 0
            while not game.done and (p not in game.explored or
                                     game.place_component.get(p) in COMP_POOL) \
                    and game.inventory.get(nxt, 0) == 0 and tries < 6:
                tries += 1
                goto(staging)
                if game.done:
                    break
                # wait at the safe staging spot until it's early morning (seg 0)
                wg = 0
                while not game.done and game.segment != 0 and wg < 6:
                    wg += 1
                    eat_if_hungry(threshold=80)
                    act("rest")
                if game.done:
                    break
                # now hop in fresh; whole day ahead to explore/scare/gather safely
                if staging in game.known_edges.get(game.location, set()) or game.location == staging:
                    if p not in game.known_edges.get(game.location, set()):
                        act("explore")
                    act(f"go_{p}")
                break  # proceed to the explore/scare/gather block below
        else:
            goto(p)
        if game.done:
            break
        if game.location not in game.explored:
            act("explore")
        # Drive off any creature here that would ambush at night (and any formal guard),
        # BEFORE we risk a night segment at this spot.
        here_c = game.place_creature.get(p)
        if here_c is not None and (p, here_c) not in game._scared_creatures \
                and (comp_guard.get(nxt) == here_c or hidden_traps.get(p) == "night_ambush"):
            beh = game.creature_behaviour.get(here_c)
            if beh == "hostile":
                act("hunt")      # need the tool; we have it
            elif beh in ("skittish", "guard"):
                act("scare")     # these flee from shouting
            else:                # 'neutral' (incl. a hidden night-ambusher): bribe it off
                if game.inventory.get("浆果", 0) > 0 or game.inventory.get("贝类", 0) > 0:
                    act("feed")
                else:
                    act("scare")  # last resort (no-op for neutral, but harmless)
        act("gather")
        eat_if_hungry(threshold=50)
        # If this site is a hidden NIGHT trap, do NOT linger into night here — step away
        # to a safe neighbour now (we arrived fresh in the morning, so there's daylight
        # left to leave). flee_night_trap only triggers at/near night; force a retreat.
        if not game.done and p in night_trap_places and game.location == p:
            nb = safe_neighbor()
            if nb is not None:
                act(f"go_{nb}")

    # 5) make sure raft lashing material is on hand
    lash = {r: n for r, n in raft_recipe.items() if r not in ESCAPE_COMPONENTS}
    if any(game.inventory.get(r, 0) < n for r, n in lash.items()):
        gather_manifest(lash)

    if max_survival and not game.done:
        # bank the last +PTS_DISCOVER_PLACE bonuses: explore EVERY place at least once.
        # We hold a torch (nights safe) and know the trap spots, so we can sweep any
        # unexplored place safely. Skip overnighting at night-trap spots: visit by day,
        # explore, then leave. (collapse spots are safe to merely explore — only GATHER
        # triggers them, and we won't gather there.)
        for p in game.places:
            if game.done:
                break
            if p in game.explored:
                continue
            if p in night_trap_places:
                # arrive fresh in the morning from a safe neighbour (same trick as the
                # component tour), explore, then leave before night.
                safe_adj = sorted(q for q in game.adj[p] if q not in night_trap_places)
                staging = "海滩" if "海滩" in safe_adj else (safe_adj[0] if safe_adj else "海滩")
                goto(staging)
                wg = 0
                while not game.done and game.segment != 0 and wg < 6:
                    wg += 1
                    eat_if_hungry(threshold=80)
                    act("rest")
                if game.done:
                    break
                if p not in game.known_edges.get(game.location, set()):
                    act("explore")
                act(f"go_{p}")
                if not game.done and game.location == p and p not in game.explored:
                    act("explore")
                if not game.done and game.location == p:
                    nb = safe_neighbor()
                    if nb is not None:
                        act(f"go_{nb}")
            else:
                goto(p)
                if not game.done and game.location == p and p not in game.explored:
                    act("explore")

    # 6) home, top up food, build the raft, escape
    goto("海滩")
    eat_if_hungry(threshold=85)

    if max_survival and not game.done:
        # SCORE-MAX line: stall safely at the beach campfire to bank every remaining
        # per-day survival bonus, then escape on the very last available action.
        # The beach has no danger/creature/hidden-trap, and we hold fire+torch, so
        # nights here are safe. Rest heals (campfire) and eating keeps food up; we burn
        # turns until exactly one action remains, then craft the raft (escape bonus).
        if "海滩" not in game.has_fire_here:
            # ensure a campfire for safe night rest (should already exist)
            act("make_fire")
        guard = 0
        # leave exactly one action for craft_raft (which ends the game without
        # advancing time), so we bank the maximum number of day boundaries first.
        while game.turn_count < game.MAX_TURNS - 1 and not game.done and guard < 200:
            guard += 1
            if game.food <= 40:
                ate = False
                for f in (nourish_raw + cook_food):
                    if game.inventory.get(f, 0) > 0:
                        act(f"cook_{f}" if game.food_property.get(f) == "cook"
                            and game._campfire_here() else f"eat_{f}")
                        ate = True
                        break
                if not ate:
                    # restock food without leaving safety longer than needed
                    if food_target:
                        gather_until(food_target, 6)
                        goto("海滩")
                    else:
                        act("rest")
            else:
                act("rest")

    if not game.done:
        act("craft_raft")

    return game.escaped, game.score, game.day, log


# ── NAIVE FIRST-ENCOUNTER player (the cross-episode learning probe) ─────────────
#
# A *competent survivor* who has NOT yet discovered this seed's hidden laws. They know
# the generic game (explore, build fire/torch/tool, eat the right foods, components are
# taken by `gather`, raft is built at the beach) — i.e. everything `explore` and basic
# trial reveal in ONE life. But they do NOT know:
#   • which 3 of the 4 look-alike raft parts are REAL (4-choose-3 decoy), and
#   • where the 2 hidden lethal traps are (explore never warned them).
# So they play the *obvious* strategy a first-timer would: survive, then "collect 3
# escape components" (the natural assumption) — grabbing the first 3 raft-parts they
# come across — and head home to escape, walking/overnighting wherever is convenient.
#
# This player should FAIL the first time on most seeds — either dying to a trap, or
# building the raft with a decoy among their 3 parts (so a real part is missing). The
# only way to win reliably is to LEARN the trap spots and the real 3 across episodes.
# That's the cross-episode signal the benchmark needs.

def naive_play(seed, rng, transcript=False):
    from games.castaway.castaway import RESOURCES, COMP_POOL

    game = CastawayGame(seed=seed)
    log = []

    def act(a):
        obs, r, done, info = game.step(a)
        if transcript:
            log.append((a, obs))
        return done

    # The naive player reasons over what they've SEEN (explored), not the true map.
    fire_recipe = game.recipes["火堆"]
    tool_recipe = game.recipes["工具"]
    torch_recipe = game.recipes["火把"]
    raft_recipe = game.raft_recipe

    def known_neighbors():
        return sorted(game.known_edges.get(game.location, set()))

    def step_toward_unseen():
        """Wander to reach somewhere new: prefer a known but unexplored neighbour, else
        any known neighbour. (No trap knowledge — they may walk into danger.)"""
        nbrs = known_neighbors()
        if not nbrs:
            return False
        unexplored = [p for p in nbrs if p not in game.explored]
        target = rng.choice(unexplored) if unexplored else rng.choice(nbrs)
        act(f"go_{target}")
        return True

    def have(r, n=1):
        return game.inventory.get(r, 0) >= n

    def walk_home_known():
        """Walk to the beach over KNOWN edges only (shortest on the known graph)."""
        from collections import deque as _dq
        g3 = 0
        while game.location != "海滩" and not game.done and g3 < 30:
            g3 += 1
            prev = {game.location: None}
            q = _dq([game.location]); found = None
            while q:
                u = q.popleft()
                for v in sorted(game.known_edges.get(u, set())):
                    if v not in prev:
                        prev[v] = u
                        if v == "海滩":
                            found = v; q.clear(); break
                        q.append(v)
            nbrs = sorted(game.known_edges.get(game.location, set()))
            if not nbrs:
                return
            if found is None:
                act(f"go_{rng.choice(nbrs)}")
            else:
                path = ["海滩"]
                while prev[path[-1]] is not None:
                    path.append(prev[path[-1]])
                path = list(reversed(path))
                act(f"go_{path[1]}")

    def naive_night_safety():
        """Generic competence: don't get caught in the open at night. If night is near
        and we're not protected, retreat to the home campfire and rest it out. The
        player does this believing fire/torch = safety — unaware of the hidden traps
        that ignore both. (So they'll happily shelter at a trap spot and still die.)"""
        if game.done or not night_imminent():
            return
        if night_is_safe_here():
            # protected here — rest through the night (heals; safe vs ORDINARY night)
            while game._is_night() and not game.done:
                try_eat()
                if game.done:
                    return
                act("rest")
            return
        if "海滩" in game.has_fire_here and game.location != "海滩":
            walk_home_known()
        while game._is_night() and not game.done:
            try_eat()
            if game.done:
                return
            act("rest")

    # A competent first-timer quickly learns (within ONE life, by trying a bite) which
    # foods nourish vs. poison vs. must-be-cooked — that's NOT a hidden cross-episode
    # law, it's revealed by immediate feedback. So we let the naive player know the food
    # properties (a proxy for "they figured food out this run") and eat safely. What they
    # CANNOT learn in one life is the trap spots and the real-vs-decoy parts.
    safe_raw = [f for f in ["淡水", "浆果", "菌菇", "贝类"]
                if game.food_property.get(f) == "nourish"]
    cookable = [f for f in ["浆果", "菌菇", "贝类"]
                if game.food_property.get(f) == "cook"]

    def try_eat():
        if game.food > 45 or game.done:
            return
        for f in safe_raw:
            if game.inventory.get(f, 0) > 0:
                act(f"eat_{f}")
                return
        if game._campfire_here():
            for f in cookable:
                if game.inventory.get(f, 0) > 0:
                    act(f"cook_{f}")
                    return

    def night_imminent():
        return (game.segment + 1) % game.SEGMENTS_PER_DAY in game.NIGHT_SEGMENTS \
            or game._is_night()

    def night_is_safe_here():
        # a competent player knows fire/torch protect the night (generic mechanic) —
        # but does NOT know the hidden night traps that ignore fire/torch.
        return game._campfire_here() or game._has_torch()

    # ── phase 0: a competent first-timer bootstraps fire + torch (generic survival).
    #    They use the known map (places they've reached) and the recipes they've worked
    #    out by trial. This is NOT hidden cross-episode knowledge — it's basic play.
    def craftables_ready(recipe):
        return all(have(r, n) for r, n in recipe.items() if r not in COMP_POOL)

    if game.location not in game.explored:
        act("explore")

    boot = 0
    while boot < 16 and not game.done and not (have("火把") and game._has_tool()):
        boot += 1
        naive_night_safety()
        if game.done:
            break
        if game.location not in game.explored:
            act("explore")
        # gather whatever materials are underfoot (also picks up components/traps)
        act("gather")
        try_eat()
        if game.done:
            break
        # build fire / torch / tool whenever we can (at the beach for fire)
        if game.location == "海滩" and not game._campfire_here() and craftables_ready(fire_recipe):
            act("make_fire")
        if game._campfire_here() and not have("火把") and craftables_ready(torch_recipe):
            act("craft_火把")
        if not game._has_tool() and craftables_ready(tool_recipe):
            act("craft_工具")
        # if we still need to build fire and we have the materials, head to the beach
        if not game._campfire_here() and craftables_ready(fire_recipe) and game.location != "海滩":
            walk_home_known()
            if game.location == "海滩" and craftables_ready(fire_recipe):
                act("make_fire")
            if game._campfire_here() and not have("火把") and craftables_ready(torch_recipe):
                act("craft_火把")
        else:
            step_toward_unseen()

    # ── phase 1: explore the rest of the island, stock food/materials ────────────
    steps_budget = 14
    while steps_budget > 0 and not game.done:
        steps_budget -= 1
        naive_night_safety()
        if game.done:
            break
        if game.location not in game.explored:
            act("explore")
        else:
            act("gather")        # grab whatever's here (incl. any component / trap)
        try_eat()
        if game.done:
            break
        if not game._has_tool() and craftables_ready(tool_recipe):
            act("craft_工具")
        # build fire as soon as we can (basic survival), at the beach
        if not have("火把") and game._campfire_here() is False and game.location == "海滩" \
                and all(have(r, n) for r, n in fire_recipe.items()):
            act("make_fire")
        # opportunistically craft torch/tool when materials are on hand
        if game._campfire_here() and all(have(r, n) for r, n in torch_recipe.items() if r not in COMP_POOL):
            if not have("火把"):
                act("craft_火把")
        if all(have(r, n) for r, n in tool_recipe.items() if r not in COMP_POOL) and not have("工具"):
            act("craft_工具")
        # move on to see more of the island
        if steps_budget > 0 and not game.done:
            step_toward_unseen()
        try_eat()

    # ── phase 2: "collect 3 escape components" (the natural, wrong assumption) ────
    # The player grabs the first 3 distinct raft-looking parts they can reach. With 4
    # such parts and no way to tell real from decoy, this is a coin-flip on success.
    def parts_held():
        return [c for c in COMP_POOL if game.inventory.get(c, 0) > 0]

    # discover where parts are by exploring; head to the nearest known part site.
    discovered_part_sites = {}  # comp -> place, as the player learns them
    def refresh_known_parts():
        for c in COMP_POOL:
            pl = game.component_place.get(c)
            # the player only "knows" a part is somewhere they've explored & seen the hint
            if pl in game.explored:
                discovered_part_sites[c] = pl

    guard = 0
    while len(parts_held()) < 3 and not game.done and guard < 40:
        guard += 1
        naive_night_safety()
        if game.done:
            break
        refresh_known_parts()
        # if standing on a part we haven't taken, grab it
        here_comp = game.place_component.get(game.location)
        if here_comp and game.inventory.get(here_comp, 0) == 0:
            # naive: just try to gather; deal with a guard by shouting/feeding/fighting
            c = game.place_creature.get(game.location)
            if c is not None and (game.location, c) not in game._scared_creatures:
                beh = game.creature_behaviour.get(c)
                if beh in ("skittish", "guard"):
                    act("scare")
                elif have("工具"):
                    act("hunt")
                elif game.inventory.get("浆果", 0) or game.inventory.get("贝类", 0):
                    act("feed")
                else:
                    act("scare")
            act("gather")
            try_eat()
            continue
        # else wander toward somewhere new to find more parts
        if not step_toward_unseen():
            break
        if game.location not in game.explored:
            act("explore")
        try_eat()

    # ── phase 3: go home and try to escape with whatever 3-ish parts we have ─────
    walk_home_known()

    if not game.done:
        try_eat()
        act("craft_raft")        # first attempt — may fail (decoy) or be missing tool/lash
        # a first-timer would try once more if it complained about materials, but they
        # cannot tell WHICH part is the decoy, so a wrong-3 stays wrong.
    return game.escaped, game.score, game.day, log


# ── isolated DECOY probe ────────────────────────────────────────────────────────
#
# Strips away survival/traps to measure the 4-choose-3 decoy signal on its own: a
# player who has mastered survival AND the traps, but does NOT yet know which 3 of the
# 4 raft-looking parts are real, naturally "collects 3 escape components" — the first 3
# they come across (a random 3-of-4). They succeed only when their 3 are exactly the
# real ones, i.e. when the part they SKIPPED is the decoy: probability 1/4. So even a
# fully trap-competent player fails the raft ~75% of the time until they LEARN the real
# 3 across episodes.

def decoy_first3_succeeds(seed, rng):
    g = CastawayGame(seed=seed)
    order = COMP_POOL[:]
    rng.shuffle(order)
    picked = set(order[:3])          # the first 3 distinct parts they happen to collect
    return picked == set(g.real_components)


# ── random baseline ────────────────────────────────────────────────────────────

def random_play(seed, rng):
    game = CastawayGame(seed=seed)
    while not game.done:
        valid = [a for a in game.get_valid_actions() if a != "status"]
        if not valid:
            break
        game.step(rng.choice(valid))
    return game.escaped, game.score, game.day


# ── seed-42 summary ────────────────────────────────────────────────────────────

def dump_summary(seed):
    g = CastawayGame(seed=seed)
    print(f"\n===== SEED {seed} ISLAND SUMMARY =====")
    print("Places:", g.places)
    print("Map (adjacency):")
    for p in g.places:
        print(f"  {p}  --  {sorted(g.adj[p])}")
    print("Resources per place:")
    for p in g.places:
        print(f"  {p}: {g.place_resources[p]}")
    print("Dangers:", {p: d for p, d in g.place_danger.items() if d})
    print("Creatures + behaviour:")
    for p, c in g.place_creature.items():
        if c:
            print(f"  {p}: {c} ({g.creature_behaviour[c]})")
    print("Food properties:", g.food_property)
    print("Recipes:")
    print("  火堆(fire):", g.recipes["火堆"])
    print("  工具(tool):", g.recipes["工具"])
    print("  火把(torch):", g.recipes["火把"])
    print("  raft:", g.raft_recipe, " needs_tool =", g.raft_needs_tool)
    print("Raft parts on the island (4 look-alikes; only 3 are REAL):")
    for comp in COMP_POOL:
        tag = "REAL " if comp in g.real_components else "DECOY"
        guard = g.component_guard.get(comp)
        print(f"  [{tag}] {comp} @ {g.component_place[comp]}"
              f"  guard={guard if guard else 'none'}")
    print("  -> decoy part (HIDDEN):", g.decoy_component)
    print("  craft raft at:", g.raft_place)
    print("HIDDEN LETHAL TRAPS (explore never reveals these):")
    if g.hidden_traps:
        for p in sorted(g.hidden_traps):
            kind = g.hidden_traps[p]
            desc = {
                "night_ambush": f"night ambush by the '{g.place_creature.get(p)}' "
                                f"(looks neutral) — overnighting here is lethal, fire/torch useless",
                "night_place": "the place turns lethal at night — fire/torch useless",
                "collapse": "gathering here triggers a hidden cave-in / gas (huge HP hit)",
            }.get(kind, kind)
            print(f"  {p}: {kind} — {desc}")
    else:
        print("  (none placeable on this small map)")


def ceiling_score(g_escaped_score):
    return g_escaped_score


# ── analytical upper bound (provable: true max <= this) ─────────────────────────
#
# Sum EVERY scoring source on this seed, IGNORING joint feasibility. This is a valid
# upper bound: no episode can score more than the sum of all individually-possible
# points. (The items need not be simultaneously achievable — that's why it's an upper
# bound, not the exact max.)

def analytical_upper_bound(seed, verbose=False):
    g = CastawayGame(seed=seed)
    # max per-day survival bonuses bankable inside the turn cap: a +PTS_SURVIVE_DAY is
    # awarded on each day boundary (segment wrap). With N advancing turns you cross
    # floor(N / SEGMENTS_PER_DAY) boundaries; the score-max line burns MAX_TURNS-1
    # advancing turns then escapes on the last action (escape doesn't advance time).
    adv_turns = g.MAX_TURNS - 1
    max_day_boundaries = adv_turns // g.SEGMENTS_PER_DAY
    items = {
        "discover_places": (len(g.places), g.PTS_DISCOVER_PLACE),     # first explore each
        "learn_recipes":   (3, g.PTS_LEARN_RECIPE),                   # fire + torch + tool
        "components_all4": (len(COMP_POOL), g.PTS_COMPONENT),         # decoy ALSO scores +18
        "survive_days":    (max_day_boundaries, g.PTS_SURVIVE_DAY),
        "escape":          (1, g.PTS_ESCAPE),
    }
    total = sum(cnt * pts for cnt, pts in items.values())
    if verbose:
        print(f"\n[UPPER BOUND] seed {seed}")
        for k, (cnt, pts) in items.items():
            print(f"  {k:16s}: {cnt} x {pts} = {cnt*pts}")
        print(f"  {'ANALYTICAL UPPER BOUND':16s} = {total}  "
              f"(items not all jointly achievable -> loose bound)")
    return total, items


def main():
    print("=" * 60)
    print("CASTAWAY — calibration & self-proof")
    print("=" * 60)

    # ---- Oracle proof + ceiling bracket on key seeds ----
    # For each proof seed we report THREE numbers that bracket the true max score:
    #   - escape-ASAP oracle  : a fast, robust escape (historical "ceiling" — an UNDER-est.)
    #   - stall-MAX oracle     : SEARCH LOWER BOUND on the true max (collect everything,
    #                            stall to the turn cap for all survival bonuses, escape last)
    #   - analytical UPPER bound: provable true_max <= this (sum of all scoring sources)
    # true_max lies in [stall-max search lower bound, analytical upper bound].
    proof_seeds = [42, 1]
    ceilings = {}
    for s in proof_seeds:
        escaped, score, days, _ = oracle_play(s)
        e_max, sc_max, d_max, _ = oracle_play(s, max_survival=True)
        ub, _ = analytical_upper_bound(s, verbose=True)
        ceilings[s] = score
        status = "ESCAPED ✅" if escaped else "FAILED ❌"
        print(f"[ORACLE] seed {s}: escape-asap {status} score={score} (day {days}) | "
              f"stall-MAX score={sc_max} escaped={e_max} (day {d_max})")
        print(f"  => true max score ∈ [{sc_max} (search lower bound), {ub} (analytical upper bound)]")
        assert escaped, f"!!! seed {s} is NOT escapable — world generation BUG !!!"
        assert sc_max <= ub, f"search lower bound {sc_max} exceeds upper bound {ub} — BUG"
    print("\nAll proof seeds are escapable. ✅")

    # ---- broader escapability sweep ----
    print("\n[ORACLE SWEEP] seeds 0..29:")
    esc = 0
    cmin, cmax = 1e9, 0
    fails = []
    for s in range(30):
        e, sc, d, _ = oracle_play(s)
        if e:
            esc += 1
            cmin = min(cmin, sc)
            cmax = max(cmax, sc)
        else:
            fails.append(s)
    print(f"  escapable {esc}/30   ceiling range [{cmin}, {cmax}]")
    if fails:
        print(f"  !! non-escapable seeds: {fails}")
    assert not fails, f"Non-escapable seeds found: {fails}"

    # ---- random baseline ----
    print("\n[RANDOM] baseline over seeds 0..29, 40 trials each:")
    rng = random.Random(12345)
    all_scores = []
    all_days = []
    rand_escapes = 0
    floor_pct = []
    for s in range(30):
        ceil = oracle_play(s)[1]
        srcs = []
        for _ in range(40):
            e, sc, d = random_play(s, rng)
            srcs.append(sc)
            all_scores.append(sc)
            all_days.append(d)
            if e:
                rand_escapes += 1
        floor_pct.append(100.0 * (sum(srcs) / len(srcs)) / ceil if ceil else 0)
    n = len(all_scores)
    mean_score = sum(all_scores) / n
    mean_days = sum(all_days) / n
    mean_floor_pct = sum(floor_pct) / len(floor_pct)
    mean_ceiling = sum(oracle_play(s)[1] for s in range(30)) / 30
    print(f"  random mean score        : {mean_score:.1f}")
    print(f"  oracle mean ceiling      : {mean_ceiling:.1f}")
    print(f"  random floor (% of ceil) : {mean_floor_pct:.1f}%")
    print(f"  random mean survival days: {mean_days:.2f}")
    print(f"  random escape rate       : {rand_escapes}/{n} = {100.0*rand_escapes/n:.2f}%")

    # ---- NAIVE FIRST-ENCOUNTER probe (the cross-episode learning signal) ----
    # A competent-but-rule-blind player (survives the generic game, "collects 3 escape
    # components", tries to escape) who does NOT know this seed's hidden traps or which
    # 3 of the 4 raft parts are real. If this player mostly FAILS, the seed cannot be
    # beaten without learning those hidden laws across episodes — exactly what we want.
    print("\n[NAIVE FIRST-ENCOUNTER] seeds 0..29, 20 trials each:")
    print("  (knows generic survival; blind to the 2 hidden traps + the real-vs-decoy parts)")
    rng2 = random.Random(20260617)
    nn = 0
    naive_escapes = 0
    cause = {"trap_death": 0, "decoy_or_missing_part": 0,
             "other_death": 0, "timeout_no_escape": 0, "escaped": 0}
    naive_days = []
    for s in range(30):
        for _ in range(20):
            nn += 1
            e, sc, d, log = naive_play(s, rng2, transcript=True)
            naive_days.append(d)
            last = log[-1][1] if log else ""
            if e:
                naive_escapes += 1
                cause["escaped"] += 1
            elif ("塌" in last or "碎石" in last or "夜半" in last or "入夜后" in last):
                cause["trap_death"] += 1
            elif ("不对劲" in last or "部件还不齐" in last or "拼不起来" in last):
                cause["decoy_or_missing_part"] += 1
            elif "时间耗尽" in last:
                cause["timeout_no_escape"] += 1
            else:
                cause["other_death"] += 1
    naive_fail_pct = 100.0 * (nn - naive_escapes) / nn
    print(f"  naive escape rate        : {naive_escapes}/{nn} = {100.0*naive_escapes/nn:.2f}%")
    print(f"  naive FIRST-ENCOUNTER FAIL rate : {naive_fail_pct:.1f}%   (must be HIGH)")
    print(f"  failure breakdown        : {cause}")
    hidden_caused = cause["trap_death"] + cause["decoy_or_missing_part"]
    print(f"  failures from hidden laws (trap death + wrong/decoy part): "
          f"{hidden_caused}/{nn} = {100.0*hidden_caused/nn:.1f}%")
    print("  => the gap between oracle(~100% escape) and naive(~0%) is the cross-episode")
    print("     learning signal: you only close it by learning the traps + the real 3.")

    # ---- isolated DECOY probe (cross-episode signal, traps factored out) ----
    print("\n[DECOY PROBE] survival+trap-competent player who hasn't learned the real 3:")
    rng3 = random.Random(31337)
    dn = 0
    dok = 0
    for s in range(30):
        for _ in range(200):
            dn += 1
            if decoy_first3_succeeds(s, rng3):
                dok += 1
    print(f"  'collect first 3 parts' SUCCESS rate : {100.0*dok/dn:.1f}%  "
          f"(decoy FAILS the raft {100.0*(dn-dok)/dn:.1f}% of first tries)")
    print("  -> ~1/4 success is the theoretical floor (skip the decoy by luck); the rest")
    print("     can only be fixed by learning WHICH 3 parts are real across episodes.")

    # ---- seed summaries ----
    dump_summary(42)
    dump_summary(1)

    print("\nDone.")


if __name__ == "__main__":
    main()
