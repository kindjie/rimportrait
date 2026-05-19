"""Apparel def -> short visual descriptive phrase.

Seeded from the user's spec. Unknown defs fall back to a humanised
slug of the def name. Quality/HP/material values are intentionally
not surfaced - the spec strips game-only numerics.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..colors import rgba_to_name
from ..records import ApparelItem
from .stuff import describe_stuff


APPAREL_VISUAL: dict[str, str] = {
  # Prestige / royal
  "Apparel_PrestigeReconArmor": (
    "sleek high-status lightweight powered combat armor"
  ),
  "Apparel_PrestigeReconHelmet": (
    "high-status lightweight combat helmet, usually carried "
    "or pushed back"
  ),
  "Apparel_PrestigeCataphractArmor": (
    "ornate heavy high-tech powered cataphract armor"
  ),
  "Apparel_PrestigeCataphractHelmet": (
    "bulky high-tech armored cataphract helmet, usually carried "
    "or open-faced"
  ),
  "Apparel_PrestigeMarineArmor": "ornate heavy futuristic marine armor",
  "Apparel_PrestigeMarineHelmet": (
    "futuristic marine helmet, usually carried or open-faced"
  ),
  # Military / spacer
  "Apparel_FlakVest": "layered military flak vest",
  "Apparel_FlakJacket": "practical layered military flak jacket",
  "Apparel_FlakPants": "reinforced military flak leg armor",
  "Apparel_ArmorHelmetSimple": (
    "simple combat helmet, usually carried or pushed back"
  ),
  "Apparel_ArmorHelmetFlak": (
    "military flak helmet, usually carried or pushed back"
  ),
  "Apparel_ArmorMarine": "heavy futuristic marine combat armor",
  "Apparel_ArmorHelmetMarine": (
    "heavy futuristic marine helmet, usually carried or open-faced"
  ),
  "Apparel_ArmorRecon": "sleek lightweight powered recon armor",
  "Apparel_ArmorHelmetRecon": (
    "lightweight recon helmet, usually carried or pushed back"
  ),
  "Apparel_ArmorCataphract": "very heavy high-tech powered cataphract armor",
  "Apparel_ArmorHelmetCataphract": (
    "bulky high-tech cataphract helmet, usually carried "
    "or open-faced"
  ),
  # Soft / civilian
  "Apparel_BasicShirt": "plain practical shirt",
  "Apparel_CollarShirt": "buttoned collared shirt",
  "Apparel_TShirt": "plain T-shirt",
  "Apparel_Pants": "practical work pants",
  "Apparel_Jacket": "practical jacket",
  "Apparel_Parka": "heavy insulated parka",
  "Apparel_Duster": "long protective duster",
  "Apparel_Tribalwear": "loose tribal clothing",
  "Apparel_TribalHeaddress": (
    "tribal headdress, usually carried, hung at neck, or set aside"
  ),
  "Apparel_CowboyHat": "wide-brimmed cowboy hat, sometimes in hand",
  "Apparel_Tuque": "wool tuque, sometimes in hand",
  "Apparel_VisageMask": "ornate visage mask (rarely worn over face)",
  "Apparel_AuthorityCap": "formal authority cap",
  "Apparel_RobeRoyal": "long royal robe",
  "Apparel_Corset": "fitted corset",
  "Apparel_VeilHood": "loose veiled hood, often pushed back",
  # Belts / gear
  "Apparel_ShieldBelt": "compact belt-mounted energy shield device",
  "Apparel_SmokepopBelt": "small belt-mounted smoke deployment pack",
  "Apparel_BabyCarrier": (
    "visible reinforced baby carrier strapped over clothing or armor"
  ),
  "SBC_BabyCarrier": (
    "visible reinforced baby carrier strapped over clothing or armor"
  ),
  "Apparel_Bandolier": (
    "ammo bandolier strapped across the torso"
  ),
  "Apparel_Cape": "long flowing cape clasped at the shoulders",
  "Apparel_PowerArmor": (
    "heavy powered combat armor with rigid plating"
  ),
  "Apparel_PowerArmorHelmet": (
    "fully enclosed power-armor helmet, usually carried or "
    "pushed back"
  ),
  "Apparel_ArmorMarineHelmetPrestige": (
    "ornate prestige marine helmet, usually carried or "
    "open-faced"
  ),
  "Apparel_ArmorMarinePrestige": "ornate prestige marine armor",
  # Gunlink head wearables
  "Apparel_Gunlink": (
    "subtle targeting visor or temple-mounted optic that leaves "
    "the face visible"
  ),
  "Apparel_PsyfocusHelmet": (
    "ornate psyfocus helmet, often carried or pushed back"
  ),
  "Apparel_BroadwrapHat": "broad-brimmed wrap hat, sometimes in hand",
}


def describe_apparel_item(item: ApparelItem) -> str:
  base = APPAREL_VISUAL.get(item.def_name)
  if base:
    return base
  if item.label:
    return item.label
  return _humanise(item.def_name)


def describe_apparel(items: Iterable[ApparelItem]) -> list[tuple[str, str]]:
  """Return [(display_label, visual_summary), ...] for the apparel block."""
  out: list[tuple[str, str]] = []
  for it in items:
    label = it.label or _humanise(it.def_name)
    out.append((label, describe_apparel_item(it)))
  return out


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


def qualifier_for_apparel(item: ApparelItem) -> str | None:
  """Comma-joined visual qualifiers: material, color, style.

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


def _humanise(def_name: str) -> str:
  s = def_name
  if s.startswith("Apparel_"):
    s = s[len("Apparel_"):]
  acc: list[str] = []
  for i, ch in enumerate(s):
    if i > 0 and ch.isupper() and not s[i - 1].isupper():
      acc.append(" ")
    acc.append(ch)
  return "".join(acc).lower()
