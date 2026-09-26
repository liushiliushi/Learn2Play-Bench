from .catnip_singularity import (
    CatnipSingularityGame,
    CatnipSingularityEasyGame,
    CatnipSingularityHardGame,
)
from .play import play_python_game


GAME_REGISTRY = {
    "catnip_singularity": CatnipSingularityGame,
    "catnip": CatnipSingularityGame,
    "catnip_singularity_easy": CatnipSingularityEasyGame,
    "catnip_easy": CatnipSingularityEasyGame,
    "catnip_singularity_hard": CatnipSingularityHardGame,
    "catnip_hard": CatnipSingularityHardGame,
}


def load_game(game_name, seed=None):
    game_cls = GAME_REGISTRY.get(game_name)
    if game_cls is None:
        available = ", ".join(sorted(GAME_REGISTRY.keys()))
        raise ValueError(
            f"Unknown python game '{game_name}'. Available games: {available}"
        )
    return game_cls(seed=seed)
