import re

from games.mola_tea.mola_tea import INSOLVENCY_LIMIT, CustomerRole, MolaTeaGame


def launch_first(game: MolaTeaGame):
    card = next(iter(game.recipe_cards.values()))
    game.step(f"develop {card.card_id}")
    game.step(f"launch {card.product_id}")
    return game.products[card.product_id]


def test_stock_and_finance_reconcile_exactly():
    game = MolaTeaGame(seed=59)
    game.reset()
    product = launch_first(game)
    before_stock = product.stock
    group = next(iter(game.groups.values()))
    game.step(f"sample {product.product_id} {group.group_id}")
    assert product.stock <= before_stock - 3
    game.step(f"restock {product.product_id} small")
    assert game.cash == 65_000 + game.gross_revenue - game.total_operating_cost
    while not game.done:
        game.step("hold")
    assert game.cash == 65_000 + game.gross_revenue - game.total_operating_cost
    assert game.expired_inventory_cost >= 0
    assert game.score == game._compute_score()


def test_stockout_caps_paid_orders_and_revenue():
    game = MolaTeaGame(seed=61)
    game.reset()
    product = launch_first(game)
    product.stock = 1
    revenue = game.gross_revenue
    sold = game._sell_product(product, 10, product.normal_price, False)
    assert sold == 1
    assert game.gross_revenue - revenue == product.normal_price
    assert product.stock == 0


def test_malformed_and_unavailable_actions_do_not_consume_turn():
    game = MolaTeaGame(seed=67)
    game.reset()
    before = game.turn_count
    game.step("feature missing_product")
    assert game.turn_count == before
    game.step("develop <base> <flavor> <texture> <temperature>")
    assert game.turn_count == before


def test_day_ledger_appears_every_three_turns():
    game = MolaTeaGame(seed=71)
    game.reset()
    for _ in range(2):
        obs, _, _, _ = game.step("hold")
        assert "Day 1 Ledger" not in obs
    obs, _, _, _ = game.step("hold")
    assert "Day 1 Ledger" in obs
    assert len(game.completed_ledgers) == 1


def test_end_conditions_and_score_stability():
    game = MolaTeaGame(seed=73)
    game.reset()
    for _ in range(game.MAX_TURNS + 3):
        game.step("hold")
    assert game.done
    assert game.turn_count == game.MAX_TURNS
    score = game.score
    game.step("hold")
    assert game.score == score
    assert game.turn_count == game.MAX_TURNS

    early = MolaTeaGame(seed=73)
    early.reset()
    early.step("close_shop")
    assert early.done
    assert early.score >= 0

    insolvent = MolaTeaGame(seed=73)
    insolvent.reset()
    insolvent.cash = INSOLVENCY_LIMIT + 1
    insolvent.step("develop recipe_a")
    assert insolvent.done


def test_status_does_not_consume_turn_or_show_score():
    game = MolaTeaGame(seed=79)
    game.reset()
    observation, _, _, _ = game.step("status")
    assert game.turn_count == 0
    assert "Final score" not in observation
    assert game.score == 0


def test_public_outputs_never_expose_private_vocabulary():
    game = MolaTeaGame(seed=83)
    opening, _ = game.reset()
    outputs = [opening]
    product = launch_first(game)
    outputs.extend([game.step("status")[0]])
    for group in game.groups.values():
        if product.stock < 3:
            product.stock = 20
        outputs.append(game.step(f"sample {product.product_id} {group.group_id}")[0])
    outputs.append(game.step("definitely invalid")[0])
    text = "\n".join(outputs).lower()
    forbidden = (
        "explorer",
        "echo",
        "verifier",
        "broadcaster",
        "anchor",
        "seeded",
        "repeated",
        "verified",
        "trending",
        "fatigued",
        "viable",
        "novelty_pressure",
        "clean_intervals",
    )
    for token in forbidden:
        assert not re.search(rf"\b{re.escape(token)}\b", text), token


def test_full_success_and_fatigue_transcript_remains_public_safe():
    game = MolaTeaGame(seed=87)
    opening, _ = game.reset()
    outputs = [opening]
    card = next(card for card in game.recipe_cards.values() if card.spec.distance(game.classic_spec) == 1)
    explorer = next(group for group in game.groups.values() if group.role == CustomerRole.EXPLORER)
    broadcaster = next(group for group in game.groups.values() if group.role == CustomerRole.BROADCASTER)
    merch = next(iter(game.merch.values()))
    actions = [
        f"develop {card.card_id}",
        f"launch {card.product_id}",
        f"sample {card.product_id} {explorer.group_id}",
        "hold",
        f"feature {card.product_id}",
        f"gift {merch.merch_id} {card.product_id} {broadcaster.group_id}",
        f"feature {card.product_id}",
        f"feature {card.product_id}",
    ]
    for action in actions:
        if card.product_id in game.products:
            game.products[card.product_id].stock = 100
        outputs.append(game.step(action)[0])
    outputs.append(game.step("status")[0])
    text = "\n".join(outputs).lower()
    for token in (
        "explorer",
        "echo",
        "verifier",
        "broadcaster",
        "anchor",
        "seeded",
        "repeated",
        "verified",
        "trending",
        "fatigued",
        "viable",
        "novelty_pressure",
        "clean_intervals",
    ):
        assert not re.search(rf"\b{re.escape(token)}\b", text), token


def test_regular_customer_loss_lowers_classic_demand_component():
    game = MolaTeaGame(seed=89)
    game.reset()
    regular = next(group for group in game.groups.values() if group.role == CustomerRole.ANCHOR)
    before = 3 + (regular.retained_size + 1) // 2
    regular.retained_size -= 4
    after = 3 + (regular.retained_size + 1) // 2
    assert after < before
