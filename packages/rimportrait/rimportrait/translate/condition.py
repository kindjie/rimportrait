"""Map an item's health/max-health ratio to a coarse condition label.

The user-supplied phrasing thresholds (from prior conversation):
  ratio >= 0.80  ->  no signal, omit
  0.50 <= r < 0.80 ->  "worn"
  0.25 <= r < 0.50 ->  "battered"
  ratio <  0.25  ->  "ruined"

Rationale for keeping a tiny phrasing table here (against the
data-first principle that retired the curated translation tables in
Step 4): the raw HP integer carries no portrait-friendly meaning on
its own, and the LLM has no way to ground a ratio against
RimWorld's default MaxHitPoints. Three coarse buckets is the
minimal translation that makes the data legible without inventing
imagery.
"""

from __future__ import annotations


def describe_condition(
  health: int | None, max_health: int | None
) -> str | None:
  if health is None or max_health is None or max_health <= 0:
    return None
  ratio = health / max_health
  if ratio >= 0.80:
    return None
  if ratio >= 0.50:
    return "worn"
  if ratio >= 0.25:
    return "battered"
  return "ruined"
