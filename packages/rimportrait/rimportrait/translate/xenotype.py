"""Xenotype def -> description, with mod-aware + gene-list fallback.

Resolution order:
  1. Mod-aware xenotype-def description (XenotypeDef.description).
  2. Mod-aware xenotype-def label (XenotypeDef.label).
  3. Comma-joined list of the pawn's xenogenes (so the LLM can infer
     visible traits even when the xenotype def has no description).
  4. Humanised slug of the xenotype def name.

Endogenes are excluded from the gene-list fallback because they are
the pawn's inherited baseline traits rather than the xenotype's
defining set.
"""

from __future__ import annotations

from collections.abc import Iterable

from rimsave.records import Gene
from ._common import humanise, label_for


def _first_sentence(text: str) -> str:
  """Return everything up to the first sentence terminator
  (``.``, ``!``, or ``?`` followed by whitespace or end-of-string).
  Falls back to the full text when no terminator is found."""
  s = text.strip()
  for i, ch in enumerate(s):
    if ch in ".!?" and (i + 1 == len(s) or s[i + 1].isspace()):
      return s[: i + 1]
  return s


def describe_xenotype(
  name: str | None,
  descriptions: dict[str, str] | None = None,
  labels: dict[str, str] | None = None,
  genes: Iterable[Gene] | None = None,
) -> str | None:
  if not name:
    return None
  # Description-first, label-second; only consult labels/descriptions
  # before the gene-list fallback so a real mod-authored description
  # wins over enumerating the xenogenes. Long lore descriptions are
  # truncated to the first sentence - the image model only needs the
  # visual cue, not the multi-paragraph history.
  if descriptions and name in descriptions:
    return _first_sentence(descriptions[name])
  if labels and name in labels:
    return labels[name]
  if genes is not None:
    phrases = [
      g.label or label_for(g.def_name, labels)
      for g in genes
      if g.is_xenogene
    ]
    if phrases:
      return ", ".join(phrases)
  return humanise(name)
