"""CLI entry point for human play.

    python -m patch_reality                 # play the full campaign
    python -m patch_reality --level PATH     # play a single level
    python -m patch_reality --list           # list available levels
"""

from __future__ import annotations

import argparse
import glob
import os

from .campaign import CampaignRunner
from .engine import GameEngine
from .io.cli_adapter import CliAdapter
from .level_loader import LevelLoader

_LEVELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "levels")


def _discover_levels() -> list[str]:
    return sorted(glob.glob(os.path.join(_LEVELS_DIR, "*.json")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="patch-reality", description=__doc__)
    parser.add_argument("--level", help="Path to a single level YAML to play.")
    parser.add_argument("--levels-dir", default=_LEVELS_DIR,
                        help="Directory of level YAML files for campaign mode.")
    parser.add_argument("--list", action="store_true", help="List levels and exit.")
    args = parser.parse_args(argv)

    loader = LevelLoader()

    if args.list:
        for path in sorted(glob.glob(os.path.join(args.levels_dir, "*.json"))):
            level = loader.load(path)
            print(f"{level.id}: {level.name} (phase {level.phase})")
        return 0

    if args.level:
        level = loader.load(args.level)
        result = GameEngine(level, CliAdapter()).run()
        return 0 if result.objective_complete else 1

    paths = sorted(glob.glob(os.path.join(args.levels_dir, "*.json")))
    if not paths:
        print(f"No level files found in {args.levels_dir}.")
        return 1
    levels = [loader.load(p) for p in paths]
    cli = CliAdapter()
    runner = CampaignRunner(levels, io_factory=lambda level, idx: cli)
    campaign = runner.run()

    print("\n" + "#" * 48)
    print(f"Campaign complete. Levels cleared: "
          f"{sum(1 for r in campaign.level_results if r.objective_complete)}"
          f"/{len(levels)}")
    print(f"Total reward: {campaign.total_reward:.0f}")
    if campaign.failed_at:
        print(f"Run ended at: {campaign.failed_at}")
    print("#" * 48)
    return 0 if campaign.completed_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
