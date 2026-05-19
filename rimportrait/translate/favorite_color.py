"""RimWorld ColorDef favorite-color names -> descriptive phrases.

The Ideology DLC stores favorite colors as ColorDef references. The
def name is a fixed enum; we map each to a short descriptive phrase
in the user's preferred style.
"""

from __future__ import annotations


FAVORITE_COLOR: dict[str, str] = {
  "LightRed": "light red / soft warm red",
  "Red": "saturated red",
  "DarkRed": "deep dark red / blood red",
  "LightOrange": "light orange / soft warm orange",
  "Orange": "saturated orange",
  "DarkOrange": "deep dark orange / burnt orange",
  "LightYellow": "pale yellow",
  "Yellow": "saturated yellow",
  "DarkYellow": "muted dark yellow / ochre",
  "LightGreen": "fresh light green",
  "Green": "saturated green",
  "DarkGreen": "deep dark green / forest green",
  "LightCyan": "pale aqua / light cyan",
  "Cyan": "bright cyan / aqua / turquoise",
  "DarkCyan": "muted dark teal",
  "LightBlue": "pale sky blue",
  "Blue": "saturated mid blue",
  "DarkBlue": "deep navy blue",
  "LightPurple": "light purple / pale violet / muted lavender",
  "Purple": "saturated purple",
  "DarkPurple": "deep dark purple",
  "LightMagenta": "pale magenta",
  "Magenta": "saturated magenta",
  "DarkMagenta": "deep dark magenta",
  "LightPink": "pale pink",
  "Pink": "saturated pink",
  "DarkPink": "deep dark pink",
  "LightBrown": "tan / light warm brown",
  "Brown": "warm brown",
  "DarkBrown": "deep dark brown",
  "White": "white",
  "Gray": "mid gray",
  "Grey": "mid gray",
  "Black": "black",
}


def describe_favorite_color(name: str | None) -> str | None:
  if not name:
    return None
  return FAVORITE_COLOR.get(name, name)
