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
