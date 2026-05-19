from __future__ import annotations

from rimportrait.translate.condition import describe_condition


def test_none_when_either_input_missing():
  assert describe_condition(None, None) is None
  assert describe_condition(80, None) is None
  assert describe_condition(None, 100) is None


def test_omitted_above_threshold():
  assert describe_condition(100, 100) is None
  assert describe_condition(90, 100) is None
  assert describe_condition(80, 100) is None


def test_worn_band():
  assert describe_condition(75, 100) == "worn"
  assert describe_condition(60, 100) == "worn"
  assert describe_condition(50, 100) == "worn"


def test_battered_band():
  assert describe_condition(49, 100) == "battered"
  assert describe_condition(30, 100) == "battered"
  assert describe_condition(25, 100) == "battered"


def test_ruined_band():
  assert describe_condition(24, 100) == "ruined"
  assert describe_condition(10, 100) == "ruined"
  assert describe_condition(0, 100) == "ruined"


def test_zero_max_health_returns_none():
  assert describe_condition(50, 0) is None


def test_handles_realistic_powerarmor_ratio():
  # Sample save: Apparel_PowerArmor health=278 with max=300 (good).
  assert describe_condition(278, 300) is None
  # Same item ~ half HP -> battered band.
  assert describe_condition(140, 300) == "battered"
