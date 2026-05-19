"""Style / composition / camera knobs for the LLM instruction.

Three free-form dimensions plus a small dict of named bundles. CLI
flags compose to a :class:`StylePreset`; the resolved values are
spliced into the LLM system instruction in :func:`compose_instruction`
so the downstream text prompt (and, transitively, the image model)
follow the desired aesthetic.

The preset phrasing is **provisional** - "needs workshopping" per the
project owner. Add or refine entries in :data:`PRESETS` as good
phrasings emerge.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StylePreset:
  style: str | None = None
  shot: str | None = None
  camera: str | None = None

  def any_set(self) -> bool:
    return any((self.style, self.shot, self.camera))


PRESETS: dict[str, StylePreset] = {
  "moody-portrait": StylePreset(
    style="realistic gritty",
    shot="posed three-quarter, calm intensity, gaze just off-camera",
    camera="85mm portrait, shallow depth of field, low-key dramatic lighting",
  ),
  "action": StylePreset(
    style="realistic gritty",
    shot="mid-action, dynamic angle, motion blur on extremities",
    camera="35mm wide, deep focus, harsh natural light, dust kicked up",
  ),
  "oil-painting": StylePreset(
    style="oil painting",
    shot="posed studio portrait, restrained background, classical framing",
    camera="soft visible brushwork, warm palette, chiaroscuro shadows",
  ),
  "comic": StylePreset(
    style="graphic novel inks",
    shot="three-quarter pose, dramatic stance",
    camera="bold linework, high contrast shading, halftone texture",
  ),
  "propaganda": StylePreset(
    style="stark Soviet propaganda poster",
    shot="heroic low-angle pose, banner flutters in frame",
    camera="hard edges, limited palette of crimson, off-white, ink black",
  ),
}


def resolve(
  preset: str | None,
  style: str | None,
  shot: str | None,
  camera: str | None,
) -> StylePreset:
  """Merge a preset (if any) with explicit overrides. Overrides win."""
  base = PRESETS[preset] if preset else StylePreset()
  return StylePreset(
    style=style or base.style,
    shot=shot or base.shot,
    camera=camera or base.camera,
  )


def compose_instruction(
  base_instruction: str, kind: str, preset: StylePreset
) -> str:
  """Splice the resolved style knobs into an instruction string.

  When ``preset.any_set()`` is False the base instruction is returned
  unchanged - existing callers see no behaviour change. Otherwise a
  ``Style/Composition/Camera`` paragraph is appended, and when
  ``preset.style`` is set a style-aware "End with" line follows that
  supersedes the base instruction's closer.
  """
  if not preset.any_set():
    return base_instruction

  bits: list[str] = []
  if preset.style:
    bits.append(f"Style: {preset.style}.")
  if preset.shot:
    bits.append(f"Composition: {preset.shot}.")
  if preset.camera:
    bits.append(f"Camera: {preset.camera}.")
  addendum = " ".join(bits)

  if preset.style:
    descriptor = (
      "family portrait" if kind == "family" else "portrait"
    )
    closer = (
      f'End with "{preset.style} RimWorld sci-fi colony '
      f'{descriptor}, no UI."'
    )
    return f"{base_instruction}\n\n{addendum}\n{closer}"
  return f"{base_instruction}\n\n{addendum}"
