"""Shared mod-aware-fallback helpers for translate modules.

Per the project's data-first principle (see memory:
"Rely on game data, let the LLM translate"), translate modules emit
RimWorld def names with the mod-aware label and description supplied
by the def index built in `extract/mods.py`. When neither is
available, we fall back to a humanised slug so output stays readable
without committing to a curated translation table.

Resolution order for inline contexts (gear summary, hediff/gene
lists): label -> humanised slug.

Resolution order for long-form contexts (apparel block, xenotype):
description -> label -> humanised slug.
"""

from __future__ import annotations


def humanise(def_name: str, strip_prefixes: tuple[str, ...] = ()) -> str:
  """Camel-case-split a def name into lowercase words.

  ``strip_prefixes`` removes the first matching prefix (e.g.
  ``"Apparel_"``, ``"Gun_"``) before splitting so the output reads as
  plain English: ``Apparel_PowerArmor`` -> ``power armor``. Embedded
  underscores collapse to single spaces: ``Beauty_Beautiful`` ->
  ``beauty beautiful``.
  """
  s = def_name
  for prefix in strip_prefixes:
    if s.startswith(prefix):
      s = s[len(prefix):]
      break
  acc: list[str] = []
  for i, ch in enumerate(s):
    if i > 0 and ch.isupper() and not s[i - 1].isupper():
      acc.append(" ")
    acc.append(ch)
  out = "".join(acc).lower().replace("_", " ")
  return " ".join(out.split())


def label_for(
  def_name: str,
  labels: dict[str, str] | None = None,
  strip_prefixes: tuple[str, ...] = (),
) -> str:
  if labels and def_name in labels:
    return labels[def_name]
  return humanise(def_name, strip_prefixes)


def description_for(
  def_name: str,
  descriptions: dict[str, str] | None = None,
  labels: dict[str, str] | None = None,
  strip_prefixes: tuple[str, ...] = (),
) -> str:
  if descriptions and def_name in descriptions:
    return descriptions[def_name]
  return label_for(def_name, labels, strip_prefixes)
