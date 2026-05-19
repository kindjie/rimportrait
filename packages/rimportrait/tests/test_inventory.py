from __future__ import annotations

from rimsave.records import InventoryItem
from rimportrait.translate.inventory import (
  describe_inventory,
  describe_inventory_item,
)


def test_single_item_uses_humanised_def_when_no_labels():
  it = InventoryItem("MealSimple", stack_count=1)
  assert describe_inventory_item(it) == "meal simple"


def test_single_item_uses_mod_label_when_provided():
  it = InventoryItem("MealSimple", stack_count=1)
  labels = {"MealSimple": "simple meal"}
  assert describe_inventory_item(it, labels) == "simple meal"


def test_stack_count_prefix_when_more_than_one():
  it = InventoryItem("MealSimple", stack_count=3)
  assert describe_inventory_item(it) == "3× meal simple"


def test_unknown_def_humanised():
  it = InventoryItem("ModdedTrinketWidget", stack_count=1)
  assert describe_inventory_item(it) == "modded trinket widget"


def test_stuff_qualifier_prefixes_phrase():
  it = InventoryItem("ReinforcedBarrel", stack_count=1, stuff="Plasteel")
  assert describe_inventory_item(it) == "plasteel reinforced barrel"


def test_describe_inventory_list_threads_labels():
  items = (
    InventoryItem("MealSimple", stack_count=2),
    InventoryItem("WakeUp", stack_count=1),
  )
  labels = {"MealSimple": "simple meal", "WakeUp": "wake-up"}
  assert describe_inventory(items, labels) == [
    "2× simple meal",
    "wake-up",
  ]
