"""Inventory item def -> label phrase.

Inventory items are typically meals, drugs, medicine, ammo, components,
or spare apparel/weapons stashed in the pawn's pack. We render them as
a compact 'carrying' line using the mod-aware label so the
image-prompt LLM knows the silhouette includes a visible pack of
supplies; the downstream LLM does the visual translation step.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..records import InventoryItem
from ._common import label_for
from .stuff import describe_stuff


def describe_inventory_item(
  item: InventoryItem,
  labels: dict[str, str] | None = None,
) -> str:
  base = label_for(item.def_name, labels)
  stuff = describe_stuff(item.stuff)
  if stuff:
    base = f"{stuff} {base}"
  if item.stack_count > 1:
    return f"{item.stack_count}× {base}"
  return base


def describe_inventory(
  items: Iterable[InventoryItem],
  labels: dict[str, str] | None = None,
) -> list[str]:
  return [describe_inventory_item(it, labels) for it in items]
