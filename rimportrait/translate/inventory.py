"""Inventory item def -> short visual phrase.

Inventory items are typically meals, drugs, medicine, ammo, components,
or spare apparel/weapons stashed in the pawn's pack. We render them as
a compact 'carrying' line so the image-prompt LLM knows the silhouette
includes a visible pack of supplies.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..records import InventoryItem
from .stuff import describe_stuff


# Curated phrasings for common inventory items. Anything not in the
# table degrades to a humanised def name, which works well for vanilla
# (MealSimple -> "meal simple", GoJuice -> "go juice).
_VISUAL: dict[str, str] = {
  "MealSimple": "simple meal",
  "MealFine": "fine meal",
  "MealLavish": "lavish meal",
  "MealSurvivalPack": "survival pack ration",
  "Pemmican": "pemmican",
  "Kibble": "kibble",
  "Beer": "beer bottle",
  "Smokeleaf": "smokeleaf joint",
  "GoJuice": "vial of go-juice",
  "WakeUp": "wake-up dose",
  "Penoxycyline": "penoxycyline pill",
  "Yayo": "yayo dose",
  "Flake": "flake dose",
  "Luciferium": "luciferium dose",
  "Ambrosia": "ambrosia fruit",
  "PsychiteTea": "psychite tea",
  "Chocolate": "chocolate bar",
  "Medicine": "industrial medicine kit",
  "MedicineHerbal": "herbal medicine bundle",
  "MedicineIndustrial": "industrial medicine kit",
  "MedicineUltratech": "glittertech medicine vial",
  "ComponentIndustrial": "industrial component",
  "ComponentSpacer": "spacer component",
  "Plasteel": "plasteel ingot",
  "Steel": "steel ingot",
  "Silver": "silver coin",
  "Gold": "gold bar",
  "Uranium": "uranium ingot",
  "Jade": "jade lump",
  "Cloth": "bolt of cloth",
  "Hyperweave": "bolt of hyperweave",
  "Synthread": "bolt of synthread",
  "ReinforcedBarrel": "reinforced gun barrel",
  "Shell_HighExplosive": "high-explosive mortar shell",
  "Shell_Incendiary": "incendiary mortar shell",
  "Shell_EMP": "EMP mortar shell",
  "Shell_AntigrainWarhead": "antigrain warhead",
}


def describe_inventory_item(item: InventoryItem) -> str:
  base = _VISUAL.get(item.def_name) or _humanise(item.def_name)
  stuff = describe_stuff(item.stuff)
  if stuff:
    base = f"{stuff} {base}"
  if item.stack_count > 1:
    return f"{item.stack_count}× {base}"
  return base


def describe_inventory(items: Iterable[InventoryItem]) -> list[str]:
  return [describe_inventory_item(it) for it in items]


def _humanise(def_name: str) -> str:
  acc: list[str] = []
  for i, ch in enumerate(def_name):
    if i > 0 and ch.isupper() and not def_name[i - 1].isupper():
      acc.append(" ")
    acc.append(ch)
  return "".join(acc).lower()
