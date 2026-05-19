"""Weapon def -> label phrase + material/color qualifier.

Per the data-first principle, the rendered phrase uses the mod-aware
def label (with humanised-slug fallback) and the downstream LLM does
the visual translation step.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..colors import rgba_to_name
from ..records import Weapon
from ._common import label_for
from .stuff import describe_stuff


_WEAPON_PREFIXES: tuple[str, ...] = ("Gun_", "MeleeWeapon_", "Bow_")


def describe_weapon(
  w: Weapon,
  labels: dict[str, str] | None = None,
) -> str:
  # Persona weapons keep their proper name when present in addition
  # to the def's label/humanised name so the LLM gets both signals.
  base = label_for(w.def_name, labels, _WEAPON_PREFIXES)
  if w.label and w.label.lower() != base.lower():
    return f"{w.label} ({base})"
  return base


def describe_weapons(
  weapons: Iterable[Weapon],
  labels: dict[str, str] | None = None,
) -> list[str]:
  return [describe_weapon(w, labels) for w in weapons]


def qualifier_for_weapon(w: Weapon) -> str | None:
  """Comma-joined material/color qualifiers for a weapon, or None."""
  bits: list[str] = []
  stuff = describe_stuff(w.stuff)
  if stuff:
    bits.append(stuff)
  if w.color is not None:
    bits.append(rgba_to_name(w.color))
  if not bits:
    return None
  return ", ".join(bits)
