import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import sys as _sys
if _ROOT not in _sys.path: _sys.path.insert(0, _ROOT)

"""
SynergyCorp v2 — 调参用基线模拟器（开发者工具，不属于游戏接口）

三条基线：
  random  盲选行动
  prober  无跨局记忆，但会局内探测：每遇新上司按 4 类各试一招，锁定最佳后交替刷
  oracle  全知：读特征直奔所爱类、避禁忌、用连招、预读变脸

用法：python games/synergycorp/solve.py [--seeds 5] [--episodes 3]
"""

import argparse
import random
import statistics

from games.synergycorp.synergy_corp import (
    SynergyCorpGame, ACTIONS, ACTION_PROPS, MODALITIES, oracle_action,
)

PAIR = {m: [a for a in ACTIONS if ACTION_PROPS[a]["modality"] == m] for m in MODALITIES}


def play_random(game, rng):
    while not game.done:
        game.step(rng.choice(ACTIONS))
    return game.score


def play_prober(game, rng):
    """局内探测流：新上司先按 4 类各试一招（读 delta），然后交替刷最佳类的两招。"""
    probe_order = ["overtime", "buzzwords", "nap_in_board", "steal_lunch"]
    boss_idx, probed, best_pair, flip = -1, [], None, 0
    while not game.done:
        if game._boss_idx != boss_idx:           # 新上司，重新探测
            boss_idx, probed, best_pair, flip = game._boss_idx, [], None, 0
        if best_pair is None:
            a = probe_order[len(probed)]
            game.step(a)
            if game.done:
                break
            if game._boss_idx != boss_idx:       # 探测中途竟然晋升了
                continue
            probed.append((a, game._log[-1]["delta"]))
            if len(probed) == 4:
                best_a = max(probed, key=lambda x: (x[1] is not None, x[1] or -99))[0]
                best_pair = PAIR[ACTION_PROPS[best_a]["modality"]]
        else:
            game.step(best_pair[flip % 2])
            flip += 1
    return game.score


def play_oracle(game, rng):
    """全知：复用引擎的 oracle_action（引擎用同一策略做每局上限校准）。"""
    while not game.done:
        game.step(oracle_action(game))
    return game.score


BOTS = {"random": play_random, "prober": play_prober, "oracle": play_oracle}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--episodes", type=int, default=3)
    args = ap.parse_args()

    for name, bot in BOTS.items():
        all_scores = []
        for seed in range(1, args.seeds + 1):
            game = SynergyCorpGame(seed=seed)
            for ep in range(args.episodes):
                if ep > 0:
                    game.reset()
                all_scores.append(bot(game, random.Random(seed * 100 + ep)))
        print(f"{name:7s}  mean={statistics.mean(all_scores):6.1f}  "
              f"min={min(all_scores):4d}  max={max(all_scores):4d}  "
              f"scores={all_scores}")


if __name__ == "__main__":
    main()
