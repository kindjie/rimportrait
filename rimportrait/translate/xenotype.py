"""Xenotype def -> description, with mod-aware fallback.

Step 4 drops the curated XENOTYPE_VISUAL table; the rendered text is
now the xenotype def's description from the mod-aware def index, with
a label/humanised-slug fallback. Step 5 will extend the fallback chain
to list constituent genes when no description is available.
"""

from __future__ import annotations

from ._common import description_for


def describe_xenotype(
  name: str | None,
  descriptions: dict[str, str] | None = None,
  labels: dict[str, str] | None = None,
) -> str | None:
  if not name:
    return None
  return description_for(name, descriptions, labels)
