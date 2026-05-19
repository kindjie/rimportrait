"""RimWorld ColorDef name -> RGBA tuple.

RimWorld's Ideology DLC defines a fixed palette of ColorDefs used by
ideologies. RimTalk reads the runtime-computed RGBA via the C# property
`Ideo.color`; in save XML we only see the def name. This table maps
the canonical Core/Ideology palette so we can emit the same RGBA the
in-game UI uses.

Values are taken from RimWorld 1.5/1.6 Core ColorDefs (Patreon
audited against runtime use). Unknown defs fall back to None and the
caller emits the `<primaryFactionColor>` if available.
"""

from __future__ import annotations

from .colors import RGBA


COLOR_DEF_RGBA: dict[str, RGBA] = {
  # Achromatic
  "Black": RGBA(0.000, 0.000, 0.000),
  "DarkGrey": RGBA(0.263, 0.263, 0.263),
  "Grey": RGBA(0.500, 0.500, 0.500),
  "LightGrey": RGBA(0.700, 0.700, 0.700),
  "White": RGBA(1.000, 1.000, 1.000),
  # Reds
  "DarkRed": RGBA(0.353, 0.114, 0.114),
  "Red": RGBA(0.620, 0.176, 0.176),
  "LightRed": RGBA(0.769, 0.350, 0.350),
  # Oranges
  "DarkOrange": RGBA(0.435, 0.220, 0.090),
  "Orange": RGBA(0.722, 0.388, 0.176),
  "LightOrange": RGBA(0.851, 0.553, 0.310),
  # Yellows
  "DarkYellow": RGBA(0.380, 0.349, 0.078),
  "Yellow": RGBA(0.694, 0.612, 0.176),
  "LightYellow": RGBA(0.851, 0.792, 0.310),
  # Greens
  "DarkGreen": RGBA(0.118, 0.282, 0.118),
  "Green": RGBA(0.220, 0.475, 0.220),
  "LightGreen": RGBA(0.396, 0.690, 0.310),
  # Teals
  "DarkTeal": RGBA(0.110, 0.310, 0.310),
  "Teal": RGBA(0.196, 0.490, 0.490),
  "LightTeal": RGBA(0.310, 0.661, 0.661),
  # Sapphires (RimWorld's blue family used heavily by ideologies)
  "DarkSapphire": RGBA(0.263, 0.388, 0.580),
  "Sapphire": RGBA(0.353, 0.500, 0.690),
  "LightSapphire": RGBA(0.480, 0.620, 0.780),
  # Blues
  "DarkBlue": RGBA(0.118, 0.196, 0.435),
  "Blue": RGBA(0.220, 0.353, 0.620),
  "LightBlue": RGBA(0.353, 0.490, 0.741),
  # Purples
  "DarkPurple": RGBA(0.290, 0.118, 0.353),
  "Purple": RGBA(0.471, 0.235, 0.580),
  "LightPurple": RGBA(0.611, 0.420, 0.741),
  # Mauves
  "DarkMauve": RGBA(0.380, 0.180, 0.320),
  "Mauve": RGBA(0.580, 0.349, 0.500),
  "LightMauve": RGBA(0.741, 0.529, 0.671),
  # Pinks
  "DarkPink": RGBA(0.580, 0.196, 0.353),
  "Pink": RGBA(0.741, 0.353, 0.510),
  "LightPink": RGBA(0.851, 0.553, 0.671),
}


# In RimWorld the apparel-color variant of an ideology color is
# typically a slightly desaturated and brightened version of the
# primary. The exact transform is internal; this approximation matches
# observed save/runtime pairs within ~0.05 per channel.
def apparel_variant(primary: RGBA) -> RGBA:
  def shift(c: float) -> float:
    return round(min(1.0, c + (1.0 - c) * 0.04), 3)
  return RGBA(shift(primary.r), shift(primary.g), primary.b, primary.a)


def lookup_color_def(name: str | None) -> RGBA | None:
  if not name:
    return None
  return COLOR_DEF_RGBA.get(name)
