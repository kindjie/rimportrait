from __future__ import annotations

from rimportrait.records import InventoryItem
from rimportrait.translate.inventory import (
  describe_inventory,
  describe_inventory_item,
)


def test_single_item_no_count_prefix():
  it = InventoryItem("MealSimple", stack_count=1)
  assert describe_inventory_item(it) == "simple meal"


def test_stack_count_prefix_when_more_than_one():
  it = InventoryItem("MealSimple", stack_count=3)
  assert describe_inventory_item(it) == "3× simple meal"


def test_unknown_def_humanised():
  it = InventoryItem("ModdedTrinketWidget", stack_count=1)
  assert describe_inventory_item(it) == "modded trinket widget"


def test_stuff_qualifier_prefixes_phrase():
  it = InventoryItem("ReinforcedBarrel", stack_count=1, stuff="Plasteel")
  assert describe_inventory_item(it) == (
    "plasteel reinforced gun barrel"
  )


def test_describe_inventory_list():
  items = (
    InventoryItem("MealSimple", stack_count=2),
    InventoryItem("WakeUp", stack_count=1),
  )
  assert describe_inventory(items) == ["2× simple meal", "wake-up dose"]
