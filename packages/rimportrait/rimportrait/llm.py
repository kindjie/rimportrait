"""Pipe a rendered portrait block through an LLM to get an image prompt.

Two providers, both with lazy SDK imports so callers who never pass
``--generate`` don't pay the import cost. API keys are read from the
provider's standard env var at call time (no constructor args).
"""

from __future__ import annotations


DEFAULT_MODELS: dict[str, str] = {
  "google": "gemini-flash-latest",
  "openai": "gpt-4o-mini",
}

PROVIDERS = tuple(DEFAULT_MODELS.keys())


def openai_complete(system: str, user: str, model: str) -> str:
  try:
    from openai import OpenAI  # type: ignore[import-not-found]
  except ImportError as e:
    raise RuntimeError(
      "openai package not installed; "
      "pip install 'rimportrait[openai]'"
    ) from e
  client = OpenAI()
  resp = client.chat.completions.create(
    model=model,
    messages=[
      {"role": "system", "content": system},
      {"role": "user", "content": user},
    ],
  )
  content = resp.choices[0].message.content
  if not content:
    raise RuntimeError("openai returned empty content")
  return content.strip()


def google_complete(system: str, user: str, model: str) -> str:
  try:
    from google import genai  # type: ignore[import-not-found]
    from google.genai import types  # type: ignore[import-not-found]
  except ImportError as e:
    raise RuntimeError(
      "google-genai package not installed; "
      "pip install 'rimportrait[google]'"
    ) from e
  client = genai.Client()
  resp = client.models.generate_content(
    model=model,
    contents=user,
    config=types.GenerateContentConfig(system_instruction=system),
  )
  text = resp.text
  if not text:
    raise RuntimeError("google-genai returned empty content")
  return text.strip()


_DISPATCH = {
  "openai": openai_complete,
  "google": google_complete,
}


def complete(
  provider: str, system: str, user: str, model: str | None = None
) -> str:
  if provider not in _DISPATCH:
    raise ValueError(
      f"unknown provider {provider!r}; expected one of {PROVIDERS}"
    )
  resolved_model = model or DEFAULT_MODELS[provider]
  return _DISPATCH[provider](system, user, resolved_model)
