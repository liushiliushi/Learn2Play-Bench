import copy
import re
import subprocess
import sys

from games.mola_tea.mola_tea import (
    MAX_ADVERTISED_ACTIONS,
    CustomerRole,
    MolaTeaGame,
)


def test_same_seed_episode_is_deterministic():
    left = MolaTeaGame(seed=7, episode=2)
    right = MolaTeaGame(seed=7, episode=2)
    left_obs, left_info = left.reset()
    right_obs, right_info = right.reset()
    assert left_obs == right_obs
    assert left_info == right_info

    actions = ["inspect customers", "develop recipe_a", "hold", "restore_classic"]
    assert [left.step(action)[0] for action in actions] == [right.step(action)[0] for action in actions]


def test_generation_is_stable_across_processes():
    code = (
        "from games.mola_tea import MolaTeaGame; "
        "g=MolaTeaGame(seed=19, episode=3); print(g.reset()[0])"
    )
    first = subprocess.check_output([sys.executable, "-c", code], text=True)
    second = subprocess.check_output([sys.executable, "-c", code], text=True)
    assert first == second


def test_same_seed_reshuffles_surface_instance_across_episodes():
    first = MolaTeaGame(seed=11, episode=0)
    second = MolaTeaGame(seed=11, episode=1)
    third = MolaTeaGame(seed=12, episode=0)
    first_observation, first_info = first.reset()
    second_observation, second_info = second.reset()
    third.reset()
    signature = lambda game: (
        game.classic_spec,
        tuple((group.display_name, group.role) for group in game.groups.values()),
        tuple(card.spec for card in game.recipe_cards.values()),
    )
    assert first_observation != second_observation
    assert first_info == second_info
    assert signature(first) != signature(second)
    assert signature(first) != signature(third)
    assert {group.role for group in first.groups.values()} == set(CustomerRole)
    assert {group.role for group in second.groups.values()} == set(CustomerRole)


def test_roles_and_recipe_distance_distribution_are_exact():
    game = MolaTeaGame(seed=23)
    game.reset()
    assert {group.role for group in game.groups.values()} == set(CustomerRole)
    assert len({group.display_name for group in game.groups.values()}) == 5
    distances = sorted(card.spec.distance(game.classic_spec) for card in game.recipe_cards.values())
    assert distances == [0, 1, 1, 2, 2, 3, 3, 4]


def test_advertised_actions_are_concrete_bounded_and_parseable():
    game = MolaTeaGame(seed=29)
    game.reset()
    actions = game.get_valid_actions()
    assert len(actions) <= MAX_ADVERTISED_ACTIONS
    assert not any(re.search(r"<[^>]+>", action) for action in actions)
    assert all(game._parse_action(action) is not None for action in actions)


def test_every_advertised_action_executes_from_the_state_that_advertised_it():
    game = MolaTeaGame(seed=31)
    game.reset()
    viable_cards = [card for card in game.recipe_cards.values() if card.spec.distance(game.classic_spec) == 1]
    for card in viable_cards:
        game.step(f"develop {card.card_id}")
        game.step(f"launch {card.product_id}")
        game.products[card.product_id].stock = 100

    for action in game.get_valid_actions():
        clone = copy.deepcopy(game)
        old_turn = clone.turn_count
        observation, _, _, _ = clone.step(action)
        assert "cannot place that command" not in observation
        assert "Unknown launched product" not in observation
        if action not in {"status", "close_shop"}:
            assert clone.turn_count == old_turn + 1


def test_unavailable_entity_combinations_are_omitted():
    game = MolaTeaGame(seed=37)
    game.reset()
    card = next(iter(game.recipe_cards.values()))
    game.step(f"develop {card.card_id}")
    game.step(f"launch {card.product_id}")
    product = game.products[card.product_id]
    product.stock = 0
    actions = game.get_valid_actions()
    assert not any(action.startswith(("sample ", "feature ", "discount ", "gift ", "bundle ")) for action in actions)
    assert all(action.startswith("restock ") for action in actions if product.product_id in action)

    product.stock = 20
    for merch in game.merch.values():
        merch.available_units = 0
    actions = game.get_valid_actions()
    assert not any(action.startswith(("gift ", "bundle ")) for action in actions)
