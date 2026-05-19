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
# visual or bearing implication). Skip-list shape, not allow-list, so
# modded genes aren't silently dropped from prompts.
_IGNORED_PATTERNS: tuple[str, ...] = (
  "Immunity",
  "ToxResist",
  "ToxResistance",
  "ChemicalDependency",
  "Sleep_",
  "Hemogenic",  # mechanic; sanguophage visuals come from xenotype
)


def _is_ignored(def_name: str) -> bool:
  return any(p in def_name for p in _IGNORED_PATTERNS)


def describe_genes(
  genes: Iterable[Gene],
  labels: dict[str, str] | None = None,
) -> list[str]:
  out: list[str] = []
  for g in genes:
    if _is_ignored(g.def_name):
      continue
    out.append(g.label or label_for(g.def_name, labels))
  return out
