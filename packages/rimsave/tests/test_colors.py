from __future__ import annotations

from rimsave.colors import RGBA, describe_rgba, rgba_to_name


def test_parse_rgba_four_channel():
  c = RGBA.parse("RGBA(0.204, 0.204, 0.204, 1.000)")
  assert c is not None
  assert c.r == 0.204
  assert c.g == 0.204
  assert c.b == 0.204
  assert c.a == 1.0


def test_parse_rgba_three_channel_defaults_alpha():
  c = RGBA.parse("RGB(0.5, 0.5, 0.5)")
  assert c is not None
  assert c.a == 1.0


def test_parse_rgba_unparseable():
  assert RGBA.parse("not a color") is None
  assert RGBA.parse(None) is None


def test_exact_override_charcoal():
  c = RGBA.parse("RGBA(0.204, 0.204, 0.204, 1.000)")
  assert c is not None
  assert rgba_to_name(c) == "very dark charcoal / near-black"


def test_exact_override_steel_blue():
  c = RGBA.parse("RGBA(0.263, 0.388, 0.580, 1.000)")
  assert c is not None
  assert rgba_to_name(c) == "muted steel blue / blue-gray"


def test_exact_override_apparel_blue_gray():
  c = RGBA.parse("RGBA(0.290, 0.405, 0.580, 1.000)")
  assert c is not None
  assert rgba_to_name(c) == "muted blue-gray"


def test_exact_override_aqua_turquoise():
  c = RGBA.parse("RGBA(0.399, 0.926, 0.931, 1.000)")
  assert c is not None
  assert rgba_to_name(c) == "bright cyan / aqua / turquoise"


def test_palette_fallback_pure_red():
  c = RGBA(0.80, 0.20, 0.20, 1.0)
  assert rgba_to_name(c) == "saturated red"


def test_palette_fallback_navy():
  c = RGBA(0.10, 0.20, 0.45, 1.0)
  assert rgba_to_name(c) == "deep navy blue"


def test_describe_rgba_includes_both_forms():
  c = RGBA.parse("RGBA(0.204, 0.204, 0.204, 1.000)")
  out = describe_rgba(c)
  assert out is not None
  assert "RGBA(0.204, 0.204, 0.204, 1.000)" in out
  assert "very dark charcoal / near-black" in out


def test_describe_rgba_none():
  assert describe_rgba(None) is None
