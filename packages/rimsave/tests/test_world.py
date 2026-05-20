"""world.py: roof-grid decompression + in-game time helpers."""

from __future__ import annotations

import base64
import struct
import zlib

import pytest

from rimsave import world


def _encode_grid(ushorts: list[int]) -> str:
  """Round-trip helper: encode ushorts the way RimWorld serialises."""
  raw = struct.pack(f"<{len(ushorts)}H", *ushorts)
  return base64.b64encode(zlib.compress(raw)[2:-4]).decode("ascii")


def test_decompress_round_trip_small_grid():
  ushorts = [0, 0, 10820, 0, 5133, 6699, 0, 0, 0]
  b64 = _encode_grid(ushorts)
  out = world.decompress_grid_ushorts(b64)
  assert list(out) == ushorts


def test_map_data_is_outdoor_treats_zero_as_no_roof():
  m = world.MapData(
    size_x=3, size_z=3,
    roof=tuple([
      0, 0, 0,
      0, 10820, 0,
      0, 0, 0,
    ]),
  )
  assert m.is_outdoor(0, 0) is True
  assert m.is_outdoor(1, 1) is False
  assert m.roof_at(1, 1) == 10820


def test_map_data_off_map_returns_outdoor():
  m = world.MapData(size_x=2, size_z=2, roof=(1, 1, 1, 1))
  assert m.is_outdoor(-1, 0) is True
  assert m.is_outdoor(5, 0) is True
  assert m.is_outdoor(0, 5) is True


def test_parse_pos_drops_y_coordinate():
  assert world.parse_pos("(174, 0, 196)") == (174, 196)
  assert world.parse_pos("(0, 1, 0)") == (0, 0)
  assert world.parse_pos(None) is None
  assert world.parse_pos("bad") is None


def test_parse_size_returns_x_and_z():
  assert world.parse_size("(200, 1, 200)") == (200, 200)
  assert world.parse_size("(150, 1, 175)") == (150, 175)


def test_hour_for_tick_uses_world_utc():
  # 60000 ticks per day, 2500 ticks per hour.
  assert world.hour_for_tick(0) == 0
  assert world.hour_for_tick(2500) == 1
  assert world.hour_for_tick(2499) == 0
  assert world.hour_for_tick(60000) == 0   # day wrap
  assert world.hour_for_tick(60000 * 5 + 2500 * 7) == 7


@pytest.mark.parametrize("name,expected", [
  ("RoofConstructed", 5133),
  ("RoofRockThin", 6699),
  ("RoofRockThick", 10819),  # base; vanilla saves observe 10820 (bumped +1)
])
def test_stable_string_hash_matches_known_def_hashes(name, expected):
  assert world.stable_string_hash(name) == expected


def test_resolve_short_hash_exact_match():
  table = {5133: "RoofConstructed", 6699: "RoofRockThin"}
  assert world.resolve_short_hash(5133, table) == "RoofConstructed"
  assert world.resolve_short_hash(6699, table) == "RoofRockThin"


def test_resolve_short_hash_walks_back_to_absorb_bumps():
  """RimWorld's ShortHashGiver bumps collisions by +1. The observed
  hash for RoofRockThick in our save is 10820, but stable hash is
  10819 - the resolver must step back."""
  table = {10819: "RoofRockThick"}
  assert world.resolve_short_hash(10820, table) == "RoofRockThick"
  assert world.resolve_short_hash(10822, table) == "RoofRockThick"


def test_resolve_short_hash_returns_none_beyond_fuzz():
  table = {100: "Foo"}
  assert world.resolve_short_hash(200, table) is None
  assert world.resolve_short_hash(105, table) == "Foo"


def test_classify_roof_def_vanilla_names():
  assert "constructed" in world.classify_roof_def("RoofConstructed")
  assert "thin rock" in world.classify_roof_def("RoofRockThin")
  assert "thick rock" in world.classify_roof_def("RoofRockThick")
  # Unknown def -> generic 'roofed' (no-roof case is handled
  # separately via the 0 shortHash short-circuit).
  assert world.classify_roof_def("ModdedFancyRoof") == "roofed"
  assert world.classify_roof_def(None) == "roofed"


def test_is_substructure_def_vanilla_and_modded():
  assert world.is_substructure_def("Substructure")
  assert world.is_substructure_def("ModdedSubstructure")
  assert world.is_substructure_def("MySubstructureFoundation")
  assert world.is_substructure_def("MyGravshipFoundation")
  assert world.is_substructure_def("GravshipFloor")
  assert not world.is_substructure_def("PavedTile")
  assert not world.is_substructure_def("Bridge")
  assert not world.is_substructure_def(None)


def test_is_bridge_def_vanilla_variants():
  assert world.is_bridge_def("Bridge")
  assert world.is_bridge_def("HeavyBridge")
  assert world.is_bridge_def("ModdedFancyBridge")
  assert not world.is_bridge_def("Substructure")
  assert not world.is_bridge_def("PavedTile")
  assert not world.is_bridge_def(None)


def test_map_data_terrain_at_falls_back_to_zero_when_empty():
  m = world.MapData(size_x=2, size_z=2, roof=(0, 0, 0, 0))
  # terrain defaults to empty tuple; lookups return 0 (no terrain).
  assert m.terrain_at(0, 0) == 0
  assert m.terrain_at(1, 1) == 0


def test_map_data_terrain_at_returns_cell_value():
  m = world.MapData(
    size_x=2, size_z=2,
    roof=(0, 0, 0, 0),
    terrain=(100, 200, 300, 400),
  )
  assert m.terrain_at(0, 0) == 100
  assert m.terrain_at(1, 0) == 200
  assert m.terrain_at(0, 1) == 300
  assert m.terrain_at(1, 1) == 400


@pytest.mark.parametrize("hour,expected", [
  (0, "night"),
  (4, "night"),
  (5, "dawn"),
  (6, "dawn"),
  (7, "morning"),
  (11, "morning"),
  (12, "day"),
  (16, "day"),
  (17, "golden-hour"),
  (18, "golden-hour"),
  (19, "dusk"),
  (20, "dusk"),
  (21, "night"),
  (23, "night"),
])
def test_time_period_for_hour_bands(hour, expected):
  assert world.time_period_for_hour(hour) == expected
