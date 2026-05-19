"""Style preset resolution + instruction composition."""

from __future__ import annotations

import pytest

from rimportrait import style
from rimportrait.style import StylePreset


def test_resolve_no_inputs_returns_empty_preset():
  out = style.resolve(None, None, None, None)
  assert out == StylePreset()
  assert not out.any_set()


def test_resolve_preset_only_fills_all_three_dimensions():
  out = style.resolve("moody-portrait", None, None, None)
  assert out.style and out.shot and out.camera
  assert "realistic" in out.style.lower()


def test_resolve_explicit_overrides_beat_preset():
  out = style.resolve(
    "moody-portrait", style="anime", shot=None, camera=None
  )
  assert out.style == "anime"
  # Untouched preset fields survive.
  assert out.shot is not None and "three-quarter" in out.shot


def test_compose_unchanged_when_no_overrides():
  base = "BASE"
  assert style.compose_instruction(base, "portrait", StylePreset()) \
    == "BASE"


def test_compose_appends_style_block_and_overrides_closer():
  out = style.compose_instruction(
    "BASE", "portrait",
    StylePreset(style="oil painting", shot=None, camera=None),
  )
  assert out.startswith("BASE\n\n")
  assert "Style: oil painting." in out
  assert 'End with "oil painting RimWorld sci-fi colony portrait, ' \
    'no UI."' in out


def test_compose_omits_closer_override_when_no_style():
  out = style.compose_instruction(
    "BASE", "portrait",
    StylePreset(style=None, shot="action", camera="35mm"),
  )
  assert "Composition: action." in out
  assert "Camera: 35mm." in out
  # No style means no closer override - base instruction's closer
  # remains the one in effect.
  assert 'End with "' not in out


def test_compose_uses_family_descriptor_for_family_kind():
  out = style.compose_instruction(
    "BASE", "family",
    StylePreset(style="oil painting", shot=None, camera=None),
  )
  assert 'sci-fi colony family portrait, no UI.' in out


def test_compose_includes_all_three_dimensions_when_set():
  out = style.compose_instruction(
    "BASE", "portrait",
    StylePreset(style="anime", shot="action", camera="35mm wide"),
  )
  assert "Style: anime." in out
  assert "Composition: action." in out
  assert "Camera: 35mm wide." in out


def test_presets_have_expected_starter_names():
  # If you rename or remove presets, update the CLI --preset choices
  # docs in the README too.
  expected = {
    "moody-portrait", "action", "oil-painting", "comic", "propaganda",
  }
  assert expected.issubset(set(style.PRESETS.keys()))


@pytest.mark.parametrize("name", list(style.PRESETS.keys()))
def test_every_preset_has_at_least_one_dimension(name):
  assert style.PRESETS[name].any_set()
