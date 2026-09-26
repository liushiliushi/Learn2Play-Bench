from games.mola_tea.mola_tea import CustomerRole, MolaTeaGame, ProductStage


def group_for(game: MolaTeaGame, role: CustomerRole):
    return next(group for group in game.groups.values() if group.role == role)


def launch_at_distance(seed: int, distance: int):
    game = MolaTeaGame(seed=seed)
    game.reset()
    card = next(card for card in game.recipe_cards.values() if card.spec.distance(game.classic_spec) == distance)
    game.step(f"develop {card.card_id}")
    game.step(f"launch {card.product_id}")
    product = game.products[card.product_id]
    product.stock = 100
    return game, product


def seed_viable_product(seed: int = 1):
    game, product = launch_at_distance(seed, 1)
    explorer = group_for(game, CustomerRole.EXPLORER)
    game.step(f"sample {product.product_id} {explorer.group_id}")
    return game, product


def reach_return(seed: int = 1):
    game, product = seed_viable_product(seed)
    game.step("hold")
    assert product.stage == ProductStage.REPEATED
    return game, product


def reach_confirmation(seed: int = 1):
    game, product = reach_return(seed)
    game.step(f"feature {product.product_id}")
    assert product.stage == ProductStage.VERIFIED
    return game, product


def reach_trend(seed: int = 1):
    game, product = reach_confirmation(seed)
    broadcaster = group_for(game, CustomerRole.BROADCASTER)
    merch = next(iter(game.merch.values()))
    game.step(f"gift {merch.merch_id} {product.product_id} {broadcaster.group_id}")
    assert product.stage == ProductStage.TRENDING
    return game, product


def test_only_distance_one_is_viable():
    game = MolaTeaGame(seed=3)
    game.reset()
    for card in game.recipe_cards.values():
        expected = card.spec.distance(game.classic_spec) == 1
        game.step(f"develop {card.card_id}")
        product = game.prototypes[card.product_id]
        assert product.viable is expected
        game.prototypes.pop(card.product_id)


def test_attribute_form_maps_to_an_available_recipe_card():
    game = MolaTeaGame(seed=5)
    game.reset()
    card = next(iter(game.recipe_cards.values()))
    action = "develop " + " ".join(card.spec.values())
    game.step(action)
    assert card.product_id in game.prototypes
    assert game.turn_count == 1


def test_launch_and_wrong_group_do_not_seed():
    game, product = launch_at_distance(7, 1)
    assert product.stage == ProductStage.LAUNCHED
    deal_group = group_for(game, CustomerRole.ECHO)
    game.step(f"sample {product.product_id} {deal_group.group_id}")
    assert product.stage == ProductStage.LAUNCHED


def test_viable_sample_and_one_clean_interval_produce_return():
    game, product = seed_viable_product(11)
    assert product.stage == ProductStage.SEEDED
    game.step("restore_classic")
    assert product.stage == ProductStage.REPEATED
    assert game.milestone_counters["natural_return"] == 1


def test_promotion_contaminates_wait_but_recovery_remains_possible():
    game, product = seed_viable_product(13)
    game.step(f"feature {product.product_id}")
    assert product.stage == ProductStage.SEEDED
    assert product.clean_intervals == 0
    assert product.contamination_count == 1
    game.step("hold")
    assert product.stage == ProductStage.REPEATED


def test_nonviable_product_never_returns():
    game, product = launch_at_distance(17, 2)
    explorer = group_for(game, CustomerRole.EXPLORER)
    game.step(f"sample {product.product_id} {explorer.group_id}")
    for _ in range(4):
        game.step("hold")
    assert product.stage == ProductStage.LAUNCHED
    assert game.milestone_counters["natural_return"] == 0


def test_confirmation_requires_current_return_evidence():
    game, product = launch_at_distance(19, 1)
    game.step(f"feature {product.product_id}")
    assert product.stage == ProductStage.LAUNCHED

    game, product = reach_return(19)
    game.step(f"feature {product.product_id}")
    assert product.stage == ProductStage.VERIFIED

    late, late_product = reach_return(23)
    late.step("hold")
    late.step("hold")
    late.step(f"feature {late_product.product_id}")
    assert late_product.stage == ProductStage.REPEATED


def test_stale_return_can_be_refreshed_by_another_clean_interval():
    game, product = reach_return(29)
    game.step("hold")
    game.step("hold")
    prior_count = product.natural_repeat_count
    game.step("hold")
    assert product.stage == ProductStage.REPEATED
    assert product.natural_repeat_count > prior_count
    assert product.verification_deadline == game.turn_count + 2


def test_diffusion_requires_right_group_and_window():
    wrong, wrong_product = reach_confirmation(31)
    wrong_group = group_for(wrong, CustomerRole.ECHO)
    merch = next(iter(wrong.merch.values()))
    wrong.step(f"gift {merch.merch_id} {wrong_product.product_id} {wrong_group.group_id}")
    assert wrong_product.stage == ProductStage.VERIFIED

    correct, product = reach_confirmation(31)
    broadcaster = group_for(correct, CustomerRole.BROADCASTER)
    merch = next(iter(correct.merch.values()))
    correct.step(f"gift {merch.merch_id} {product.product_id} {broadcaster.group_id}")
    assert product.stage == ProductStage.TRENDING

    late, late_product = reach_confirmation(37)
    late.step("hold")
    late.step("hold")
    merch = next(iter(late.merch.values()))
    broadcaster = group_for(late, CustomerRole.BROADCASTER)
    late.step(f"gift {merch.merch_id} {late_product.product_id} {broadcaster.group_id}")
    assert late_product.stage == ProductStage.VERIFIED


def test_deep_discount_trains_price_without_blocking_later_progress():
    game, product = launch_at_distance(41, 1)
    game.step(f"discount {product.product_id} deep")
    assert product.price_trained
    explorer = group_for(game, CustomerRole.EXPLORER)
    game.step(f"sample {product.product_id} {explorer.group_id}")
    game.step("hold")
    assert product.stage == ProductStage.REPEATED


def test_pressure_threshold_and_repeated_push_create_fatigue():
    game, product = reach_trend(43)
    game.step(f"feature {product.product_id}")
    assert product.stage == ProductStage.TRENDING
    game.step(f"feature {product.product_id}")
    assert product.stage == ProductStage.FATIGUED


def test_hold_reduces_pressure_and_post_fatigue_promotion_loses_customer():
    game, product = reach_trend(47)
    before = max(0, sum(product.rolling_pressure))
    game.step("hold")
    assert max(0, sum(product.rolling_pressure)) < before
    product.stage = ProductStage.FATIGUED
    churn = game.total_customer_churn
    game.step(f"discount {product.product_id} small")
    assert game.total_customer_churn == churn + 1


def test_store_pressure_causes_irreversible_regular_loss():
    game, product = launch_at_distance(53, 1)
    regular_group = group_for(game, CustomerRole.ANCHOR)
    game.novelty_pressure = 3
    retained = regular_group.retained_size
    game.step(f"feature {product.product_id}")
    assert regular_group.retained_size == retained - 1
    game.step("restore_classic")
    assert regular_group.retained_size == retained - 1

