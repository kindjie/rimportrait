"""LLM dispatch + missing-SDK error-shape tests.

Real provider SDKs are not exercised here — the dispatch layer is
monkeypatched so the suite stays offline-safe and doesn't require
either optional dep to be installed.
"""

from __future__ import annotations

import sys

import pytest

from rimportrait import llm


def test_dispatch_routes_to_google(monkeypatch):
  calls: list[tuple[str, str, str]] = []
  monkeypatch.setitem(
    llm._DISPATCH, "google",
    lambda system, user, model: (
      calls.append((system, user, model)) or "gemini result"
    ),
  )
  out = llm.complete("google", system="sys", user="usr")
  assert out == "gemini result"
  # Default Google text model is now Pro.
  assert calls == [("sys", "usr", "gemini-3.1-pro-preview")]


def test_model_fast_tier_routes_text_to_google_flash(monkeypatch):
  """``--model fast`` resolves to the fast text model for Google."""
  calls: list[tuple[str, str, str]] = []
  monkeypatch.setitem(
    llm._DISPATCH, "google",
    lambda system, user, model: (
      calls.append((system, user, model)) or "flash result"
    ),
  )
  llm.complete("google", system="s", user="u", model="fast")
  assert calls == [("s", "u", "gemini-flash-latest")]


def test_model_pro_tier_is_default():
  """``model=None`` and ``model='pro'`` resolve identically."""
  assert llm.resolve_model("google", "text", None) == \
    llm.resolve_model("google", "text", "pro") == \
    "gemini-3.1-pro-preview"


def test_resolve_model_picks_per_tier():
  assert llm.resolve_model("google", "text", "pro") == \
    "gemini-3.1-pro-preview"
  assert llm.resolve_model("google", "text", "fast") == \
    "gemini-flash-latest"
  # Explicit text model ID wins for the text step.
  assert llm.resolve_model("google", "text", "custom-text") \
    == "custom-text"


def test_explicit_image_id_does_not_leak_into_text_step():
  """An image-shaped model ID passed via --model must NOT be used as
  the text model; the text step falls back to the provider's pro
  default. This lets users override only the image step without
  forcing a wrong text model."""
  resolved = llm.resolve_model(
    "google", "text", "gemini-3-pro-image-preview"
  )
  assert resolved == "gemini-3.1-pro-preview"  # the text pro default


def test_explicit_text_id_does_not_leak_into_image_step():
  """Mirror case: a text-shaped --model only overrides text;
  image falls back to pro."""
  resolved = llm.resolve_model("openai", "image", "gpt-4o-mini")
  assert resolved == "gpt-image-2"  # the image pro default


def test_dispatch_routes_to_openai_with_explicit_model(monkeypatch):
  monkeypatch.setitem(
    llm._DISPATCH, "openai",
    lambda system, user, model: f"openai({model})",
  )
  out = llm.complete(
    "openai", system="s", user="u", model="gpt-x"
  )
  assert out == "openai(gpt-x)"


def test_unknown_provider_raises_valueerror():
  with pytest.raises(ValueError, match="unknown provider"):
    llm.complete("anthropic", system="s", user="u")


def test_missing_openai_sdk_raises_with_install_hint(monkeypatch):
  monkeypatch.setitem(sys.modules, "openai", None)
  with pytest.raises(RuntimeError, match=r"openai package not installed"):
    llm.openai_complete("s", "u", "gpt-4o-mini")


def test_missing_google_sdk_raises_with_install_hint(monkeypatch):
  monkeypatch.setitem(sys.modules, "google.genai", None)
  with pytest.raises(
    RuntimeError, match=r"google-genai package not installed"
  ):
    llm.google_complete("s", "u", "gemini-flash-latest")


def test_resolve_model_covers_all_providers_and_kinds():
  """Every (kind, provider, tier) combo must resolve to a model ID
  so the CLI never bottoms out with a missing default."""
  for provider in llm.PROVIDERS:
    for kind in ("text", "image"):
      for tier in llm.TIERS:
        assert llm.resolve_model(provider, kind, tier)
