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
  out = style.resolve("renaissance", None, None, None)
  assert out.style and out.shot and out.camera
  assert "renaissance" in out.style.lower()
  # No accidental "Photorealistic" suppression escape - the painterly
  # override must explicitly tell the LLM not to use that mode trigger.
  assert "NOT a photograph" in out.style


def test_resolve_explicit_overrides_beat_preset():
  out = style.resolve(
    "renaissance", style="anime", shot=None, camera=None
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
  # Addendum now prepends with the override header.
  assert out.startswith("USER STYLE OVERRIDE")
  # Base instruction lands after the separator.
  assert "\n\n---\n\nBASE" in out
  assert "Style: oil painting." in out
  assert ('End the paragraph with: "oil painting RimWorld sci-fi '
          'colony portrait, no UI."') in out


def test_compose_omits_closer_override_when_no_style():
  out = style.compose_instruction(
    "BASE", "portrait",
    StylePreset(style=None, shot="action", camera="35mm"),
  )
  assert "Composition: action." in out
  assert "Camera: 35mm." in out
  # No style means no closer override - base instruction's closer
  # remains the one in effect.
  assert "End the paragraph with:" not in out


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
    "renaissance", "action", "oil-painting",
    "comic", "anime", "propaganda", "pixel-art",
  }
  assert expected.issubset(set(style.PRESETS.keys()))


@pytest.mark.parametrize("name", list(style.PRESETS.keys()))
def test_every_preset_has_at_least_one_dimension(name):
  assert style.PRESETS[name].any_set()


def test_scene_alone_appends_block_but_keeps_default_closer():
  out = style.compose_instruction(
    "BASE", "portrait",
    StylePreset(scene="crowded refugee corridor, smoke"),
  )
  assert "Scene: crowded refugee corridor, smoke." in out
  assert "End the paragraph with:" not in out


def test_time_alone_appends_time_of_day_line():
  out = style.compose_instruction(
    "BASE", "portrait", StylePreset(time="dusk"),
  )
  assert "Time of day: dusk." in out


def test_resolve_passes_scene_and_time_through():
  out = style.resolve(
    None, None, None, None,
    scene="rain-slick alley", time="night",
  )
  assert out.scene == "rain-slick alley"
  assert out.time == "night"
  assert out.any_set()


def test_resolve_combines_preset_with_scene_override():
  out = style.resolve(
    "action", None, None, None,
    scene="burning barn", time="golden-hour",
  )
  # Preset's shot/camera survive (action preset has no style; its
  # base swap is what gives it the cinematic voice).
  assert out.shot is not None
  assert out.camera is not None
  assert out.base == "action"
  # Overrides take.
  assert out.scene == "burning barn"
  assert out.time == "golden-hour"


def test_action_preset_uses_action_base():
  """The action preset swaps the LLM system instruction's base
  voice via StylePreset.base instead of setting a style closer.
  """
  assert style.PRESETS["action"].base == "action"
  assert style.PRESETS["action"].style is None
  # Non-action presets must not accidentally swap the base.
  for name, preset in style.PRESETS.items():
    if name == "action":
      continue
    assert preset.base is None, (
      f"preset {name!r} must not set base= (only action does)"
    )


def test_compose_instruction_preserves_base_closer_when_action():
  """When preset.base is set, compose_instruction must NOT inject
  a portrait-style closer override - the action base instruction
  has its own '...action still...' closer that should win.
  """
  out = style.compose_instruction(
    "BASE",
    "portrait",
    StylePreset(
      style="oil painting", base="action",
    ),
  )
  # Style addendum still applies.
  assert "Style: oil painting." in out
  # But no closer override (would start "End the paragraph with:")
  assert "End the paragraph with:" not in out


def test_closer_uses_short_style_when_full_style_is_verbose():
  """Multi-clause style strings (e.g. comic / anime presets with
  their explicit anti-references) must not bloat the closer."""
  out = style.compose_instruction(
    "BASE", "portrait",
    StylePreset(
      style=(
        "Western graphic novel inks - bold halftone shading; "
        "NOT anime"
      ),
    ),
  )
  # The full prose stays in the addendum.
  assert (
    "Style: Western graphic novel inks - bold halftone shading; "
    "NOT anime."
  ) in out
  # The closer uses the trimmed lead phrase only.
  assert ('End the paragraph with: "Western graphic novel inks '
          'RimWorld sci-fi colony portrait, no UI."') in out
  closer_segment = out.split(
    'End the paragraph with: "', 1
  )[1].split('"', 1)[0]
  assert "NOT anime" not in closer_segment


def test_closer_passes_through_short_style_unchanged():
  out = style.compose_instruction(
    "BASE", "portrait", StylePreset(style="oil painting"),
  )
  assert ('End the paragraph with: "oil painting RimWorld sci-fi '
          'colony portrait, no UI."') in out


def test_comic_and_anime_presets_explicitly_disambiguate():
  """The two stylized-ink presets must name-check the OTHER tradition
  in negation so the LLM doesn't blend them.

  If you rephrase, keep at least one explicit anti-reference in each
  preset (e.g. comic says "not anime"; anime says "not Western
  comic").
  """
  comic = style.PRESETS["comic"].style or ""
  anime = style.PRESETS["anime"].style or ""
  assert "Western" in comic or "comic" in comic.lower()
  assert "NOT anime" in comic or "not anime" in comic.lower()
  assert "anime" in anime.lower() or "manga" in anime.lower()
  assert (
    "NOT Western" in anime or "not western" in anime.lower()
    or "not comic" in anime.lower()
  )


def test_action_preset_shot_references_save_signals():
  """The action preset's shot prose must name the block fields it
  elevates. The action base instruction already names them too, but
  the shot field is what lands in the addendum that follows the
  paragraph; keeping the reference here guards the dual-mention.
  """
  shot = style.PRESETS["action"].shot or ""
  for signal in ("Pose/activity", "Inspiration"):
    assert signal in shot, f"action preset must reference {signal!r}"
  # At least one combat-readiness signal is named.
  combat_terms = (
    "combat", "shoot frenzy", "berserker", "piloting", "shambling",
    "drug-high", "aggressive",
  )
  assert any(t in shot for t in combat_terms), (
    "action preset must name at least one combat-readiness signal"
  )
