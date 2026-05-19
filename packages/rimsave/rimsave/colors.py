"""RGBA parsing and natural-color naming.

RimWorld stores colors as RGBA tuples in 0..1 floats. We translate them
into descriptive phrases for image-prompt consumption. Two layers:

1. Exact-match overrides from spec (rounded to 3 decimals).
2. Nearest-neighbour fallback in CIE Lab over a curated palette.

Lab distance is used instead of RGB to avoid the failure where dark
navy reads as 'purple' under naive RGB distance.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_RGBA_RE = re.compile(
  r"""
    RGBA?\s*\(\s*
    (-?[0-9.]+)\s*,\s*
    (-?[0-9.]+)\s*,\s*
    (-?[0-9.]+)
    (?:\s*,\s*(-?[0-9.]+))?
    \s*\)
  """,
  re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class RGBA:
  r: float
  g: float
  b: float
  a: float = 1.0

  @classmethod
  def parse(cls, s: str | None) -> RGBA | None:
    if s is None:
      return None
    m = _RGBA_RE.search(s)
    if not m:
      return None
    return cls(
      r=float(m[1]),
      g=float(m[2]),
      b=float(m[3]),
      a=float(m[4]) if m[4] else 1.0,
    )

  def rounded3(self) -> tuple[float, float, float]:
    return (round(self.r, 3), round(self.g, 3), round(self.b, 3))

  def as_string(self) -> str:
    return (
      f"RGBA({self.r:.3f}, {self.g:.3f}, "
      f"{self.b:.3f}, {self.a:.3f})"
    )


# Exact phrasings from the user's spec, keyed on 3-decimal RGB.
# These bypass nearest-neighbour to preserve canonical wording.
_EXACT: dict[tuple[float, float, float], str] = {
  (0.204, 0.204, 0.204): "very dark charcoal / near-black",
  (0.263, 0.388, 0.580): "muted steel blue / blue-gray",
  (0.290, 0.405, 0.580): "muted blue-gray",
  (0.399, 0.926, 0.931): "bright cyan / aqua / turquoise",
}


# Curated descriptive palette in the user's preferred phrasing style.
_PALETTE: list[tuple[tuple[float, float, float], str]] = [
  ((0.00, 0.00, 0.00), "black"),
  ((0.10, 0.10, 0.10), "near-black"),
  ((0.20, 0.20, 0.20), "very dark charcoal / near-black"),
  ((0.35, 0.35, 0.35), "dark charcoal gray"),
  ((0.55, 0.55, 0.55), "mid gray"),
  ((0.80, 0.80, 0.80), "light gray"),
  ((0.97, 0.97, 0.97), "near-white"),
  ((0.30, 0.20, 0.10), "deep dark brown"),
  ((0.45, 0.30, 0.18), "warm brown"),
  ((0.68, 0.50, 0.32), "tan / light warm brown"),
  ((0.85, 0.70, 0.50), "pale sandy beige"),
  ((0.55, 0.10, 0.10), "deep blood red"),
  ((0.80, 0.20, 0.20), "saturated red"),
  ((0.85, 0.45, 0.45), "muted dusty red"),
  ((0.95, 0.70, 0.70), "pale pink"),
  ((0.85, 0.45, 0.10), "burnt orange"),
  ((0.95, 0.65, 0.30), "warm amber"),
  ((0.85, 0.80, 0.20), "muted yellow"),
  ((0.95, 0.90, 0.50), "pale yellow"),
  ((0.15, 0.30, 0.15), "dark forest green"),
  ((0.30, 0.55, 0.30), "muted olive green"),
  ((0.55, 0.80, 0.40), "fresh light green"),
  ((0.80, 0.95, 0.70), "pale green"),
  ((0.20, 0.55, 0.55), "muted teal"),
  ((0.40, 0.93, 0.93), "bright cyan / aqua / turquoise"),
  ((0.70, 0.95, 0.95), "pale aqua"),
  ((0.10, 0.20, 0.45), "deep navy blue"),
  ((0.26, 0.39, 0.58), "muted steel blue / blue-gray"),
  ((0.30, 0.55, 0.85), "saturated mid blue"),
  ((0.70, 0.85, 0.95), "pale sky blue"),
  ((0.30, 0.15, 0.45), "deep dark purple"),
  ((0.55, 0.40, 0.75), "muted violet"),
  ((0.78, 0.70, 0.90), "light purple / pale violet / muted lavender"),
  ((0.80, 0.30, 0.60), "saturated magenta"),
  ((0.95, 0.75, 0.85), "pale rose pink"),
]


def _srgb_to_linear(c: float) -> float:
  if c <= 0.04045:
    return c / 12.92
  return math.pow((c + 0.055) / 1.055, 2.4)


def _to_xyz(r: float, g: float, b: float) -> tuple[float, float, float]:
  r = _srgb_to_linear(max(0.0, min(1.0, r)))
  g = _srgb_to_linear(max(0.0, min(1.0, g)))
  b = _srgb_to_linear(max(0.0, min(1.0, b)))
  x = r * 0.4124 + g * 0.3576 + b * 0.1805
  y = r * 0.2126 + g * 0.7152 + b * 0.0722
  z = r * 0.0193 + g * 0.1192 + b * 0.9505
  return x, y, z


def _f_lab(t: float) -> float:
  if t > 0.008856:
    return math.pow(t, 1.0 / 3.0)
  return 7.787 * t + 16.0 / 116.0


def _to_lab(r: float, g: float, b: float) -> tuple[float, float, float]:
  x, y, z = _to_xyz(r, g, b)
  # D65 white reference
  x /= 0.95047
  y /= 1.00000
  z /= 1.08883
  fx, fy, fz = _f_lab(x), _f_lab(y), _f_lab(z)
  L = 116.0 * fy - 16.0
  a = 500.0 * (fx - fy)
  b2 = 200.0 * (fy - fz)
  return L, a, b2


def _lab_dist(a: tuple[float, float, float],
              b: tuple[float, float, float]) -> float:
  return math.sqrt(
    (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
  )


def rgba_to_name(c: RGBA) -> str:
  """Return a natural descriptive name for an RGBA color."""
  k = c.rounded3()
  if k in _EXACT:
    return _EXACT[k]
  target = _to_lab(c.r, c.g, c.b)
  best_name = ""
  best_dist = float("inf")
  for (pr, pg, pb), name in _PALETTE:
    d = _lab_dist(target, _to_lab(pr, pg, pb))
    if d < best_dist:
      best_dist = d
      best_name = name
  return best_name


def describe_rgba(c: RGBA | None) -> str | None:
  """Format an RGBA as 'RGBA(...) and natural color', or None if absent."""
  if c is None:
    return None
  return f"{c.as_string()} and {rgba_to_name(c)}"
