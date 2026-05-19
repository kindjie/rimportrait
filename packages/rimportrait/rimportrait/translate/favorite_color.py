"""ColorDef favorite-color reference -> natural-language phrase.

Per the data-first principle we no longer keep a curated table of
``LightRed -> "light red / soft warm red"`` phrasings. Instead we
resolve the ColorDef name to its RGBA value and let the existing
Lab-nearest-neighbour palette in ``colors.py`` pick a descriptive
name. ColorDef names that don't resolve to RGBA fall back to a
humanised slug.
"""

from __future__ import annotations

from rimsave.colors import rgba_to_name
from ._common import humanise
from rimsave.colordef import lookup_color_def


def describe_favorite_color(name: str | None) -> str | None:
  if not name:
    return None
  rgba = lookup_color_def(name)
  if rgba is not None:
    return rgba_to_name(rgba)
  return humanise(name)
