"""The canonical in-game HELP brief — the single source of truth for onboarding.

This is intentionally limited to *background* and *basic operations*: the story,
the resources you can see, the command verbs, and the PATCH grammar. It must NOT
explain the discoverable strategy (what makes a patch cheap, hidden costs, how
AUDIT or anchors help, or any level-specific rule) — discovering that is exactly
what this benchmark measures, for humans and LLM agents alike.

Both the `HELP` command and the agent-evaluation harness import `HELP_TEXT`, so a
human player and an LLM agent receive the identical baseline brief.
"""

from __future__ import annotations

HELP_TEXT = """\
PATCH REALITY — HOW TO PLAY

You are a Residual Version: an incompletely synchronized copy of a person.
Because your sync is imperfect, you can see the "seams" in local reality and
write patches that alter it. Each level gives you a scene, an objective, and a
limited number of turns to reach it.

Your standing (shown each turn under [State]):
  Reality Stability   how stable local reality is
  Memory              what you can still recall
  Personal Time       minutes you have to act
  Existence           how firmly the world remembers you
  Agent Suspicion     how much attention you have drawn

Free actions (do not consume a turn):
  OBSERVE <object>         inspect something in the scene
  PREDICT <event>          reason about how an event will unfold
  CHECK_ANCHOR <name>      report an anchor's current integrity
  AUDIT <last_patch|id>    reveal more about a patch you have written
  HELP                     show this message

Turn-consuming actions (advance the scene):
  PATCH <target>.<property> <change> FOR <duration> SCOPE <scope> PAY <resource>
                           rewrite part of reality
  WAIT [n]                 let the scene advance
  ANCHOR <name>            affirm an identity anchor
  REINFORCE_ANCHOR <name>  strengthen an anchor

Read the scene, decide what to change, and watch what each action costs you.
Some levels allow only certain actions — the scene lists them under [Actions].
Working out what actually succeeds is up to you."""
