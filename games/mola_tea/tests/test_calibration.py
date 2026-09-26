from games.mola_tea.solve import (
    classic_only_episode,
    naive_promotion_episode,
    oracle_episode,
    random_episode,
    repeated_feature_episode,
)


def test_oracle_ceiling_is_high_without_saturating():
    scores = [oracle_episode(seed=seed, episode=1) for seed in range(1, 13)]
    assert min(scores) >= 850
    assert sum(scores) / len(scores) < 980


def test_classic_only_is_between_thirty_and_fifty_percent_of_oracle():
    oracle = [oracle_episode(seed=seed, episode=1) for seed in range(1, 11)]
    classic = [classic_only_episode(seed=seed, episode=1) for seed in range(1, 11)]
    ratio = (sum(classic) / len(classic)) / (sum(oracle) / len(oracle))
    assert 0.30 <= ratio <= 0.50


def test_random_and_naive_promotion_remain_low():
    random_scores = [
        random_episode(seed=seed, episode=1, trial=trial)
        for seed in range(1, 10)
        for trial in range(3)
    ]
    naive_scores = [naive_promotion_episode(seed=seed, episode=1) for seed in range(1, 10)]
    assert sum(random_scores) / len(random_scores) < 250
    assert sum(naive_scores) / len(naive_scores) < 250


def test_repeated_feature_policy_stays_below_sixty_percent_of_oracle():
    oracle = [oracle_episode(seed=seed, episode=1) for seed in range(1, 10)]
    repeated = [repeated_feature_episode(seed=seed, episode=1) for seed in range(1, 10)]
    assert sum(repeated) / len(repeated) < 0.60 * (sum(oracle) / len(oracle))
