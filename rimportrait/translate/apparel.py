"""Apparel def -> label phrase, plus material/color/style qualifier.

Per the project's data-first principle, the rendered phrase is the
mod-aware def label (with a humanised-slug fallback) instead of a
curated visual table; the downstream LLM does the visual translation.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..colors import rgba_to_name
from ..records import ApparelItem
from ._common import description_for, humanise, label_for
from .condition import describe_condition
from .stuff import describe_stuff


_APPAREL_PREFIXES: tuple[str, ...] = ("Apparel_",)


# Patterns that mark an apparel item as silhouette-level utility gear
# (belts, packs, baby carriers, head-mounted optics) rather than a
# clothing or armor layer. Substring match so modded variants like
# `SBC_BabyCarrier` or `Foo_JumpPack` are caught alongside vanilla defs.
_UTILITY_PATTERNS: tuple[str, ...] = (
  "Belt",
  "Bandolier",
  "Carrier",
  "Gunlink",
  "JumpPack",
)


def is_utility_apparel(def_name: str) -> bool:
  return any(p in def_name for p in _UTILITY_PATTERNS)


def is_baby_carrier(def_name: str) -> bool:
  """Match vanilla Apparel_BabyCarrier and modded variants (SBC_*).

  Substring match on ``BabyCarrier`` is intentionally broad so any
  mod that follows the naming convention is caught automatically.
  """
  return "BabyCarrier" in def_name


def describe_apparel_item(
  item: ApparelItem,
  labels: dict[str, str] | None = None,
) -> str:
  if item.label:
    return item.label
  return label_for(item.def_name, labels, _APPAREL_PREFIXES)


def describe_apparel(
  items: Iterable[ApparelItem],
  labels: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
  """Return [(display_label, visual_summary), ...] for the apparel block."""
  out: list[tuple[str, str]] = []
  for it in items:
    nicer = (
      it.label
      or (labels.get(it.def_name) if labels else None)
      or humanise(it.def_name, _APPAREL_PREFIXES)
    )
    out.append((nicer, describe_apparel_item(it, labels)))
  return out


def long_form_apparel_phrase(
  item: ApparelItem,
  descriptions: dict[str, str] | None = None,
  labels: dict[str, str] | None = None,
) -> str:
  return description_for(
    item.def_name, descriptions, labels, _APPAREL_PREFIXES
  )


def qualifier_for_apparel(item: ApparelItem) -> str | None:
  """Comma-joined visual qualifiers: material, color, style, condition.

  Returns None when an item carries no qualifier signal. Used both for
  the inline gear summary line and the long-form apparel block.
  """
  bits: list[str] = []
  stuff = describe_stuff(item.stuff)
  if stuff:
    bits.append(stuff)
  if item.color is not None:
    bits.append(rgba_to_name(item.color))
  style = describe_style_def(item.style_def)
  if style:
    bits.append(style)
  condition = describe_condition(item.health, item.max_health)
  if condition:
    bits.append(condition)
  if not bits:
    return None
  return ", ".join(bits)


def describe_style_def(style_def: str | None) -> str | None:
  """Render an ideology style variant ('Samurai', 'Rustic', ...) inline.

  RimWorld's styleDef is shaped ``<ThingName>_<StyleName>`` (e.g.
  ``PrestigeMarineHelmet_Samurai``). We surface just the style suffix
  as "<Style> style"; if the def has no underscore we treat it as a
  bare style name.
  """
  if not style_def:
    return None
  tail = style_def.rsplit("_", 1)[-1]
  if not tail:
    return None
  return f"{tail} style"
