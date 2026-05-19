"""Hediff def -> visible body change description.

A hediff is anything the game models as a 'health diff' on a pawn:
implants, injuries, missing parts, diseases, tolerances. Only those
that produce a visible silhouette or face change should reach the
portrait prompt.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..records import Hediff


# Exact-match descriptive table for well-known visible hediffs.
VISIBLE: dict[str, str] = {
  "MissingBodyPart": "missing limb or body part",
  "BionicEye": "smooth metallic bionic eye",
  "ArchotechEye": "luminous archotech eye with subtle inner glow",
  "BionicArm": "sleek bionic arm",
  "ArchotechArm": "ornate archotech arm with subtle inner glow",
  "BionicLeg": "sleek bionic leg",
  "ArchotechLeg": "ornate archotech leg with subtle inner glow",
  "BionicSpine": "augmented spine bearing, upright posture",
  "BionicJaw": "metallic prosthetic jaw",
  "BionicEar": "metallic prosthetic ear",
  "PowerClaw": "heavy industrial power-claw hand",
  "DrillArm": "industrial drill arm",
  "FieldHand": "bulky field-work prosthetic hand",
  "ElbowSpike": "elbow spike",
  "KneeSpike": "knee spike",
  "GhoulPlating": "rough ghoul plating",
  "Scarring": "visible scar",
  "Burn": "visible burn scar",
  "Crush": "visible crush injury",
  "Crack": "visible crack injury",
  "Cut": "visible cut",
  "Gunshot": "visible gunshot scar",
  "Stab": "visible stab scar",
  "Bite": "visible bite scar",
  "Frostbite": "visible frostbite damage",
}


# Substring patterns that mark a hediff as visible. Catches mod variants
# and DLC additions without listing every def.
_VISIBLE_PATTERNS: tuple[str, ...] = (
  "Bionic", "Archotech", "Prosthetic", "PowerClaw", "DrillArm",
  "Spike", "Plating", "Carapace", "Talon", "Tentacle",
)


_IGNORED_PATTERNS: tuple[str, ...] = (
  "Immunity", "Tolerance", "Dependency", "Resistance",
  "Hangover", "Catharsis", "Withdrawal", "Pregnant",
)


def _is_visible_pattern(def_name: str) -> bool:
  return any(p in def_name for p in _VISIBLE_PATTERNS)


def _is_ignored_pattern(def_name: str) -> bool:
  return any(p in def_name for p in _IGNORED_PATTERNS)


def describe_hediffs(hediffs: Iterable[Hediff]) -> list[str]:
  out: list[str] = []
  for h in hediffs:
    if _is_ignored_pattern(h.def_name):
      continue
    if h.def_name in VISIBLE:
      desc = VISIBLE[h.def_name]
      if h.body_part:
        desc = f"{desc} ({h.body_part})"
      out.append(desc)
      continue
    if _is_visible_pattern(h.def_name):
      label = h.label or _humanise(h.def_name)
      if h.body_part:
        label = f"{label} ({h.body_part})"
      out.append(label)
  return out


def _humanise(def_name: str) -> str:
  # Strip common prefixes, split CamelCase into lowercase words.
  s = def_name
  for prefix in ("Hediff_", "BodyPart_"):
    if s.startswith(prefix):
      s = s[len(prefix):]
  acc: list[str] = []
  for i, ch in enumerate(s):
    if i > 0 and ch.isupper() and not s[i - 1].isupper():
      acc.append(" ")
    acc.append(ch)
  return "".join(acc).lower()
