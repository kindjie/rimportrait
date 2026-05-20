"""Hediff def -> label phrase.

A hediff is anything the game models as a 'health diff' on a pawn:
implants, injuries, missing parts, diseases, tolerances. Per the
data-first principle we surface the mod-aware label of every hediff
the pawn carries; a skip-list excludes obviously-non-visual mechanical
states (immunities, tolerances, withdrawals) to bound prompt context.

Drug-high hediffs (vanilla `*High`, `Drunk`, modded `HighOn*`) are
partitioned out by `partition_chemical_state` so the render layer
can surface them on their own expression-cue line.
"""

from __future__ import annotations

from collections.abc import Iterable

from rimsave.records import Hediff
from ._common import label_for


_HEDIFF_PREFIXES: tuple[str, ...] = ("Hediff_",)


# Skip-list of obviously-non-visual hediff patterns. Substring match
# so mod variants are caught alongside vanilla. Visible body changes
# (BionicEye, PowerClaw, ScarMild, missing limbs, etc.) stay in the
# output; only internal organs / brain implants / metabolic states
# / numeric tolerances are filtered.
_IGNORED_PATTERNS: tuple[str, ...] = (
  # Numeric / mechanical tolerances and saving throws
  "Immunity",
  "Tolerance",
  "Dependency",
  "Resistance",
  "Hangover",
  "Catharsis",
  "Withdrawal",
  "Pregnant",
  # Internal organ implants — no external silhouette change
  "GastroAnalyzer",
  "NuclearStomach",
  "DetoxifierKidney",
  "DetoxifierLung",
  "ScanHeart",
  "Joywire",
  "AestheticNose",
  "AestheticShaper",
  "LearningAssistant",
  "NeuralCalculator",
  # Brain implants / psy-class hediffs
  "Psylink",
  "Psychic",  # PsychicSpeed, PsychicSensitivity, PsychicReader, ...
  # Transient/metabolic states with no visible cue
  "Lactating",
  "Glucosoid",
  "GenesRegrowing",
  "Regrowing",
  "Regenerat",  # Regenerating, Regeneration*
  "Xenogerm",   # XenogermReplicating - transient gene-rewrite state
  # RimTalk artifact hediff (not a real body change)
  "Persona",
)


def _is_ignored(def_name: str) -> bool:
  return any(p in def_name for p in _IGNORED_PATTERNS)


# Body parts whose hediffs don't change the silhouette (internal
# organs + tiny appendages buried under clothing/armor). A hediff
# attached to one of these parts is filtered out regardless of the
# def name — catches modded implants the def-name skip-list misses.
_INVISIBLE_BODY_PARTS: frozenset[str] = frozenset({
  # Internal organs
  "Brain", "Stomach", "Liver", "Kidney", "Lung", "Heart", "Spleen",
  "Intestine", "Intestines", "Pancreas",
  # Tiny appendages hidden by clothing/armor
  "LittleToe", "FourthToe", "MiddleToe", "SecondToe", "BigToe",
  "Toe", "Pinky", "RingFinger", "MiddleFinger", "IndexFinger",
  "Thumb", "Finger",
})


def _has_invisible_part(body_part: str | None) -> bool:
  """Detect hediffs attached to organs / digits that don't affect
  the portrait silhouette. Matches case-insensitively against a
  curated set so 'left fourth toe' and 'Stomach' both filter out."""
  if not body_part:
    return False
  # Normalise: 'left fourth toe' -> 'FourthToe' (the canonical
  # RimWorld body-part def slug). We compare against both the raw
  # string and a CamelCase normalised form.
  candidates = {body_part}
  parts = body_part.replace("-", " ").split()
  if parts:
    # Drop side prefixes (left/right/upper/lower); keep the noun.
    side = {"left", "right", "upper", "lower"}
    keep = [w for w in parts if w.lower() not in side]
    candidates.add("".join(w.capitalize() for w in keep))
    candidates.add(keep[-1].capitalize() if keep else "")
  return any(c in _INVISIBLE_BODY_PARTS for c in candidates)


def is_pilot_state(def_name: str) -> bool:
  """Detect the Odyssey gravship pilot-implant hediff family.

  Matches the vanilla ``PilotAssistant`` neural-interface implant
  plus any modded pilot-class hediff via substring on ``Pilot``.
  The predicate is only called on hediff defs, so the broad match
  is safe.
  """
  return "Pilot" in def_name


def is_shambler_state(def_name: str) -> bool:
  """Detect the Anomaly Shambler reanimation hediff family.

  Matches the vanilla ``Shambler`` def and the closely-related
  ``ShamblerCorpse`` plus any modded variant with the substring,
  so re-animated/mutated states are promoted to a dedicated line
  rather than blending with permanent body changes.
  """
  return "Shambler" in def_name


def is_drug_high(def_name: str) -> bool:
  """Detect drug-induced expression states.

  Covers vanilla ``YayoHigh``/``GoJuiceHigh``/etc., the standalone
  ``Drunk`` def, and the modded ``HighOn*`` convention. The match is
  intentionally narrow — non-drug defs that happen to share these
  substrings shouldn't sneak in.
  """
  if def_name == "Drunk":
    return True
  if def_name.startswith("HighOn"):
    return True
  if def_name.endswith("High"):
    return True
  return False


def _format(h: Hediff, labels: dict[str, str] | None) -> str:
  base = h.label or label_for(h.def_name, labels, _HEDIFF_PREFIXES)
  if h.body_part:
    return f"{base} ({h.body_part})"
  return base


def describe_hediffs(
  hediffs: Iterable[Hediff],
  labels: dict[str, str] | None = None,
) -> list[str]:
  out: list[str] = []
  for h in hediffs:
    if _is_ignored(h.def_name):
      continue
    if is_drug_high(h.def_name):
      continue
    if is_shambler_state(h.def_name):
      continue
    if is_pilot_state(h.def_name):
      continue
    if _has_invisible_part(h.body_part):
      continue
    out.append(_format(h, labels))
  return out


def describe_chemical_state(
  hediffs: Iterable[Hediff],
  labels: dict[str, str] | None = None,
) -> list[str]:
  """Return only drug-high hediffs, formatted like body-change hediffs."""
  out: list[str] = []
  for h in hediffs:
    if _is_ignored(h.def_name):
      continue
    if not is_drug_high(h.def_name):
      continue
    out.append(_format(h, labels))
  return out


def describe_shambler_state(
  hediffs: Iterable[Hediff],
  labels: dict[str, str] | None = None,
) -> list[str]:
  """Return only shambler-state hediffs (reanimated / corpse-shambler)."""
  out: list[str] = []
  for h in hediffs:
    if _is_ignored(h.def_name):
      continue
    if not is_shambler_state(h.def_name):
      continue
    out.append(_format(h, labels))
  return out


def describe_pilot_state(
  hediffs: Iterable[Hediff],
  labels: dict[str, str] | None = None,
) -> list[str]:
  """Return only Odyssey pilot-implant hediffs."""
  out: list[str] = []
  for h in hediffs:
    if _is_ignored(h.def_name):
      continue
    if not is_pilot_state(h.def_name):
      continue
    out.append(_format(h, labels))
  return out
