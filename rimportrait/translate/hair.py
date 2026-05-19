"""Hair style and GradientHair descriptions.

Hair defs/labels/texture paths map to a short style description used
in the head-and-face block. Texture path is preferred over label since
the same label can map to different visual styles across mod packs.

GradientHair mask def names map to a phrase describing where the
gradient sits on the strand.
"""

from __future__ import annotations


HAIR_STYLE_BY_TEXTURE: dict[str, str] = {
  "Hairs/fluffySidePartS": "thick side-swept voluminous hair",
  "Hairs/fluffySidePartM": "thick side-swept voluminous hair",
  "Hairs/fluffySidePartL": "thick side-swept voluminous hair",
}

HAIR_STYLE_BY_DEF: dict[str, str] = {
  "SDfluffysideparts": "thick side-swept voluminous hair",
}

HAIR_STYLE_BY_LABEL: dict[str, str] = {
  "SD Zayne": "thick side-swept voluminous hair",
}


GRADIENT_MASK_REGION: dict[str, str] = {
  "GradientHair/MaskAHigh": "tip-only gradient region",
  "GradientHair/MaskAMid": "mid-length gradient region",
  "GradientHair/MaskALow": "root-only gradient region",
  "GradientHair/MaskBHigh": "tip-only gradient region",
  "GradientHair/MaskBMidHigh": "mid-to-tip gradient region",
  "GradientHair/MaskBLow": "root-to-mid gradient region",
  "GradientHair/MaskBFull": "full-length gradient",
  "GradientHair/MaskCHigh": "tip-only side gradient region",
  "GradientHair/MaskCMid": "mid-length side gradient region",
  "GradientHair/MaskCLow": "root-side gradient region",
}


def describe_hair_style(
  hair_def: str | None,
  hair_label: str | None,
  hair_texture_path: str | None,
) -> str | None:
  if hair_texture_path and hair_texture_path in HAIR_STYLE_BY_TEXTURE:
    return HAIR_STYLE_BY_TEXTURE[hair_texture_path]
  if hair_def and hair_def in HAIR_STYLE_BY_DEF:
    return HAIR_STYLE_BY_DEF[hair_def]
  if hair_label and hair_label in HAIR_STYLE_BY_LABEL:
    return HAIR_STYLE_BY_LABEL[hair_label]
  return None


def describe_gradient_mask(mask: str | None) -> str | None:
  if not mask:
    return None
  return GRADIENT_MASK_REGION.get(mask, mask)
