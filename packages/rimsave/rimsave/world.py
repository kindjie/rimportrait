"""Map-wide world data: roof grid decompression + in-game time.

RimWorld serialises the per-cell roof grid as base64-wrapped raw
DEFLATE-compressed bytes (``wbits=-15``, not zlib-with-header). Once
decompressed the grid is a little-endian ``ushort[]`` of size
``mapSize.x * mapSize.z`` indexed by ``cell.x + cell.z * mapSize.x``.
A value of 0 means "no roof" (outdoor); any other value is the
``RoofDef.shortHash`` of the roof at that cell.

In-game time is derived from ``tickManager/ticksGame``: there are
60000 ticks per day and 2500 ticks per in-game hour. The tile's
longitude offset is ignored for now (world-UTC hour).
"""

from __future__ import annotations

import base64
import struct
import zlib
from dataclasses import dataclass


TICKS_PER_DAY = 60000
TICKS_PER_HOUR = 2500


@dataclass(frozen=True)
class MapData:
  """Decoded per-map data needed for pawn-position lookups."""
  size_x: int
  size_z: int
  roof: tuple[int, ...]  # length size_x * size_z, ushort values

  def roof_at(self, x: int, z: int) -> int:
    if not (0 <= x < self.size_x and 0 <= z < self.size_z):
      return 0  # off-map -> treat as outdoor
    return self.roof[x + z * self.size_x]

  def is_outdoor(self, x: int, z: int) -> bool:
    return self.roof_at(x, z) == 0


def decompress_grid_ushorts(b64_text: str) -> tuple[int, ...]:
  """Decompress a RimWorld ``*Deflate`` payload as a tuple of ushorts."""
  raw = zlib.decompress(base64.b64decode(b64_text), wbits=-15)
  n = len(raw) // 2
  return struct.unpack(f"<{n}H", raw)


def parse_size(text: str | None) -> tuple[int, int] | None:
  """Parse RimWorld's ``(x, y, z)`` size triple. Returns ``(x, z)``."""
  if not text:
    return None
  inner = text.strip().lstrip("(").rstrip(")")
  parts = [p.strip() for p in inner.split(",")]
  if len(parts) != 3:
    return None
  try:
    return int(parts[0]), int(parts[2])
  except ValueError:
    return None


def parse_pos(text: str | None) -> tuple[int, int] | None:
  """Parse RimWorld's ``(x, y, z)`` pos. Returns ``(x, z)`` (drops y)."""
  return parse_size(text)


def hour_for_tick(ticks_game: int) -> int:
  """In-game hour 0-23 from raw ``ticksGame``."""
  return (ticks_game % TICKS_PER_DAY) // TICKS_PER_HOUR


# Banding mirrors the existing --time CLI choices so the same six
# labels are used whether the time came from the save or from a flag.
def time_period_for_hour(hour: int) -> str:
  if 5 <= hour < 7:
    return "dawn"
  if 7 <= hour < 12:
    return "morning"
  if 12 <= hour < 17:
    return "day"
  if 17 <= hour < 19:
    return "golden-hour"
  if 19 <= hour < 21:
    return "dusk"
  return "night"
