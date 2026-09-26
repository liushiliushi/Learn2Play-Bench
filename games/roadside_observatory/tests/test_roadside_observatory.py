from games.roadside_observatory.roadside_observatory import (
    A_DRIVER,
    A_MECHANIC,
    A_RANGER,
    RoadsideObservatoryGame,
)
from games.roadside_observatory.solve import (
    naive_episode,
    oracle_episode,
    random_episode,
)


def travel_to_archetype(game: RoadsideObservatoryGame, archetype: str) -> None:
    while not game.done:
        enc = game._current_encounter()
        if enc is not None and enc.archetype == archetype:
            return
        game.step("walk main road")
    raise AssertionError(f"did not reach {archetype}")


def test_deterministic_same_seed_episode():
    g1 = RoadsideObservatoryGame(seed=7, episode=2)
    g2 = RoadsideObservatoryGame(seed=7, episode=2)
    obs1, info1 = g1.reset()
    obs2, info2 = g2.reset()
    assert obs1 == obs2
    assert info1["valid"] == info2["valid"]
    actions = ["walk main road", "visit landmark", "walk main road", "observe person"]
    trace1 = [g1.step(a)[0] for a in actions]
    trace2 = [g2.step(a)[0] for a in actions]
    assert trace1 == trace2


def test_same_seed_location_has_same_distance_across_travel_methods():
    arrivals = []
    for action in ["walk main road", "walk scenic trail", "take bus", "hitch safe", "hitch risky"]:
        g = RoadsideObservatoryGame(seed=7, episode=2)
        g.reset()
        g.step(action)
        arrivals.append((g.current_location, g.distance_to_observatory))

    assert len({location for location, _ in arrivals}) == 1
    assert len({distance for _, distance in arrivals}) == 1


def test_same_location_protocol_success_does_not_change_distance():
    mechanic = RoadsideObservatoryGame(seed=8, episode=2)
    mechanic.reset()
    travel_to_archetype(mechanic, A_MECHANIC)
    mechanic_distance = mechanic.distance_to_observatory
    mechanic_index = mechanic._route_index
    mechanic.step("offer help")
    mechanic.step("ask ride")
    assert mechanic._route_index == mechanic_index
    assert mechanic.distance_to_observatory == mechanic_distance

    ranger = RoadsideObservatoryGame(seed=9, episode=2)
    ranger.reset()
    travel_to_archetype(ranger, A_RANGER)
    ranger.energy = 80
    ranger_distance = ranger.distance_to_observatory
    ranger_index = ranger._route_index
    ranger.step("ask weather")
    ranger.step("ask shortcut")
    assert ranger._route_index == ranger_index
    assert ranger.distance_to_observatory == ranger_distance


def test_different_episodes_reshuffle_surface():
    g = RoadsideObservatoryGame(seed=11)
    g.reset()
    first = [
        (loc.name, loc.encounter.name if loc.encounter else None, loc.encounter.role if loc.encounter else None)
        for loc in g._locations
    ]
    g.reset()
    second = [
        (loc.name, loc.encounter.name if loc.encounter else None, loc.encounter.role if loc.encounter else None)
        for loc in g._locations
    ]
    assert first != second


def test_hidden_protocol_constants_invariant():
    g = RoadsideObservatoryGame(seed=13)
    g.reset()
    sig1 = g._protocol_signature()
    mapping1 = {loc.name: loc.encounter.archetype for loc in g._locations if loc.encounter}
    g.reset()
    sig2 = g._protocol_signature()
    mapping2 = {loc.name: loc.encounter.archetype for loc in g._locations if loc.encounter}
    assert sig1 == sig2
    assert mapping1 != mapping2


def test_action_parser_accepts_generated_valid_actions():
    g = RoadsideObservatoryGame(seed=1)
    g.reset()
    for action in g.get_valid_actions():
        assert g._parse_action(action) is not None, action


def test_chinese_language_renders_status_and_action_labels():
    g = RoadsideObservatoryGame(seed=1, lang="zh")
    obs, _ = g.reset()
    assert "旅人：" in obs
    assert "距离：" in obs
    assert "物品：" in obs
    assert "Traveler:" not in obs
    assert "Distance:" not in obs
    assert g.get_action_label("walk main road") == "沿主路步行"
    assert g.get_action_label("show item creased map") == "出示物品：折痕地图"
    assert g._parse_action("沿主路步行")["canonical"] == "walk main road"
    assert g._parse_action("出示物品：折痕地图")["canonical"] == "show item creased map"


def test_no_step_feedback_leaks_hidden_terms():
    g = RoadsideObservatoryGame(seed=3)
    obs, _ = g.reset()
    outputs = [obs]
    for action in ["walk main road", "visit landmark", "walk main road", "observe person", "ask route"]:
        outputs.append(g.step(action)[0])
    text = "\n".join(outputs).lower()
    forbidden = [
        "trust",
        "protocol",
        "correct",
        "wrong",
        "+points",
        "score",
        "point delta",
        "patient mechanic",
        "cautious ranger",
        "generous hiker",
        "story collector",
        "too-convenient",
        "night astronomer",
    ]
    for word in forbidden:
        assert word not in text


def test_immediate_driver_acceptance_not_explicitly_labeled():
    g = RoadsideObservatoryGame(seed=4)
    g.reset()
    travel_to_archetype(g, A_DRIVER)
    obs, _, _, _ = g.step("accept offer")
    text = obs.lower()
    forbidden = ["trap", "because", "wrong", "failed", "protocol", "too-convenient"]
    for word in forbidden:
        assert word not in text


def test_oracle_scores_above_850():
    scores = [oracle_episode(seed=21, episode=ep) for ep in range(1, 8)]
    assert min(scores) > 850


def test_random_mean_below_350():
    scores = [
        random_episode(seed=31, episode=ep, trial=trial)
        for ep in range(1, 8)
        for trial in range(4)
    ]
    assert sum(scores) / len(scores) < 350


def test_naive_at_most_70_percent_of_oracle():
    oracle = [oracle_episode(seed=41, episode=ep) for ep in range(1, 8)]
    naive = [naive_episode(seed=41, episode=ep) for ep in range(1, 8)]
    assert sum(naive) / len(naive) <= 0.70 * (sum(oracle) / len(oracle))


def test_every_episode_has_reachable_path_to_observatory():
    scores = [oracle_episode(seed=51, episode=ep) for ep in range(1, 8)]
    assert min(scores) > 850


def test_no_soft_lock_when_resources_reach_zero():
    g = RoadsideObservatoryGame(seed=61)
    g.reset()
    g.energy = 0
    g.supplies = 0
    g.cash = 0
    for _ in range(g.MAX_TURNS):
        valid = g.get_valid_actions()
        assert any(a != "status" for a in valid)
        if "walk main road" in valid:
            g.step("walk main road")
        else:
            g.step(next(a for a in valid if a != "status"))
        if g.done:
            break


def test_max_turns_enforced():
    g = RoadsideObservatoryGame(seed=71)
    g.reset()
    for _ in range(g.MAX_TURNS + 5):
        g.step("rest")
    assert g.done
    assert g.turn_count == g.MAX_TURNS
