"""Style preset registry and instruction composer.

The CLI exposes two style knobs: ``--preset NAME`` and ``--style
"..."``. The preset registry below maps a name to a
:class:`StylePreset` (mostly just a :class:`StyleSection` + an
optional ``base`` swap). The composer assembles the kind's core +
the chosen section into one coherent system instruction; no
prepended override blocks, no closer rewrites — every preset speaks
in one voice.

Section authoring principles
----------------------------
1. **Medium texture is explicit.** Each section's ``prose`` names
   the physical / printing / film / digital artifacts that make
   the medium feel real (brush ridges, halftone dots, cel-paint
   edges + CRT scanlines, pixel-cluster discipline, anamorphic
   flare). Without prompt-side mention, the LLM tends to drop them.
2. ``mode_trigger`` is a noun phrase (so the gpt-image-2 overlay's
   "Lead the paragraph with ``<X>``" line reads naturally for any
   style).
3. ``closer_phrase`` ends in ``, no UI.`` — consistent contract
   for the validation item 10 check + the Output-format "End with:"
   line.
4. Style-dependent ``Avoid`` lives in the section; the base only
   carries the universal "UI, HUD, captions, watermarks, fake
   text" avoidance.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StyleSection:
  """The style-dependent slice of the LLM system instruction.

  Three pieces, because two of them are referenced elsewhere in the
  composed prompt and need to stay programmatically accessible:

  - ``prose`` is the bulk: the ``Style:`` paragraph plus
    Composition / Medium texture / Avoid (style-dependent) blocks.
    Dropped verbatim into the kind's core where the
    ``{style_section_prose}`` placeholder lives.
  - ``mode_trigger`` is the single noun phrase the gpt-image-2
    overlay leads the paragraph with ("Photorealistic" / "An oil
    painting" / "A Japanese anime cel-shaded illustration" / ...).
  - ``closer_phrase`` is the literal closing sentence the LLM must
    end its paragraph with. Spliced into the kind's core in two
    places: the ``End with:`` line of the Output format section
    and validation item 10's exact-phrase check.
  """
  prose: str
  mode_trigger: str
  closer_phrase: str


# --- preset sections ------------------------------------------------

RENAISSANCE_SECTION = StyleSection(
  mode_trigger="An Old Masters oil painting",
  closer_phrase=(
    "Old Masters oil painting RimWorld sci-fi colony portrait, "
    "no UI."
  ),
  prose=(
    "Style:\n"
    "Renaissance Old Masters oil painting on canvas against a plain "
    "unadorned dark background. This is a painted portrait, NOT a "
    "photograph. Use painted language (brushwork, glaze, impasto, "
    "sfumato, varnish, underpainting). Do NOT use photographic "
    "language (lens, depth of field, photorealistic, film grain).\n\n"
    "Composition:\n"
    "Classical sitter portrait, head-and-shoulders or three-quarter, "
    "warm gaze just off-camera, restrained gesture, subject set "
    "against a plain unadorned dark background.\n\n"
    "Medium texture:\n"
    "Visible directional brushwork following the form, raised "
    "impasto highlights on cheekbones / armor edges / fabric "
    "creases, soft sfumato transitions on the skin, deep "
    "translucent glazes layered in the shadows, subtle linen-canvas "
    "weave just visible under thin areas, aged yellow varnish "
    "patina across the whole surface, faint craquelure threading "
    "through the dark passages.\n\n"
    "Avoid (style-dependent):\n"
    "Photographic language, shallow depth of field, lens artifacts, "
    "film grain, modern studio lighting, clean digital edges, "
    "glossy 3D render finish, anime, cartoon, chibi, "
    "passport-photo pose."
  ),
)


ACRYLIC_SECTION = StyleSection(
  mode_trigger="A vibrant acrylic painting",
  closer_phrase=(
    "vibrant acrylic painting RimWorld sci-fi colony portrait, "
    "no UI."
  ),
  prose=(
    "Style:\n"
    "Vibrant contemporary acrylic painting on raw cotton canvas. "
    "Bright saturated palette, opaque flat-layered colour blocks, "
    "confident bristle-brush gestures. This is a modern painted "
    "portrait — NOT an oil glaze, NOT a photograph, NOT a digital "
    "render. Do not use Old Masters chiaroscuro or thin translucent "
    "glazes; acrylic sits on top of the surface, not in it.\n\n"
    "Composition:\n"
    "Posed three-quarter or bust, clean uncluttered background "
    "(a single saturated colour field or a loose painted ground).\n\n"
    "Medium texture:\n"
    "Visible bristle-brush marks running across flat colour blocks, "
    "a slight raised ridge where wet acrylic met dry, ever-so-slight "
    "matte sheen on the painted surface, occasional paint beading at "
    "the bristle ends, raw cotton-canvas weave just visible under "
    "thin areas at the edges, deliberate hue contrasts between "
    "neighbouring blocks rather than smooth gradients.\n\n"
    "Avoid (style-dependent):\n"
    "Photographic language, oil-glaze depth, Old Masters sfumato, "
    "lens artifacts, shallow depth of field, anime, cartoon, "
    "chibi, smooth digital painting."
  ),
)


ACTION_SECTION = StyleSection(
  mode_trigger="A cinematic action still",
  closer_phrase=(
    "realistic gritty RimWorld sci-fi colony action still, no UI."
  ),
  prose=(
    "Style:\n"
    "Realistic live-action cinematic sci-fi or grounded film-still "
    "language. Natural proportions, practical materials, imperfect "
    "surfaces, weathering, dust, sweat, grime, believable clothing.\n\n"
    "Signal selection:\n"
    "Scan the block for ALL active dramatic signals before choosing "
    "a verb. Candidate signals, in descending dramatic priority:\n"
    "  1. Shambler state (reanimated body horror — overrides "
    "everything; render the active mutation).\n"
    "  2. Creepjoiner state (anomaly entity revealing itself — "
    "render the threshold moment).\n"
    "  3. Inspiration (Shoot Frenzy / Berserker Rage / Frenetic / "
    "Inspired Creativity / etc. — render the peak of the inspired "
    "act).\n"
    "  4. Chemical/drug state (active high or withdrawal — render "
    "the visible bodily evidence: dilated eyes, sweat, tremor, "
    "ecstatic stillness).\n"
    "  5. Pilot state when actively piloting (render at the helm, "
    "neural interface engaged).\n"
    "  6. Commanded mechs entourage (render with the mech retinue "
    "in active formation, not idle).\n"
    "  7. Mood extremes (berserk / catatonic / sad-wandering / "
    "tantrum — render the visible behavioural break).\n"
    "  8. Pose/activity (current job) — only when no higher-priority "
    "signal fires. Translate the verb visually: HaulToCell → "
    "dragging a sealed crate mid-stride; Mine → swinging a pick "
    "into rock with sparks; Tend → bandaging a bleeding patient; "
    "etc.\n"
    "PICK the single most dramatic signal that fires, render the "
    "peak instant of THAT moment, and let everything else (gear, "
    "mood, setting) serve it. Do not blend signals into a generic "
    "stance.\n\n"
    "Composition:\n"
    "Layered foreground / subject-midground / background. Motivated "
    "lighting from a visible or plausible scene source — fire, "
    "floodlights, muzzle flash, doorway light, monitors, lightning, "
    "sunrise, emergency lamps. Camera as if filming the action: "
    "shot size, angle, distance, lens feel, handheld / tracking / "
    "over-the-shoulder when useful. Sharp eyes / face / hands "
    "against a slightly blurred background.\n\n"
    "Medium texture:\n"
    "Cinematic 35mm or super-35 film grain across the whole frame, "
    "subtle anamorphic flare across in-frame highlight points, "
    "restrained filmic colour grade (teal-orange or muted earth, "
    "never neon-clean), micro-contrast in the shadow areas, no "
    "perfectly clean digital edges — every edge has a faint optical "
    "softness, motion evidence through physical artifacts (flying "
    "dust, sparks, recoil, debris, blurred fast-moving elements, "
    "torn cloth).\n\n"
    "Avoid (style-dependent):\n"
    "Static portrait pose, centered character-sheet framing, "
    "superhero poster composition, glossy fantasy armor, anime, "
    "cartoon, chibi, plastic-looking 3D render, clean studio "
    "lighting, excessive beauty retouching."
  ),
)


COMIC_SECTION = StyleSection(
  mode_trigger="A Western graphic novel ink illustration",
  closer_phrase=(
    "Western graphic novel ink illustration RimWorld sci-fi colony "
    "portrait, no UI."
  ),
  prose=(
    "Style:\n"
    "Western graphic novel ink illustration. Bold hand-drawn black "
    "inks, halftone screentone shading, high-contrast spot colour. "
    "This is emphatically NOT anime, NOT manga, NOT cel-shaded, "
    "NOT a smooth digital painting.\n\n"
    "Composition:\n"
    "Dramatic three-quarter pose, comic-book panel composition, "
    "hard-edged shadows, limited spot colour palette.\n\n"
    "Medium texture:\n"
    "Printed-page artifacts: Ben Day halftone dots visible at near "
    "distance in screened mid-tones, slight ink bleed into the "
    "paper fibre at solid blacks, faint colour-plate registration "
    "drift where spot colours meet (the cyan or red sits a "
    "half-millimetre off the black), off-white pulpy paper grain "
    "across the whole frame, occasional ink-smear or hairline brush "
    "shake at bold black areas, slight age yellowing.\n\n"
    "Avoid (style-dependent):\n"
    "Photographic skin texture, anime cel-shading, manga screentone "
    "panel-borders, smooth digital painting, sharp clean digital "
    "edges, photorealistic lighting."
  ),
)


ANIME_SECTION = StyleSection(
  mode_trigger="A Japanese anime cel-shaded illustration",
  closer_phrase=(
    "Japanese anime cel-shaded illustration RimWorld sci-fi colony "
    "portrait, no UI."
  ),
  prose=(
    "Style:\n"
    "Japanese anime / manga cel-shaded illustration in the "
    "1990s-early-2000s OVA tradition. Clean line art, two-tone "
    "shadows, painted backgrounds. This is emphatically NOT Western "
    "comic inks, NOT halftone screentone, NOT a graphic novel, NOT "
    "photographic.\n\n"
    "Composition:\n"
    "Expressive three-quarter pose, manga-panel composition, "
    "dynamic foreshortening, painted background that supports the "
    "subject.\n\n"
    "Medium texture:\n"
    "Cel-animation artifacts: visible paint-cell edges where flat "
    "colour blocks meet, line-weight variation along hand-inked "
    "outlines (thicker where shadows would fall, thinner at "
    "highlights), occasional rim-light spill into adjacent areas, "
    "subtle bloom on bright highlights, 35mm OVA film grain "
    "layered on top of the cel work, faint CRT-display scanlines "
    "with mild chromatic aberration at high-contrast edges (as if "
    "the cel is being viewed through a period analogue display), "
    "registration jitter between foreground and background cel "
    "layers.\n\n"
    "Avoid (style-dependent):\n"
    "Photorealistic skin texture, shallow depth of field, lens "
    "artifacts, halftone screentone, Western comic inks, "
    "passport-photo pose, glossy 3D render."
  ),
)


PROPAGANDA_SECTION = StyleSection(
  mode_trigger="A stark Soviet propaganda poster",
  closer_phrase=(
    "stark Soviet propaganda poster RimWorld sci-fi colony "
    "portrait, no UI."
  ),
  prose=(
    "Style:\n"
    "Stark Soviet propaganda silkscreen poster. Heraldic "
    "composition, monumental subject, designed to be read from "
    "across a room. Limited palette of crimson, off-white, ink "
    "black with restrained accent colours. Hard edges, flat "
    "painted shadows.\n\n"
    "Composition:\n"
    "Heroic low-angle stance — static heraldic pose, subject "
    "occupies the central vertical mass, single banner fluttering "
    "in frame above one shoulder, gaze fixed forward or slightly "
    "upward toward an unseen horizon.\n\n"
    "Medium texture:\n"
    "Silkscreen-print artifacts: visible off-white paper grain "
    "across the whole frame, halftone dots in any screened mid-tones, "
    "noticeable ink-registration drift where the crimson plate "
    "misaligns from the black by a fraction of a millimetre, slight "
    "ink-bleed at bold poster edges, mild age fade where the "
    "off-white paper has yellowed, occasional poster-folding crease "
    "ghost.\n\n"
    "Avoid (style-dependent):\n"
    "Photorealistic skin texture, lens artifacts, depth-of-field "
    "blur, subtle asymmetry, candid expressions, action verbs "
    "implying motion blur, anime, cartoon, chibi."
  ),
)


PIXEL_ART_SECTION = StyleSection(
  mode_trigger="A high-detail painterly pixel-art portrait",
  closer_phrase=(
    "high-detail painterly pixel-art RimWorld sci-fi colony "
    "portrait, no UI."
  ),
  prose=(
    "Style:\n"
    "High-detail modern painterly pixel art with hand-placed "
    "pixels, limited palette, deliberate pixel contour. This is "
    "emphatically NOT chunky 8-bit retro, NOT vector, NOT a smooth "
    "downscaled digital painting.\n\n"
    "Composition:\n"
    "Tight portrait or three-quarter, sprite-sheet framing, "
    "deliberate pixel contour on every silhouette edge.\n\n"
    "Medium texture:\n"
    "Hand-placed pixel clusters with absolutely no anti-aliasing "
    "on silhouette edges, ordered dithering patterns (Bayer 4x4 or "
    "checkerboard) for mid-tones, deliberate hue-shift between "
    "neighbouring palette entries rather than pure brightness "
    "ramps, occasional single-pixel specular highlights, no "
    "rotational or scaling smoothing, every diagonal made of "
    "clean stair-step jaggies — the image must read as deliberate "
    "pixel art, not a downscaled high-res render.\n\n"
    "Avoid (style-dependent):\n"
    "Anti-aliased outlines, smooth digital painting, photorealistic "
    "textures, anime cel-shading, motion blur, depth-of-field blur."
  ),
)


@dataclass(frozen=True)
class StylePreset:
  """A named preset is a :class:`StyleSection` plus an optional
  ``base`` instruction swap (only used by ``action`` today, which
  pairs with ``base="action"`` to also switch the core
  instruction file from the portrait template to the action one)."""
  section: StyleSection
  base: str | None = None


PRESETS: dict[str, StylePreset] = {
  "renaissance": StylePreset(section=RENAISSANCE_SECTION),
  "acrylic":     StylePreset(section=ACRYLIC_SECTION),
  "action":      StylePreset(section=ACTION_SECTION, base="action"),
  "comic":       StylePreset(section=COMIC_SECTION),
  "anime":       StylePreset(section=ANIME_SECTION),
  "propaganda":  StylePreset(section=PROPAGANDA_SECTION),
  "pixel-art":   StylePreset(section=PIXEL_ART_SECTION),
}


def compose_instruction(
  kind: str,
  preset: StylePreset | None,
  image_model: str | None = None,
  effective_kind: str | None = None,
  user_style: str | None = None,
) -> str:
  """Assemble the full system instruction the LLM will receive.

  - ``kind`` is the original render kind (``portrait`` / ``family`` /
    ``action``).
  - ``preset`` is a :class:`StylePreset` from :data:`PRESETS`, or
    None when ``--preset`` was not given.
  - ``effective_kind`` is the kind for base-instruction selection
    (action's ``base="action"`` swap lives here). Defaults to
    ``kind``.
  - ``user_style`` is the freeform ``--style`` value. When set, it
    appends an "Additional style note:" sentence to whichever
    section's prose is active.

  Single assembly path: pick the section (preset's, or the kind's
  default when no preset), optionally append the user-style note,
  delegate to :func:`render.instruction_for` for the final
  core + section + per-image-model-overlay assembly.
  """
  # Lazy import to avoid the style ↔ render circular dependency at
  # module load.
  from .render import instruction_for, _KIND_TO_DEFAULT_SECTION
  effective = effective_kind or kind
  section = preset.section if preset is not None \
            else _KIND_TO_DEFAULT_SECTION[kind]
  if user_style:
    section = StyleSection(
      prose=(
        section.prose
        + f"\n\nAdditional style note:\n{user_style}."
      ),
      mode_trigger=section.mode_trigger,
      closer_phrase=section.closer_phrase,
    )
  return instruction_for(
    effective, image_model=image_model, section=section,
  )
