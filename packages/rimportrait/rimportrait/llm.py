"""Pipe a rendered portrait block through an LLM to get an image
prompt, and optionally feed that prompt to an image-generation model.

Two providers (google, openai), both with lazy SDK imports so callers
who never pass ``--generate`` / ``--image`` don't pay the import cost.
API keys are read from the provider's standard env var at call time
(no constructor args).
"""

from __future__ import annotations

import base64


# Model resolution
#
# A single ``--model TIER|MODEL_ID`` flag drives both the text and the
# image step. Two tier names (``fast``, ``pro``) resolve per-provider
# per-kind via the table below. An explicit model ID (anything not in
# TIERS) only affects the step its ID belongs to (text vs image is
# inferred from the ID) — the other step falls back to ``pro``.
PROVIDERS: tuple[str, ...] = ("google", "openai")

TIERS: tuple[str, ...] = ("fast", "pro")

_MODELS: dict[tuple[str, str, str], str] = {
  # (kind, provider, tier) -> model id
  ("text",  "google", "pro"):  "gemini-3.1-pro-preview",
  ("text",  "google", "fast"): "gemini-flash-latest",
  ("text",  "openai", "pro"):  "gpt-5.5",
  ("text",  "openai", "fast"): "gpt-4o",
  ("image", "google", "pro"):  "gemini-3-pro-image-preview",  # Nano Banana Pro
  ("image", "google", "fast"): "gemini-3.1-flash-image-preview",  # Nano Banana 2
  ("image", "openai", "pro"):  "gpt-image-2",
  ("image", "openai", "fast"): "gpt-image-2",  # no separate fast tier
}


def is_image_model_id(model_id: str) -> bool:
  """Heuristic routing for an explicit ``--model`` ID. Image-gen model
  IDs typically contain ``image``, ``imagen``, or ``dall-e``."""
  s = model_id.lower()
  return "image" in s or "imagen" in s or "dall-e" in s


def resolve_model(
  provider: str, kind: str, model_arg: str | None
) -> str:
  """Pick the model that will actually be called for ``kind``
  (``text`` or ``image``) on ``provider``.

  ``model_arg`` may be:
  - None or ``pro``  -> the provider's default (pro) model for the kind.
  - ``fast``         -> the provider's fast model for the kind.
  - any other string -> an explicit model ID. Applied only when the
    ID matches ``kind`` (image IDs to image, text IDs to text); the
    non-matching step falls back to the pro default. This lets users
    override one step without forcing the other to a wrong model.
  """
  if provider not in PROVIDERS:
    raise ValueError(
      f"unknown provider {provider!r}; expected one of {PROVIDERS}"
    )
  if kind not in ("text", "image"):
    raise ValueError(
      f"unknown kind {kind!r}; expected 'text' or 'image'"
    )
  if model_arg is None or model_arg == "pro":
    return _MODELS[(kind, provider, "pro")]
  if model_arg == "fast":
    return _MODELS[(kind, provider, "fast")]
  # Explicit model ID: only honour for the step whose kind matches.
  arg_is_image = is_image_model_id(model_arg)
  if (kind == "image") == arg_is_image:
    return model_arg
  return _MODELS[(kind, provider, "pro")]

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


def complete(
  provider: str,
  system: str,
  user: str,
  model: str | None = None,
) -> str:
  if provider not in _DISPATCH:
    raise ValueError(
      f"unknown provider {provider!r}; expected one of {PROVIDERS}"
    )
  resolved_model = resolve_model(provider, "text", model)
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


def generate_image(
  provider: str,
  prompt: str,
  kind: str,
  model: str | None = None,
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
  resolved_model = resolve_model(provider, "image", model)
  if provider == "openai":
    return openai_image(
      prompt, resolved_model, size=_KIND_OPENAI_SIZE[kind]
    )
  return google_image(
    prompt, resolved_model, aspect_ratio=_KIND_GOOGLE_ASPECT[kind]
  )
