"""Weapon def -> short visual descriptive phrase."""

from __future__ import annotations

from collections.abc import Iterable

from ..records import Weapon


WEAPON_VISUAL: dict[str, str] = {
  # Spacer / charge
  "Gun_ChargeRifle": "sleek futuristic charge rifle",
  "Gun_ChargeLance": "long sleek futuristic charge lance",
  "Gun_BeamRifle": "advanced energy beam rifle",
  "Gun_BeamRepeater": "advanced energy beam repeater",
  "Gun_HeavyChargeBlaster": "heavy mounted charge blaster",
  "Gun_PulseRifle": "futuristic pulse rifle",
  "Gun_GaussRifle": "long-barreled gauss rifle",
  # Industrial / military
  "Gun_AssaultRifle": "modern assault rifle",
  "Gun_SniperRifle": "long-barreled sniper rifle",
  "Gun_BoltActionRifle": "wooden-stock bolt-action rifle",
  "Gun_MachinePistol": "compact machine pistol",
  "Gun_Autopistol": "modern autopistol",
  "Gun_Revolver": "heavy revolver",
  "Gun_PumpShotgun": "pump-action shotgun",
  "Gun_ChainShotgun": "compact chain shotgun",
  "Gun_HeavySMG": "boxy heavy SMG",
  "Gun_LMG": "heavy belt-fed light machine gun",
  "Gun_Minigun": "rotary minigun",
  "Gun_IncendiaryLauncher": "shoulder-fired incendiary launcher",
  "Gun_SmokeLauncher": "shoulder-fired smoke launcher",
  "Gun_DoomsdayRocket": "single-shot doomsday rocket launcher",
  "Gun_TripleRocket": "triple-tube rocket launcher",
  "Gun_ChargeShotgun": "futuristic charge shotgun",
  # Melee
  "MeleeWeapon_Knife": "utility knife",
  "MeleeWeapon_Gladius": "short gladius blade",
  "MeleeWeapon_LongSword": "long sword",
  "MeleeWeapon_Mace": "blunt mace",
  "MeleeWeapon_WarHammer": "two-handed war hammer",
  "MeleeWeapon_Spear": "long-shafted spear",
  "MeleeWeapon_Club": "rough wooden club",
  "MeleeWeapon_PlasmaSword": "humming plasma blade",
  "MeleeWeapon_Zeushammer": "massive electrified hammer",
  "MeleeWeapon_MonoSword": "thin mono-edged sword",
  # Bows
  "Bow_Short": "short bow",
  "Bow_Recurve": "recurve bow",
  "Bow_Great": "great bow",
}


def describe_weapon(w: Weapon) -> str:
  base = WEAPON_VISUAL.get(w.def_name)
  if base:
    # Persona weapons keep their proper name when present.
    if w.label and w.label.lower() != _humanise(w.def_name):
      return f"{w.label} ({base})"
    return base
  if w.label:
    return w.label
  return _humanise(w.def_name)


def describe_weapons(weapons: Iterable[Weapon]) -> list[str]:
  return [describe_weapon(w) for w in weapons]


def _humanise(def_name: str) -> str:
  s = def_name
  for prefix in ("Gun_", "MeleeWeapon_", "Bow_"):
    if s.startswith(prefix):
      s = s[len(prefix):]
  acc: list[str] = []
  for i, ch in enumerate(s):
    if i > 0 and ch.isupper() and not s[i - 1].isupper():
      acc.append(" ")
    acc.append(ch)
  return "".join(acc).lower()
