from games.lost_and_found.lost_and_found import LostAndFoundGame
from games.lost_and_found.models import ClaimantRole


def _case_signature(game: LostAndFoundGame):
    return tuple(
        (
            case.item_name,
            case.item_archetype_id,
            case.surface_description,
            case.owner_id,
            tuple((cid, claimant.display_name, claimant.role) for cid, claimant in case.claimants.items()),
        )
        for case in game.cases
    )


def test_same_seed_episode_is_deterministic():
    left = LostAndFoundGame(seed=7, episode=2)
    right = LostAndFoundGame(seed=7, episode=2)
    left_observation, left_info = left.reset()
    right_observation, right_info = right.reset()

    assert left_observation == right_observation
    assert left_info == right_info
    assert _case_signature(left) == _case_signature(right)


def test_same_seed_reshuffles_cases_across_episodes():
    first = LostAndFoundGame(seed=11, episode=0)
    second = LostAndFoundGame(seed=11, episode=1)
    first.reset()
    second.reset()

    assert _case_signature(first) != _case_signature(second)
    for game in (first, second):
        for case in game.cases:
            assert {claimant.role for claimant in case.claimants.values()} == set(ClaimantRole)
