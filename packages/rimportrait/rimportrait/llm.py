"""Pipe a rendered portrait block through an LLM to get an image
prompt, and optionally feed that prompt to an image-generation model.

Two providers (google, openai), both with lazy SDK imports so callers
who never pass ``--generate`` / ``--image`` don't pay the import cost.
API keys are read from the provider's standard env var at call time
(no constructor args).
"""

from __future__ import annotations

import base64


DEFAULT_MODELS: dict[str, str] = {
  "google": "gemini-3.1-pro-preview",  # Gemini 3 Pro - high quality text
  "openai": "gpt-4o-mini",
}

FAST_MODELS: dict[str, str] = {
  "google": "gemini-flash-latest",  # Flash - fast / cheap text
  "openai": "gpt-4o-mini",  # OpenAI exposes no separate fast tier
}

DEFAULT_IMAGE_MODELS: dict[str, str] = {
  "google": "gemini-3-pro-image-preview",  # Nano Banana Pro (high quality)
  "openai": "gpt-image-2",
}

FAST_IMAGE_MODELS: dict[str, str] = {
  "google": "gemini-3.1-flash-image-preview",  # Nano Banana 2 (fast)
  "openai": "gpt-image-2",  # OpenAI exposes no separate fast tier
}

PROVIDERS = tuple(DEFAULT_MODELS.keys())

_KIND_OPENAI_SIZE = {
  "portrait": "1024x1536",
  "family": "1536x1024",
}
_KIND_GOOGLE_ASPECT = {
  "portrait": "3:4",
  "family": "4:3",
}


def openai_complete(system: str, user: str, model: str) -> str:
  try:
    from openai import OpenAI  # type: ignore[import-not-found]
  except ImportError as e:
    raise RuntimeError(
      "openai package not installed; "
      "uv pip install -e 'packages/rimportrait[openai]' "
      "(or `uv add --dev 'rimportrait[openai]'`)"
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
      "uv pip install -e 'packages/rimportrait[google]' "
      "(or `uv add --dev 'rimportrait[google]'`)"
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


def resolve_text_model(
  provider: str, model: str | None = None, fast: bool = False
) -> str:
  """Pick the text model that will actually be called.

  Mirrors :func:`resolve_image_model`. Explicit ``model`` always
  wins; otherwise return the fast variant if ``fast`` is set, else
  the default.
  """
  if model:
    return model
  if provider not in DEFAULT_MODELS:
    raise ValueError(
      f"unknown provider {provider!r}; expected one of {PROVIDERS}"
    )
  table = FAST_MODELS if fast else DEFAULT_MODELS
  return table[provider]


def complete(
  provider: str,
  system: str,
  user: str,
  model: str | None = None,
  *,
  fast: bool = False,
) -> str:
  if provider not in _DISPATCH:
    raise ValueError(
      f"unknown provider {provider!r}; expected one of {PROVIDERS}"
    )
  resolved_model = resolve_text_model(provider, model, fast)
  return _DISPATCH[provider](system, user, resolved_model)


# --- image generation ----------------------------------------------


def openai_image(prompt: str, model: str, *, size: str) -> tuple[bytes, str]:
  try:
    from openai import OpenAI  # type: ignore[import-not-found]
  except ImportError as e:
    raise RuntimeError(
      "openai package not installed; "
      "uv pip install -e 'packages/rimportrait[openai]' "
      "(or `uv add --dev 'rimportrait[openai]'`)"
    ) from e
  client = OpenAI()
  resp = client.images.generate(model=model, prompt=prompt, size=size)
  data = resp.data
  if not data or not data[0].b64_json:
    raise RuntimeError("openai images returned no content")
  return base64.b64decode(data[0].b64_json), "png"


def google_image(
  prompt: str, model: str, *, aspect_ratio: str
) -> tuple[bytes, str]:
  try:
    from google import genai  # type: ignore[import-not-found]
    from google.genai import types  # type: ignore[import-not-found]
  except ImportError as e:
    raise RuntimeError(
      "google-genai package not installed; "
      "uv pip install -e 'packages/rimportrait[google]' "
      "(or `uv add --dev 'rimportrait[google]'`)"
    ) from e

  def _config(with_aspect: bool):
    kwargs: dict = {"response_modalities": ["IMAGE"]}
    if with_aspect and hasattr(types, "ImageConfig"):
      try:
        kwargs["image_config"] = types.ImageConfig(
          aspect_ratio=aspect_ratio
        )
      except Exception:
        pass
    return types.GenerateContentConfig(**kwargs)

  client = genai.Client()
  try:
    resp = client.models.generate_content(
      model=model, contents=[prompt], config=_config(True)
    )
  except Exception as e:
    msg = str(e).lower()
    if "image_config" in msg or "aspect" in msg:
      resp = client.models.generate_content(
        model=model, contents=[prompt], config=_config(False)
      )
    else:
      raise
  if not resp.candidates:
    raise RuntimeError("google-genai returned no candidates")
  parts = resp.candidates[0].content.parts or []
  for part in parts:
    inline = getattr(part, "inline_data", None)
    if inline and getattr(inline, "mime_type", "").startswith("image/"):
      ext = inline.mime_type.split("/")[-1] or "png"
      return inline.data, ext
  raise RuntimeError("google-genai returned no image part")


_IMAGE_DISPATCH = {
  "openai": openai_image,
  "google": google_image,
}


def resolve_image_model(
  provider: str, model: str | None = None, fast: bool = False
) -> str:
  """Pick the image model that will actually be called.

  Explicit ``model`` always wins. Otherwise return the fast variant
  if ``fast`` is set, else the default. Used by both
  :func:`generate_image` (for the actual call) and the CLI (so the
  text step knows which model-specific instruction to use).
  """
  if model:
    return model
  if provider not in DEFAULT_IMAGE_MODELS:
    raise ValueError(
      f"unknown provider {provider!r}; expected one of {PROVIDERS}"
    )
  table = FAST_IMAGE_MODELS if fast else DEFAULT_IMAGE_MODELS
  return table[provider]


def generate_image(
  provider: str,
  prompt: str,
  kind: str,
  model: str | None = None,
  *,
  fast: bool = False,
) -> tuple[bytes, str]:
  """Return ``(image_bytes, extension)`` for the prompt.

  ``kind`` picks portrait/landscape framing per the rimportrait
  render kind. ``extension`` is the suggested file extension (no dot)
  derived from the response mime type.
  """
  if provider not in _IMAGE_DISPATCH:
    raise ValueError(
      f"unknown provider {provider!r}; expected one of {PROVIDERS}"
    )
  if kind not in _KIND_OPENAI_SIZE:
    raise ValueError(
      f"unknown kind {kind!r}; expected 'portrait' or 'family'"
    )
  resolved_model = resolve_image_model(provider, model, fast)
  if provider == "openai":
    return openai_image(
      prompt, resolved_model, size=_KIND_OPENAI_SIZE[kind]
    )
  return google_image(
    prompt, resolved_model, aspect_ratio=_KIND_GOOGLE_ASPECT[kind]
  )
