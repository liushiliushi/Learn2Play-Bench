"""Mola Tea: a hidden customer-adoption protocol benchmark game."""

from __future__ import annotations

import hashlib
import itertools
import math
import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto

from . import content


STARTING_CASH = 65_000
INSOLVENCY_LIMIT = -15_000
PROTOTYPE_SLOTS = 2
MAX_LAUNCHED_PRODUCTS = 2
LAUNCH_STOCK = 14
SMALL_RESTOCK = 10
LARGE_RESTOCK = 24
SAMPLE_UNITS = 3
GIFT_PACK_UNITS = 4
INITIAL_MERCH_UNITS = 12
INITIAL_GROUP_SIZE = 8
MAX_ADVERTISED_ACTIONS = 49
MAX_CREDITED_REPEAT_ORDERS = 8


class ProductStage(Enum):
    PROTOTYPE = auto()
    LAUNCHED = auto()
    SEEDED = auto()
    REPEATED = auto()
    VERIFIED = auto()
    TRENDING = auto()
    FATIGUED = auto()
    RETIRED = auto()


class CustomerRole(Enum):
    EXPLORER = auto()
    ECHO = auto()
    VERIFIER = auto()
    BROADCASTER = auto()
    ANCHOR = auto()


ROLE_ORDER = (
    CustomerRole.EXPLORER,
    CustomerRole.ECHO,
    CustomerRole.VERIFIER,
    CustomerRole.BROADCASTER,
    CustomerRole.ANCHOR,
)


@dataclass(frozen=True)
class ProductSpec:
    base: str
    flavor: str
    texture: str
    temperature: str

    def values(self) -> tuple[str, str, str, str]:
        return (self.base, self.flavor, self.texture, self.temperature)

    def distance(self, other: "ProductSpec") -> int:
        return sum(left != right for left, right in zip(self.values(), other.values()))


@dataclass
class RecipeCard:
    card_id: str
    product_id: str
    display_name: str
    spec: ProductSpec
    developed: bool = False


@dataclass
class ProductState:
    product_id: str
    display_name: str
    spec: ProductSpec
    stage: ProductStage
    viable: bool
    launched: bool = False
    retired: bool = False
    stock: int = 0
    normal_price: int = 0
    unit_cost: int = 0
    launch_turn: int | None = None
    seeded_turn: int | None = None
    clean_intervals: int = 0
    verification_deadline: int | None = None
    diffusion_deadline: int | None = None
    contamination_count: int = 0
    price_trained: bool = False
    rolling_pressure: deque[int] = field(default_factory=lambda: deque(maxlen=3))
    natural_repeat_count: int = 0
    verified_repeat_orders: int = 0
    total_orders: int = 0
    pending_trend_turn: int | None = None
    last_promo_kind: str | None = None
    last_promo_turn: int | None = None
    repeat_milestone_awarded: bool = False
    verification_milestone_awarded: bool = False
    diffusion_milestone_awarded: bool = False
    bundle_milestone_awarded: bool = False


@dataclass
class CustomerGroupState:
    group_id: str
    display_name: str
    role: CustomerRole
    initial_size: int = INITIAL_GROUP_SIZE
    retained_size: int = INITIAL_GROUP_SIZE
    clue_cursor: int = 0
    exposures: dict[str, int] = field(default_factory=dict)
    paid_orders: dict[str, int] = field(default_factory=dict)
    freebie_visits: int = 0


@dataclass
class MerchState:
    merch_id: str
    display_name: str
    unit_cost: int
    available_units: int = INITIAL_MERCH_UNITS


@dataclass
class DailyLedger:
    day: int
    orders: int = 0
    gross_revenue: int = 0
    ingredient_cost: int = 0
    promotion_cost: int = 0
    narrative_notes: list[str] = field(default_factory=list)
    cash_after: int = 0

    @property
    def total_cost(self) -> int:
        return self.ingredient_cost + self.promotion_cost


def _stable_int(material: str) -> int:
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def episode_rng(seed: int, episode_index: int) -> random.Random:
    """RNG stream for one episode's *surface* (shop: recipes, groups, prices).

    The surface reshuffles every episode via ``episode_index`` so agents cannot
    memorize a fixed shop or fixed customer identities. The transferable rule is
    the role behavior system itself: agents must infer each episode's roles from
    customer clues and action outcomes.
    """
    return random.Random(_stable_int(f"mola_tea:{seed}:{episode_index}"))


def _money(cents: int) -> str:
    return f"${cents / 100:.2f}"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class MolaTeaGame:
    MAX_TURNS = 21

    def __init__(self, seed: int | None = 0, episode: int = 0, lang: str = "en"):
        if seed is None:
            seed = random.randint(0, 10**9)
        self.seed = int(seed)
        self._episode = episode
        self._lang = "en"
        self._rng = episode_rng(self.seed, episode)
        self._turn = 0
        self._done = False
        self._final_score = 0
        self._end_reason = ""
        self._last_feedback: list[str] = []
        self._last_ledger: DailyLedger | None = None
        self._reset_fields()

    def _reset_fields(self) -> None:
        self.cash = STARTING_CASH
        self.gross_revenue = 0
        self.total_operating_cost = 0
        self.total_customer_churn = 0
        self.novelty_pressure = 0
        self.expired_inventory_cost = 0
        self.clear_promotion_waste_events = 0
        self.classic_spec = ProductSpec("", "", "", "")
        self.classic_name = ""
        self.classic_price = 0
        self.classic_unit_cost = 0
        self.attribute_pools: dict[str, tuple[str, ...]] = {}
        self.recipe_cards: dict[str, RecipeCard] = {}
        self.prototypes: dict[str, ProductState] = {}
        self.products: dict[str, ProductState] = {}
        self.groups: dict[str, CustomerGroupState] = {}
        self.merch: dict[str, MerchState] = {}
        self.current_ledger = DailyLedger(day=1)
        self.completed_ledgers: list[DailyLedger] = []
        self.public_observations: list[str] = []
        self.milestone_counters = {
            "natural_return": 0,
            "confirmation": 0,
            "diffusion": 0,
            "trend_bundle": 0,
        }
        self._inspect_offset = 0
        self._weather_note = ""
        self._classic_boost = 0
        self._costs: dict[str, int] = {}
        self._bundle_markup = 0

    @property
    def score(self) -> int:
        return self._final_score if self._done else 0

    @property
    def turn_count(self) -> int:
        return self._turn

    @property
    def done(self) -> bool:
        return self._done

    def reset(self) -> tuple[str, dict]:
        self._episode += 1
        self._rng = episode_rng(self.seed, self._episode)
        self._turn = 0
        self._done = False
        self._final_score = 0
        self._end_reason = ""
        self._last_feedback = []
        self._last_ledger = None
        self._reset_fields()
        self._generate_episode()
        self._last_feedback = [self._weather_note]
        return self._render(opening=True), self._info()

    # Episode generation -------------------------------------------------

    def _generate_episode(self) -> None:
        self.attribute_pools = {
            "base": tuple(self._rng.sample(content.BASES, 3)),
            "flavor": tuple(self._rng.sample(content.FLAVORS, 3)),
            "texture": tuple(self._rng.sample(content.TEXTURES, 3)),
            "temperature": tuple(self._rng.sample(content.TEMPERATURES, 3)),
        }
        self.classic_spec = ProductSpec(
            self._rng.choice(self.attribute_pools["base"]),
            self._rng.choice(self.attribute_pools["flavor"]),
            self._rng.choice(self.attribute_pools["texture"]),
            self._rng.choice(self.attribute_pools["temperature"]),
        )
        self.classic_name = self._rng.choice(content.CLASSIC_NAMES)
        self.classic_price = self._rng.randint(7, 9) * 100
        self.classic_unit_cost = self.classic_price - self._rng.choice((150, 200, 250))
        self._costs = {
            "develop": self._rng.randint(40, 55) * 100,
            "launch": self._rng.randint(30, 45) * 100,
            "feature": self._rng.randint(12, 20) * 100,
            "sample": self._rng.randint(6, 10) * 100,
            "discount_small": self._rng.randint(8, 12) * 100,
            "discount_deep": self._rng.randint(15, 22) * 100,
            "gift": self._rng.randint(45, 70) * 100,
            "bundle": self._rng.randint(18, 30) * 100,
        }
        self._bundle_markup = self._rng.randint(4, 7) * 100
        self._weather_note = self._rng.choice(content.WEATHER_NOTES)
        self._generate_cards()
        self._generate_groups()
        self._generate_merch()

    def _generate_cards(self) -> None:
        distances = [0, 1, 1, 2, 2, 3, 3, 4]
        specs: list[ProductSpec] = []
        seen: set[ProductSpec] = set()
        for distance in distances:
            while True:
                values = list(self.classic_spec.values())
                changed = self._rng.sample(range(4), distance)
                pools = (
                    self.attribute_pools["base"],
                    self.attribute_pools["flavor"],
                    self.attribute_pools["texture"],
                    self.attribute_pools["temperature"],
                )
                for index in changed:
                    values[index] = self._rng.choice([v for v in pools[index] if v != values[index]])
                spec = ProductSpec(*values)
                if spec not in seen:
                    seen.add(spec)
                    specs.append(spec)
                    break
        self._rng.shuffle(specs)
        names = self._rng.sample(content.PRODUCT_NAMES, len(specs))
        for index, (spec, (display_name, product_id)) in enumerate(zip(specs, names)):
            card_id = f"recipe_{chr(ord('a') + index)}"
            self.recipe_cards[card_id] = RecipeCard(
                card_id=card_id,
                product_id=product_id,
                display_name=display_name,
                spec=spec,
            )

    def _generate_groups(self) -> None:
        names = self._rng.sample(content.GROUP_NAMES, 5)
        permutations = tuple(itertools.permutations(ROLE_ORDER))
        base = _stable_int(f"mola_tea:roles:{self.seed}")
        roles = permutations[(base + 37 * self._episode) % len(permutations)]
        for index, (name, role) in enumerate(zip(names, roles)):
            group_id = f"group_{chr(ord('a') + index)}"
            self.groups[group_id] = CustomerGroupState(group_id, name, role)

    def _generate_merch(self) -> None:
        for merch_id, display_name in self._rng.sample(content.MERCHANDISE, 2):
            self.merch[merch_id] = MerchState(
                merch_id=merch_id,
                display_name=display_name,
                unit_cost=self._rng.randint(2, 5) * 100,
            )

    # Public action surface ----------------------------------------------

    def get_valid_actions(self) -> list[str]:
        if self._done:
            return ["status"]

        actions = ["inspect customers"]
        if len(self.prototypes) < PROTOTYPE_SLOTS and len(self.products) < MAX_LAUNCHED_PRODUCTS:
            actions.extend(
                f"develop {card.card_id}"
                for card in self.recipe_cards.values()
                if not card.developed
            )
        if len(self.products) < MAX_LAUNCHED_PRODUCTS:
            actions.extend(f"launch {product_id}" for product_id in self.prototypes)

        active_groups = [group for group in self.groups.values() if group.retained_size > 0]
        for product in self.products.values():
            if product.retired:
                continue
            if product.stock >= SAMPLE_UNITS:
                actions.extend(f"sample {product.product_id} {group.group_id}" for group in active_groups)
            if product.stock > 0:
                actions.append(f"feature {product.product_id}")
                actions.extend(
                    (f"discount {product.product_id} small", f"discount {product.product_id} deep")
                )
                for merch in self.merch.values():
                    if merch.available_units >= GIFT_PACK_UNITS:
                        actions.extend(
                            f"gift {merch.merch_id} {product.product_id} {group.group_id}"
                            for group in active_groups
                        )
                    if merch.available_units >= 1:
                        actions.append(f"bundle {product.product_id} {merch.merch_id}")
            actions.extend(
                (f"restock {product.product_id} small", f"restock {product.product_id} large")
            )

        actions.extend(["restore_classic", "hold", "status", "close_shop"])
        if len(actions) > MAX_ADVERTISED_ACTIONS:
            raise AssertionError(f"Mola Tea advertised {len(actions)} actions; expected at most {MAX_ADVERTISED_ACTIONS}")
        return actions

    def get_action_label(self, action: str) -> str:
        return action

    def _parse_action(self, action: str) -> dict | None:
        text = (action or "").strip().lower()
        parts = text.split()
        if text == "status":
            return {"kind": "status", "canonical": "status"}
        if text == "hold":
            return {"kind": "hold", "canonical": "hold"}
        if text in {"restore_classic", "restore classic"}:
            return {"kind": "restore", "canonical": "restore_classic"}
        if text in {"close_shop", "close shop"}:
            return {"kind": "close", "canonical": "close_shop"}
        if text == "inspect customers":
            return {"kind": "inspect", "canonical": "inspect customers"}

        if len(parts) == 2 and parts[0] == "develop":
            return {"kind": "develop_card", "card_id": parts[1], "canonical": text}
        if len(parts) == 5 and parts[0] == "develop":
            return {"kind": "develop_spec", "values": tuple(parts[1:]), "canonical": text}
        if len(parts) == 2 and parts[0] == "launch":
            return {"kind": "launch", "product_id": parts[1], "canonical": text}
        if len(parts) == 3 and parts[0] == "sample":
            return {
                "kind": "sample",
                "product_id": parts[1],
                "group_id": parts[2],
                "canonical": text,
            }
        if len(parts) == 2 and parts[0] == "feature":
            return {"kind": "feature", "product_id": parts[1], "canonical": text}
        if len(parts) == 3 and parts[0] == "discount" and parts[2] in {"small", "mild", "deep"}:
            level = "small" if parts[2] == "mild" else parts[2]
            return {
                "kind": "discount",
                "product_id": parts[1],
                "level": level,
                "canonical": f"discount {parts[1]} {level}",
            }
        if len(parts) == 4 and parts[0] == "gift":
            return {
                "kind": "gift",
                "merch_id": parts[1],
                "product_id": parts[2],
                "group_id": parts[3],
                "canonical": text,
            }
        if len(parts) == 3 and parts[0] == "bundle":
            return {
                "kind": "bundle",
                "product_id": parts[1],
                "merch_id": parts[2],
                "canonical": text,
            }
        if len(parts) == 3 and parts[0] == "restock" and parts[2] in {"small", "large"}:
            return {
                "kind": "restock",
                "product_id": parts[1],
                "size": parts[2],
                "canonical": text,
            }
        return None

    # Step resolution ----------------------------------------------------

    def step(self, action: str) -> tuple[str, int, bool, dict]:
        event = self._parse_action(action)
        if event and event["kind"] == "status":
            return self._render(status=True), 0, self._done, self._info()
        if self._done:
            return self._render(status=True), 0, True, self._info()
        if not event:
            self._last_feedback = [
                "The register cannot place that command. Use one of the currently listed actions."
            ]
            return self._render(), 0, False, self._info()
        if event["kind"] == "close":
            self._finish("The owner closes the shop before the seventh day is complete.")
            return self._render(status=True), 0, True, self._info()

        error = self._validate_event(event)
        if error:
            self._last_feedback = [error]
            return self._render(), 0, False, self._info()

        self._turn += 1
        self._last_feedback = []
        self._last_ledger = None
        self._classic_boost = 0
        previous_stages = {pid: product.stage for pid, product in self.products.items()}
        context = self._apply_action(event)

        newly_seeded = {
            pid
            for pid, product in self.products.items()
            if previous_stages.get(pid) != ProductStage.SEEDED and product.stage == ProductStage.SEEDED
        }
        repeat_candidates = self._update_clean_intervals(event, newly_seeded)
        self._simulate_classic_sales()
        self._simulate_product_sales(event, context)
        self._resolve_natural_returns(repeat_candidates)
        self._update_product_pressure(event)
        self._resolve_store_pressure()

        if not self._last_feedback:
            self._note(self._rng.choice(content.ORDINARY_NOTES))

        if self._turn % 3 == 0:
            self._complete_day()

        if self._turn >= self.MAX_TURNS:
            self._finish("Day 7 ends and the shop closes for the week.")
        elif self.cash < INSOLVENCY_LIMIT:
            self._finish("The shop can no longer cover the week's operating bills.")

        return self._render(), 0, self._done, self._info()

    def _validate_event(self, event: dict) -> str | None:
        kind = event["kind"]
        if kind in {"inspect", "hold", "restore"}:
            return None
        if kind in {"develop_card", "develop_spec"}:
            if len(self.prototypes) >= PROTOTYPE_SLOTS:
                return "Both prototype slots are occupied. Launch an existing prototype first."
            if len(self.products) >= MAX_LAUNCHED_PRODUCTS:
                return "The week's two new-product launch positions are already filled."
            card = self._card_for_event(event)
            if card is None:
                available = ", ".join(c.card_id for c in self.recipe_cards.values() if not c.developed)
                return f"That recipe is not an available card. Current cards: {available or 'none'}."
            if card.developed:
                return f"{card.card_id} has already been developed."
            event["card_id"] = card.card_id
            return None
        if kind == "launch":
            if event["product_id"] not in self.prototypes:
                valid = ", ".join(self.prototypes) or "none"
                return f"Unknown prototype '{event['product_id']}'. Current prototypes: {valid}."
            if len(self.products) >= MAX_LAUNCHED_PRODUCTS:
                return "The week's two new-product launch positions are already filled."
            return None

        product = self.products.get(event.get("product_id", ""))
        if product is None or product.retired:
            valid = ", ".join(self.products) or "none"
            return f"Unknown launched product '{event.get('product_id', '')}'. Current products: {valid}."
        if kind == "sample" and product.stock < SAMPLE_UNITS:
            return f"{product.display_name} needs {SAMPLE_UNITS} units in stock for sampling."
        if kind in {"feature", "discount", "gift", "bundle"} and product.stock <= 0:
            return f"{product.display_name} is out of stock. Restock it before using that offer."
        if kind in {"sample", "gift"}:
            group = self.groups.get(event.get("group_id", ""))
            if group is None or group.retained_size <= 0:
                valid = ", ".join(g.group_id for g in self.groups.values() if g.retained_size > 0)
                return f"Unknown customer group '{event.get('group_id', '')}'. Current groups: {valid}."
        if kind in {"gift", "bundle"}:
            merch = self.merch.get(event.get("merch_id", ""))
            if merch is None:
                valid = ", ".join(self.merch) or "none"
                return f"Unknown merchandise '{event.get('merch_id', '')}'. Current merchandise: {valid}."
            required = GIFT_PACK_UNITS if kind == "gift" else 1
            if merch.available_units < required:
                return f"Only {merch.available_units} units of {merch.display_name} remain."
        return None

    def _card_for_event(self, event: dict) -> RecipeCard | None:
        if event["kind"] == "develop_card":
            return self.recipe_cards.get(event.get("card_id", ""))
        values = event.get("values")
        for card in self.recipe_cards.values():
            if card.spec.values() == values:
                return card
        return None

    def _apply_action(self, event: dict) -> dict:
        kind = event["kind"]
        context: dict = {"direct_sales": []}
        if kind == "inspect":
            self._inspect_customers()
        elif kind == "develop_card" or kind == "develop_spec":
            self._develop(event["card_id"])
        elif kind == "launch":
            product = self._launch(event["product_id"])
            context["direct_sales"].append((product, self._rng.randint(1, 4), product.normal_price, False))
        elif kind == "sample":
            self._sample(event, context)
        elif kind == "feature":
            self._feature(event, context)
        elif kind == "discount":
            self._discount(event, context)
        elif kind == "gift":
            self._gift(event, context)
        elif kind == "bundle":
            self._bundle(event, context)
        elif kind == "restock":
            self._restock(event)
        elif kind == "restore":
            self.novelty_pressure = max(0, self.novelty_pressure - 2)
            self._classic_boost = 2
            self._note("The original menu board returns to the center of the counter for the shift.")
        elif kind == "hold":
            self.novelty_pressure = max(0, self.novelty_pressure - 1)
            self._note("The shop runs without a targeted campaign and the regular menu remains easy to see.")
        return context

    def _inspect_customers(self) -> None:
        group_list = list(self.groups.values())
        selected = [group_list[(self._inspect_offset + index) % len(group_list)] for index in range(3)]
        self._inspect_offset = (self._inspect_offset + 3) % len(group_list)
        for group in selected:
            pool = content.CUSTOMER_CLUES[ROLE_ORDER.index(group.role)]
            template = pool[group.clue_cursor % len(pool)]
            group.clue_cursor += 1
            note = template.format(group=group.display_name)
            self._note(note)

    def _develop(self, card_id: str) -> None:
        card = self.recipe_cards[card_id]
        card.developed = True
        product = ProductState(
            product_id=card.product_id,
            display_name=card.display_name,
            spec=card.spec,
            stage=ProductStage.PROTOTYPE,
            viable=card.spec.distance(self.classic_spec) == 1,
            normal_price=self._rng.randint(8, 11) * 100,
            unit_cost=self._rng.choice(tuple(range(250, 401, 25))),
        )
        self.prototypes[product.product_id] = product
        self._charge(self._costs["develop"], "promotion")
        self._note(f"The kitchen completes the {product.display_name} prototype and records its recipe.")

    def _launch(self, product_id: str) -> ProductState:
        product = self.prototypes.pop(product_id)
        product.launched = True
        product.stage = ProductStage.LAUNCHED
        product.stock = LAUNCH_STOCK
        product.launch_turn = self._turn
        self.products[product_id] = product
        self._charge(self._costs["launch"], "promotion")
        self._charge(LAUNCH_STOCK * product.unit_cost, "ingredient")
        self.novelty_pressure += 1
        self._note(self._rng.choice(content.LAUNCH_NOTES))
        return product

    def _sample(self, event: dict, context: dict) -> None:
        product = self.products[event["product_id"]]
        group = self.groups[event["group_id"]]
        product.stock -= SAMPLE_UNITS
        group.exposures[product.product_id] = group.exposures.get(product.product_id, 0) + 1
        self._charge(self._costs["sample"], "promotion")
        if product.viable and product.stage == ProductStage.LAUNCHED and group.role == CustomerRole.EXPLORER:
            product.stage = ProductStage.SEEDED
            product.seeded_turn = self._turn
            product.clean_intervals = 0
            self._note(
                f"Several people from {group.display_name} compare {product.display_name} with the house drink and finish their tastes."
            )
        elif group.role == CustomerRole.ECHO:
            group.freebie_visits += 1
            context["direct_sales"].append((product, self._rng.randint(2, 5), product.normal_price, False))
            self._note(self._rng.choice(content.PROMOTION_TRAFFIC_NOTES))
            if group.exposures[product.product_id] > 1:
                self.clear_promotion_waste_events += 1
        else:
            context["direct_sales"].append((product, self._rng.randint(0, 1), product.normal_price, False))
            self._note(
                f"{group.display_name} accepts the tasting tray; the response stays polite and limited to the moment."
            )

    def _feature(self, event: dict, context: dict) -> None:
        product = self.products[event["product_id"]]
        self._charge(self._costs["feature"], "promotion")
        self.novelty_pressure += 1
        if (
            product.stage == ProductStage.REPEATED
            and product.verification_deadline is not None
            and self._turn <= product.verification_deadline
        ):
            product.stage = ProductStage.VERIFIED
            product.diffusion_deadline = self._turn + 2
            if not product.verification_milestone_awarded:
                product.verification_milestone_awarded = True
                self.milestone_counters["confirmation"] += 1
            context["direct_sales"].append((product, self._rng.randint(2, 4), product.normal_price, True))
            self._note(
                self._rng.choice(content.CONFIRMATION_NOTES).format(product=product.display_name)
            )
        elif product.stage == ProductStage.TRENDING:
            context["direct_sales"].append((product, self._rng.randint(3, 5), product.normal_price, True))
            self._note(f"The front display brings another wave of full-price {product.display_name} orders.")
        else:
            context["direct_sales"].append((product, self._rng.randint(1, 3), product.normal_price, False))
            self._note("The feature board creates ordinary curiosity and a few immediate orders.")

    def _discount(self, event: dict, context: dict) -> None:
        product = self.products[event["product_id"]]
        level = event["level"]
        self._charge(self._costs[f"discount_{level}"], "promotion")
        self.novelty_pressure += 1
        if level == "deep" and product.stage in {
            ProductStage.LAUNCHED,
            ProductStage.SEEDED,
            ProductStage.REPEATED,
        }:
            product.price_trained = True
        percentage = 85 if level == "small" else 70
        sale_price = product.normal_price * percentage // 100
        context["direct_sales"].append((product, self._rng.randint(2, 5), sale_price, False))
        self._note(self._rng.choice(content.PROMOTION_TRAFFIC_NOTES))

    def _gift(self, event: dict, context: dict) -> None:
        product = self.products[event["product_id"]]
        group = self.groups[event["group_id"]]
        merch = self.merch[event["merch_id"]]
        merch.available_units -= GIFT_PACK_UNITS
        self._charge(self._costs["gift"], "promotion")
        self.novelty_pressure += 1
        group.freebie_visits += GIFT_PACK_UNITS
        if (
            product.stage == ProductStage.VERIFIED
            and product.diffusion_deadline is not None
            and self._turn <= product.diffusion_deadline
            and group.role == CustomerRole.BROADCASTER
        ):
            product.stage = ProductStage.TRENDING
            product.pending_trend_turn = self._turn + 1
            if not product.diffusion_milestone_awarded:
                product.diffusion_milestone_awarded = True
                self.milestone_counters["diffusion"] += 1
            self._note(
                self._rng.choice(content.DIFFUSION_NOTES).format(
                    product=product.display_name, merch=merch.display_name
                )
            )
        else:
            self.clear_promotion_waste_events += 1
            if group.role == CustomerRole.ECHO:
                context["direct_sales"].append((product, self._rng.randint(1, 3), product.normal_price, False))
            self._note(self._rng.choice(content.WEAK_GIFT_NOTES).format(merch=merch.display_name))

    def _bundle(self, event: dict, context: dict) -> None:
        product = self.products[event["product_id"]]
        merch = self.merch[event["merch_id"]]
        self._charge(self._costs["bundle"], "promotion")
        self.novelty_pressure += 1
        demand = self._rng.randint(4, 7) if product.stage == ProductStage.TRENDING else self._rng.randint(0, 2)
        sold = self._sell_bundle(product, merch, demand)
        if product.stage == ProductStage.TRENDING and sold > 0:
            if not product.bundle_milestone_awarded:
                product.bundle_milestone_awarded = True
                self.milestone_counters["trend_bundle"] += 1
            self._note(
                f"Customers buy {product.display_name} with the {merch.display_name} as a paid set."
            )
        else:
            if sold <= 1:
                self.clear_promotion_waste_events += 1
            self._note("The paid set gets a few looks, but most of the prepared offer remains untouched.")

    def _restock(self, event: dict) -> None:
        product = self.products[event["product_id"]]
        quantity = SMALL_RESTOCK if event["size"] == "small" else LARGE_RESTOCK
        product.stock += quantity
        self._charge(quantity * product.unit_cost, "ingredient")
        self._note(f"The kitchen prepares {quantity} more units of {product.display_name} stock.")

    def _update_clean_intervals(self, event: dict, newly_seeded: set[str]) -> list[ProductState]:
        contaminating = {"sample", "feature", "discount", "gift", "bundle"}
        targeted_product = event.get("product_id")
        candidates: list[ProductState] = []
        for product in self.products.values():
            if product.product_id in newly_seeded:
                continue
            contaminated = event["kind"] in contaminating and targeted_product == product.product_id
            if product.stage == ProductStage.SEEDED:
                if contaminated:
                    product.clean_intervals = 0
                    product.contamination_count += 1
                else:
                    product.clean_intervals += 1
                    if product.clean_intervals >= 1 and product.viable:
                        candidates.append(product)
            elif product.stage == ProductStage.REPEATED:
                stale = product.verification_deadline is not None and self._turn > product.verification_deadline
                if stale and not contaminated and product.viable:
                    candidates.append(product)
        return candidates

    # Demand and finance -------------------------------------------------

    def _simulate_classic_sales(self) -> None:
        regular_group = next(group for group in self.groups.values() if group.role == CustomerRole.ANCHOR)
        demand = 3 + math.ceil(regular_group.retained_size / 2)
        demand += self._rng.choice((-1, 0, 0, 0, 1)) + self._classic_boost
        orders = max(0, demand)
        revenue = orders * self.classic_price
        cost = orders * self.classic_unit_cost
        self._record_revenue(revenue, orders)
        self._charge(cost, "ingredient")

    def _simulate_product_sales(self, event: dict, context: dict) -> None:
        for product, demand, price, repeat_full_price in context.get("direct_sales", []):
            self._sell_product(product, demand, price, repeat_full_price)

        for product in self.products.values():
            if product.retired:
                continue
            if product.pending_trend_turn == self._turn:
                demand = self._rng.randint(5, 9)
                price = product.normal_price if not product.price_trained else product.normal_price * 85 // 100
                self._sell_product(product, demand, price, not product.price_trained)
                product.pending_trend_turn = None
            elif product.stage == ProductStage.TRENDING:
                demand = self._rng.randint(2, 4)
                price = product.normal_price if not product.price_trained else product.normal_price * 85 // 100
                self._sell_product(product, demand, price, not product.price_trained)
            elif product.stage == ProductStage.FATIGUED:
                self._sell_product(product, self._rng.randint(0, 3), product.normal_price, False)
            else:
                self._sell_product(product, self._rng.randint(0, 2), product.normal_price, False)

    def _resolve_natural_returns(self, candidates: list[ProductState]) -> None:
        for product in candidates:
            demand = self._rng.randint(1, 2)
            sold = self._sell_product(product, demand, product.normal_price, True)
            if sold <= 0:
                continue
            product.stage = ProductStage.REPEATED
            product.natural_repeat_count += sold
            product.clean_intervals = 0
            product.verification_deadline = self._turn + 2
            if not product.repeat_milestone_awarded:
                product.repeat_milestone_awarded = True
                self.milestone_counters["natural_return"] += 1
            self._note(
                self._rng.choice(content.NATURAL_RETURN_NOTES).format(product=product.display_name)
            )

    def _sell_product(
        self,
        product: ProductState,
        demand: int,
        price: int,
        repeat_full_price: bool,
    ) -> int:
        if demand <= 0:
            return 0
        sold = min(demand, product.stock)
        product.stock -= sold
        product.total_orders += sold
        if repeat_full_price:
            product.verified_repeat_orders = min(
                MAX_CREDITED_REPEAT_ORDERS,
                product.verified_repeat_orders + sold,
            )
        self._record_revenue(sold * price, sold)
        if demand > sold:
            self._note(self._rng.choice(content.STOCKOUT_NOTES))
        return sold

    def _sell_bundle(self, product: ProductState, merch: MerchState, demand: int) -> int:
        sold = min(demand, product.stock, merch.available_units)
        product.stock -= sold
        merch.available_units -= sold
        product.total_orders += sold
        price = product.normal_price + self._bundle_markup
        if product.price_trained:
            price = product.normal_price * 90 // 100 + self._bundle_markup // 2
        self._record_revenue(sold * price, sold)
        self._charge(sold * merch.unit_cost, "promotion")
        if demand > sold:
            self._note(self._rng.choice(content.STOCKOUT_NOTES))
        return sold

    def _record_revenue(self, cents: int, orders: int) -> None:
        self.cash += cents
        self.gross_revenue += cents
        self.current_ledger.gross_revenue += cents
        self.current_ledger.orders += orders

    def _charge(self, cents: int, category: str) -> None:
        self.cash -= cents
        self.total_operating_cost += cents
        if category == "ingredient":
            self.current_ledger.ingredient_cost += cents
        else:
            self.current_ledger.promotion_cost += cents

    # Pressure and end state ---------------------------------------------

    def _update_product_pressure(self, event: dict) -> None:
        values = {"feature": 1, "sample": 1, "discount": 1, "gift": 2, "bundle": 1}
        targeted_product = event.get("product_id")
        for product in self.products.values():
            if product.stage not in {ProductStage.TRENDING, ProductStage.FATIGUED}:
                continue
            delta = 0
            if event["kind"] in {"hold", "restore"}:
                delta = -1
            elif targeted_product == product.product_id:
                delta = values.get(event["kind"], 0)
                if event["kind"] == "discount" and event.get("level") == "deep":
                    delta = 2
            product.rolling_pressure.append(delta)
            pressure = max(0, sum(product.rolling_pressure))
            repeated_push = (
                delta > 0
                and product.last_promo_kind == event["kind"]
                and product.last_promo_turn == self._turn - 1
            )
            if delta > 0:
                product.last_promo_kind = event["kind"]
                product.last_promo_turn = self._turn
            if product.stage == ProductStage.TRENDING and (pressure >= 4 or repeated_push):
                product.stage = ProductStage.FATIGUED
                self._note(self._rng.choice(content.FATIGUE_NOTES))
            elif product.stage == ProductStage.FATIGUED and delta > 0:
                self._apply_customer_loss(1)
                self._note(self._rng.choice(content.FATIGUE_NOTES))

    def _resolve_store_pressure(self) -> None:
        if self.novelty_pressure < 4:
            return
        self._apply_customer_loss(1)
        self.novelty_pressure = max(0, self.novelty_pressure - 1)
        self._note(self._rng.choice(content.CHURN_NOTES))

    def _apply_customer_loss(self, count: int) -> None:
        regular_group = next(group for group in self.groups.values() if group.role == CustomerRole.ANCHOR)
        actual = min(count, regular_group.retained_size)
        regular_group.retained_size -= actual
        self.total_customer_churn += actual

    def _complete_day(self) -> None:
        self.current_ledger.cash_after = self.cash
        self.completed_ledgers.append(self.current_ledger)
        self._last_ledger = self.current_ledger
        if self._turn < self.MAX_TURNS:
            self.current_ledger = DailyLedger(day=self._turn // 3 + 1)

    def _compute_score(self) -> int:
        net_profit = (self.gross_revenue - self.total_operating_cost) / 100
        regular_group = next(group for group in self.groups.values() if group.role == CustomerRole.ANCHOR)
        repeat_orders = sum(product.verified_repeat_orders for product in self.products.values())
        score = 120
        score += _clamp(0.8 * net_profit, -180, 320)
        score += 50 * self.milestone_counters["natural_return"]
        score += 90 * self.milestone_counters["confirmation"]
        score += 160 * self.milestone_counters["diffusion"]
        score += 70 * self.milestone_counters["trend_bundle"]
        score += 8 * repeat_orders
        score += 10 * regular_group.retained_size
        score -= 18 * self.total_customer_churn
        score -= self.expired_inventory_cost / 100
        score -= 45 * self.clear_promotion_waste_events
        return round(_clamp(score, 0, 1000))

    def _finish(self, reason: str) -> None:
        if self._done:
            return
        self._end_reason = reason
        self.expired_inventory_cost = sum(
            product.stock * product.unit_cost for product in self.products.values() if not product.retired
        )
        self._done = True
        self._final_score = self._compute_score()
        self._last_feedback = (self._last_feedback + [reason])[-6:]

    def finalize(self) -> None:
        if not self._done:
            self._finish("The owner closes the shop before the seventh day is complete.")

    # Rendering ----------------------------------------------------------

    def _note(self, note: str) -> None:
        self._last_feedback.append(note)
        self.current_ledger.narrative_notes.append(note)
        self.public_observations.append(note)
        self.public_observations = self.public_observations[-40:]

    def _render(self, opening: bool = False, status: bool = False) -> str:
        lines: list[str] = []
        if opening:
            lines.extend(
                [
                    "You manage Mola Tea for seven days.",
                    "Develop and launch drinks, offer samples, run promotions, distribute merchandise, and manage stock.",
                    "High traffic does not always mean a healthy business: promotions cost money, some customers never return, and excessive change can drive regulars away.",
                    "Watch what people do across time and build a profitable, durable customer base.",
                    "The shop closes after Day 7. A business score is shown only at the end.",
                    "",
                ]
            )

        day = min(7, self._turn // 3 + 1)
        lines.append(f"Mola Tea | Day {day} | Turn {self._turn}/{self.MAX_TURNS}")
        lines.append(
            f"Cash: {_money(self.cash)} | Gross revenue: {_money(self.gross_revenue)} | Recorded spending: {_money(self.total_operating_cost)}"
        )
        lines.append(
            f"House drink: {self.classic_name} | {self._spec_text(self.classic_spec)} | price {_money(self.classic_price)}"
        )

        if opening or status:
            lines.extend(["", "Recipe cards:"])
            for card in self.recipe_cards.values():
                availability = "developed" if card.developed else "available"
                lines.append(
                    f"- {card.card_id}: {card.display_name} | {self._spec_text(card.spec)} | {availability}"
                )
            lines.extend(["", "Customer groups:"])
            for group in self.groups.values():
                lines.append(f"- {group.group_id}: {group.display_name}")
            lines.extend(["", "Merchandise:"])
            for merch in self.merch.values():
                lines.append(
                    f"- {merch.merch_id}: {merch.display_name} | units {merch.available_units} | unit cost {_money(merch.unit_cost)}"
                )
            lines.extend(
                [
                    "",
                    "Public campaign costs:",
                    f"- develop {_money(self._costs['develop'])}; launch setup {_money(self._costs['launch'])}; sample service {_money(self._costs['sample'])}",
                    f"- feature {_money(self._costs['feature'])}; small discount {_money(self._costs['discount_small'])}; deep discount {_money(self._costs['discount_deep'])}",
                    "- small discount price: 15% off; deep discount price: 30% off",
                    f"- gift pack {_money(self._costs['gift'])}; bundle setup {_money(self._costs['bundle'])}; bundle markup {_money(self._bundle_markup)}",
                ]
            )

        if self.prototypes:
            lines.extend(["", "Prototypes:"])
            for product in self.prototypes.values():
                lines.append(
                    f"- {product.product_id}: {product.display_name} | {self._spec_text(product.spec)} | planned price {_money(product.normal_price)} | unit stock cost {_money(product.unit_cost)}"
                )
        if self.products:
            lines.extend(["", "Launched drinks:"])
            for product in self.products.values():
                lines.append(
                    f"- {product.product_id}: {product.display_name} | stock {product.stock} | price {_money(product.normal_price)} | unit restock cost {_money(product.unit_cost)}"
                )

        if self._last_feedback:
            lines.extend(["", "Recent observations:"])
            lines.extend(f"- {note}" for note in self._last_feedback[-6:])
        if self._last_ledger is not None:
            lines.extend(["", self._ledger_text(self._last_ledger)])
        elif status and self.completed_ledgers:
            lines.extend(["", self._ledger_text(self.completed_ledgers[-1])])

        if self._done:
            lines.extend(
                [
                    "",
                    "Final Business Report",
                    f"Gross revenue: {_money(self.gross_revenue)}",
                    f"Recorded spending: {_money(self.total_operating_cost)}",
                    f"Net operating result: {_money(self.gross_revenue - self.total_operating_cost)}",
                    f"Discarded new-drink inventory value: {_money(self.expired_inventory_cost)}",
                    f"Customers lost: {self.total_customer_churn}",
                    f"Final score: {self._final_score}",
                ]
            )
        return "\n".join(lines)

    def _ledger_text(self, ledger: DailyLedger) -> str:
        notes = ledger.narrative_notes[-3:]
        lines = [
            f"Day {ledger.day} Ledger",
            f"Orders completed: {ledger.orders}",
            f"Gross revenue: {_money(ledger.gross_revenue)}",
            f"Ingredient and packaging cost: {_money(ledger.ingredient_cost)}",
            f"Promotion, merchandise, and setup spending: {_money(ledger.promotion_cost)}",
            f"Cash after operations: {_money(ledger.cash_after or self.cash)}",
        ]
        if notes:
            lines.append("Observed behavior:")
            lines.extend(f"- {note}" for note in notes)
        return "\n".join(lines)

    @staticmethod
    def _spec_text(spec: ProductSpec) -> str:
        return (
            f"base={spec.base}, flavor={spec.flavor}, texture={spec.texture}, "
            f"temperature={spec.temperature}"
        )

    def _info(self) -> dict:
        return {"valid": self.get_valid_actions()}

    # White-box diagnostics used only by tests and calibration scripts.
    def diagnostics(self) -> dict:
        return {
            "seed": self.seed,
            "episode": self._episode,
            "role_mapping": {group.group_id: group.role.name for group in self.groups.values()},
            "recipe_distances": {
                card.card_id: card.spec.distance(self.classic_spec) for card in self.recipe_cards.values()
            },
            "products": {
                product.product_id: {
                    "viable": product.viable,
                    "stage": product.stage.name,
                    "contamination_count": product.contamination_count,
                    "pressure": list(product.rolling_pressure),
                }
                for product in self.products.values()
            },
            "novelty_pressure": self.novelty_pressure,
            "customer_churn": self.total_customer_churn,
            "gross_revenue": self.gross_revenue,
            "operating_cost": self.total_operating_cost,
            "net_profit": self.gross_revenue - self.total_operating_cost,
            "inventory_waste": self.expired_inventory_cost,
            "score": self.score,
        }
