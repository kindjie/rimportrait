"""Image-gen dispatch + missing-SDK error-shape tests.

Real provider SDKs are never called — both ``openai_image`` and
``google_image`` are monkeypatched so the suite stays offline-safe
and doesn't require either optional dep to be installed.
"""

from __future__ import annotations

import sys

import pytest

from rimportrait import llm


def test_dispatch_routes_to_google_with_portrait_aspect(monkeypatch):
  calls: list[dict] = []

  def fake_google(prompt, model, *, aspect_ratio):
    calls.append(
      {"prompt": prompt, "model": model, "aspect_ratio": aspect_ratio}
    )
    return (b"\x89PNG-google", "png")

  monkeypatch.setattr(llm, "google_image", fake_google)
  png, ext = llm.generate_image("google", "prompt-text", "portrait")
  assert png == b"\x89PNG-google"
  assert ext == "png"
  assert calls == [{
    "prompt": "prompt-text",
    "model": "gemini-3-pro-image-preview",  # Nano Banana Pro is default
    "aspect_ratio": "3:4",
  }]


def test_model_fast_tier_routes_to_google_flash(monkeypatch):
  """``--model fast`` resolves to the fast image model for Google."""
  calls: list[dict] = []

  def fake_google(prompt, model, *, aspect_ratio):
    calls.append({"model": model})
    return (b"\x89PNG-flash", "png")

  monkeypatch.setattr(llm, "google_image", fake_google)
  llm.generate_image("google", "p", "portrait", model="fast")
  assert calls == [{"model": "gemini-3.1-flash-image-preview"}]


def test_explicit_image_model_id_used_for_image_step(monkeypatch):
  """An image-shaped --model ID is honoured for the image step."""
  calls: list[dict] = []

  def fake_google(prompt, model, *, aspect_ratio):
    calls.append({"model": model})
    return (b"\x89PNG", "png")

  monkeypatch.setattr(llm, "google_image", fake_google)
  llm.generate_image(
    "google", "p", "portrait", model="gemini-3-pro-image-preview",
  )
  assert calls == [{"model": "gemini-3-pro-image-preview"}]


def test_resolve_image_model_picks_per_tier():
  assert llm.resolve_model("google", "image", None) == \
    "gemini-3-pro-image-preview"
  assert llm.resolve_model("google", "image", "pro") == \
    "gemini-3-pro-image-preview"
  assert llm.resolve_model("google", "image", "fast") == \
    "gemini-3.1-flash-image-preview"
  assert llm.resolve_model("openai", "image", None) == "gpt-image-2"
  # Explicit image-shaped ID wins for the image step.
  assert llm.resolve_model("google", "image", "custom-image-x") \
    == "custom-image-x"


def test_text_shaped_id_falls_back_to_pro_for_image_step():
  """A text-shaped --model only overrides text; the image step
  falls back to the pro image default."""
  assert llm.resolve_model("openai", "image", "gpt-4o-mini") \
    == "gpt-image-2"


def test_is_image_model_id_heuristic():
  assert llm.is_image_model_id("gemini-3-pro-image-preview")
  assert llm.is_image_model_id("gpt-image-2")
  assert llm.is_image_model_id("dall-e-3")
  assert llm.is_image_model_id("imagen-3")
  assert not llm.is_image_model_id("gemini-3.1-pro-preview")
  assert not llm.is_image_model_id("gpt-4o-mini")


def test_dispatch_routes_to_openai_with_family_size_and_model(monkeypatch):
  calls: list[dict] = []

  def fake_openai(prompt, model, *, size, quality, moderation):
    calls.append({
      "prompt": prompt, "model": model, "size": size,
      "quality": quality, "moderation": moderation,
    })
    return (b"\x89PNG-openai", "png")

  monkeypatch.setattr(llm, "openai_image", fake_openai)
  png, ext = llm.generate_image(
    "openai", "p", "family", model="gpt-image-2-custom"
  )
  assert png == b"\x89PNG-openai"
  assert ext == "png"
  # Explicit model IDs default to pro-tier quality.
  assert calls == [{
    "prompt": "p",
    "model": "gpt-image-2-custom",
    "size": "1536x1024",
    "quality": "high",
    "moderation": "low",
  }]


def test_openai_fast_tier_uses_low_quality(monkeypatch):
  calls: list[dict] = []

  def fake_openai(prompt, model, *, size, quality, moderation):
    calls.append({"quality": quality, "moderation": moderation})
    return (b"x", "png")

  monkeypatch.setattr(llm, "openai_image", fake_openai)
  llm.generate_image("openai", "p", "portrait", model="fast")
  assert calls == [{"quality": "low", "moderation": "low"}]


def test_openai_pro_tier_uses_high_quality(monkeypatch):
  calls: list[dict] = []

  def fake_openai(prompt, model, *, size, quality, moderation):
    calls.append({"quality": quality, "moderation": moderation})
    return (b"x", "png")

  monkeypatch.setattr(llm, "openai_image", fake_openai)
  llm.generate_image("openai", "p", "portrait", model="pro")
  assert calls == [{"quality": "high", "moderation": "low"}]


def test_unknown_provider_raises_valueerror():
  with pytest.raises(ValueError, match="unknown provider"):
    llm.generate_image("anthropic", "p", "portrait")


def test_unknown_kind_raises_valueerror():
  with pytest.raises(ValueError, match="unknown kind"):
    llm.generate_image("google", "p", "still-life")


def test_missing_openai_sdk_raises_with_install_hint(monkeypatch):
  monkeypatch.setitem(sys.modules, "openai", None)
  with pytest.raises(RuntimeError, match=r"openai package not installed"):
    llm.openai_image(
      "p", "gpt-image-2", size="1024x1536",
      quality="high", moderation="low",
    )


def test_missing_google_sdk_raises_with_install_hint(monkeypatch):
  monkeypatch.setitem(sys.modules, "google.genai", None)
  with pytest.raises(
    RuntimeError, match=r"google-genai package not installed"
  ):
    llm.google_image("p", "gemini-3.1-flash-image-preview",
                     aspect_ratio="3:4")


def test_instruction_for_returns_assembled_base_when_no_model():
  """``instruction_for`` now assembles the kind's core with the
  default section (no overlay when image_model is None or
  unknown)."""
  from rimportrait.render import instruction_for
  for kind in ("portrait", "family", "action"):
    out = instruction_for(kind)
    assert "Always avoid (style-independent):" in out
    # No model overlay when no image_model.
    assert "Additional notes for" not in out
  # Unknown image model -> no overlay either.
  assert "Additional notes for" not in instruction_for(
    "portrait", image_model="unknown"
  )


def test_instruction_for_appends_model_overlay_when_known():
  from rimportrait.render import instruction_for
  out = instruction_for("portrait", image_model="gpt-image-2")
  assert "Additional notes for OpenAI gpt-image-2" in out
  # Default mode trigger is "Photorealistic".
  assert "Lead the paragraph with \"Photorealistic\"" in out

  out = instruction_for(
    "portrait", image_model="gemini-3-pro-image-preview"
  )
  assert "Nano Banana Pro" in out
  assert "POSITIVE reframing" in out

  out = instruction_for(
    "portrait", image_model="gemini-3.1-flash-image-preview"
  )
  assert "Nano Banana 2" in out
  assert "Flash drops detail aggressively" in out


def test_instruction_for_action_with_overlay():
  from rimportrait.render import instruction_for
  out = instruction_for("action", image_model="gpt-image-2")
  assert "RimWorld sci-fi colony action still, no UI." in out
  assert "Additional notes for OpenAI gpt-image-2" in out


def test_instruction_for_section_swaps_mode_trigger_and_closer():
  """When a StyleSection is passed, the kind's core renders with
  the section's closer + prose, and the overlay receives the
  section's mode trigger."""
  from rimportrait.render import instruction_for
  from rimportrait.style import StyleSection
  custom = StyleSection(
    prose="Style:\nTest style prose.",
    mode_trigger="A test trigger",
    closer_phrase="test closer phrase, no UI.",
  )
  out = instruction_for(
    "portrait", image_model="gpt-image-2", section=custom,
  )
  # Closer is spliced in both Output-format and validation item 10.
  assert 'End with: "test closer phrase, no UI."' in out
  assert 'closing phrase is exactly: "test closer phrase, no UI."' in out
  # Section prose lands in the body.
  assert "Test style prose." in out
  # Overlay's leading-verb rule uses the section's mode trigger.
  assert "Lead the paragraph with \"A test trigger\"" in out


def test_instruction_for_unknown_kind_raises():
  import pytest
  from rimportrait.render import instruction_for
  with pytest.raises(ValueError, match="unknown render kind"):
    instruction_for("still-life")
