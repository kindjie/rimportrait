"""Render PawnRecord/family groups into prompt-context blocks.

Block format and the trailing 'Final prompt instruction' strings come
verbatim from the user's spec. Both renderers omit lines whose values
are unavailable rather than emitting empty placeholders - keeps blocks
tight for downstream LLM consumption.
"""

from __future__ import annotations

from collections.abc import Iterable

from rimsave.colors import describe_rgba
from rimsave.records import (
  ApparelItem,
  BondedAnimal,
  CreepJoinerState,
  GradientHair,
  IdeoRecord,
  MapContext,
  PawnRecord,
  Relation,
  RoyalTitle,
  Weapon,
)
from rimsave.wealth import wealth_tier
from .translate.apparel import (
  describe_apparel,
  describe_apparel_item,
  is_baby_carrier,
  is_utility_apparel,
  long_form_apparel_phrase,
  qualifier_for_apparel,
)
from .translate.favorite_color import describe_favorite_color
from .translate.genes import describe_genes
from .translate.hair import describe_gradient_mask, describe_hair_style
from .translate._common import description_for, humanise
from .translate.hediffs import (
  describe_chemical_state,
  describe_hediffs,
  describe_pilot_state,
  describe_shambler_state,
)
from .translate.inventory import describe_inventory
from .translate.weapons import describe_weapon, qualifier_for_weapon
from .translate.xenotype import describe_xenotype


SINGLE_PROMPT_INSTRUCTION = (
  "You write image-generation prompts for modern multimodal image "
  "models such as gpt-image-2 and gemini-3-pro-image-preview.\n\n"
  "Task:\n"
  "Given the [PORTRAIT SUBJECT] block below, produce one polished "
  "image-generation prompt for a grounded cinematic portrait of "
  "that single RimWorld pawn.\n\n"
  "Output format:\n"
  "- One paragraph only.\n"
  "- 90-220 words preferred.\n"
  "- No JSON.\n"
  "- No bullet points.\n"
  "- No labels like 'Subject:' or 'Style:'.\n"
  "- Do not generate multiple options.\n"
  "- The final output must be directly usable as an image-generation "
  "prompt.\n\n"
  "Core goal:\n"
  "Create a believable portrait of a real person, not a poster, "
  "character sheet, fashion shoot, game screenshot, trading card, "
  "or generic concept-art lineup.\n\n"
  "Prompt content:\n"
  "- Start with the portrait subject and framing (head-and-shoulders, "
  "bust, half-body, three-quarter portrait, or full-body portrait). "
  "Open with 'Portrait of a [age]-year-old [role/identity], ...' - "
  "do NOT include the pawn's name in the prompt; image models don't "
  "read names visually and themed nicknames can pull weird "
  "associations. The name is for filenames and identification only.\n"
  "- TRANSLATE RimWorld game-specific terms into VISUAL descriptors. "
  "The image model does not know what 'Sanguophage', 'Yttakin', "
  "'Hussar', 'Impid', 'Genie', 'Pigskin', 'Wasterhound' (or modded "
  "xenotypes), ideology meme names, faction names, hediff defs, "
  "weapon defs, hair-style defs ('Senorita', 'Bowlcut', 'Mohawk'), "
  "beard-style defs ('Curly', 'Squared'), or gradient mask names "
  "('MaskAHigh') MEAN - write the visual cues from the block's "
  "description instead of echoing the term verbatim. Examples: "
  "Sanguophage -> 'pale-skinned with slight fangs and a predatory "
  "stillness'. Charge lance -> 'sleek plasteel energy rifle'. "
  "Senorita -> 'long flowing hair past the shoulders, swept to one "
  "side, voluminous waves'. Bowlcut -> 'short bowl-shaped haircut "
  "cropped at the jawline'. Mohawk -> 'sides shaved, central strip "
  "of upright hair'. Curly (beard) -> 'short curly beard following "
  "the jawline'. Gradient hair -> describe the colour transition "
  "directly ('charcoal roots fading to saturated red at the tips').\n"
  "- Hair and beard are defining features the image model frequently "
  "drops. Describe them with concrete structural language - length, "
  "direction, texture, parting, colour transition - and place that "
  "description early in the paragraph. A colour gradient should read "
  "as a clean transition, not a list of colours.\n"
  "- Make the face clearly visible and the emotional focus.\n"
  "- Translate the block's personality, traits, mood, role, "
  "relationships, hediffs, and backstory into VISIBLE behavior - "
  "expression, body language, clothing wear, scars, fatigue, warmth, "
  "tension, guardedness.\n"
  "- Anchor the scene on ONE specific verb the pawn is doing (drawn "
  "from the block's Pose/activity, Inspiration, combat-readiness "
  "signals, or another grounded RimWorld action - soldering a "
  "circuit, hauling a crate, levelling the charge lance, stitching "
  "a wound). Avoid generic standing/posing.\n"
  "- Use 2-4 important clothing/gear/prop details from the block - "
  "the strongest visible ones. Do not overload with inventory.\n"
  "- Include the wielded weapon and hair description; image models "
  "drop late details, so anchor these early in the paragraph.\n"
  "- A simple setting that supports the subject without stealing "
  "focus.\n"
  "- Describe lighting and camera treatment: soft side light, "
  "window light, practical lamp light, shallow depth of field, "
  "realistic lens feel, natural skin texture, restrained cinematic "
  "color grading.\n"
  "- When a helmet or hat is carried/cradled/tucked rather than "
  "worn, describe its interior as visibly empty (hollow, lined "
  "padding, no face, no head, no eyes inside) - image models "
  "otherwise fill the negative space with a severed head.\n\n"
  "Style:\n"
  "Realistic cinematic portrait language. Natural proportions, "
  "practical materials, imperfect surfaces, lived-in clothing, "
  "visible texture, subtle asymmetry, believable skin, weathering, "
  "dust, sweat, grime, restrained color grading.\n\n"
  "RimWorld context:\n"
  "Use gritty colony survival imagery - patched spacer-fabric "
  "clothing, improvised armor, steel walls, workshops, med bays, "
  "hydroponics, transport pods, rough repairs, utility lighting, "
  "hostile weather outside, worn tools, practical weapons, tired "
  "eyes, grounded expressions. Do not copy RimWorld's top-down "
  "game UI style.\n\n"
  "Avoid:\n"
  "Blank expression, glamor retouching, exaggerated beauty, static "
  "passport-photo pose, centered character-sheet framing, superhero "
  "poster composition, glossy fantasy armor, anime, cartoon, chibi, "
  "plastic-looking 3D render, clean studio lighting, excessive "
  "background detail, UI, HUD, captions, labels, watermarks, "
  "unreadable fake text.\n\n"
  "When source notes include relationships, show them subtly "
  "through expression, posture, keepsakes, gaze direction, "
  "protective stance, distance, or tension. Do not invent major "
  "relationship events.\n\n"
  "When source notes are sparse, invent only modest visual details "
  "needed for coherence. Do not invent major backstory, names, "
  "titles, symbols, factions, or plot events.\n\n"
  "End with \"realistic gritty RimWorld sci-fi colony portrait, "
  "grounded expression, no UI.\""
)


FAMILY_PROMPT_INSTRUCTION = (
  "You write image-generation prompts for modern multimodal image "
  "models such as gpt-image-2 and gemini-3-pro-image-preview.\n\n"
  "Task:\n"
  "Given the [FAMILY PORTRAIT SUBJECT] block below, produce one "
  "polished image-generation prompt for a grounded cinematic family "
  "portrait of the focus pawn and the listed members.\n\n"
  "Output format:\n"
  "- One paragraph only.\n"
  "- 130-260 words preferred.\n"
  "- No JSON.\n"
  "- No bullet points.\n"
  "- No labels like 'Subject:' or 'Style:'.\n"
  "- Do not generate multiple options.\n"
  "- The final output must be directly usable as an image-generation "
  "prompt.\n\n"
  "Core goal:\n"
  "Create a believable group portrait of these people, not a poster, "
  "character sheet, fashion shoot, game screenshot, or generic "
  "concept-art lineup.\n\n"
  "Prompt content:\n"
  "- Open with 'Family portrait of...' or 'Group portrait of...'. "
  "Do NOT include pawn names in the prompt; image models don't read "
  "names visually and exotic names can pull weird associations. "
  "Refer to people by role/relationship/age/gender ('a tall "
  "auburn-haired woman in her thirties', 'the youngest child').\n"
  "- TRANSLATE RimWorld game-specific terms into VISUAL descriptors. "
  "The image model does not know what 'Sanguophage', 'Yttakin', "
  "'Hussar', 'Impid', 'Genie', 'Pigskin', 'Wasterhound' (or modded "
  "xenotypes), ideology meme names, faction names, hediff defs, "
  "weapon defs, hair-style defs ('Senorita', 'Bowlcut', 'Mohawk'), "
  "beard-style defs ('Curly', 'Squared'), or gradient mask names "
  "MEAN - write the visual cues from the block's description "
  "instead of echoing the term verbatim. Hair: describe length, "
  "direction, texture, parting, colour transition (gradients as "
  "clean transitions, e.g. 'charcoal roots fading to red tips'). "
  "Beard: describe shape and length ('short curly beard following "
  "the jawline').\n"
  "- Hair, beard, and wielded weapon per person are defining "
  "features the image model frequently drops. Anchor them early in "
  "each person's clause with concrete structural language.\n"
  "- Block the composition spatially: who stands where, who is "
  "closer to camera, gaze directions, who looks at whom.\n"
  "- For each person: one verb (from their Pose/activity or "
  "Inspiration), an emote matched to their mood and traits, and "
  "2-4 visible details (one apparel, one weapon/gear, one prop or "
  "texture). Do not overload with inventory.\n"
  "- Include the wielded weapon and hair description per person; "
  "image models drop late details, so anchor these early.\n"
  "- Show relationships through gesture: protective stance, "
  "shielding, shared glance, touch, distance, tension. Children "
  "look age-appropriate and are never sexualized.\n"
  "- Helmets are usually removed or carried so faces are visible. "
  "When carried/cradled, describe the interior as visibly empty "
  "(hollow, lined padding, no face/head inside).\n"
  "- A simple setting that grounds the group without stealing "
  "focus.\n"
  "- One shared camera + lens + lighting line for the whole "
  "composition (e.g. 'shot on 50mm at f/4, warm directional light "
  "from camera-right').\n\n"
  "Style:\n"
  "Realistic cinematic portrait language. Natural proportions, "
  "practical materials, imperfect surfaces, lived-in clothing, "
  "visible texture, subtle asymmetry, believable skin, weathering, "
  "dust, sweat, grime, restrained color grading.\n\n"
  "RimWorld context:\n"
  "Use gritty colony survival imagery - patched clothing, "
  "improvised armor, steel walls, workshops, med bays, rough "
  "repairs, utility lighting, hostile weather outside, worn tools, "
  "practical weapons, tired eyes, grounded expressions. Do not "
  "copy RimWorld's top-down game UI style.\n\n"
  "Avoid:\n"
  "Static line-up framing, glamor retouching, exaggerated beauty, "
  "superhero poster composition, glossy fantasy armor, anime, "
  "cartoon, chibi, plastic-looking 3D render, clean studio "
  "lighting, UI, HUD, captions, labels, watermarks, unreadable "
  "fake text.\n\n"
  "When source notes are sparse, invent only modest visual details "
  "needed for coherence. Do not invent major backstory, names, "
  "titles, symbols, factions, or plot events.\n\n"
  "End with \"realistic gritty RimWorld sci-fi colony family "
  "portrait, grounded expressions, no UI.\""
)


ACTION_PROMPT_INSTRUCTION = (
  "You write image-generation prompts for modern multimodal image "
  "models such as gpt-image-2 and gemini-3-pro-image-preview.\n\n"
  "Task:\n"
  "Given the [PORTRAIT SUBJECT] block below, produce one polished "
  "image-generation prompt for a cinematic action image that looks "
  "like a still frame from a live-action movie.\n\n"
  "Output format:\n"
  "- One paragraph only.\n"
  "- 120-260 words preferred.\n"
  "- No JSON.\n"
  "- No bullet points.\n"
  "- No labels like 'Camera:' or 'Style:'.\n"
  "- Do not generate multiple options.\n"
  "- The final output must be directly usable as an image-generation "
  "prompt.\n\n"
  "Core goal:\n"
  "Create a single frozen moment from a believable movie scene, not "
  "a poster, character sheet, portrait, game screenshot, or "
  "concept-art lineup.\n\n"
  "Prompt content:\n"
  "- Do NOT include the pawn's name in the prompt; image models "
  "don't read names visually and themed nicknames can pull weird "
  "associations. Refer to the subject by role / age / gender "
  "('the colonist', 'a 27-year-old man').\n"
  "- TRANSLATE RimWorld game-specific terms into VISUAL descriptors. "
  "The image model does not know what 'Sanguophage', 'Yttakin', "
  "'Hussar', 'Impid', 'Genie', 'Pigskin', 'Wasterhound' (or modded "
  "xenotypes), ideology meme names, faction names, hediff defs, "
  "weapon defs, hair-style defs ('Senorita', 'Bowlcut', 'Mohawk'), "
  "beard-style defs ('Curly', 'Squared'), or gradient mask names "
  "MEAN - write the visual cues from the block's description "
  "instead of echoing the term. Examples: Sanguophage -> "
  "'pale-skinned with slight fangs and a predatory stillness'. "
  "Charge lance -> 'sleek plasteel energy rifle'. Senorita -> "
  "'long flowing hair past the shoulders, swept to one side'. "
  "Gradient hair -> describe the colour transition directly "
  "('charcoal roots fading to red at the tips').\n"
  "- Hair, beard, and wielded weapon are defining features the "
  "image model frequently drops. Anchor them with concrete "
  "structural language - length, direction, texture, grip, "
  "colour transition - in the first half of the paragraph.\n"
  "- Start with the exact instant of action - what is happening "
  "right now. Draw the verb from the block's Pose/activity, "
  "Inspiration, combat-readiness signals (shoot frenzy / berserker "
  "rage / frenetic / piloting / shambling / drug-high / aggressive), "
  "or another grounded RimWorld action - and escalate it to its "
  "most dramatic plausible form.\n"
  "- Include the subject's visible emotion, body language, and "
  "immediate objective.\n"
  "- Face visible unless the block clearly requires otherwise.\n"
  "- Camera as if filming the action: shot size, angle, distance, "
  "lens feel, handheld/tracking/over-the-shoulder if useful.\n"
  "- Layered composition: foreground, subject/midground, background.\n"
  "- Motivated lighting from visible or plausible scene sources - "
  "fire, floodlights, muzzle flash, doorway light, monitors, "
  "lightning, sunrise, emergency lamps.\n"
  "- Motion through physical evidence: flying dust, rain, sparks, "
  "smoke, torn cloth, hair, recoil, debris, footprints, splashes, "
  "blurred background movement.\n"
  "- Specify sharp vs blurred: usually sharp eyes/face/hands, "
  "slightly blurred background or fast-moving elements.\n"
  "- Translate personality, traits, relationships, role, and "
  "backstory into visible behavior, not explained lore.\n"
  "- 2-4 important clothing/gear/prop details from the block. Do "
  "not overload the prompt with inventory.\n"
  "- Include the wielded weapon and hair description; image models "
  "drop late details, so anchor these early.\n"
  "- Keep the environment active and relevant to the action.\n"
  "- When a helmet or hat is carried/cradled/tucked rather than "
  "worn, describe its interior as visibly empty (hollow, lined "
  "padding, no face/head inside) - image models otherwise fill the "
  "negative space with a severed head.\n\n"
  "Style:\n"
  "Realistic live-action cinematic sci-fi or grounded film-still "
  "language. Natural proportions, practical materials, imperfect "
  "surfaces, weathering, dust, sweat, grime, believable clothing, "
  "restrained cinematic color grading.\n\n"
  "RimWorld context:\n"
  "Use gritty colony survival imagery - improvised defenses, steel "
  "walls, muddy yards, hydroponics rooms, workshops, med bays, "
  "transport pods, hostile weather, emergency lights, damaged "
  "armor, practical weapons, patched clothing, exhausted but "
  "grounded expressions. Do not copy RimWorld's top-down game UI "
  "style.\n\n"
  "Avoid:\n"
  "Static portrait pose, centered character-sheet framing, "
  "superhero poster composition, glossy fantasy armor, anime, "
  "cartoon, chibi, plastic-looking 3D render, clean studio "
  "lighting, excessive beauty retouching, UI, HUD, captions, "
  "labels, watermarks, unreadable fake text.\n\n"
  "When source notes include multiple characters, show "
  "relationship-aware blocking - distance, touch, eye lines, "
  "shielding gestures, hesitation, conflict, coordination. "
  "Children look age-appropriate and are never sexualized.\n\n"
  "When source notes are sparse, invent only modest visual details "
  "needed for coherence. Do not invent major backstory, names, "
  "titles, symbols, factions, or plot events.\n\n"
  "End with \"realistic gritty RimWorld sci-fi colony action still, "
  "no UI.\""
)


# --- Per-model overlays ---------------------------------------------
# Thin model-specific notes appended to the base instruction when
# --image targets a known model. Encodes what the documented
# prompting guidance for each model says to do (or avoid) on top of
# the general voice in the base instructions above.


_OVERLAY_GPT_IMAGE_2 = (
  "Additional notes for OpenAI gpt-image-2 (the downstream image "
  "model):\n"
  "- Lead the paragraph with the word \"Photorealistic\" - it is "
  "gpt-image-2's documented mode trigger.\n"
  "- gpt-image-2 has no negative-prompt parameter; rely on in-prompt "
  "exclusions (\"no UI\", \"no text overlay\", \"no watermark\").\n"
  "- For any held/carried object, name the hand (\"left hand\"), "
  "the height (\"at hip\", \"under arm\"), and the state "
  "(\"empty\", \"sheathed\", \"shouldered\") - gpt-image-2's "
  "Thinking Mode reasons over explicit spatial relationships, and "
  "naming them is the documented antidote to negative-space "
  "hallucinations."
)

_OVERLAY_GEMINI_PRO = (
  "Additional notes for Google Gemini 3 Pro Image - Nano Banana Pro "
  "(the downstream image model):\n"
  "- Start the paragraph with a strong verb: \"Render\", "
  "\"Photograph\", \"Paint\".\n"
  "- Use POSITIVE reframing of negatives - describe what IS, not "
  "what isn't. Instead of \"no head in the helmet\" write \"empty "
  "helmet gripped by the rim, hollow leather-lined interior facing "
  "the camera\".\n"
  "- Use material-specific nouns (\"navy tweed cuirass\" over "
  "\"armor\"; \"sun-bleached canvas duster\" over \"jacket\") - the "
  "highest-ROI lever this model rewards.\n"
  "- Pro tolerates and rewards dense clause-heavy prompts; aim "
  "toward the upper end of the word budget when the source block "
  "is rich."
)

_OVERLAY_GEMINI_FLASH = (
  "Additional notes for Google Gemini 3.1 Flash Image - Nano "
  "Banana 2 (the downstream image model):\n"
  "- Start the paragraph with a strong verb: \"Photograph\", "
  "\"Render\".\n"
  "- Flash drops detail aggressively on long prompts; aim for the "
  "lower end of the word budget and strip nice-to-have flourishes.\n"
  "- Use POSITIVE reframing of negatives (\"empty helmet, hollow "
  "interior visible\" not \"no head in the helmet\").\n"
  "- Soften violence/wound language to avoid the safety filter: "
  "prefer \"battle-worn\", \"scarred\", \"weathered\", "
  "\"powder-burned\" over explicit gore verbs. Describe weapons as "
  "objects (\"holds a bolt-action rifle\") not actions "
  "(\"aiming\", \"firing\") unless the block clearly signals "
  "active combat."
)


_PER_MODEL_OVERLAY: dict[str, str] = {
  "gpt-image-2": _OVERLAY_GPT_IMAGE_2,
  "gemini-3-pro-image-preview": _OVERLAY_GEMINI_PRO,
  "gemini-3.1-flash-image-preview": _OVERLAY_GEMINI_FLASH,
}


_KIND_TO_BASE: dict[str, str] = {
  "portrait": SINGLE_PROMPT_INSTRUCTION,
  "family": FAMILY_PROMPT_INSTRUCTION,
  "action": ACTION_PROMPT_INSTRUCTION,
}


def instruction_for(
  kind: str, image_model: str | None = None
) -> str:
  """Pick the system instruction for this image kind, with overlay.

  ``kind`` is ``portrait`` (single pawn), ``family`` (group), or
  ``action`` (cinematic still). The matching base instruction (in
  the user's reference voice) is returned, with a short per-model
  overlay appended when ``image_model`` matches one of the three
  tuned models.
  """
  if kind not in _KIND_TO_BASE:
    raise ValueError(f"unknown render kind {kind!r}")
  base = _KIND_TO_BASE[kind]
  overlay = _PER_MODEL_OVERLAY.get(image_model) if image_model else None
  if overlay:
    return f"{base}\n\n{overlay}"
  return base


# --- helpers ----------------------------------------------------------

def _line(label: str, value: str | None) -> str | None:
  if value is None or value == "":
    return None
  return f"{label}: {value}"


def _sub(label: str, value: str | None) -> str | None:
  if value is None or value == "":
    return None
  return f"- {label}: {value}"


def _age_str(bio: float | None, chrono: float | None) -> str | None:
  if bio is None and chrono is None:
    return None
  if bio is not None and chrono is not None and abs(bio - chrono) > 1:
    return f"biological {bio:.0f}, chronological {chrono:.0f}"
  age = bio if bio is not None else chrono
  assert age is not None
  return f"{age:.0f}"


def _gradient_value(gh: GradientHair | None) -> str | None:
  # Omit when the mod is absent OR when the mod is present but the
  # pawn has no gradient applied. Either way the line adds no signal
  # for an image prompt.
  if gh is None or not gh.enabled:
    return None
  parts = ["enabled"]
  c_b = describe_rgba(gh.color_b)
  if c_b:
    parts.append(f"gradient color {c_b}")
  region = describe_gradient_mask(gh.mask)
  if region:
    parts.append(f"mask {region}")
  return "; ".join(parts)


def _apparel_phrase(
  it: ApparelItem,
  labels: dict[str, str] | None = None,
  carrying_infant: bool = False,
) -> str:
  """Render one apparel item's inline phrase.

  Baby carriers gain an "empty" marker when no infant is being held,
  so the LLM doesn't draw a baby into an unused carrier (or miss the
  carrier signal entirely when one is present).
  """
  base = describe_apparel_item(it, labels)
  qual = qualifier_for_apparel(it)
  if is_baby_carrier(it.def_name) and not carrying_infant:
    qual = f"{qual}, empty" if qual else "empty"
  return f"{base} ({qual})" if qual else base


def _weapon_phrase(
  w: Weapon, labels: dict[str, str] | None = None
) -> str:
  base = describe_weapon(w, labels)
  qual = qualifier_for_weapon(w)
  return f"{base} ({qual})" if qual else base


def _gear_lines(
  p: PawnRecord, labels: dict[str, str] | None = None
) -> list[tuple[str, str]]:
  """Split worn gear into three prominence buckets.

  Returns (label, value) pairs for: armor/clothing layers, belt/utility
  gear, and the wielded weapon. Each bucket is omitted when empty.
  Inventory (carried pack contents) is reported on its own line by
  _carrying_summary and is not included here, so the equipped
  silhouette stays distinct from pack supplies.
  """
  armor: list[str] = []
  utility: list[str] = []
  carrying = p.carried_infant is not None
  for it in p.apparel:
    target = utility if is_utility_apparel(it.def_name) else armor
    target.append(_apparel_phrase(it, labels, carrying_infant=carrying))
  weapons = [_weapon_phrase(w, labels) for w in p.equipment]
  out: list[tuple[str, str]] = []
  if armor:
    out.append(("Worn armor/clothing", ", ".join(armor)))
  if utility:
    out.append(("Utility belts/gear", ", ".join(utility)))
  if weapons:
    out.append(("Wielded weapon", ", ".join(weapons)))
  return out


def _carrying_summary(
  p: PawnRecord, labels: dict[str, str] | None = None
) -> str | None:
  items = describe_inventory(p.inventory, labels)
  if not items:
    return None
  return ", ".join(items)


def _carrying_infant(p: PawnRecord) -> str | None:
  ci = p.carried_infant
  if ci is None:
    return None
  if ci.name and ci.bio_age is not None:
    return f"{ci.name} (infant, age {ci.bio_age:.1f})"
  if ci.name:
    return f"{ci.name} (infant)"
  return f"{ci.pawn_id} (infant)"


def _pilot_state_value(
  p: PawnRecord,
  labels: dict[str, str] | None = None,
) -> str | None:
  """Combine the pilot implant + actively-piloting cue.

  Always emits the implant phrase when present; appends a
  ``(currently piloting)`` flag when the pawn's curJob is
  PilotConsole so the LLM can render an action-shot at the
  gravship helm rather than the latent capability alone.
  """
  implant_parts = describe_pilot_state(p.hediffs, labels)
  actively = (p.current_job or "") == "PilotConsole"
  if not implant_parts and not actively:
    return None
  parts: list[str] = list(implant_parts)
  if actively:
    parts.append("currently piloting at the helm")
  return ", ".join(parts)


def _creepjoiner_value(
  cj: CreepJoinerState | None,
  labels: dict[str, str] | None = None,
) -> str | None:
  """Render the latent creepjoiner persona as form + (benefit/downside).

  All four slots (form, benefit, downside, aggressive) are def names
  resolved through the mod-aware label index. Status flags
  (triggered_downside / has_left) are appended when set so the LLM
  can pick up that the dark side has fired or the entity has fled.
  """
  if cj is None:
    return None

  def lbl(d: str | None) -> str | None:
    if not d:
      return None
    return (labels.get(d) if labels else None) or humanise(d)

  bits: list[str] = []
  form = lbl(cj.form)
  if form:
    bits.append(form)
  pairs: list[str] = []
  benefit = lbl(cj.benefit)
  if benefit:
    pairs.append(f"benefit: {benefit}")
  downside = lbl(cj.downside)
  if downside:
    pairs.append(f"downside: {downside}")
  aggressive = lbl(cj.aggressive)
  if aggressive:
    pairs.append(f"aggressive: {aggressive}")
  rejection = lbl(cj.rejection)
  if rejection:
    pairs.append(f"rejection: {rejection}")
  if pairs:
    bits.append("(" + "; ".join(pairs) + ")")
  flags: list[str] = []
  if cj.triggered_downside:
    flags.append("downside triggered")
  if cj.has_left:
    flags.append("has left")
  if flags:
    bits.append("[" + ", ".join(flags) + "]")
  if not bits:
    return None
  return " ".join(bits)


def _abilities_value(
  abilities: tuple[str, ...],
  labels: dict[str, str] | None = None,
) -> str | None:
  if not abilities:
    return None
  parts = [
    (labels.get(d) if labels else None) or humanise(d)
    for d in abilities
  ]
  return ", ".join(parts)


def _psyfocus_value(psyfocus: float | None) -> str | None:
  """Render psyfocus as a band label, suppressed below 25%.

  Thresholds chosen to align with RimWorld's UI psyfocus quartile
  display: depleted/low/moderate/high/full. The label includes the
  numeric percentage so the LLM can ground a 'how charged are they
  looking' decision against the raw signal too.
  """
  if psyfocus is None:
    return None
  pct = int(round(psyfocus * 100))
  if psyfocus >= 0.95:
    band = "full"
  elif psyfocus >= 0.75:
    band = "high"
  elif psyfocus >= 0.50:
    band = "moderate"
  elif psyfocus >= 0.25:
    band = "low"
  else:
    band = "depleted"
  return f"{band} ({pct}%)"


def _bonded_animals_value(
  animals: tuple[BondedAnimal, ...],
  labels: dict[str, str] | None = None,
) -> str | None:
  """Render bonded animals as 'Name the Species (Gender, Xy), ...'.

  Species def is threaded through mod-aware labels. Anonymous animals
  fall back to "the <species>" without a name prefix. Age and gender
  are omitted from the parenthetical when unknown.
  """
  if not animals:
    return None
  parts: list[str] = []
  for a in animals:
    species = (
      (labels.get(a.def_name) if labels else None)
      or humanise(a.def_name)
    )
    head = f"{a.name} the {species}" if a.name else f"the {species}"
    bits: list[str] = []
    if a.gender:
      bits.append(a.gender)
    if a.bio_age is not None:
      bits.append(f"{a.bio_age:.0f}y")
    if bits:
      head += " (" + ", ".join(bits) + ")"
    parts.append(head)
  return ", ".join(parts)


def _connections_value(
  connections: tuple[str, ...],
  labels: dict[str, str] | None = None,
) -> str | None:
  """Compact connections summary with per-def tallies.

  Used for gauranlen tree links, dryad bonds, and any mod-defined
  connected things. Order matches commanded-mechs: sort by count
  descending, then label ascending; singleton entries omit the
  ``× 1`` suffix.
  """
  if not connections:
    return None
  counts: dict[str, int] = {}
  for d in connections:
    counts[d] = counts.get(d, 0) + 1
  by_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
  parts: list[str] = []
  for def_name, n in by_count:
    label = (
      (labels.get(def_name) if labels else None)
      or humanise(def_name)
    )
    parts.append(f"{label} × {n}" if n > 1 else label)
  return ", ".join(parts)


def _commanded_mechs_value(
  mech_defs: tuple[str, ...],
  labels: dict[str, str] | None = None,
) -> str | None:
  """Compact entourage summary: total count + per-def tallies.

  Mechs commanded by a mechanitor are a strong silhouette signal -
  they appear at the pawn's side in portraits. We surface the total
  count plus a sorted (count desc, then label asc) per-mech-def
  breakdown using mod-aware labels.
  """
  if not mech_defs:
    return None
  counts: dict[str, int] = {}
  for d in mech_defs:
    counts[d] = counts.get(d, 0) + 1
  by_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
  parts: list[str] = []
  for def_name, n in by_count:
    # Strip the conventional Mech_ prefix so the breakdown reads
    # "cleansweeper × 3" rather than "mech cleansweeper × 3".
    label = (
      (labels.get(def_name) if labels else None)
      or humanise(def_name, ("Mech_",))
    )
    parts.append(f"{label} × {n}" if n > 1 else label)
  total = len(mech_defs)
  return f"{total} — " + ", ".join(parts)


def _inspiration_value(
  inspiration: str | None,
  descriptions: dict[str, str] | None = None,
  labels: dict[str, str] | None = None,
) -> str | None:
  """Render the active inspiration def with mod-aware description.

  Inspirations (Inspired_Taming, Frenzy_Shoot, ...) are visible
  expression cues - frenzied vs calm-focused vs spirit-soaring - so
  we surface the description when available, falling back through
  the def label and humanised slug per the data-first principle.
  """
  if not inspiration:
    return None
  resolved = description_for(inspiration, descriptions, labels)
  if resolved and resolved != humanise(inspiration):
    return f"{inspiration} - {resolved}"
  return inspiration


def _royal_title_line(
  titles: tuple[RoyalTitle, ...],
  labels: dict[str, str] | None = None,
) -> str | None:
  """Render royal titles using the mod-aware label override.

  RimWorld's RoyalTitleDef labels (e.g. ``Count`` -> ``archon`` for
  the Empire) live in the def index. We surface both the def name and
  the resolved label so the LLM has both signals.
  """
  if not titles:
    return None
  parts: list[str] = []
  for t in titles:
    label = labels.get(t.def_name) if labels else None
    if label and label != t.def_name:
      head = f"{t.def_name} - {label}"
    else:
      head = t.def_name
    if t.faction_name:
      parts.append(f"{head}, of {t.faction_name}")
    else:
      parts.append(head)
  return "; ".join(parts)


def _race_xenotype(
  p: PawnRecord,
  descriptions: dict[str, str] | None = None,
  labels: dict[str, str] | None = None,
) -> str | None:
  if p.xenotype:
    desc = describe_xenotype(
      p.xenotype, descriptions, labels, p.genes
    )
    # Suppress the redundant dash form when the description is just
    # the humanised def name; emit only the def name in that case.
    if desc and desc != humanise(p.xenotype):
      return f"{p.xenotype} - {desc}"
    return p.xenotype
  if p.race:
    return p.race
  return None


def _physical_state(p: PawnRecord) -> str | None:
  """Compose a portrait-visible physical-state phrase.

  Surfaces only the three needs that produce visible cues on a
  portrait — hunger (gaunt cheeks), exhaustion (droopy eyes),
  deathrest deprivation (sanguophage lethargy/pallor). Each tier is
  triggered at thresholds matching RimWorld's UI: <0.50 = early
  stage, <0.25 = severe. The line is omitted when no need is below
  0.50.
  """
  bits: list[str] = []

  def push(level: float | None, mild: str, severe: str) -> None:
    if level is None or level >= 0.50:
      return
    bits.append(severe if level < 0.25 else mild)

  push(p.food_need, "hungry", "starving / gaunt")
  push(p.rest_need, "tired", "exhausted / droopy-eyed")
  push(p.deathrest_need, "deathrest-tired",
       "deathrest-deprived / pale and unsteady")
  if not bits:
    return None
  return ", ".join(bits)


def _personality(p: PawnRecord) -> str | None:
  if p.personality:
    return p.personality
  bits: list[str] = []
  if p.backstory_child:
    bits.append(f"childhood: {p.backstory_child}")
  if p.backstory_adult:
    bits.append(f"adulthood: {p.backstory_adult}")
  if not bits:
    return None
  return "; ".join(bits)


def _compact_head_and_face(
  p: PawnRecord,
  labels: dict[str, str] | None = None,
  categories: dict[str, str] | None = None,
) -> str | None:
  bits: list[str] = []
  hair_style = describe_hair_style(
    p.hair_def, p.hair_label, p.hair_texture_path
  )
  hair_disp = p.hair_label or p.hair_def
  if hair_style and hair_disp:
    bits.append(f"hair {hair_disp} ({hair_style})")
  elif hair_style:
    bits.append(f"hair {hair_style}")
  elif hair_disp:
    bits.append(f"hair {hair_disp}")
  hair_color = describe_rgba(p.hair_color)
  if hair_color:
    bits.append(f"hair color {hair_color}")
  grad = _gradient_value(p.gradient_hair)
  if grad and grad != "disabled":
    bits.append(f"gradient {grad}")
  beard = p.beard_label or p.beard_def
  if beard and beard.lower() != "nobeard":
    bits.append(f"beard {beard}")
  face_tat = _tattoo_phrase(p.face_tattoo, labels, categories)
  if face_tat:
    bits.append(f"face tattoo {face_tat}")
  body_tat = _tattoo_phrase(p.body_tattoo, labels, categories)
  if body_tat:
    bits.append(f"body tattoo {body_tat}")
  skin = describe_rgba(p.skin_color)
  if skin:
    bits.append(f"skin {skin}")
  eye = describe_rgba(p.eye_color)
  if eye:
    bits.append(f"eyes {eye}")
  if not bits:
    return None
  return "; ".join(bits)


# --- single-portrait block --------------------------------------------

def _tattoo_phrase(
  def_name: str | None,
  labels: dict[str, str] | None,
  categories: dict[str, str] | None,
) -> str | None:
  """Render a tattoo def as 'label (Category style)' when possible.

  TattooDefs carry both a human-readable ``<label>`` and a
  ``<category>`` (Punk / Tribal / Royal / etc.) that's a strong
  visual genre cue for the image-prompt LLM. We thread both through
  the mod-aware def index; the def name still appears as a fallback
  prefix when only one of the two is known.
  """
  if not def_name:
    return None
  label = labels.get(def_name) if labels else None
  category = categories.get(def_name) if categories else None
  if label and category:
    return f"{label} ({category} style)"
  if label:
    return label
  if category:
    return f"{def_name} ({category} style)"
  return def_name


def _head_and_face_block(
  p: PawnRecord,
  labels: dict[str, str] | None = None,
  categories: dict[str, str] | None = None,
) -> list[str]:
  hair_style = describe_hair_style(
    p.hair_def, p.hair_label, p.hair_texture_path
  )
  hair_disp = p.hair_label or p.hair_def
  if hair_style and hair_disp:
    hair_disp = f"{hair_disp} ({hair_style})"
  elif hair_style:
    hair_disp = hair_style
  beard_disp = p.beard_label or p.beard_def
  if beard_disp and beard_disp.lower() == "nobeard":
    beard_disp = None
  lines: list[str | None] = [
    _sub("Hair style", hair_disp),
    _sub("Hair texture path", p.hair_texture_path),
    _sub("Hair/base beard color", describe_rgba(p.hair_color)),
    _sub("Hair gradient", _gradient_value(p.gradient_hair)),
    _sub("Beard", beard_disp),
    _sub("Beard color",
         describe_rgba(p.beard_color) if p.beard_color else None),
    _sub("Face tattoo", _tattoo_phrase(p.face_tattoo, labels, categories)),
    _sub("Body tattoo", _tattoo_phrase(p.body_tattoo, labels, categories)),
    _sub("Skin color", describe_rgba(p.skin_color)),
    _sub("Eye color", describe_rgba(p.eye_color)),
  ]
  return [s for s in lines if s]


def _ideo_block_lines(ideo: IdeoRecord | None) -> list[str]:
  if ideo is None:
    return []
  lines: list[str | None] = [
    _line("Ideology/culture", ideo.name),
    _line("Ideology primary color", describe_rgba(ideo.color)),
    _line("Ideology apparel color", describe_rgba(ideo.apparel_color)),
    _line("Ideology description/style",
          ideo.description or ideo.style_summary),
    _line("Ideology style aesthetic", _style_categories_value(ideo)),
    _line("Ideology memes", ", ".join(ideo.memes) or None),
  ]
  return [s for s in lines if s]


def _style_categories_value(ideo: IdeoRecord) -> str | None:
  """Render the ideology's thingStyleCategories as 'X (priority N), ...'.

  Priority is included verbatim from the save - the LLM can decide
  weighting. No curated visual phrasing; per the project's data-first
  principle the def names are emitted as-is.
  """
  if not ideo.style_categories:
    return None
  parts = [f"{cat} (priority {pri})" for cat, pri in ideo.style_categories]
  return ", ".join(parts)


def _time_of_day_value(m: MapContext) -> str | None:
  if m.time_hour is None and m.time_period is None:
    return None
  if m.time_hour is not None and m.time_period is not None:
    return f"{m.time_period} (hour {m.time_hour:02d})"
  if m.time_period is not None:
    return m.time_period
  return f"hour {m.time_hour:02d}"  # period unset only if hour None


def _map_block_lines(m: MapContext | None) -> list[str]:
  if m is None:
    return []
  threat = ", ".join(m.active_threats) if m.active_threats else None
  inner: list[str | None] = [
    _sub("Time of day", _time_of_day_value(m)),
    _sub("Weather", m.weather),
    _sub("Biome", m.biome),
    _sub("Wealth context", wealth_tier(m.wealth)),
    _sub("Situation/threat context", threat),
  ]
  inner_filtered = [s for s in inner if s]
  if not inner_filtered:
    return []
  return ["Colony/environment:"] + inner_filtered


def _apparel_section(
  items: Iterable[ApparelItem],
  def_descriptions: dict[str, str] | None = None,
  def_labels: dict[str, str] | None = None,
) -> list[str]:
  items_list = list(items)
  rows = describe_apparel(items_list, def_labels)
  if not rows:
    return []
  out = ["Apparel visual descriptions:"]
  for item, (label, _summary) in zip(items_list, rows):
    body = long_form_apparel_phrase(item, def_descriptions, def_labels)
    qual = qualifier_for_apparel(item)
    head = f"- {label}"
    if qual:
      head += f" [{qual}]"
    out.append(f"{head}: {body}")
  return out


def render_portrait(
  p: PawnRecord,
  map_context: MapContext | None = None,
  *,
  include_instruction: bool = True,
  def_descriptions: dict[str, str] | None = None,
  def_labels: dict[str, str] | None = None,
  def_categories: dict[str, str] | None = None,
) -> str:
  """Build the [PORTRAIT SUBJECT] block for a single pawn."""
  name = p.label or p.nickname or p.name_full
  lines: list[str] = ["[PORTRAIT SUBJECT]"]
  for ln in (
    _line("Name", name),
    _line("Role", p.role.capitalize() if p.role else None),
    _line("Royal title",
          _royal_title_line(p.royal_titles, def_labels)),
    _line("Race/xenotype",
          _race_xenotype(p, def_descriptions, def_labels)),
    _line("Gender", p.gender),
    _line("Age", _age_str(p.bio_age, p.chrono_age)),
  ):
    if ln:
      lines.append(ln)
  head = _head_and_face_block(p, def_labels, def_categories)
  if head:
    lines.append("Head and face:")
    lines.extend(head)
  for ln in (
    _line("Traits affecting expression",
          ", ".join(p.traits) if p.traits else None),
    _line("Personality/expression", _personality(p)),
    _line("Mood", p.mood),
    _line("Physical state", _physical_state(p)),
    _line("Inspiration",
          _inspiration_value(p.inspiration, def_descriptions, def_labels)),
    _line("Chemical/drug state",
          ", ".join(describe_chemical_state(p.hediffs, def_labels))
          or None),
    _line("Shambler state",
          ", ".join(describe_shambler_state(p.hediffs, def_labels))
          or None),
    _line("Creepjoiner state",
          _creepjoiner_value(p.creepjoiner, def_labels)),
    _line("Pilot state", _pilot_state_value(p, def_labels)),
    _line("Commanded mechs",
          _commanded_mechs_value(p.commanded_mechs, def_labels)),
    _line("Connections",
          _connections_value(p.connections, def_labels)),
    _line("Bonded animals",
          _bonded_animals_value(p.bonded_animals, def_labels)),
    _line("Abilities", _abilities_value(p.abilities, def_labels)),
    _line("Psyfocus", _psyfocus_value(p.psyfocus)),
    _line("Pose/activity", p.current_job),
    _line("Outdoors/indoors",
          None if p.outdoor is None else
          ("outdoors (unroofed tile)" if p.outdoor
           else "indoors (roofed tile)")),
    _line("Immediate setting", p.location),
    _line("Favorite color/accent",
          describe_favorite_color(p.favorite_color)),
    _line("Visible genes/body traits",
          ", ".join(describe_genes(p.genes, def_labels)) or None),
    _line("Visible implants/injuries/body changes",
          ", ".join(describe_hediffs(p.hediffs, def_labels)) or None),
    *(_line(label, value)
      for label, value in _gear_lines(p, def_labels)),
    _line("Carrying infant in arms", _carrying_infant(p)),
    _line("Carrying (pack/inventory)",
          _carrying_summary(p, def_labels)),
  ):
    if ln:
      lines.append(ln)
  lines.extend(_ideo_block_lines(p.ideo))
  lines.extend(_map_block_lines(map_context))
  lines.extend(_apparel_section(p.apparel, def_descriptions, def_labels))
  lines.append("[/PORTRAIT SUBJECT]")
  block = "\n".join(lines)
  if include_instruction:
    return block + "\n\n" + SINGLE_PROMPT_INSTRUCTION
  return block


# --- family-portrait block --------------------------------------------

def _person_block(
  p: PawnRecord,
  relation_to_focus: str,
  def_descriptions: dict[str, str] | None = None,
  def_labels: dict[str, str] | None = None,
  def_categories: dict[str, str] | None = None,
) -> list[str]:
  lines: list[str] = ["[PERSON]"]
  name = p.label or p.nickname or p.name_full
  for ln in (
    _line("Name", name),
    _line("Relation to focus pawn", relation_to_focus),
    _line("Role", p.role.capitalize() if p.role else None),
    _line("Royal title",
          _royal_title_line(p.royal_titles, def_labels)),
    _line("Race/xenotype",
          _race_xenotype(p, def_descriptions, def_labels)),
    _line("Gender", p.gender),
    _line("Age", _age_str(p.bio_age, p.chrono_age)),
    _line("Head and face",
          _compact_head_and_face(p, def_labels, def_categories)),
    _line("Traits affecting expression",
          ", ".join(p.traits) if p.traits else None),
    _line("Personality/expression", _personality(p)),
    _line("Mood", p.mood),
    _line("Physical state", _physical_state(p)),
    _line("Inspiration",
          _inspiration_value(p.inspiration, def_descriptions, def_labels)),
    _line("Chemical/drug state",
          ", ".join(describe_chemical_state(p.hediffs, def_labels))
          or None),
    _line("Shambler state",
          ", ".join(describe_shambler_state(p.hediffs, def_labels))
          or None),
    _line("Creepjoiner state",
          _creepjoiner_value(p.creepjoiner, def_labels)),
    _line("Pilot state", _pilot_state_value(p, def_labels)),
    _line("Commanded mechs",
          _commanded_mechs_value(p.commanded_mechs, def_labels)),
    _line("Connections",
          _connections_value(p.connections, def_labels)),
    _line("Bonded animals",
          _bonded_animals_value(p.bonded_animals, def_labels)),
    _line("Abilities", _abilities_value(p.abilities, def_labels)),
    _line("Psyfocus", _psyfocus_value(p.psyfocus)),
    _line("Pose/activity before portrait", p.current_job),
    _line("Outdoors/indoors",
          None if p.outdoor is None else
          ("outdoors (unroofed tile)" if p.outdoor
           else "indoors (roofed tile)")),
    _line("Favorite color/accent",
          describe_favorite_color(p.favorite_color)),
    _line("Visible genes/body traits",
          ", ".join(describe_genes(p.genes, def_labels)) or None),
    _line("Visible implants/injuries/body changes",
          ", ".join(describe_hediffs(p.hediffs, def_labels)) or None),
    *(_line(label, value)
      for label, value in _gear_lines(p, def_labels)),
    _line("Carrying infant in arms", _carrying_infant(p)),
    _line("Carrying (pack/inventory)",
          _carrying_summary(p, def_labels)),
  ):
    if ln:
      lines.append(ln)
  lines.append("[/PERSON]")
  return lines


def render_family(
  focus: PawnRecord,
  members: list[tuple[Relation, PawnRecord]],
  map_context: MapContext | None = None,
  *,
  include_instruction: bool = True,
  def_descriptions: dict[str, str] | None = None,
  def_labels: dict[str, str] | None = None,
  def_categories: dict[str, str] | None = None,
) -> str:
  """Build the [FAMILY PORTRAIT SUBJECT] block.

  members: list of (Relation, PawnRecord) for each directly-related
    pawn. Relation.def_name describes how that pawn relates to focus.
  """
  focus_name = focus.label or focus.nickname or focus.name_full
  lines: list[str] = ["[FAMILY PORTRAIT SUBJECT]"]
  lines.append(f"Focus pawn: {focus_name}")
  if focus.ideo:
    for ln in (
      _line("Shared ideology/culture", focus.ideo.name),
      _line("Ideology primary color", describe_rgba(focus.ideo.color)),
      _line("Ideology apparel color",
            describe_rgba(focus.ideo.apparel_color)),
      _line("Ideology style aesthetic",
            _style_categories_value(focus.ideo)),
      _line("Ideology memes", ", ".join(focus.ideo.memes) or None),
    ):
      if ln:
        lines.append(ln)
  env_lines = _map_block_lines(map_context)
  if env_lines:
    # Replace 'Colony/environment:' header with 'Shared environment:'.
    env_lines[0] = "Shared environment:"
    lines.extend(env_lines)
  # Focus pawn gets its own full [PERSON] block. Without this the
  # LLM only sees the name + ideology and ends up under-describing
  # the very pawn the family portrait centres on.
  lines.append("Focus pawn details:")
  lines.extend(_person_block(
    focus, "Focus pawn (centre of the family portrait)",
    def_descriptions, def_labels, def_categories,
  ))
  if members:
    lines.append("Family/direct relations from focus pawn:")
    for rel, other in members:
      other_name = other.label or other.nickname or other.name_full
      lines.append(f"- {rel.def_name}: {other_name}")
    lines.append("Family members:")
    for rel, other in members:
      lines.extend(_person_block(
        other, rel.def_name, def_descriptions, def_labels,
        def_categories,
      ))
  lines.append("[/FAMILY PORTRAIT SUBJECT]")
  block = "\n".join(lines)
  if include_instruction:
    return block + "\n\n" + FAMILY_PROMPT_INSTRUCTION
  return block
