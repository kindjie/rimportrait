"""Apparel def -> short visual descriptive phrase.

Seeded from the user's spec. Unknown defs fall back to a humanised
slug of the def name. Quality/HP/material values are intentionally
not surfaced - the spec strips game-only numerics.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..records import ApparelItem


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
