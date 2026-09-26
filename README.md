# Learn2Play Bench

This repository contains the 20 text-based game templates used in Learn2Play Bench. It is a code snapshot for anonymous peer review. It contains no human-player records or API credentials.

## Play a game

Use Python 3.10 or newer. The games in this snapshot use the standard library.

```bash
python play.py poisoner --seed 2 --episode 1 --lang en
```

Enter an action at the prompt. The commands `valid`, `status`, `score`, and `quit` show available actions, the current state, the score, and the final score. The official game IDs and seeds are listed in [`default_seeds.json`](default_seeds.json).

To play another episode of a game, keep the seed and change `--episode`. The game rules remain the same across episodes, while the visible instance changes in the re-shuffled games.
