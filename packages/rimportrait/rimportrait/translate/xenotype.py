"""Xenotype def -> description + visible-xenogene signature.

Output shape:
  ``<base text>. Visible xenogene traits: <gene1>, <gene2>, ...``

Base text resolution:
  1. Mod-aware XenotypeDef.description, truncated to its first sentence
     (subsequent sentences are usually multi-paragraph history/society
     lore that the image model can't use).
  2. Mod-aware XenotypeDef.label.
  3. Humanised slug of the xenotype def name.

The signature suffix is always appended when the pawn carries any
visible xenogenes, regardless of which base text was used. This is
the per-pawn visual anchor — the description's first sentence often
leads with lore (``Sanguophages are a type of archotech-enhanced
xenohuman.``) which tells the image model nothing visual on its
own, so the xenogene list grounds it in actual silhouette cues
(piercing spine, ageless, attractive, dark vision, scarless).

Endogenes are excluded from the signature because they're the
pawn's inherited baseline traits rather than the xenotype's
defining set; the body section already lists them.
"""

from __future__ import annotations

from collections.abc import Iterable

from rimsave.records import Gene
from ._common import humanise, label_for
from .genes import is_visible_gene_def


def _first_sentence(text: str) -> str:
  """Return everything up to the first sentence terminator
  (``.``, ``!``, or ``?`` followed by whitespace or end-of-string).
  Falls back to the full text when no terminator is found."""
  s = text.strip()
  for i, ch in enumerate(s):
    if ch in ".!?" and (i + 1 == len(s) or s[i + 1].isspace()):
      return s[: i + 1]
  return s


def _visible_xenogene_signature(
  genes: Iterable[Gene] | None,
  labels: dict[str, str] | None,
) -> str | None:
  """Comma-joined labels of the pawn's visible xenogenes (filtered
  with the same skip-list the body block uses). Returns None when
  no genes are provided or every xenogene is non-visual."""
  if genes is None:
    return None
  out: list[str] = []
  for g in genes:
    if not g.is_xenogene:
      continue
    if not is_visible_gene_def(g.def_name):
      continue
    out.append(g.label or label_for(g.def_name, labels))
  if not out:
    return None
  return ", ".join(out)


def describe_xenotype(
  name: str | None,
  descriptions: dict[str, str] | None = None,
  labels: dict[str, str] | None = None,
  genes: Iterable[Gene] | None = None,
) -> str | None:
  if not name:
    return None
  # Real lore-level text first; the humanised slug is reserved for
  # the final fallback below, because the render-layer wrapper
  # already emits ``<xenotype-def> - <desc>`` and would otherwise
  # repeat the slug ('Sanguophage - sanguophage Visible xenogene...').
  base: str | None = None
  if descriptions and name in descriptions:
    base = _first_sentence(descriptions[name])
  elif labels and name in labels:
    base = labels[name]
  signature = _visible_xenogene_signature(genes, labels)
  if base and signature:
    return f"{base} Visible xenogene traits: {signature}."
  if base:
    return base
  if signature:
    return f"Visible xenogene traits: {signature}."
  return humanise(name)
