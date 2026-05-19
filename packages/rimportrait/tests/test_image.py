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
    "model": "gemini-3.1-flash-image-preview",
    "aspect_ratio": "3:4",
  }]


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
