"""Hair style + gradient mask passthroughs.

Per the data-first principle the curated hair-style table and the
gradient-mask region table have been removed. The renderer surfaces
the hair def name, mod-aware label, and texture path directly; the
gradient mask is emitted as the raw RimWorld texture path.
"""

from __future__ import annotations


def describe_hair_style(
  hair_def: str | None,
  hair_label: str | None,
  hair_texture_path: str | None,
) -> str | None:
  """Curated style mapping retired; the renderer now uses label+path.

  Returns None unconditionally. Kept as a thin shim so the renderer
  signature stays stable while the surrounding code uses ``hair_label``
  and ``hair_texture_path`` directly.
  """
  _ = (hair_def, hair_label, hair_texture_path)
  return None


def describe_gradient_mask(mask: str | None) -> str | None:
  if not mask:
    return None
  return mask
