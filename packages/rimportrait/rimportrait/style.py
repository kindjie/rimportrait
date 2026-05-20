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
  scene: str | None = None
  time: str | None = None
  # Swap the LLM system instruction's base voice. None = default
  # (portrait for --pawn, family for --family). Set to "action" on
  # presets that want a cinematic-action-still shape.
  base: str | None = None

  def any_set(self) -> bool:
    return any(
      (self.style, self.shot, self.camera, self.scene, self.time)
    )


PRESETS: dict[str, StylePreset] = {
  "renaissance": StylePreset(
    style=(
      "Renaissance oil painting on canvas against a plain dark "
      "background - this is a painted portrait, NOT a photograph. "
      "Use painted language (brushwork, glaze, impasto, sfumato, "
      "varnish, underpainting), not photographic language (lens, "
      "depth of field, photorealistic, film grain). Do NOT begin "
      "the prompt with 'Photorealistic'"
    ),
    shot=(
      "classical sitter portrait, head-and-shoulders or "
      "three-quarter, warm gaze just off-camera, restrained "
      "gesture, subject set against a plain unadorned dark "
      "background"
    ),
    camera=(
      "Old Masters technique: warm underpainting beneath thin "
      "translucent glazes, visible directional brushwork and "
      "impasto highlights on raised features, soft sfumato "
      "transitions on the skin, deep chiaroscuro from a single high "
      "warm light source from camera-left, restrained earth-tone "
      "palette (umber, sienna, ochre, bone, deep madder), painterly "
      "background reduced to atmospheric darkness, subtle canvas "
      "weave texture throughout, slight aged varnish patina"
    ),
  ),
  "action": StylePreset(
    base="action",
    shot=(
      "the scene's verb pulled from the block's Pose/activity, "
      "Inspiration, or combat-readiness signal - if the pawn is in "
      "combat, inspired (shoot frenzy / berserker rage / frenetic), "
      "piloting, shambling, drug-high, or aggressive, escalate to "
      "the most dramatic plausible instant of that moment"
    ),
    camera=(
      "motivated lighting from a visible source in frame, motion "
      "evidence (dust, sparks, recoil, debris, blurred fast-moving "
      "elements), layered foreground/midground/background, sharp "
      "eyes and hands against a slightly blurred background"
    ),
  ),
  "oil-painting": StylePreset(
    style="oil painting",
    shot="posed studio portrait, restrained background, classical framing",
    camera="soft visible brushwork, warm palette, chiaroscuro shadows",
  ),
  "comic": StylePreset(
    style=(
      "Western graphic novel ink illustration - bold hand-drawn "
      "black inks, halftone screentone shading, high-contrast spot "
      "color; emphatically NOT anime, NOT manga, NOT cel-shaded"
    ),
    shot="dramatic three-quarter pose, comic-book panel composition",
    camera=(
      "bold black ink linework, halftone screentone shading, "
      "hard-edged shadows, limited spot color, gritty paper texture"
    ),
  ),
  "anime": StylePreset(
    style=(
      "Japanese anime / manga cel-shaded illustration - clean line "
      "art, two-tone shadows, painted backgrounds, 1990s-early-2000s "
      "OVA film grain; emphatically NOT Western comic inks, NOT "
      "halftone, NOT graphic novel"
    ),
    shot=(
      "expressive three-quarter pose, manga-panel composition, "
      "dynamic foreshortening"
    ),
    camera=(
      "clean cel-shading with two-tone shadows, crisp line art, "
      "subtle rim light and bloom, painted background, 90s OVA film "
      "grain"
    ),
  ),
  "propaganda": StylePreset(
    style="stark Soviet propaganda poster",
    shot="heroic low-angle pose, banner flutters in frame",
    camera="hard edges, limited palette of crimson, off-white, ink black",
  ),
  "pixel-art": StylePreset(
    style=(
      "high-detail modern painterly pixel art - hand-placed pixels "
      "with painterly highlights, limited palette, deliberate "
      "pixel contour; NOT chunky 8-bit retro, NOT vector, NOT "
      "smooth digital painting"
    ),
    shot=(
      "tight portrait or three-quarter, sprite-sheet framing, "
      "deliberate pixel contour on every silhouette edge"
    ),
    camera=(
      "limited palette of 24-48 colors, hard pixel edges with no "
      "anti-aliasing on outlines, selective dithering for shading, "
      "subtle painted highlights for depth, perceptibly chunky "
      "pixels (the texture must read as deliberate pixel art, not "
      "downscaled high-res)"
    ),
  ),
}


def resolve(
  preset: str | None,
  style: str | None,
) -> StylePreset:
  """Merge a preset (if any) with the freeform ``--style`` override.

  The preset's pre-set ``shot`` / ``camera`` / ``scene`` / ``time``
  fields flow through unchanged - presets are richer bundles than
  the CLI exposes flag-by-flag. The CLI only exposes ``--preset``
  and ``--style`` so callers express *what aesthetic*, not the
  granular composition / lens / scene / time knobs (those live in
  the preset author's hands or are inferred from the rendered
  block's Setting / Time of day lines)."""
  base = PRESETS[preset] if preset else StylePreset()
  return StylePreset(
    style=style or base.style,
    shot=base.shot,
    camera=base.camera,
    scene=base.scene,
    time=base.time,
    base=base.base,
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
  if preset.scene:
    bits.append(f"Scene: {preset.scene}.")
  if preset.time:
    bits.append(f"Time of day: {preset.time}.")
  addendum = " ".join(bits)

  # The override block PREPENDS the base instruction so it lands
  # before the base's own style/closer guidance and takes precedence.
  # Without this, the base instruction (which is long) tends to
  # drown out a trailing addendum.
  override_lines = [
    "USER STYLE OVERRIDE - the following directives take precedence "
    "over any default style guidance in the task below:",
    "",
    addendum,
  ]
  # When preset.base is set (e.g. action), let the base instruction's
  # own closer stand - the addendum still applies, but we don't
  # rewrite the closer with a portrait-style line that would
  # conflict.
  if preset.style and not preset.base:
    descriptor = (
      "family portrait" if kind == "family" else "portrait"
    )
    short = _short_style(preset.style)
    override_lines.append(
      f'End the paragraph with: "{short} RimWorld sci-fi colony '
      f'{descriptor}, no UI." This closer replaces any default '
      f'"End with" line in the task below.'
    )
  override = "\n".join(override_lines)
  return f"{override}\n\n---\n\n{base_instruction}"


def _short_style(style: str) -> str:
  """Trim a verbose style string down to the leading phrase.

  Used for the "End with ..." closer so a multi-sentence style
  (e.g. comic preset's explicit "not anime" anti-reference) doesn't
  swallow the closer. The full prose still appears in the "Style:"
  line of the addendum where the LLM uses it as guidance.

  Heuristic: take everything before the first ``" - "``, ``" ("``
  or sentence end (". ").
  """
  for sep in (" - ", " (", ". "):
    if sep in style:
      style = style.split(sep, 1)[0]
  return style.strip().rstrip(",")
