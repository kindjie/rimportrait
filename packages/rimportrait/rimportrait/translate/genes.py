"""Gene def -> label phrase.

Per the data-first principle, all genes the pawn carries are surfaced
with their mod-aware label (humanised-slug fallback) so the downstream
LLM can decide what's visually relevant. A small skip-list filters
obviously-non-visual mechanical genes to bound prompt context size.
"""

from __future__ import annotations

from collections.abc import Iterable

from rimsave.records import Gene
from ._common import label_for


# Substring patterns that mark a gene as purely mechanical (no
# visual implication). Skip-list shape so modded genes aren't
# silently dropped — only obvious internal/metabolic/skill genes
# are filtered. Visible body-mod genes (PiercingSpine, LongjumpLegs,
# Tinderskin, DarkVision, ScarLess, etc.) stay in the output.
_IGNORED_PATTERNS: tuple[str, ...] = (
  # Immune / metabolic / sleep
  "Immunity",
  "ToxResist",
  "ToxResistance",
  "ChemicalDependency",
  "Sleep_",
  "LowSleep",
  "VeryLowSleep",
  "ArchiteMetabolism",
  # Sanguophage mechanics — xenotype line already conveys the visual
  "Hemogenic",
  "HemogenDrain",
  "Bloodfeeder",
  "Coagulate",
  "GeneImplanter",
  "Deathrest",
  # Sense / mental — no visible correlate
  "PsychicSensitivity",
  "PsychicAbility",
  "PsySensitive",
  "Pyrophobia",
  "UVSensitivity",
  # Physiology that doesn't change silhouette
  "WoundHealing",
  "Aggressive",
  "Robust",
  "FastRunner",
  "StrongMeleeDamage",
  "NonSenescent",
  # Skill aptitudes (numeric bonuses, no visual)
  "AptitudeStrong",
  "AptitudeBad",
  "AptitudeNeutral",
  "AptitudeLearning",
)


def _is_ignored(def_name: str) -> bool:
  return any(p in def_name for p in _IGNORED_PATTERNS)


def is_visible_gene_def(def_name: str) -> bool:
  """Public predicate: True when a gene def name carries a visible
  body-mod / pigment / silhouette signal (and is NOT in the
  skip-list of internal / metabolic / aptitude genes). Used by the
  xenotype renderer to emit a per-pawn visible-xenogene signature."""
  return not _is_ignored(def_name)


def describe_genes(
  genes: Iterable[Gene],
  labels: dict[str, str] | None = None,
  endogenes_only: bool = False,
) -> list[str]:
  """List humanised gene labels, filtered by the visibility skip-list.

  When ``endogenes_only=True`` xenogenes are excluded; used by the
  Body section so it doesn't duplicate the xenogene signature now
  surfaced on the ``Race/xenotype`` line. Endogenes (the pawn's
  inherited baseline traits) stay because they still convey
  silhouette / pigment cues independent of the xenotype."""
  out: list[str] = []
  for g in genes:
    if _is_ignored(g.def_name):
      continue
    if endogenes_only and g.is_xenogene:
      continue
    out.append(g.label or label_for(g.def_name, labels))
  return out
