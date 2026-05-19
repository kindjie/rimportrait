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
  assert calls == [("sys", "usr", "gemini-flash-latest")]


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
  with pytest.raises(RuntimeError, match=r"pip install .*openai"):
    llm.openai_complete("s", "u", "gpt-4o-mini")


def test_missing_google_sdk_raises_with_install_hint(monkeypatch):
  monkeypatch.setitem(sys.modules, "google.genai", None)
  with pytest.raises(RuntimeError, match=r"pip install .*google"):
    llm.google_complete("s", "u", "gemini-flash-latest")


def test_default_models_cover_all_providers():
  assert set(llm.DEFAULT_MODELS) == set(llm.PROVIDERS)
