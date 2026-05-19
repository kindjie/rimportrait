"""Map wealth -> descriptive tier sentence.

Raw wealth numbers leak game-mechanic feel into image prompts. The spec
converts them into qualitative descriptions of the colony's material
level.
"""

from __future__ import annotations


_TIERS: tuple[tuple[int, str], ...] = (
  (50_000, (
    "poor frontier settlement with improvised rooms, "
    "rough storage, and worn equipment"
  )),
  (200_000, (
    "modest colony with functional rooms, mixed materials, "
    "and practical defenses"
  )),
  (750_000, (
    "prosperous colony with solid infrastructure, "
    "specialized rooms, and decent equipment"
  )),
  (2_000_000, (
    "rich colony with advanced materials, clean infrastructure, "
    "high-tech equipment, and ornate rooms"
  )),
)

_TOP_TIER = (
  "extremely wealthy late-game colony with elite armor, "
  "polished high-tech infrastructure, and ornate fortified interiors"
)


def wealth_tier(wealth: float | None) -> str | None:
  if wealth is None:
    return None
  for threshold, phrase in _TIERS:
    if wealth < threshold:
      return phrase
  return _TOP_TIER
