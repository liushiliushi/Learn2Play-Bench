"""Public content pools for Mola Tea.

The engine selects from these pools deterministically. Hidden enum names are
deliberately absent from player-facing templates.
"""

BASES = (
    "black_tea",
    "jasmine_tea",
    "oolong_tea",
    "green_tea",
    "oat_milk",
    "rice_milk",
    "barley_tea",
    "white_tea",
)

FLAVORS = (
    "brown_sugar",
    "roasted_peach",
    "salted_plum",
    "winter_melon",
    "honey_pear",
    "toasted_coconut",
    "ginger_fig",
    "citrus_blossom",
    "red_bean",
    "lychee",
)

TEXTURES = (
    "no_topping",
    "jelly",
    "foam",
    "tapioca",
    "pudding",
    "aloe",
    "rice_pearls",
    "grass_jelly",
)

TEMPERATURES = (
    "cold",
    "warm",
    "hot",
    "iced",
    "cool",
    "steaming",
)

GROUP_NAMES = (
    "Blue Umbrella Club",
    "North Window Table",
    "Late Bus Crowd",
    "Paper Crane Circle",
    "Riverside Walkers",
    "Glass Badge Group",
    "Quiet Corner Regulars",
    "Station Exit Crowd",
    "Green Notebook Club",
    "Moonlight Study Group",
    "Copper Ticket Table",
    "East Stair Circle",
    "Raincoat Gathering",
    "Lantern Lane Group",
    "Maple Bench Table",
)

PRODUCT_NAMES = (
    ("Cedar Jelly Tea", "cedar_jelly"),
    ("Peach Cloud Tea", "peach_cloud"),
    ("Harbor Pearl Tea", "harbor_pearl"),
    ("Maple Window Tea", "maple_window"),
    ("Silver Reed Tea", "silver_reed"),
    ("Lantern Foam Tea", "lantern_foam"),
    ("Riverstone Tea", "riverstone"),
    ("Paper Kite Tea", "paper_kite"),
    ("Orchard Bell Tea", "orchard_bell"),
    ("Copper Rain Tea", "copper_rain"),
    ("Willow Pearl Tea", "willow_pearl"),
    ("Northlight Tea", "northlight"),
    ("Garden Step Tea", "garden_step"),
    ("Quiet Harbor Tea", "quiet_harbor"),
    ("Evening Crane Tea", "evening_crane"),
    ("Glass Leaf Tea", "glass_leaf"),
)

CLASSIC_NAMES = (
    "Mola House Milk Tea",
    "Mola Original Tea",
    "Old Window Milk Tea",
    "House Lantern Tea",
    "First Pour Milk Tea",
    "Mola Cloud Classic",
)

MERCHANDISE = (
    ("mola_pin", "Mola enamel pin"),
    ("cloud_keychain", "Cloud keychain"),
    ("crane_sticker", "Paper-crane sticker sheet"),
    ("window_charm", "Window charm"),
    ("tea_tag", "Stamped tea tag"),
    ("river_patch", "River cloth patch"),
)

WEATHER_NOTES = (
    "A light rain keeps the pavement bright outside the shop.",
    "Warm air from the station brings a steady but unhurried crowd.",
    "Cloud cover makes the window seats more popular than usual.",
    "A clear afternoon sends short waves of foot traffic past the door.",
    "A nearby evening market adds a little noise to the street.",
    "Cool wind moves people quickly between the station and the shop.",
)

# Ordered by the engine's private role index. The text itself carries only
# behavioral evidence and is safe to render.
CUSTOMER_CLUES = (
    (
        "{group} studies the new-item card before asking what it costs.",
        "Someone from {group} asks exactly what changed from the house drink.",
        "{group} accepts a small taste and spends more time discussing the recipe than the offer.",
        "A visitor from {group} compares the ingredient line with the familiar menu.",
        "{group} is curious about one clear change but loses interest when the description becomes muddled.",
        "A member of {group} says they would return for a drink that still feels connected to the shop.",
    ),
    (
        "{group} asks whether today's offer is free before looking at the drink name.",
        "Several people from {group} repeat the wording from the promotion board.",
        "{group} arrives quickly when a giveaway starts, then disperses just as quickly.",
        "A member of {group} asks whether the same price cut will be available tomorrow.",
        "{group} notices the largest discount sign before anything else on the menu.",
        "People from {group} collect offer cards but rarely mention a past order.",
    ),
    (
        "{group} watches the pickup counter when someone orders without reading the menu.",
        "A person from {group} pays close attention when a returning customer uses a drink name.",
        "{group} studies receipts and nearby conversations more than advertisements.",
        "Members of {group} wait to see what familiar faces order at the listed price.",
        "{group} seems interested only after another customer returns for the same item.",
        "Someone from {group} asks whether people have come back for the new drink yet.",
    ),
    (
        "{group} photographs drinks that already seem established around the shop.",
        "A member of {group} discusses products after hearing several people request them by name.",
        "{group} ignores isolated tests but notices signs that a drink has caught on.",
        "People from {group} compare small shop items with drinks that others already recognize.",
        "{group} shares menu discoveries only after seeing clear interest from other tables.",
        "Someone from {group} says a shop item makes more sense beside a drink people already know.",
    ),
    (
        "{group} walks in and orders the house drink without opening the menu.",
        "A member of {group} asks whether the familiar recipe is still available.",
        "{group} notices successive menu changes and looks back toward the original board.",
        "People from {group} greet the staff and ask for their usual order.",
        "{group} is comfortable with one new item but uneasy when the house drink disappears from view.",
        "Someone from {group} says the original drink is why this shop became part of their route.",
    ),
)

LAUNCH_NOTES = (
    "The new card draws a small knot of curious customers; a few order before comparing it with anything else.",
    "Several passersby stop for the launch display, producing a brief run of first-time orders.",
    "The unfamiliar name gets attention at the counter and a handful of customers decide to try it.",
    "The launch board creates a lively few minutes, though most buyers leave without discussing another visit.",
    "A short opening rush forms around the new drink and settles before the shift is over.",
    "The first service of the new item brings scattered curiosity and several paid cups.",
    "Customers point at the new menu line and place a few exploratory orders.",
    "The launch produces a visible but brief patch of activity near the register.",
)

NATURAL_RETURN_NOTES = (
    "Someone who tried {product} earlier returns without checking the promotion board. They order it by name and pay the listed price.",
    "A previous taster comes back for {product}, asks for it directly, and pays the regular price.",
    "A customer from an earlier visit enters, names {product} before seeing the display, and buys it at the posted price.",
    "Without asking about an offer, a familiar face returns and orders {product} by name.",
    "A customer who sampled {product} before comes back on their own and pays the full listed amount.",
    "The staff recognize a past taster who has returned specifically for {product}, with no mention of a promotion.",
    "A returning customer skips the offer board and requests {product} at its normal price.",
    "Someone seen during the earlier tasting returns alone and orders {product} by name.",
)

CONFIRMATION_NOTES = (
    "A nearby table waits until the returning customer collects {product}, then places several regular-price orders for it.",
    "After hearing {product} requested by name, another table studies the pickup counter and orders it at the listed price.",
    "Several watchful customers notice the return visit and decide to buy {product} without asking for an offer.",
    "The named order catches the attention of a quiet table; they follow with full-price orders of their own.",
    "A few customers compare the returning buyer's cup with the menu, then order {product} at the normal price.",
    "People who had been watching the counter place regular-price {product} orders after the return visit.",
    "The earlier customer's confident order prompts several nearby buyers to choose {product} at the posted price.",
    "A table that had ignored the display responds to the return visit with several paid {product} orders.",
)

DIFFUSION_NOTES = (
    "Photos of {product} beside the {merch} begin appearing in customer conversations. Later arrivals ask for the drink by name.",
    "Recipients pair the {merch} with {product} in their photos, and later visitors arrive already knowing the drink name.",
    "The {merch} travels beyond the first table with mentions of {product}; new customers soon request it directly.",
    "Several customers share {product} with the {merch} in view, and name-led orders follow later in the shift.",
    "Conversation about the {merch} carries the name {product} to people who have not read the shop menu.",
    "The combination of {product} and the {merch} shows up repeatedly, followed by arrivals who ask for the drink outright.",
    "Customers photograph {product} with the {merch}; the next wave enters using the product name.",
    "The {merch} gives an already familiar drink a wider audience, and direct requests for {product} begin to spread.",
)

FATIGUE_NOTES = (
    "The display still attracts glances, but fewer people join the queue and several say they have seen the offer too often.",
    "Customers recognize the promotion immediately, yet the line is much shorter than before.",
    "Another push for the same drink draws weary looks and only a thin response.",
    "The campaign remains visible around the shop, but its novelty has plainly worn down.",
    "People pass the familiar display without stopping; a few describe it as overdone.",
    "The promotion produces scattered orders while more customers turn back to the rest of the menu.",
    "Successive signs for the drink now create less conversation and a noticeably smaller queue.",
    "The latest campaign feels familiar to the room, and the earlier energy does not return.",
)

CHURN_NOTES = (
    "Two familiar customers pause at the changed menu and one leaves without placing the usual order.",
    "A regular asks whether the original drink has been removed, then chooses another shop.",
    "A familiar face searches for the house-drink board and leaves after failing to find it quickly.",
    "One usual customer looks over the novelty displays, asks about the original menu, and walks out.",
    "The changed counter arrangement unsettles a regular customer, who leaves without ordering.",
    "A long-time visitor says the shop no longer feels familiar and does not join the queue.",
    "Someone known for ordering the house drink turns away after another menu change.",
    "A regular customer waits for the original drink to be mentioned, then quietly leaves.",
)

PROMOTION_TRAFFIC_NOTES = (
    "The offer creates a quick queue, but several visitors ask only whether it will be cheaper again tomorrow.",
    "Discount wording travels quickly and brings a burst of price-focused orders.",
    "The campaign fills the counter briefly; many buyers keep the offer card in hand while ordering.",
    "A short-lived wave arrives for the promotion and thins soon after the sign comes down.",
    "The lower price draws visible activity, with recurring questions about the next deal.",
    "Several visitors quote the campaign line exactly and place discounted orders.",
)

WEAK_GIFT_NOTES = (
    "The {merch} is taken quickly. Several visitors leave after asking whether another free batch will appear tomorrow.",
    "The giveaway creates a busy counter, but conversation stays focused on the free {merch}.",
    "Recipients pocket the {merch}; the surrounding chatter fades without many drink names being mentioned.",
    "A small crowd gathers for the {merch} and disperses once the campaign pack is gone.",
    "The free {merch} moves briskly, while later visitors mainly ask whether more will be handed out.",
    "The campaign produces photographs of the {merch}, but little sustained discussion of the drink.",
)

STOCKOUT_NOTES = (
    "The drink sells out before the end of the shift, and later requests cannot be filled.",
    "The final prepared cup leaves the counter while a few customers are still deciding.",
    "Stock runs out during the shift, leaving several requests unfilled.",
    "The product board remains up after the last available cup has been sold.",
    "A late cluster of orders arrives after the remaining stock is gone.",
    "The shop cannot fill every request before the product stock reaches zero.",
)

ORDINARY_NOTES = (
    "The shift continues with a mixture of house-drink orders and quiet browsing.",
    "Foot traffic stays ordinary, with no single item dominating the counter.",
    "A few one-off orders break up a steady run of familiar purchases.",
    "Customers move through at an unhurried pace and the menu gets scattered attention.",
    "The counter sees routine business with a handful of new-item questions.",
    "The shop remains calm while regular orders carry most of the shift.",
)
