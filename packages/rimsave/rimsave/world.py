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

# Tolerance window when resolving an observed grid shortHash back to
# a def name. RimWorld's ShortHashGiver bumps collisions by +1 across
# all DefTypes; without iterating every def in the game we can't know
# exact collision sets, but in practice 0-3 bumps cover the vanilla
# load order. Increase if a modded save shows mis-resolutions.
SHORTHASH_FUZZ = 5


@dataclass(frozen=True)
class MapData:
  """Decoded per-map data needed for pawn-position lookups."""
  size_x: int
  size_z: int
  roof: tuple[int, ...]  # length size_x * size_z, ushort roof short-hashes
  terrain: tuple[int, ...] = ()  # same shape, terrain short-hashes (0 = unset)

  def roof_at(self, x: int, z: int) -> int:
    if not (0 <= x < self.size_x and 0 <= z < self.size_z):
      return 0  # off-map -> treat as outdoor
    return self.roof[x + z * self.size_x]

  def is_outdoor(self, x: int, z: int) -> bool:
    return self.roof_at(x, z) == 0

  def terrain_at(self, x: int, z: int) -> int:
    if not (0 <= x < self.size_x and 0 <= z < self.size_z):
      return 0
    if not self.terrain:
      return 0
    return self.terrain[x + z * self.size_x]


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


def stable_string_hash(s: str) -> int:
  """RimWorld's ``GenText.StableStringHash``: polynomial-31 over chars,
  base 23, wrapping as C# signed int32, then ``% 65535`` with negative
  wrap to non-negative. Used to compute ``Def.shortHash`` before
  ``ShortHashGiver`` collision-bumping is applied.
  """
  num = 23
  for c in s:
    num = num * 31 + ord(c)
    num = num & 0xFFFFFFFF
    if num >= 1 << 31:
      num -= 1 << 32
  h = num % 65535
  if h < 0:
    h += 65535
  return h


def resolve_short_hash(
  observed: int,
  base_hashes: dict[int, str],
  fuzz: int = SHORTHASH_FUZZ,
) -> str | None:
  """Resolve an observed short-hash to a def name.

  ``base_hashes`` maps the *unbumped* StableStringHash of each
  candidate def name to that def name. We try exact match first, then
  walk backwards up to ``fuzz`` steps to absorb collision bumps
  (RimWorld's ``ShortHashGiver`` increments by +1 on collisions).
  """
  if observed in base_hashes:
    return base_hashes[observed]
  for step in range(1, fuzz + 1):
    candidate = observed - step
    if candidate in base_hashes:
      return base_hashes[candidate]
  return None


def classify_roof_def(def_name: str | None) -> str:
  """Map a RoofDef name to a coarse readable label."""
  if not def_name:
    return "roofed"  # unknown roof; only no-roof (shortHash 0) is "unroofed"
  n = def_name.lower()
  if n == "roofconstructed":
    return "constructed roof"
  if n == "roofrockthin":
    return "thin rock overhead (mountain tunnel)"
  if n == "roofrockthick":
    return "thick rock overhead (deep mountain)"
  if "rock" in n:
    return "rock overhead"
  return "roofed"


def is_substructure_def(def_name: str | None) -> bool:
  """Substructure (gravship foundation), vanilla or modded."""
  if not def_name:
    return False
  n = def_name.lower()
  if n == "substructure":
    return True
  # Modded gravship foundations tend to include 'substructure' or
  # 'gravship_foundation' in the def name.
  if "substructure" in n:
    return True
  if "gravship" in n and ("foundation" in n or "floor" in n):
    return True
  return False


def is_bridge_def(def_name: str | None) -> bool:
  """Bridge / HeavyBridge (over-water crossing)."""
  if not def_name:
    return False
  n = def_name.lower()
  return n in ("bridge", "heavybridge") or n.endswith("bridge")


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
