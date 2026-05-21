"""Style preset registry + single-path instruction composer."""

from __future__ import annotations

import pytest

from rimportrait import style
from rimportrait.style import StylePreset, StyleSection


# --- preset registry shape ------------------------------------------


def test_presets_have_expected_starter_names():
  expected = {
    "renaissance", "acrylic", "action",
    "comic", "anime", "pinup", "propaganda", "pixel-art",
  }
  assert expected == set(style.PRESETS.keys()), (
    "If you rename or remove presets, update the README's preset "
    "table too."
  )


@pytest.mark.parametrize("name", list(style.PRESETS.keys()))
def test_every_preset_has_a_section(name):
  preset = style.PRESETS[name]
  assert preset.section is not None, name


def test_action_preset_uses_action_base_swap():
  """The action preset is the only one that swaps the base
  instruction file (via base='action'); every other preset uses
  the portrait base with its own style section."""
  assert style.PRESETS["action"].base == "action"
  for name, preset in style.PRESETS.items():
    if name == "action":
      continue
    assert preset.base is None, (
      f"preset {name!r} must not set base= (only action does)"
    )


# --- section content sanity checks ----------------------------------


def test_section_mode_triggers_are_noun_phrases():
  """The gpt-image-2 overlay reads 'Lead the paragraph with <X>',
  so mode triggers should read naturally as opening noun phrases."""
  for name, preset in style.PRESETS.items():
    trigger = preset.section.mode_trigger
    assert trigger.startswith(("A ", "An ", "The ")), (
      f"preset {name!r} mode_trigger {trigger!r} should be a "
      "noun phrase starting with 'A', 'An', or 'The'"
    )


def test_section_closers_end_with_no_ui():
  """Every closer ends with `, no UI.` so validation item 10's
  exact-phrase check sees a consistent trailing marker."""
  for name, preset in style.PRESETS.items():
    closer = preset.section.closer_phrase
    assert closer.endswith(", no UI."), (
      f"preset {name!r} closer must end with ', no UI.' "
      f"got: {closer!r}"
    )


def test_every_section_describes_medium_texture():
  """Each section's prose must include an explicit 'Medium texture:'
  block — the single biggest lever for making the medium feel real
  in the rendered image. If you add a new preset, add the block."""
  for name, preset in style.PRESETS.items():
    assert "Medium texture:" in preset.section.prose, (
      f"preset {name!r} section must include a 'Medium texture:' "
      "block describing the physical / printing / film / digital "
      "artifacts that make this medium recognisable"
    )


def test_anime_section_calls_out_cel_and_crt_artifacts():
  """The anime preset is uniquely identifiable by cel-paint edges
  plus analogue CRT-display artifacts — both must appear in the
  medium-texture description."""
  prose = style.PRESETS["anime"].section.prose
  assert "cel" in prose.lower()
  assert "CRT" in prose or "crt" in prose.lower()


def test_comic_section_calls_out_halftone_and_registration():
  prose = style.PRESETS["comic"].section.prose
  assert "halftone" in prose.lower()
  assert "registration" in prose.lower()


def test_acrylic_section_distinguishes_from_renaissance():
  """Acrylic and renaissance are both 'painted' presets; the
  prose must explicitly disambiguate to keep the LLM from
  mixing them."""
  acrylic = style.PRESETS["acrylic"].section.prose
  assert "acrylic" in acrylic.lower()
  assert "saturated" in acrylic.lower() or "vibrant" in acrylic.lower()
  # Negative-reference disambiguation against renaissance.
  assert ("NOT" in acrylic and ("oil" in acrylic.lower()
                                or "glaze" in acrylic.lower()
                                or "Old Masters" in acrylic))


def test_comic_and_anime_presets_explicitly_disambiguate():
  """The two stylized-ink presets must name-check the OTHER
  tradition in negation so the LLM doesn't blend them."""
  comic = style.PRESETS["comic"].section.prose
  anime = style.PRESETS["anime"].section.prose
  assert "anime" in comic.lower() and "NOT" in comic
  assert "Western" in anime or "comic" in anime.lower()


def test_action_section_references_save_signals():
  """The action section must name the block fields that drive its
  verb choice (Pose/activity / Inspiration / combat-readiness
  signals)."""
  prose = style.PRESETS["action"].section.prose
  for signal in ("Pose/activity", "Inspiration"):
    assert signal in prose, (
      f"action section must reference {signal!r}"
    )
  combat_terms = (
    "combat", "shoot frenzy", "berserker", "piloting",
    "shambling", "drug-high", "aggressive",
  )
  assert any(t in prose for t in combat_terms), (
    "action section must name at least one combat-readiness signal"
  )


# --- compose_instruction --------------------------------------------


def test_compose_no_preset_uses_default_section():
  """No preset → the kind's default section drives the composed
  output. No 'USER STYLE OVERRIDE' header should ever appear (that
  was the legacy path, now removed)."""
  out = style.compose_instruction("portrait", None)
  assert "USER STYLE OVERRIDE" not in out
  # Default section's closer is the original portrait closer.
  assert ('realistic gritty RimWorld sci-fi colony portrait, '
          'grounded expression, no UI.') in out


def test_compose_with_preset_uses_section_closer_and_prose():
  out = style.compose_instruction(
    "portrait", style.PRESETS["renaissance"],
  )
  assert "USER STYLE OVERRIDE" not in out
  assert "Renaissance Old Masters oil painting" in out
  # Closer appears in both Output-format and validation item 10.
  closer = style.PRESETS["renaissance"].section.closer_phrase
  assert f'End with: "{closer}"' in out
  assert f'closing phrase is exactly: "{closer}"' in out


def test_compose_acrylic_distinct_from_renaissance():
  """The acrylic preset must compose with its own mode trigger
  and closer (regression against the rename-from-oil-painting)."""
  out = style.compose_instruction(
    "portrait", style.PRESETS["acrylic"],
    image_model="gpt-image-2",
  )
  assert "USER STYLE OVERRIDE" not in out
  assert "vibrant acrylic painting" in out.lower()
  assert "Lead the paragraph with \"A vibrant acrylic painting\"" in out


def test_compose_action_swaps_base_and_uses_section_closer():
  """Action sets base='action'; compose_instruction's caller is
  expected to pass effective_kind='action' so the action core is
  selected. The section's action closer is used end-to-end."""
  out = style.compose_instruction(
    "portrait", style.PRESETS["action"],
    effective_kind="action",
  )
  assert "USER STYLE OVERRIDE" not in out
  assert (
    'realistic gritty RimWorld sci-fi colony action still, no UI.'
  ) in out


def test_compose_threads_mode_trigger_into_gpt_image_2_overlay():
  """The gpt-image-2 overlay's leading-verb rule must use the
  active section's mode_trigger, not a hardcoded
  'Photorealistic'."""
  out = style.compose_instruction(
    "portrait", style.PRESETS["renaissance"],
    image_model="gpt-image-2",
  )
  assert 'Lead the paragraph with "An Old Masters oil painting"' in out
  assert 'Lead the paragraph with "Photorealistic"' not in out


def test_compose_default_mode_trigger_is_photorealistic():
  """No preset → default section → overlay leads with
  'Photorealistic' (today's no-preset behaviour preserved)."""
  out = style.compose_instruction(
    "portrait", None, image_model="gpt-image-2",
  )
  assert 'Lead the paragraph with "Photorealistic"' in out


def test_compose_user_style_appends_to_section_prose():
  """``--style "moody candlelit"`` lands as an additional-style-note
  block on whichever section is active."""
  out = style.compose_instruction(
    "portrait", None, user_style="moody candlelit",
  )
  assert "Additional style note:" in out
  assert "moody candlelit." in out


def test_compose_user_style_with_preset_stacks_on_section():
  """``--style`` works alongside ``--preset`` — the note appends
  after the preset's own prose, not replacing it."""
  out = style.compose_instruction(
    "portrait", style.PRESETS["renaissance"],
    user_style="dawn light",
  )
  # Renaissance prose still present.
  assert "Renaissance Old Masters oil painting" in out
  # User-style addendum present.
  assert "Additional style note:" in out
  assert "dawn light." in out


# --- StyleSection invariants ----------------------------------------


def test_style_section_dataclass_is_frozen():
  """StyleSection is value-typed; instances must be immutable."""
  s = StyleSection(prose="x", mode_trigger="y", closer_phrase="z")
  with pytest.raises(Exception):
    s.prose = "mutated"  # type: ignore[misc]


def test_style_preset_dataclass_is_frozen():
  s = StyleSection(prose="x", mode_trigger="y", closer_phrase="z")
  p = StylePreset(section=s)
  with pytest.raises(Exception):
    p.base = "action"  # type: ignore[misc]
