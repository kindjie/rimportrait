"""Xenotype def name -> visual descriptive phrase.

The image model does not know RimWorld lore. Each xenotype maps to a
description grounded in visible anatomy and bearing only. Phrases come
straight from the spec.
"""

from __future__ import annotations


XENOTYPE_VISUAL: dict[str, str] = {
  "Baseliner": "ordinary human",
  "Sanguophage": (
    "ageless vampire-like transhuman, predatory elegance, "
    "fangs only if listed"
  ),
  "Yttakin": (
    "large furred humanoid, shaggy animal-like features, "
    "tail/fur only if listed"
  ),
  "Hussar": (
    "combat-engineered soldier with aggressive military bearing"
  ),
  "Genie": (
    "delicate engineered intellectual/craftsperson, fragile build, "
    "precise expression"
  ),
  "Pigskin": "pig-like humanoid with rough practical features",
  "Highmate": (
    "beautiful social companion type with soft, warm presence"
  ),
  "Impid": (
    "heat-adapted humanoid with harsh fire-touched presence; "
    "horns/tail only if listed"
  ),
  "Dirtmole": (
    "underground-adapted human, compact miner silhouette, "
    "pale/squinting only if supported"
  ),
  "Neanderthal": "robust archaic human, broad and rugged",
  "Waster": (
    "polluted-world survivor, harsh toxic-wasteland bearing; "
    "respirator only if listed"
  ),
}


_UNKNOWN = (
  "unknown xenotype; infer only from listed genes, health, "
  + "apparel, and profile"
)


def describe_xenotype(name: str | None) -> str:
  if not name:
    return _UNKNOWN
  if name in XENOTYPE_VISUAL:
    return XENOTYPE_VISUAL[name]
  return (
    f"{name} (custom xenotype; infer from listed genes, health, "
    + "apparel, and profile)"
  )
