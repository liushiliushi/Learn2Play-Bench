"""
Learn2Play Bench 交互式游戏入口

用法：
    python play.py <game> [--seed SEED] [--show_valid]

游戏列表：
    catnip, synergycorp, abyss, relay, gemforge, trader,
    surveyors, dungeon, aqueduct, ancientpalace,
    tideharvest, primordialsoup, hydrosync, festival_line_producer,
    midnight_control_room, signal_aquarium, roadside_observatory, mola_tea,
    lost_and_found

示例：
    python play.py dungeon --seed 42 --show_valid
    python play.py gemforge
    python play.py catnip --seed 42

游戏中输入行动名执行，输入 valid 查看可用行动，输入 status 查看状态，quit/q 退出。
"""

import argparse
import json
import sys
from pathlib import Path

# 把项目根目录加入路径
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def _default_seed(game):
    """每个正式基准游戏固定一个 seed（default_seeds.json）；不带 --seed 时用它。
    表外游戏返回 None（保持随机）。"""
    try:
        with open(ROOT / "default_seeds.json", encoding="utf-8") as f:
            return json.load(f).get("seeds", {}).get(game)
    except Exception:
        return None


def load_game(game_name: str, seed, lang='zh'):
    if game_name == "synergycorp":
        from games.synergycorp.synergy_corp import SynergyCorpGame
        return SynergyCorpGame(seed=seed, lang=lang)
    if game_name == "cathedral_of_echoes":
        from games.cathedral_of_echoes.cathedral_of_echoes import CathedralOfEchoesGame
        return CathedralOfEchoesGame(seed=seed, lang=lang)
    elif game_name == "catnip":
        sys.path.insert(0, str(ROOT / "games" / "catnip-singularity" / "src" / "python_games"))
        from catnip_singularity import CatnipSingularityGame
        return CatnipSingularityGame(seed=seed, lang=lang)
    elif game_name == "abyss":
        from games.abysminer.abyss_miner import AbyssMinerGame
        return AbyssMinerGame(seed=seed)
    elif game_name == "relay":
        from games.relay.relay import WastelandRelayGame
        return WastelandRelayGame(seed=seed)
    elif game_name == "gemforge":
        from games.gemforge.gemforge import GemForgeGame
        return GemForgeGame(seed=seed, lang=lang)
    elif game_name == "trader":
        from games.trader.trader import TraderGame
        return TraderGame(seed=seed)
    elif game_name == "surveyors":
        from games.surveyors.surveyors import SurveyorCorpsGame
        return SurveyorCorpsGame(seed=seed)
    elif game_name == "dungeon":
        from games.dungeon.dungeon import DungeonLabyrinthGame
        return DungeonLabyrinthGame(seed=seed, lang=lang)
    elif game_name == "aqueduct":
        from games.aqueduct.aqueduct import AqueductGame
        return AqueductGame(seed=seed)
    elif game_name == "aquarium":
        from games.aquarium.aquarium import AquariumGame
        return AquariumGame(seed=seed, lang=lang)
    elif game_name == "ancientpalace":
        from games.ancientpalace.ancientpalace import AncientPalaceGame
        return AncientPalaceGame(seed=seed, lang=lang)
    elif game_name == "tideharvest":
        from games.tideharvest.tideharvest import TideHarvestGame
        return TideHarvestGame(seed=seed)
    elif game_name == "primordialsoup":
        from games.primordialsoup.primordialsoup import PrimordialSoupGame
        return PrimordialSoupGame(seed=seed, lang=lang)
    elif game_name == "hydrosync":
        from games.hydrosync.hydrosync import HydroSyncGame
        return HydroSyncGame(seed=seed)
    elif game_name == "patch_reality":
        from games.patch_reality.patch_reality import PatchRealityGame
        return PatchRealityGame(seed=seed, lang=lang)
    elif game_name == "patch_reality_moderate":
        from games.patch_reality.patch_reality import PatchRealityGame
        return PatchRealityGame(seed=seed, mode="moderate", lang=lang)
    elif game_name == "patch_reality_hard":
        from games.patch_reality.patch_reality import PatchRealityGame
        return PatchRealityGame(seed=seed, mode="hard", lang=lang)
    elif game_name == "dreamgarden":
        from games.dreamgarden.dreamgarden import DreamGardenGame
        return DreamGardenGame(seed=seed, lang=lang)
    elif game_name == "castaway":
        from games.castaway.castaway import CastawayGame
        return CastawayGame(seed=seed, lang=lang)
    elif game_name == "clockwork":
        from games.clockwork.clockwork import ClockworkGame
        return ClockworkGame(seed=seed, lang=lang)
    elif game_name == "undertow":
        from games.undertow.undertow import UndertowGame
        return UndertowGame(seed=seed, lang=lang)
    elif game_name == "flotsam":
        from games.flotsam.flotsam import FlotsamGame
        return FlotsamGame(seed=seed, lang=lang)
    elif game_name == "grapevine":
        from games.grapevine.grapevine import GrapevineGame
        return GrapevineGame(seed=seed, lang=lang)
    elif game_name == "bourse_echoes":
        from games.bourse_echoes.bourse_echoes import BourseEchoesGame
        return BourseEchoesGame(seed=seed, lang=lang)
    elif game_name == "wildcraft":
        from games.wildcraft.wildcraft import WildcraftGame
        return WildcraftGame(seed=seed, lang=lang)
    elif game_name == "lighthouse_quorum":
        from games.lighthouse_quorum.lighthouse_quorum import LighthouseQuorumGame
        return LighthouseQuorumGame(seed=seed, lang=lang)
    elif game_name == "bindweaver_loom":
        from games.bindweaver_loom.bindweaver_loom import BindweaverLoomGame
        return BindweaverLoomGame(seed=seed, lang=lang)
    elif game_name == "seance_choir":
        from games.seance_choir.seance_choir import SeanceChoirGame
        return SeanceChoirGame(seed=seed, lang=lang)
    elif game_name == "aetherforge":
        from games.aetherforge.aetherforge import AetherforgeGame
        return AetherforgeGame(seed=seed, lang=lang)
    elif game_name == "tessera_weald":
        from games.tessera_weald.tessera_weald import TesseraWealdGame
        return TesseraWealdGame(seed=seed, lang=lang)
    elif game_name == "bellfounder":
        from games.bellfounder.bellfounder import BellfounderGame
        return BellfounderGame(seed=seed, lang=lang)
    elif game_name == "cinder_envoy":
        from games.cinder_envoy.cinder_envoy import CinderEnvoyGame
        return CinderEnvoyGame(seed=seed, lang=lang)
    elif game_name == "wayfinder_loom":
        from games.wayfinder_loom.wayfinder_loom import WayfinderLoomGame
        return WayfinderLoomGame(seed=seed, lang=lang)
    elif game_name == "codex_errant":
        from games.codex_errant.codex_errant import CodexErrantGame
        return CodexErrantGame(seed=seed, lang=lang)
    elif game_name == "rosetta_engine":
        from games.rosetta_engine.rosetta_engine import RosettaEngineGame
        return RosettaEngineGame(seed=seed, lang=lang)
    elif game_name == "tidewright":
        from games.tidewright.tidewright import TidewrightGame
        return TidewrightGame(seed=seed, lang=lang)
    elif game_name == "loomwright":
        from games.loomwright.loomwright import LoomwrightGame
        return LoomwrightGame(seed=seed, lang=lang)
    elif game_name == "ecosphere":
        from games.ecosphere.ecosphere import EcosphereGame
        return EcosphereGame(seed=seed, lang=lang)
    elif game_name == "hauntedinn":
        from games.hauntedinn.hauntedinn import HauntedInnGame
        return HauntedInnGame(seed=seed, lang=lang)
    elif game_name == "hidden_concord":
        from games.hidden_concord.hidden_concord import HiddenConcordGame
        return HiddenConcordGame(seed=seed, lang=lang)
    elif game_name == "augur_court":
        from games.augur_court.augur_court import AugurCourtGame
        return AugurCourtGame(seed=seed, lang=lang)
    elif game_name == "lampwright_circuit":
        from games.lampwright_circuit.lampwright_circuit import LampwrightCircuitGame
        return LampwrightCircuitGame(seed=seed, lang=lang)
    elif game_name == "tideglass_rite":
        from games.tideglass_rite.tideglass_rite import TideglassRiteGame
        return TideglassRiteGame(seed=seed, lang=lang)
    elif game_name == "tallowright_abacus":
        from games.tallowright_abacus.tallowright_abacus import TallowrightAbacusGame
        return TallowrightAbacusGame(seed=seed, lang=lang)
    elif game_name == "cellarwright":
        from games.cellarwright.cellarwright import CellarwrightGame
        return CellarwrightGame(seed=seed, lang=lang)
    elif game_name == "crypt_taboo":
        from games.crypt_taboo.crypt_taboo import CryptOfTaboosGame
        return CryptOfTaboosGame(seed=seed, lang=lang)
    elif game_name == "colossus":
        from games.colossus.colossus import ColossusHuntGame
        return ColossusHuntGame(seed=seed, lang=lang)
    elif game_name == "plague":
        from games.plague.plague import PlagueDoctorGame
        return PlagueDoctorGame(seed=seed, lang=lang)
    elif game_name == "cartomancer":
        from games.cartomancer.cartomancer import CartomancerGame
        return CartomancerGame(seed=seed)
    elif game_name == "runesmith":
        from games.runesmith.runesmith import RunesmithGame
        return RunesmithGame(seed=seed)
    elif game_name == "harvest_moon":
        from games.harvest_moon.harvest_moon import HarvestMoonGame
        return HarvestMoonGame(seed=seed)
    elif game_name == "modelkeeper":
        from games.modelkeeper.modelkeeper import ModelkeeperGame
        return ModelkeeperGame(seed=seed, lang=lang)
    elif game_name == "modelkeeper_hard":
        from games.modelkeeper.modelkeeper import ModelkeeperGame
        return ModelkeeperGame(seed=seed, mode="hard", lang=lang)
    elif game_name == "modelkeeper_expert":
        from games.modelkeeper.modelkeeper import ModelkeeperGame
        return ModelkeeperGame(seed=seed, mode="expert", lang=lang)
    elif game_name == "modelkeeper_hard_dense":
        # Diagnostic feedback-ablation variant (NOT an official benchmark game):
        # same hard machine/scoring/probe budget, row-level score feedback in EXAM.
        from games.modelkeeper.modelkeeper import ModelkeeperGame
        return ModelkeeperGame(seed=seed, mode="hard", feedback_mode="row_score", lang=lang)
    elif game_name == "modelkeeper_hard_teacher":
        # Diagnostic feedback-ablation variant (NOT an official benchmark game):
        # like _dense but also reveals the correct row values (teacher upper bound).
        from games.modelkeeper.modelkeeper import ModelkeeperGame
        return ModelkeeperGame(seed=seed, mode="hard", feedback_mode="row_answer", lang=lang)
    elif game_name == "emotion_market":
        from games.emotion_market.emotion_market import EmotionMarketGame
        return EmotionMarketGame(seed=seed, lang=lang)
    elif game_name == "oracle_bones":
        from games.oracle_bones.oracle_bones import OracleBonesGame
        return OracleBonesGame(seed=seed, lang=lang)
    elif game_name == "priming_ritual":
        from games.priming_ritual.priming_ritual import PrimingRitualGame
        return PrimingRitualGame(seed=seed, lang=lang)
    elif game_name == "silk_code":
        from games.silk_code.silk_code import SilkCodeGame
        return SilkCodeGame(seed=seed, lang=lang)
    elif game_name == "festival_line_producer":
        from games.festival_line_producer.festival_line_producer import FestivalLineProducerGame
        return FestivalLineProducerGame(seed=seed, lang=lang)
    elif game_name == "midnight_control_room":
        from games.midnight_control_room.midnight_control_room import MidnightControlRoomGame
        return MidnightControlRoomGame(seed=seed, lang=lang)
    elif game_name == "signal_aquarium":
        from games.signal_aquarium.signal_aquarium import SignalAquariumGame
        return SignalAquariumGame(seed=seed, lang=lang)
    elif game_name == "roadside_observatory":
        from games.roadside_observatory.roadside_observatory import RoadsideObservatoryGame
        return RoadsideObservatoryGame(seed=seed, lang=lang)
    elif game_name == "mola_tea":
        from games.mola_tea.mola_tea import MolaTeaGame
        return MolaTeaGame(seed=seed, lang=lang)
    elif game_name == "lost_and_found":
        from games.lost_and_found.lost_and_found import LostAndFoundGame
        return LostAndFoundGame(seed=seed, lang=lang)
    elif game_name == "poisoner":
        from games.poisoner.poisoner import PoisonerGame
        return PoisonerGame(seed=seed, lang=lang)
    elif game_name == "hezu":
        from games.hezu.hezu import HezuGame
        return HezuGame(seed=seed, lang=lang)
    elif game_name == "loop":
        from games.loop.loop import TheLoopGame
        return TheLoopGame(seed=seed, lang=lang)
    elif game_name == "duel":
        from games.duel.duel import TheDuelGame
        return TheDuelGame(seed=seed, lang=lang)
    elif game_name == "redeye":
        from games.redeye.redeye import RedEyeGame
        return RedEyeGame(seed=seed, lang=lang)
    elif game_name == "butterfly":
        from games.butterfly.butterfly import ButterflyGardenGame
        return ButterflyGardenGame(seed=seed, lang=lang)
    else:
        raise ValueError(
            f"未知游戏：{game_name}\n"
            f"可选：catnip, synergycorp, abyss, relay, gemforge, trader, "
            f"surveyors, dungeon, aqueduct, ancientpalace, tideharvest, patch_reality, patch_reality_moderate, patch_reality_hard, "
            f"primordialsoup, hydrosync, dreamgarden, clockwork, undertow, ecosphere, "
            f"cartomancer, runesmith, harvest_moon, modelkeeper, modelkeeper_hard, modelkeeper_expert, oracle_bones, priming_ritual, silk_code, festival_line_producer, midnight_control_room, signal_aquarium, roadside_observatory, mola_tea, lost_and_found"
        )


def print_valid(actions, game=None):
    all_actions_fn = getattr(game, 'get_all_actions', None)
    display = [a for a in (all_actions_fn() if all_actions_fn else actions) if a != "status"]
    labeler = getattr(game, 'get_action_label', None)
    lang = getattr(game, '_lang', 'zh')
    parts = []
    for i, a in enumerate(display):
        label = labeler(a) if labeler else a
        parts.append(f"{i+1}.{label}")
    prefix = "Actions: " if lang == 'en' else "可用行动："
    print(prefix + "  ".join(parts))


def replay_json(game, commands):
    """Replay public commands; expose only observations, actions and score.

    EOF means an intermediate replay, never a completed benchmark episode.
    Explicit quit applies exactly the same finalization as the text interface.
    This is a transport for automated players, not a second game engine.
    """
    if not isinstance(commands, list) or not all(isinstance(x, str) for x in commands):
        raise ValueError("Replay input must be a JSON list of command strings")
    obs, _ = game.reset()
    ended = bool(game.done)
    for command in commands:
        command = command.strip()
        if ended:
            # Match the text CLI: once terminal, unread stdin is not executed.
            # Callers retain the original submitted history for audit.
            break
        if not command or command.lower() in {"valid", "score"}:
            continue
        if command.lower() in {"quit", "q"}:
            if hasattr(game, "finalize") and not game.done:
                game.finalize()
                obs = game.step("status")[0]
            ended = True
            break
        current = [a for a in game.get_valid_actions() if a != "status"]
        all_actions = getattr(game, "get_all_actions", None)
        display = [a for a in all_actions() if a != "status"] if all_actions else current
        parts = command.split()
        if parts[0].isdigit() and 0 <= int(parts[0]) - 1 < len(display):
            command = display[int(parts[0]) - 1] + (" " + parts[1] if len(parts) > 1 else "")
        obs, _, done, _ = game.step(command)
        ended = bool(done)
    return {"observation": obs, "valid_actions": [] if ended else game.get_valid_actions(),
            "score": game.score, "done": ended, "game_done": bool(game.done)}


def main():
    parser = argparse.ArgumentParser(description="Learn2Play Bench 交互式游戏入口")
    parser.add_argument("game", help="游戏名称")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--show_valid", action="store_true", default=True, help="每步自动显示可用行动")
    parser.add_argument("--lang", default="zh", choices=["zh", "en"], help="游戏语言 (zh/en)，支持 gemforge/dungeon/synergycorp/catnip/ancientpalace/patch_reality(_moderate/_hard)")
    parser.add_argument("--episode", type=int, default=None, help="（仅每回合重生布局的游戏，如 wildcraft/flotsam）指定第几回合的布局，规律不变；用于跨回合验证")
    parser.add_argument("--replay-json", action="store_true", help="Replay a JSON command list from stdin; only explicit quit or game termination completes an episode")
    parser.add_argument("--no-finalize", action="store_true", help="EOF/quit 时不自动演完剩余回合（供 webplay 等交互前端显示中间态；基准评测勿用，否则停手刷分漏洞会复活）")
    args = parser.parse_args()

    # 不指定 --seed 时，用该游戏固定的默认 seed（default_seeds.json）。
    if args.seed is None:
        args.seed = _default_seed(args.game)

    try:
        game = load_game(args.game, args.seed, lang=args.lang)
    except ValueError as e:
        print(e)
        sys.exit(1)

    # 仅显式传入 --episode 时生效：让本次运行使用指定回合的重生布局（隐藏规律仍由 seed 固定）
    if args.episode is not None and hasattr(game, "_episode"):
        game._episode = args.episode - 1

    if args.replay_json:
        import json
        print(json.dumps(replay_json(game, json.load(sys.stdin)), ensure_ascii=False))
        return

    obs, info = game.reset()
    lang = getattr(game, '_lang', 'zh')
    seed_str = args.seed if args.seed is not None else 'random'
    if lang == 'en':
        print(f"Game: {args.game}  |  Seed: {seed_str}  |  quit to exit")
    else:
        print(f"游戏：{args.game}  |  Seed：{seed_str}  |  退出：q")
    print("-" * 60)
    print(obs)

    current_valid = [a for a in game.get_valid_actions() if a != "status"]
    # 固定行动集用于显示和数字映射（若游戏提供）
    all_actions_fn = getattr(game, 'get_all_actions', None)
    display_actions = [a for a in all_actions_fn() if a != "status"] if all_actions_fn else current_valid
    print_valid(current_valid, game)

    while True:
        try:
            command = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            if not args.no_finalize and hasattr(game, "finalize") and not game.done:
                game.finalize()
                print("\n" + game.step("status")[0])  # 打印结算后的最终棋盘，杜绝自数旧棋盘刷分
                print(f"\nQuit. Final score: {game.score}" if lang == 'en' else f"\n退出。最终得分：{game.score}")
            else:
                # --no-finalize（交互前端）：只显示当前态，不演完、不报"最终分"（裸退出标记会被前端剥除）
                print("\nQuit." if lang == 'en' else "\n退出。")
            break

        if not command:
            continue

        if command.lower() in ("quit", "q"):
            if not args.no_finalize and hasattr(game, "finalize") and not game.done:
                game.finalize()
                print("\n" + game.step("status")[0])  # 打印结算后的最终棋盘，杜绝自数旧棋盘刷分
            if lang == 'en':
                print(f"Quit. Final score: {game.score}")
            else:
                print(f"退出。最终得分：{game.score}")
            break

        if command.lower() == "valid":
            print_valid(current_valid, game)
            continue

        if command.lower() == "score":
            if lang == 'en':
                print(f"Score: {game.score}  |  Steps: {game.turn_count}/{game.MAX_TURNS}")
            else:
                print(f"得分：{game.score}  |  回合：{game.turn_count}/{game.MAX_TURNS}")
            continue

        if command.lower() == "status":
            obs, _, _, _ = game.step("status")
            print(obs)
            continue

        # 数字 → 行动名（用固定 display_actions 映射，编号不随状态变化）
        parts = command.split()
        if parts[0].isdigit():
            idx = int(parts[0]) - 1
            if 0 <= idx < len(display_actions):
                qty_suffix = f" {parts[1]}" if len(parts) > 1 else ""
                command = display_actions[idx] + qty_suffix

        prev_score = game.score
        obs, reward, done, info = game.step(command)
        print("\n" + obs)

        if "delta" in info and not done:
            d = info["delta"]
            inf = info["influence"]
            thr = info["threshold"]
            d_str = f"{d:+.0f}" if d != 0 else "±0"
            if lang == 'en':
                print(f"  Approval: {d_str}  →  {inf:.0f}/{thr}  |  Promoted: {game.score}/5")
            else:
                print(f"  好感度：{d_str}  →  {inf:.0f}/{thr}  |  已晋升：{game.score}/5")
        else:
            delta = game.score - prev_score
            if delta != 0:
                if lang == 'en':
                    print(f"  Score change: {delta:+d}")
                else:
                    print(f"  得分变化：{delta:+d}")

        if done:
            print("=" * 60)
            if lang == 'en':
                print(f"Game over! Final score: {game.score}")
            else:
                print(f"游戏结束！最终得分：{game.score}")
            print("=" * 60)
            break

        current_valid = [a for a in info.get("valid", game.get_valid_actions()) if a != "status"]
        # 数字映射必须与 print_valid 打印的列表逐回合保持一致：有固定行动集的游戏也要刷新，
        # 因为 catnip 等游戏的 get_all_actions 会随阶段变化（选品种→主循环→收服菜单），
        # 只在开局抓取一次会让主循环里的数字错映射到旧阶段的行动（如“3”→品种字母“c”）。
        display_actions = ([a for a in all_actions_fn() if a != "status"]
                           if all_actions_fn else current_valid)
        if args.show_valid:
            print_valid(current_valid, game)


if __name__ == "__main__":
    main()
