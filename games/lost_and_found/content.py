"""Curated, semantic content bundles for Lost & Found Office."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Bundle:
    marker_key: str
    marker: str
    purpose_key: str
    purpose: str
    shallow: str
    timelines: tuple[str, str]


@dataclass(frozen=True)
class Archetype:
    archetype_id: str
    display_names: tuple[str, str, str]
    surfaces: tuple[str, str, str]
    recovery_scenes: tuple[str, str, str]
    bundles: tuple[Bundle, Bundle, Bundle]
    records: tuple[tuple[str, str], tuple[str, str]]
    decoys: tuple[tuple[str, str], tuple[str, str]]


def B(key: str, marker: str, purpose: str, shallow: str, a: str, b: str) -> Bundle:
    return Bundle(key, marker, f"purpose_{key}", purpose, shallow, (a, b))


ARCHETYPES = (
    Archetype("camera_case", ("camera case", "small photo bag", "padded camera pouch"),
        ("a scratched lower corner", "a faded wrist strap", "a pale sticker mark on the lid"),
        ("beneath the east mirror-maze bench", "beside the photo-booth queue rail", "under a seat near the fountain"),
        (B("red_thread_loop", "an uneven red-thread repair beneath the second strap loop", "the strap snapped at a hotel and a cousin repaired it with thread from a travel sewing kit", "two spare batteries", "used after the photo booth and before entering the mirror maze", "set beside a bench while helping a child fasten a coat after the photo booth"),
         B("paper_battery_shim", "a folded paper shim inside the left battery slot", "the paper stops loose batteries rattling during the morning commute", "a lens cloth", "changed a battery after the carousel and noticed the case missing after buying a drink", "used it beside the carousel before stopping at the drink kiosk"),
         B("blue_charm", "a tiny blue star charm inside the lid", "the charm distinguishes the case from a sibling's identical bag", "a spare memory card", "opened it after the river ride and before the locker visit", "last handled it while checking a locker number after the river ride")),
        (("photo_booth_log", "The photo-booth log shows the pictured case in use before the mirror-maze entry window."), ("locker_access_log", "The locker log places the relevant access after the river-ride exit.")),
        (("west_gate_camera", "The west-gate camera shows heavy foot traffic but no usable view of the item."), ("gift_shop_till", "The gift-shop till records several battery purchases without identifying any bag."))),
    Archetype("backpack", ("day backpack", "compact rucksack", "canvas backpack"),
        ("a scuffed green base", "one sun-faded shoulder panel", "a bent outer buckle"),
        ("by the climbing-wall cubbies", "behind a play-area chair", "near the north locker bank"),
        (B("orange_zip_tie", "an orange cable tie replacing the inner zipper pull", "it was fitted after the original pull broke during a school trip", "a yellow raincoat", "opened after the climbing wall and before lunch", "placed by a chair while tying a child's shoe before lunch"),
         B("map_patch", "a park-map patch sewn beneath the left shoulder strap", "the patch covers a tear made by a bicycle basket", "a steel water bottle", "carried through the aquarium before using the north lockers", "checked the side pocket after the aquarium and before the locker visit"),
         B("name_under_flap", "the initials 'R.K.' written under the rain flap", "the hidden initials separate it from matching team bags", "a striped scarf", "used after the puppet show and before the fountain stop", "removed the scarf after the puppet show while seated by the fountain")),
        (("climbing_entry_log", "The climbing-wall entry scan occurred before the lunch receipt window."), ("north_locker_log", "The north locker was opened shortly after the aquarium exit.")),
        (("south_locker_log", "The south lockers were busy, but the entries do not concern this route."), ("tram_manifest", "The tram manifest lists group counts, not carried belongings."))),
    Archetype("thermos", ("metal thermos", "travel flask", "insulated bottle"),
        ("a dent beside the base", "a worn band of silver paint", "a cloudy mark on the cap"),
        ("on the benches outside the ice rink", "beside the tea kiosk rail", "under a table in the family lounge"),
        (B("cork_cap_wedge", "a thin cork wedge beneath the cap seal", "a grandparent added it to stop the cap leaking on train journeys", "a citrus tea smell", "refilled after skating and before the puppet show", "set down while removing gloves after the ice-rink session"),
         B("three_dots", "three blue enamel dots beneath the base", "the dots mark which flask belongs to the night-shift crew", "a removable tea strainer", "used after the laser show and before the tea kiosk purchase", "filled it at the kiosk shortly after the laser show"),
         B("red_gasket", "a hand-cut red gasket inside the lid", "the gasket was cut from a baking mat after the factory seal failed", "a cinnamon scent", "opened beside the family lounge after the carousel", "last used while sharing a drink after leaving the carousel")),
        (("rink_exit_log", "The ice-rink exit scan precedes the puppet-show admission."), ("tea_receipt", "A tea-kiosk receipt falls just after the laser-show exit.")),
        (("arcade_camera", "The arcade camera never faces the drink tables."), ("bakery_receipt", "The bakery receipt lists pastries only."))),
    Archetype("plush_toy", ("plush fox", "stuffed penguin", "soft toy rabbit"),
        ("one flattened ear", "a worn patch on its back", "a faded ribbon at the neck"),
        ("inside the soft-play shoe rack", "beside the story-stage curtain", "under a stroller bay bench"),
        (B("bell_removed", "an empty cloth loop where a bell was carefully removed", "the bell was removed because it woke a younger sibling at night", "a lavender sachet", "carried after story time and before the soft-play visit", "placed by the shoe rack while helping with boots after story time"),
         B("green_heart", "a green felt heart sewn beneath the left paw", "the heart was added after a hospital visit as a private good-luck mark", "a small fabric tag", "held during the parade before entering the stroller bay", "tucked into a stroller after the parade"),
         B("rice_weight", "a small rice-filled weight stitched into the lower seam", "the weight keeps the toy upright during video calls with a traveling parent", "a vanilla fabric scent", "used at the video booth after the puppet show", "set on a bench while packing snacks after the video booth")),
        (("story_stage_photo", "A stage photograph shows the toy present before the soft-play entry."), ("parade_camera", "The parade camera shows the toy before the stroller-bay stop.")),
        (("coat_check_log", "The coat check records clothing tags, not toys."), ("east_gate_camera", "The crowded east-gate view cannot distinguish plush toys."))),
    Archetype("notebook", ("pocket notebook", "spiral journal", "small sketchbook"),
        ("a water-warped cover", "a cracked elastic band", "a black ink stain on one corner"),
        ("on a ledge near the map room", "beneath a cafe stool", "beside the science-show seats"),
        (B("pages_removed", "three pages neatly removed after page twelve", "the pages were torn out to write directions for a younger relative", "a pressed leaf", "consulted after the map room and before the cafe stop", "used to give directions after leaving the map room"),
         B("thread_bookmark", "a purple thread bookmark knotted through the back binding", "the thread came from a costume made for a first stage performance", "a pencil stub", "sketched during the science show before visiting the cafe", "closed it as the science show ended and headed to the cafe"),
         B("mirror_note", "a reversed phone number written inside the rear cover", "it was written backward as a memory game shared with a grandparent", "two ticket stubs", "used after the memory exhibit and before the map room", "checked the number while leaving the memory exhibit")),
        (("map_room_entry", "The map-room entry precedes the cafe purchase by several minutes."), ("science_show_photo", "A show photograph places the notebook in use before the cafe visit.")),
        (("bookshop_till", "The bookshop sold many notebooks of this size."), ("west_hall_camera", "The west-hall camera cannot read anything on the notebook."))),
    Archetype("headphone_case", ("headphone case", "earbud pouch", "audio case"),
        ("a chipped hard-shell edge", "a rubbed-out logo", "a pale cord mark around the case"),
        ("beneath an arcade racing seat", "near the quiet-room doorway", "beside the tram waiting line"),
        (B("foam_notch", "a triangular notch cut from the inner foam", "the notch makes room for an earpiece modified after an ear injury", "a short charging cable", "used after the arcade race and before boarding the tram", "removed the headphones after the arcade race while waiting for the tram"),
         B("silver_tape", "a strip of silver tape under the hinge", "the tape silences a hinge click during library study sessions", "a spare silicone tip", "opened in the quiet room after the music show", "packed it while leaving the quiet room for the food hall"),
         B("braille_dot", "a raised glue dot beside the charging socket", "the dot makes the case easy to orient by touch without glasses", "a coiled adapter", "charged it after the planetarium and before the tram", "unplugged it at the planetarium lounge before walking to the tram")),
        (("tram_boarding_log", "The tram boarding scan follows the arcade-race session."), ("quiet_room_log", "The quiet-room entry follows the music-show exit.")),
        (("arcade_prize_log", "The prize desk records no audio equipment."), ("north_gate_camera", "The north-gate view is too wide to show a small case."))),
    Archetype("umbrella_sleeve", ("umbrella sleeve", "folding-umbrella cover", "rain sleeve"),
        ("a frayed mouth", "a pale water line", "a tiny burn mark near the hem"),
        ("hanging from the coat-rack rail", "under the indoor garden bench", "beside the rain-simulator exit"),
        (B("elastic_loop", "a green elastic loop sewn inside the mouth", "the loop attaches to a wheelchair bag so the sleeve cannot fall", "a folded drying cloth", "used after the rain simulator and before the garden cafe", "secured it while leaving the rain simulator"),
         B("waxed_seam", "a hand-waxed seam along the inner edge", "the seam was waxed after rain leaked onto a concert program", "a faint beeswax smell", "carried through the indoor garden before coat check", "folded it at the garden exit before using coat check"),
         B("yellow_snap", "a mismatched yellow snap hidden under the flap", "the snap came from a child's old raincoat during an emergency repair", "a paper transit sleeve", "opened after the water show and before the tram ride", "put it away while walking from the water show to the tram")),
        (("rain_sim_exit", "The rain-simulator exit scan precedes the garden-cafe receipt."), ("coat_check_log", "The coat-check timestamp follows the indoor-garden entry.")),
        (("weather_desk", "The weather desk notes indoor humidity only."), ("south_gate_camera", "The south-gate camera shows many closed umbrellas."))),
    Archetype("card_wallet", ("card wallet", "small pass holder", "zip card purse"),
        ("a peeling corner", "a scratched clear window", "a faded blue edge"),
        ("at the ticket-reload machine", "beneath a food-court counter", "beside the locker-payment kiosk"),
        (B("coin_pocket", "a foreign coin stitched into the lining", "the coin was sewn in as a keepsake from a first solo trip", "two expired transit cards", "used after the locker kiosk and before the food-court purchase", "returned it to a pocket after paying at the locker kiosk"),
         B("red_tab", "a red fabric tab behind the clear card window", "the tab helps a color-blind partner identify the shared family pass", "a folded receipt", "reloaded a pass after the carousel and before lunch", "used the reload machine while walking from the carousel to lunch"),
         B("split_lining", "a diagonal split deliberately left in the inner lining", "the split gives quick access to an emergency contact card", "a brass locker token", "opened after the first-aid desk and before the locker bank", "checked the emergency card while leaving first aid")),
        (("locker_payment_log", "The locker payment occurs before the food-court receipt."), ("reload_machine_log", "The pass reload follows the carousel exit scan.")),
        (("cash_machine_log", "The cash machine records no wallet description."), ("retail_camera", "The retail camera view is blocked at waist height."))),
    Archetype("lunch_bag", ("lunch bag", "insulated food tote", "small cooler bag"),
        ("a sauce stain near the base", "a creased silver lining", "a worn carrying handle"),
        ("under a picnic-zone table", "beside the cooking-show seats", "near the family-room counter"),
        (B("wooden_button", "a wooden button sewn inside the side pocket", "the button came from a late grandparent's coat and is kept as a lunch-time ritual", "a blue ice pack", "opened after the cooking show and before the picnic zone", "packed leftovers when the cooking show ended"),
         B("foil_patch", "a star-shaped foil patch beneath the inner base", "the patch covers a puncture made by a child's science project", "a striped napkin", "used in the family room before the puppet show", "set it down while warming food in the family room"),
         B("double_label", "a second name label hidden under the main label", "the older label was kept when the bag passed from one sibling to another", "a green snack box", "carried from the play area to the picnic tables", "opened it after leaving the play area")),
        (("cooking_show_photo", "A cooking-show photograph shows the bag before the picnic-zone stop."), ("family_room_log", "The family-room appliance log precedes the puppet show.")),
        (("restaurant_booking", "The restaurant booking contains no item details."), ("kitchen_till", "The kitchen till lists generic meals only."))),
    Archetype("console_pouch", ("game-console pouch", "handheld-game case", "gaming sleeve"),
        ("a pixel sticker shadow", "a compressed top edge", "a scratched zipper ring"),
        ("beneath an esports-viewing seat", "beside the retro-arcade counter", "near the charging-station bench"),
        (B("felt_divider", "a hand-cut orange felt divider inside the cartridge pocket", "the divider was made to separate a dyslexic child's school and game cards", "three game cartridges", "used after the esports match and before charging", "packed it as the esports match ended"),
         B("magnet_removed", "an empty circular recess where the closure magnet was removed", "the magnet was removed to protect a medical-device accessory carried nearby", "a braided charging lead", "opened near the charging station after the retro arcade", "unplugged the console after leaving the retro arcade"),
         B("score_card", "a tiny laminated score card beneath the lining", "the card preserves the score from a first tournament played with a cousin", "a cleaning cloth", "played after the tournament exhibit and before the food hall", "checked the score card while leaving the tournament exhibit")),
        (("charging_station_log", "The charging session follows the esports-match exit."), ("retro_arcade_log", "The arcade card was used before the charging-station session.")),
        (("prize_counter_log", "The prize counter issued toys, not consoles."), ("food_hall_camera", "The food-hall camera cannot distinguish small pouches."))),
)


NAMES = tuple("Nora Eli Mika Tomas Amina Benji Clara Dev Farah Gabe Hana Idris Juno Kai Lena Mateo Nia Omar Priya Quinn Rosa Sami Talia Uri Vera Wade Xena Yusuf Zoe Anika Bruno Celia Dario Esme Felix Greta Hugo Imani Jonas Keira".split())

BIOGRAPHIES = (
    "visiting with two cousins", "a university student on a day trip", "waiting for a family member",
    "attending a park workshop", "a parent near the play area", "traveling with a school group",
    "meeting friends after lunch", "a freelance illustrator", "an off-duty nurse", "a museum volunteer",
    "a delivery coordinator", "a music teacher", "a software tester", "a local baker",
    "a retired librarian", "a graduate researcher", "a youth football coach", "a theatre technician",
    "a community gardener", "a visiting accountant",
)

NEUTRAL_EVENTS = (
    "The queue shuffles forward.", "A child points toward the item's color.", "Rain taps the glass roof.",
    "An announcement echoes from the tram hall.", "Someone checks the closing clock.",
    "The counter printer clicks once.", "A stroller passes the office door.", "The nearby cafe grinder starts.",
    "A staff radio crackles in the corridor.", "The waiting area grows quieter.", "A locker door closes nearby.",
    "The overhead lights brighten.", "A tour group crosses the lobby.", "A lost-property cart rattles past.",
    "A claimant folds a park map.", "The service bell shifts on the counter.", "Music starts in the atrium.",
    "A cleaner replaces a floor sign.", "The queue rope is moved aside.", "A clock chimes the quarter hour.",
)

# Eight render variants per category; semantic selection happens in the engine.
RESPONSE_TEMPLATES = {
    topic: tuple(f"{topic}_response_{index}" for index in range(8))
    for topic in ("concealed_detail", "relationship", "loss_timeline", "last_use", "recovery_scene")
}
