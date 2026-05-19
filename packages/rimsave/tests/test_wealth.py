from __future__ import annotations

from rimsave.wealth import wealth_tier


def test_none_returns_none():
  assert wealth_tier(None) is None


def test_poor_frontier():
  assert "poor frontier" in (wealth_tier(10_000) or "")
  assert "poor frontier" in (wealth_tier(49_999) or "")


def test_modest():
  assert "modest" in (wealth_tier(50_000) or "")
  assert "modest" in (wealth_tier(199_999) or "")


def test_prosperous():
  assert "prosperous" in (wealth_tier(200_000) or "")
  assert "prosperous" in (wealth_tier(749_999) or "")


def test_rich():
  assert "rich" in (wealth_tier(750_000) or "")
  assert "rich" in (wealth_tier(1_999_999) or "")


def test_extremely_wealthy():
  out = wealth_tier(2_000_000) or ""
  assert "extremely wealthy" in out
  out2 = wealth_tier(10_000_000) or ""
  assert "extremely wealthy" in out2
