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


def test_dispatch_with_fast_routes_to_google_flash(monkeypatch):
  calls: list[dict] = []

  def fake_google(prompt, model, *, aspect_ratio):
    calls.append({"model": model})
    return (b"\x89PNG-flash", "png")

  monkeypatch.setattr(llm, "google_image", fake_google)
  llm.generate_image("google", "p", "portrait", fast=True)
  assert calls == [{"model": "gemini-3.1-flash-image-preview"}]


def test_explicit_image_model_beats_fast(monkeypatch):
  calls: list[dict] = []

  def fake_google(prompt, model, *, aspect_ratio):
    calls.append({"model": model})
    return (b"\x89PNG", "png")

  monkeypatch.setattr(llm, "google_image", fake_google)
  llm.generate_image(
    "google", "p", "portrait",
    model="gemini-3-pro-image-preview", fast=True,
  )
  # Explicit model wins over --fast.
  assert calls == [{"model": "gemini-3-pro-image-preview"}]


def test_resolve_image_model_picks_per_table():
  assert llm.resolve_image_model("google") == \
    "gemini-3-pro-image-preview"
  assert llm.resolve_image_model("google", fast=True) == \
    "gemini-3.1-flash-image-preview"
  assert llm.resolve_image_model("openai") == "gpt-image-2"
  # Explicit override always wins.
  assert llm.resolve_image_model("google", "custom-model") == \
    "custom-model"
  assert llm.resolve_image_model(
    "google", "custom-model", fast=True
  ) == "custom-model"


def test_dispatch_routes_to_openai_with_family_size_and_model(monkeypatch):
  calls: list[dict] = []

  def fake_openai(prompt, model, *, size):
    calls.append(
      {"prompt": prompt, "model": model, "size": size}
    )
    return (b"\x89PNG-openai", "png")

  monkeypatch.setattr(llm, "openai_image", fake_openai)
  png, ext = llm.generate_image(
    "openai", "p", "family", model="gpt-image-2-custom"
  )
  assert png == b"\x89PNG-openai"
  assert ext == "png"
  assert calls == [{
    "prompt": "p",
    "model": "gpt-image-2-custom",
    "size": "1536x1024",
  }]


def test_unknown_provider_raises_valueerror():
  with pytest.raises(ValueError, match="unknown provider"):
    llm.generate_image("anthropic", "p", "portrait")


def test_unknown_kind_raises_valueerror():
  with pytest.raises(ValueError, match="unknown kind"):
    llm.generate_image("google", "p", "still-life")


def test_missing_openai_sdk_raises_with_install_hint(monkeypatch):
  monkeypatch.setitem(sys.modules, "openai", None)
  with pytest.raises(RuntimeError, match=r"pip install .*openai"):
    llm.openai_image("p", "gpt-image-2", size="1024x1536")


def test_missing_google_sdk_raises_with_install_hint(monkeypatch):
  monkeypatch.setitem(sys.modules, "google.genai", None)
  with pytest.raises(RuntimeError, match=r"pip install .*google"):
    llm.google_image("p", "gemini-3.1-flash-image-preview",
                     aspect_ratio="3:4")


def test_default_image_models_cover_all_providers():
  assert set(llm.DEFAULT_IMAGE_MODELS) == set(llm.PROVIDERS)


def test_fast_image_models_cover_all_providers():
  assert set(llm.FAST_IMAGE_MODELS) == set(llm.PROVIDERS)


def test_instruction_for_returns_base_when_no_model():
  from rimportrait.render import (
    instruction_for,
    SINGLE_PROMPT_INSTRUCTION,
    FAMILY_PROMPT_INSTRUCTION,
    ACTION_PROMPT_INSTRUCTION,
  )
  assert instruction_for("portrait") is SINGLE_PROMPT_INSTRUCTION
  assert instruction_for("family") is FAMILY_PROMPT_INSTRUCTION
  assert instruction_for("action") is ACTION_PROMPT_INSTRUCTION
  # Unknown image model -> fall back to base, no overlay appended.
  assert instruction_for("portrait", image_model="unknown") \
    is SINGLE_PROMPT_INSTRUCTION


def test_instruction_for_appends_model_overlay_when_known():
  from rimportrait.render import (
    instruction_for, SINGLE_PROMPT_INSTRUCTION,
  )
  out = instruction_for("portrait", image_model="gpt-image-2")
  assert out.startswith(SINGLE_PROMPT_INSTRUCTION)
  assert out != SINGLE_PROMPT_INSTRUCTION
  assert "Additional notes for OpenAI gpt-image-2" in out

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
  from rimportrait.render import (
    instruction_for, ACTION_PROMPT_INSTRUCTION,
  )
  out = instruction_for("action", image_model="gpt-image-2")
  assert out.startswith(ACTION_PROMPT_INSTRUCTION)
  assert "Additional notes for OpenAI gpt-image-2" in out


def test_instruction_for_unknown_kind_raises():
  import pytest
  from rimportrait.render import instruction_for
  with pytest.raises(ValueError, match="unknown render kind"):
    instruction_for("still-life")
