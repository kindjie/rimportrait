"""Render PawnRecord/family groups into prompt-context blocks.

Block format and the trailing 'Final prompt instruction' strings come
verbatim from the user's spec. Both renderers omit lines whose values
are unavailable rather than emitting empty placeholders - keeps blocks
tight for downstream LLM consumption.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from rimsave.colors import rgba_to_name
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
from rimsave.mods import layer_rank
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
from .translate.hair import describe_hair_style
from .translate._common import description_for, humanise
from .translate.hediffs import (
  describe_chemical_state,
  describe_hediffs,
  describe_pilot_state,
  describe_shambler_state,
)
from .translate.weapons import describe_weapon, qualifier_for_weapon
from .translate.xenotype import describe_xenotype
from .style import StyleSection


# --- shared instruction fragments ------------------------------------
#
# The three INSTRUCTION constants below (SINGLE / FAMILY / ACTION)
# share ~60% of their prose. Centralising the truly identical pieces
# here keeps edits in one place; per-mode wording stays inline.

_PREAMBLE = (
  "You write image-generation prompts for modern multimodal image "
  "models such as gpt-image-2 and gemini-3-pro-image-preview.\n\n"
)


def _output_format(min_words: int, max_words: int) -> str:
  return (
    "Output format:\n"
    "- One paragraph only.\n"
    f"- {min_words}-{max_words} words preferred.\n"
    "- No JSON.\n"
    "- No bullet points.\n"
    "- No labels like 'Subject:' or 'Style:'.\n"
    "- Do not generate multiple options.\n"
    "- The final output must be directly usable as an "
    "image-generation prompt.\n\n"
  )


_EMPTY_HELMET = (
  "- When a helmet or hat is carried/cradled/tucked rather than "
  "worn, describe its interior as visibly empty (hollow, lined "
  "padding, no face/head inside) - image models otherwise fill the "
  "negative space with a severed head.\n"
)


_SPARSE_NOTES = (
  "When source notes are sparse, invent only modest visual details "
  "needed for coherence. Do not invent major backstory, names, "
  "titles, symbols, factions, or plot events.\n\n"
)


_CHILD_SAFETY = (
  "Children look age-appropriate and are never sexualized."
)


def _ender(noun: str) -> str:
  return f'End with "realistic gritty RimWorld sci-fi colony {noun}, no UI."'


SINGLE_PROMPT_INSTRUCTION = """\
You write image-generation prompts for modern multimodal image \
models such as gpt-image-2 and gemini-3-pro-image-preview.

Task:
Given a [PORTRAIT SUBJECT] block, produce one polished \
image-generation prompt for a grounded cinematic portrait of one \
RimWorld pawn.

Output format:
- One paragraph only.
- 160-300 words preferred.
- No JSON.
- No bullet points.
- No labels like "Subject:" or "Style:".
- Do not generate multiple options.
- Do not include the pawn's name.
- End with: "{closer_phrase}"

Core goal:
Create a single coherent portrait image of the subject, in the \
style described below.

{style_section_prose}

Opening:
Start with "Portrait of a [age]-year-old [role/identity]..." using \
visual identity rather than game terms. Do not write raw def names \
such as Sanguophage, Yttakin, Hussar, Cataphract, Zeushammer, \
Victoria, MaskAHigh, Psycast, Hemogen, or ideology meme names \
unless they are also translated into clear visual language.

Translation rule:
Translate all RimWorld-specific terms into visual descriptors. The \
image model does not know game defs. Use the source descriptions to \
infer visible cues.

Examples:
- Sanguophage -> pale archotech-altered immortal human, slight \
fangs, unnaturally flawless skin, predatory stillness, blood-drinker \
undertone.
- Yttakin (or any furred xenotype / Furskin gene) -> the entire \
body is covered head-to-toe in a plush medium-to-long DOUBLE \
COAT of fur with visible length and weight (think Samoyed, Husky, \
Golden Retriever, Border Collie — not a short-haired breed, not \
bare skin). The 'Skin color' field in the block describes the \
FUR colour (not a visible skin tone underneath); write it as \
'a thick tan double coat with longer guard hairs across the \
shoulders' or 'dense black fur, medium length, slightly tufted \
at the cheeks and forearms', NOT as '[colour] skin' and NOT as a \
shaved short pelt. 'Hairstyle: Bald' for a furred xenotype \
just means no separate scalp hair on top of the fur — it does \
NOT mean visible bald skin; the head is still fully fur-covered. \
Any listed face/body tattoos must be re-expressed as marks the \
fur itself can carry: shaved-into-fur patterns (negative-space \
designs where the fur is cut short), dyed fur in contrasting \
colour, or raised scarification visible through the coat — NOT \
inked-on-skin tattoos, since the skin isn't visible. Animal-like \
ears or muzzle shape may be implied; eyes and a humanoid \
silhouette remain.
- Prestige cataphract armor -> ornate futuristic powered armor with \
bulky sealed plasteel plates, gold trim, servo-assisted joints, \
psychic-thread detailing, high-status military finish.
- Cataphract helmet -> heavy futuristic enclosed combat helmet with \
opaque visor optics, sealed plasteel shell, padded empty interior \
if carried.
- Persona zeushammer -> massive ultra-tech warhammer with seamless \
composite casing, charged impact head, faint blue-white electrical \
arcs, impossible precision.
- Psychic shock lance -> slim archotech sidearm/tool with seamless \
casing, faint iridescent channels, alien medical-instrument \
precision.
- Gunlink -> compact targeting computer with sensor modules and \
retinal-projector hardware.
- Cape -> visible over-armor drape, cloth/leather weight, \
colony-worn.
- Bandolier -> industrial shoulder belt with cartridge loops, \
pouches, worn leather, metal buckles.
- Baby carrier -> empty practical cloth carrier with simple straps \
and buckles.
- Hair-style defs -> translate into visible hair structure.
- Gradient hair -> describe the clean colour transition directly.

Tech-level rule:
Preserve the tech level of every visible item, regardless of visual \
art style. Do not turn futuristic equipment into medieval fantasy \
armor or generic knight armor.

Use this vocabulary:
- Neolithic-tech: knapped stone, bone, sinew, hide stitching, \
charred wood, rough handwork.
- Medieval-tech: rivets, hammered metal, leather straps, wool, \
hand stitching, polished or engraved metal for high quality.
- Industrial-tech: milled steel, machine stitching, brass fittings, \
gunpowder hardware, canvas, buckles, cartridges, factory-made wear.
- Spacer-tech: powered exosuit, servomotors, sealed composite \
plates, plasteel weave, visor optics, ablative coating, integrated \
sensors, armored joints, sci-fi life-support sealing.
- Ultra-tech: seamless nano-composite, impossible precision, \
contained energy fields, luminous channels, smart materials, \
compact high-energy mechanisms.
- Archotech-tech: alien-minimal seamless surfaces, faint \
iridescence, nonhuman geometry, subtle reality-bending glow, \
psychic or neural-machine unease.

Layering rule:
Describe only what is visible. Shell-layer armor hides middle-layer \
and onskin clothing on the same body region. An overhead helmet \
hides hair and most facial details if worn. For portraits, prefer \
the helmet removed, tucked under one arm, resting against the hip, \
or held at the side unless the source explicitly requires it worn. \
If a helmet is carried, clearly describe it as empty, with hollow \
padded interior and no face or head inside. Belt-layer gear, \
bandoliers, capes, baby carriers, sidearms, and carried weapons \
remain visible over armor.

Portrait priority:
The face must be clearly visible and be the emotional focus. If the \
pawn has defining hair, facial hair, tattoos, scars, skin tone, \
fangs, unusual eyes, or other identity cues, place those details \
early in the paragraph. Hair should be described structurally: \
length, parting, volume, direction, texture, and colour transition. \
Do not just repeat the hair def name.

Visible-body rule:
Mention only visible body traits. Do not describe hidden implants, \
missing toes, internal organs, stomach implants, brain implants, \
lactation, genes, hediffs, or abilities unless they create visible \
cues in the portrait. Translate invisible traits into expression, \
posture, stillness, confidence, fatigue, fear of fire, predatory \
restraint, or other visible behavior.

Expression and personality:
Translate personality, mood, role, relationships, traits, and \
backstory into visible behavior. Do not explain lore. Show it \
through expression, gaze, posture, warmth, tension, protectiveness, \
confidence, hunger, fatigue, guardedness, or social ease.

Action:
Anchor the portrait on one grounded action, not a static pose. Use \
the pawn's current activity when possible, translated visually. For \
HaulToCell, use something like carrying a sealed supply crate, \
dragging a storage bin, shifting weight under a heavy load, or \
pausing mid-haul in a colony yard. The action should support the \
portrait without becoming a full action scene.

Gear selection:
Use the 2-4 strongest visible gear elements, plus the wielded \
weapon if important. Do not list inventory. Prioritize visually \
distinctive and identity-defining items: futuristic powered armor, \
carried helmet, signature weapon, visible sidearm/tool, cape, \
bandolier, baby carrier, tattoos, hair, face.

Setting:
Use a simple RimWorld colony setting that supports the subject \
without stealing focus: steel colony yard, workshop, med bay, \
hydroponics room, transport-pad area, storage zone, rough perimeter \
wall, muddy forest clearing, improvised defenses. Use biome, \
weather, and time of day to motivate lighting. Morning clear \
weather means warm directional sunlight, crisp shadows, cool \
ambient fill, and dust or dew in the air.

Ideology and culture:
Do not name ideology memes or factions. Translate them into subtle \
palette, materials, posture, and background mood. Use ideological \
colours as accents only when visually useful. Morbid, spikecore, \
transhumanist, collectivist, supremacist, tunneler, or religious \
cues should appear as restrained visual influence, not explicit \
exposition or symbols unless the source names a specific visible \
object.

Always avoid (style-independent):
UI, HUD, captions, labels, watermarks, fake text, unreadable \
symbols, blank expression, exaggerated beauty.

If source notes conflict:
Prefer visual coherence. For example, if the prompt needs the face \
and hair visible but the pawn wears a helmet, carry the helmet \
instead of wearing it. If an item would be hidden under armor, \
omit it. If too many traits or objects are present, choose the \
most visually important ones.

Validation (silent self-check before responding):
Re-read your draft once against the checklist below. For each \
failing item, rewrite the offending fragment and re-check. Output \
ONLY the final paragraph - never the checklist, never an \
explanation, never multiple drafts.
1. No raw RimWorld def names appear (Sanguophage, Cataphract, \
Marine, Recon, Zeushammer, Persona, Senorita, Bowlcut, Mohawk, \
Curly, MaskAHigh, Hemogen, Psycast, HaulToCell, ideology meme \
names, faction names) unless the same clause also gives visual \
translation. Example pass: "an immortal blood-drinker"; example \
fail: "a Sanguophage colonist".
2. Every visible item's vocabulary matches its tech level. \
Spacer-tech items read as powered exosuits / servomotors / sealed \
plasteel / visor optics - never as cuirasses, breastplates, \
knight armor, or fantasy plate. Ultra/archotech items read as \
seamless composite / iridescent / energy-cored - never as forged \
steel hammers. Medieval items don't read as sci-fi. Neolithic \
items don't read as machined. Industrial items don't read as \
laser/plasma.
3. No clothing item that would be hidden under outer armor appears \
in the paragraph. Shell-layer armor over the torso hides any \
shirt, corset, blouse, robe, or pants on that body region - those \
items must not be described. Capes, belts, bandoliers, baby \
carriers, sidearms, and gunlinks DO remain visible over armor and \
should be kept.
4. If a helmet is mentioned, it is either (a) explicitly carried, \
tucked, or held at the side with its interior described as empty - \
hollow padded shell, no face, no head, no eyes inside - or (b) \
worn in a way the source demands. The face is never accidentally \
obscured.
5. The pawn's name does not appear anywhere in the paragraph.
6. The paragraph is a single block: no JSON, no bullets, no \
"Subject:" / "Style:" labels, no multiple alternative options, \
no headings.
7. Every face feature present in the Head and face section of \
the block appears in the paragraph and is described visually. \
This includes: hair (always, when present), beard / facial hair \
(when present - never omit; describe shape, length, coverage, and \
colour), face tattoo (when present - describe shape, placement, \
style), body tattoo (when present and visible on neck/arms/chest \
in the chosen framing), skin color (when present - skin tone), \
eye color (when present), and any other Head-and-face line. \
Missing the beard, face tattoo, or any other listed face feature \
is a failure - rewrite to add it.
8. Hair is described structurally - length, parting, volume, \
direction, texture, colour transition - within the first third of \
the paragraph. Not just the hair def name.
9. The portrait is anchored on one grounded RimWorld action \
translated visually, not a static or generic pose.
10. The closing phrase is exactly: "{closer_phrase}" with no \
extra words after it."""


FAMILY_PROMPT_INSTRUCTION = (
  _PREAMBLE
  + "Task:\n"
  "Given the [FAMILY PORTRAIT SUBJECT] block below, produce one "
  "polished image-generation prompt for a grounded cinematic family "
  "portrait of the focus pawn and the listed members.\n\n"
  + _output_format(130, 260)
  + "Core goal:\n"
  "Create a single coherent group portrait image of these people, "
  "in the style described below.\n\n"
  "{style_section_prose}\n\n"
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
  "- Trust the section-scoped Guidance: paragraphs inside each "
  "[PERSON] block; they govern apparel layering / tech, face, "
  "body, and pose. Do not contradict them.\n"
  "- Block the composition spatially: who stands where, who is "
  "closer to camera, gaze directions, who looks at whom.\n"
  "- For each person: one verb (from their Pose/activity or "
  "Inspiration), an emote matched to their mood and traits, and "
  "2-4 visible details (one apparel, one weapon/gear, one prop or "
  "texture). Do not overload with inventory.\n"
  "- Include the wielded weapon and hair description per person; "
  "image models drop late details, so anchor these early.\n"
  "- Show relationships through gesture: protective stance, "
  "shielding, shared glance, touch, distance, tension. "
  + _CHILD_SAFETY + "\n"
  "- Helmets are usually removed or carried so faces are visible. "
  + _EMPTY_HELMET +
  "- A simple setting that grounds the group without stealing "
  "focus.\n"
  "- One shared camera + lens + lighting line for the whole "
  "composition (e.g. 'shot on 50mm at f/4, warm directional light "
  "from camera-right').\n\n"
  "Always avoid (style-independent):\n"
  "UI, HUD, captions, labels, watermarks, fake text, unreadable "
  "symbols, blank expressions, exaggerated beauty, static line-up "
  "framing.\n\n"
  + _SPARSE_NOTES
  + 'End with "{closer_phrase}"'
)


ACTION_PROMPT_INSTRUCTION = (
  _PREAMBLE
  + "Task:\n"
  "Given the [PORTRAIT SUBJECT] block below, produce one polished "
  "image-generation prompt for a cinematic action image that looks "
  "like a still frame from a live-action movie.\n\n"
  + _output_format(120, 260)
  + "Core goal:\n"
  "Create a single coherent action image of the subject, in the "
  "style described below.\n\n"
  "{style_section_prose}\n\n"
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
  "- Trust the section-scoped Guidance: paragraphs inside the "
  "[PORTRAIT SUBJECT] block; they govern apparel layering / tech, "
  "face, body, pose, and environment. Do not contradict them.\n"
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
  + _EMPTY_HELMET
  + "\nAlways avoid (style-independent):\n"
  "UI, HUD, captions, labels, watermarks, fake text, unreadable "
  "symbols, static portrait pose, centered character-sheet framing, "
  "exaggerated beauty.\n\n"
  "When source notes include multiple characters, show "
  "relationship-aware blocking - distance, touch, eye lines, "
  "shielding gestures, hesitation, conflict, coordination. "
  + _CHILD_SAFETY + "\n\n"
  + _SPARSE_NOTES
  + 'End with "{closer_phrase}"'
)


# --- Per-model overlays ---------------------------------------------
# Thin model-specific notes appended to the base instruction when
# --image targets a known model. Each overlay is parameterised on
# the active style's ``mode_trigger`` so the leading-verb / mode
# rule swaps with the style (renaissance gets "An oil painting",
# default gets "Photorealistic", etc.).


def _overlay_gpt_image_2(mode_trigger: str) -> str:
  return (
    "Additional notes for OpenAI gpt-image-2 (the downstream image "
    "model):\n"
    f"- Lead the paragraph with \"{mode_trigger}\" - it is "
    "gpt-image-2's documented mode trigger.\n"
    "- gpt-image-2 has no negative-prompt parameter; rely on "
    "in-prompt exclusions (\"no UI\", \"no text overlay\", "
    "\"no watermark\").\n"
    "- For any held/carried object, name the hand (\"left hand\"), "
    "the height (\"at hip\", \"under arm\"), and the state "
    "(\"empty\", \"sheathed\", \"shouldered\") - gpt-image-2's "
    "Thinking Mode reasons over explicit spatial relationships, and "
    "naming them is the documented antidote to negative-space "
    "hallucinations."
  )


def _overlay_gemini_pro(mode_trigger: str) -> str:
  return (
    "Additional notes for Google Gemini 3 Pro Image - Nano Banana "
    "Pro (the downstream image model):\n"
    f"- Start the paragraph with \"{mode_trigger}\" or another "
    "strong verb that matches the style (\"Render\", "
    "\"Photograph\", \"Paint\").\n"
    "- Use POSITIVE reframing of negatives - describe what IS, not "
    "what isn't. Instead of \"no head in the helmet\" write "
    "\"empty helmet gripped by the rim, hollow leather-lined "
    "interior facing the camera\".\n"
    "- Use material-specific nouns (\"navy tweed cuirass\" over "
    "\"armor\"; \"sun-bleached canvas duster\" over \"jacket\") - "
    "the highest-ROI lever this model rewards.\n"
    "- Pro tolerates and rewards dense clause-heavy prompts; aim "
    "toward the upper end of the word budget when the source block "
    "is rich."
  )


def _overlay_gemini_flash(mode_trigger: str) -> str:
  return (
    "Additional notes for Google Gemini 3.1 Flash Image - Nano "
    "Banana 2 (the downstream image model):\n"
    f"- Start the paragraph with \"{mode_trigger}\" or another "
    "strong verb that matches the style (\"Photograph\", "
    "\"Render\").\n"
    "- Flash drops detail aggressively on long prompts; aim for "
    "the lower end of the word budget and strip nice-to-have "
    "flourishes.\n"
    "- Use POSITIVE reframing of negatives (\"empty helmet, "
    "hollow interior visible\" not \"no head in the helmet\").\n"
    "- Soften violence/wound language to avoid the safety filter: "
    "prefer \"battle-worn\", \"scarred\", \"weathered\", "
    "\"powder-burned\" over explicit gore verbs. Describe weapons "
    "as objects (\"holds a bolt-action rifle\") not actions "
    "(\"aiming\", \"firing\") unless the block clearly signals "
    "active combat."
  )


_PER_MODEL_OVERLAY: dict[str, "Callable[[str], str]"] = {
  "gpt-image-2": _overlay_gpt_image_2,
  "gemini-3-pro-image-preview": _overlay_gemini_pro,
  "gemini-3.1-flash-image-preview": _overlay_gemini_flash,
}


_KIND_TO_BASE: dict[str, str] = {
  "portrait": SINGLE_PROMPT_INSTRUCTION,
  "family": FAMILY_PROMPT_INSTRUCTION,
  "action": ACTION_PROMPT_INSTRUCTION,
}


# --- Default style sections (no-preset path) -------------------------
# When no preset is active, the kind's core is rendered with the
# kind's default section. The prose here reconstitutes the original
# Style + Avoid + RimWorld-context language so existing no-preset
# users see no behaviour change after the refactor.

_DEFAULT_PORTRAIT_SECTION = StyleSection(
  mode_trigger="Photorealistic",
  closer_phrase=(
    "realistic gritty RimWorld sci-fi colony portrait, "
    "grounded expression, no UI."
  ),
  prose=(
    "Style:\n"
    "Use realistic cinematic portrait language: natural proportions, "
    "believable skin texture, subtle asymmetry, practical materials, "
    "worn surfaces, dust, scratches, sweat, grime, lived-in clothing, "
    "restrained color grading, shallow depth of field, realistic "
    "lens feel, soft side light or motivated practical light.\n\n"
    "Avoid (style-dependent):\n"
    "Glamour retouching, static passport-photo pose, centered "
    "character-sheet framing, superhero poster composition, "
    "fantasy knight armor, glossy fantasy armor, anime, cartoon, "
    "chibi, plastic-looking 3D render, clean studio lighting, "
    "excessive background detail."
  ),
)

_DEFAULT_FAMILY_SECTION = StyleSection(
  mode_trigger="Photorealistic",
  closer_phrase=(
    "realistic gritty RimWorld sci-fi colony family portrait, "
    "grounded expressions, no UI."
  ),
  prose=(
    "Style:\n"
    "Realistic cinematic portrait language. Natural proportions, "
    "practical materials, imperfect surfaces, lived-in clothing, "
    "visible texture, subtle asymmetry, believable skin, weathering, "
    "dust, sweat, grime, restrained color grading.\n\n"
    "RimWorld context:\n"
    "Use gritty colony survival imagery - patched clothing, "
    "improvised armor, steel walls, workshops, med bays, rough "
    "repairs, utility lighting, hostile weather outside, worn "
    "tools, practical weapons, tired eyes, grounded expressions. "
    "Do not copy RimWorld's top-down game UI style.\n\n"
    "Avoid (style-dependent):\n"
    "Glamour retouching, superhero poster composition, glossy "
    "fantasy armor, anime, cartoon, chibi, plastic-looking 3D "
    "render, clean studio lighting."
  ),
)

_DEFAULT_ACTION_SECTION = StyleSection(
  mode_trigger="Photorealistic",
  closer_phrase=(
    "realistic gritty RimWorld sci-fi colony action still, no UI."
  ),
  prose=(
    "Style:\n"
    "Realistic live-action cinematic sci-fi or grounded film-still "
    "language. Natural proportions, practical materials, imperfect "
    "surfaces, weathering, dust, sweat, grime, believable clothing, "
    "restrained cinematic color grading.\n\n"
    "RimWorld context:\n"
    "Use gritty colony survival imagery - improvised defenses, "
    "steel walls, muddy yards, hydroponics rooms, workshops, med "
    "bays, transport pods, hostile weather, emergency lights, "
    "damaged armor, practical weapons, patched clothing, exhausted "
    "but grounded expressions. Do not copy RimWorld's top-down "
    "game UI style.\n\n"
    "Avoid (style-dependent):\n"
    "Superhero poster composition, glossy fantasy armor, anime, "
    "cartoon, chibi, plastic-looking 3D render, clean studio "
    "lighting."
  ),
)


_KIND_TO_DEFAULT_SECTION: dict[str, StyleSection] = {
  "portrait": _DEFAULT_PORTRAIT_SECTION,
  "family": _DEFAULT_FAMILY_SECTION,
  "action": _DEFAULT_ACTION_SECTION,
}


def instruction_for(
  kind: str,
  image_model: str | None = None,
  section: StyleSection | None = None,
) -> str:
  """Assemble the system instruction for this image kind.

  ``kind`` is ``portrait`` (single pawn), ``family`` (group), or
  ``action`` (cinematic still). ``section`` is the style envelope
  to splice in; when omitted, the kind's default section is used
  (matches today's no-preset output).

  The model-specific overlay (when ``image_model`` matches a tuned
  model) is appended below the assembled base, with its
  leading-verb rule wired to the section's ``mode_trigger`` so it
  doesn't contradict the active style.
  """
  if kind not in _KIND_TO_BASE:
    raise ValueError(f"unknown render kind {kind!r}")
  if section is None:
    section = _KIND_TO_DEFAULT_SECTION[kind]
  base = _KIND_TO_BASE[kind].format(
    closer_phrase=section.closer_phrase,
    style_section_prose=section.prose,
  )
  overlay_fn = _PER_MODEL_OVERLAY.get(image_model) if image_model else None
  if overlay_fn is None:
    return base
  overlay = overlay_fn(section.mode_trigger)
  return f"{base}\n\n{overlay}"


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
  c_b = rgba_to_name(gh.color_b) if gh.color_b else None
  if c_b:
    parts.append(f"gradient color {c_b}")
  return "; ".join(parts)


def _layer_tag(
  def_name: str,
  apparel_layers: dict[str, str] | None,
) -> str:
  """Return a ``[<layer>-layer]`` tag for the def, or empty string.

  Sourced from the def's <apparel><layers> tag (mod-aware,
  ParentName-inherited). The render layer also uses this layer to
  sort items outer-to-inner so the worn-armor line reads from the
  outermost visible silhouette inward."""
  if apparel_layers is None:
    return ""
  layer = apparel_layers.get(def_name)
  if not layer:
    return ""
  return f" [{layer.lower()}-layer]"


def _tech_tag(
  def_name: str,
  tech_levels: dict[str, str] | None,
) -> str:
  """Return a ``[<tech>-tech]`` tag for the def, or empty string.

  Sourced from the def's <techLevel> tag (mod-aware, ParentName-
  inherited). The LLM uses this to pick period-appropriate vocabulary
  without having to guess from the item name."""
  if tech_levels is None:
    return ""
  tech = tech_levels.get(def_name)
  if not tech:
    return ""
  return f" [{tech}-tech]"


def _apparel_phrase(
  it: ApparelItem,
  labels: dict[str, str] | None = None,
  carrying_infant: bool = False,
  cost_materials: dict[str, str] | None = None,
  tech_levels: dict[str, str] | None = None,
  apparel_layers: dict[str, str] | None = None,
) -> str:
  """Render one apparel item's inline phrase.

  Baby carriers gain an "empty" marker when no infant is being held,
  so the LLM doesn't draw a baby into an unused carrier (or miss the
  carrier signal entirely when one is present).
  """
  base = describe_apparel_item(it, labels)
  qual = qualifier_for_apparel(it, cost_materials)
  if is_baby_carrier(it.def_name) and not carrying_infant:
    qual = f"{qual}, empty" if qual else "empty"
  body = f"{base} ({qual})" if qual else base
  return (body
          + _layer_tag(it.def_name, apparel_layers)
          + _tech_tag(it.def_name, tech_levels))


def _weapon_phrase(
  w: Weapon,
  labels: dict[str, str] | None = None,
  tech_levels: dict[str, str] | None = None,
) -> str:
  base = describe_weapon(w, labels)
  qual = qualifier_for_weapon(w)
  body = f"{base} ({qual})" if qual else base
  return body + _tech_tag(w.def_name, tech_levels)


def _gear_lines(
  p: PawnRecord,
  labels: dict[str, str] | None = None,
  cost_materials: dict[str, str] | None = None,
  tech_levels: dict[str, str] | None = None,
  apparel_layers: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
  """Split worn gear into three prominence buckets.

  Returns (label, value) pairs for: armor/clothing layers, belt/utility
  gear, and the wielded weapon. Each bucket is omitted when empty.
  Inventory (carried pack contents) is reported on its own line by
  _carrying_summary and is not included here, so the equipped
  silhouette stays distinct from pack supplies.
  """
  armor_items: list[ApparelItem] = []
  utility_items: list[ApparelItem] = []
  carrying = p.carried_infant is not None
  for it in p.apparel:
    target = utility_items if is_utility_apparel(it.def_name) else armor_items
    target.append(it)
  # Sort outer -> inner so the rendered line reads from the visible
  # silhouette inward. Belt items (utility) and torso layers each
  # sort within their own bucket. Stable sort preserves extraction
  # order on ties.
  def _outer_key(it: ApparelItem) -> int:
    layer = (apparel_layers or {}).get(it.def_name)
    return layer_rank(layer)
  armor_items.sort(key=_outer_key)
  utility_items.sort(key=_outer_key)
  armor = [_apparel_phrase(
    it, labels, carrying_infant=carrying,
    cost_materials=cost_materials,
    tech_levels=tech_levels,
    apparel_layers=apparel_layers,
  ) for it in armor_items]
  utility = [_apparel_phrase(
    it, labels, carrying_infant=carrying,
    cost_materials=cost_materials,
    tech_levels=tech_levels,
    apparel_layers=apparel_layers,
  ) for it in utility_items]
  weapons = [_weapon_phrase(w, labels, tech_levels) for w in p.equipment]
  out: list[tuple[str, str]] = []
  if armor:
    out.append(("Worn armor/clothing", ", ".join(armor)))
  if utility:
    out.append(("Utility belts/gear", ", ".join(utility)))
  if weapons:
    out.append(("Wielded weapon", ", ".join(weapons)))
  return out


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
    # Prefer the resolved Empire / mod label (e.g. RimWorld's
    # `Count` def with label `archon`); fall back to the def name.
    head = label if label else t.def_name
    if t.faction_name:
      parts.append(f"{head} of {t.faction_name}")
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
    return _strip_rimtalk_style(p.personality)
  bits: list[str] = []
  if p.backstory_child:
    bits.append(f"childhood: {p.backstory_child}")
  if p.backstory_adult:
    bits.append(f"adulthood: {p.backstory_adult}")
  if not bits:
    return None
  return "; ".join(bits)


def _strip_rimtalk_style(text: str) -> str:
  """Drop the trailing RimTalk ``Style: talk X, warmth Y, ...``
  sentence appended to every personality blob. These numeric voice
  stats don't shape the visual portrait."""
  marker = " Style: "
  idx = text.find(marker)
  if idx == -1:
    return text
  return text[:idx].rstrip()


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
  hair_color = rgba_to_name(p.hair_color) if p.hair_color else None
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
  skin = rgba_to_name(p.skin_color) if p.skin_color else None
  if skin:
    bits.append(f"skin {skin}")
  eye = rgba_to_name(p.eye_color) if p.eye_color else None
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
    _sub("Hair/base beard color",
         rgba_to_name(p.hair_color) if p.hair_color else None),
    _sub("Hair gradient", _gradient_value(p.gradient_hair)),
    _sub("Beard", beard_disp),
    _sub("Beard color",
         rgba_to_name(p.beard_color) if p.beard_color else None),
    _sub("Face tattoo", _tattoo_phrase(p.face_tattoo, labels, categories)),
    _sub("Body tattoo", _tattoo_phrase(p.body_tattoo, labels, categories)),
    _sub("Skin color",
         rgba_to_name(p.skin_color) if p.skin_color else None),
    _sub("Eye color",
         rgba_to_name(p.eye_color) if p.eye_color else None),
  ]
  return [s for s in lines if s]


def _ideo_block_lines(ideo: IdeoRecord | None) -> list[str]:
  if ideo is None:
    return []
  lines: list[str | None] = [
    _line("Ideology/culture", ideo.name),
    _line("Ideology primary color",
          rgba_to_name(ideo.color) if ideo.color else None),
    _line("Ideology apparel color",
          rgba_to_name(ideo.apparel_color) if ideo.apparel_color else None),
    _line("Ideology description/style",
          _first_sentence(ideo.description or ideo.style_summary)),
    _line("Ideology style aesthetic", _style_categories_value(ideo)),
    _line("Ideology memes", _meme_list(ideo.memes)),
  ]
  return [s for s in lines if s]


def _style_categories_value(ideo: IdeoRecord) -> str | None:
  """Render thingStyleCategories as a comma-joined name list.

  Priority numbers are dropped - they don't help the image model
  decide weighting, and the ordering of the list (already
  priority-descending from the save) already encodes precedence."""
  if not ideo.style_categories:
    return None
  return ", ".join(cat for cat, _pri in ideo.style_categories)


def _meme_list(memes: tuple[str, ...]) -> str | None:
  """Comma-join meme defs, stripping the internal ``Structure_``
  category prefix from the first (structure) meme so the LLM sees
  the readable identity (``TheistEmbodied``) rather than the
  internal class marker."""
  if not memes:
    return None
  cleaned = [m.removeprefix("Structure_") for m in memes]
  return ", ".join(cleaned)


def _first_sentence(text: str | None) -> str | None:
  """Truncate prose to its first sentence (everything up to and
  including the first ``. ``). Used to trim multi-paragraph lore
  paragraphs (xenotype, ideology, apparel descriptions) down to the
  one sentence that actually carries visual signal."""
  if not text:
    return None
  s = text.strip()
  if not s:
    return None
  # Find the earliest sentence terminator followed by whitespace.
  for i, ch in enumerate(s):
    if ch in ".!?" and (i + 1 == len(s) or s[i + 1].isspace()):
      return s[: i + 1]
  return s


def _setting_value(p: PawnRecord) -> str | None:
  """Compose a single 'Setting:' line from outdoor/roof/terrain/map_kind/
  caravan flags. Returns None when no signal is available at all."""
  if p.caravan:
    return "traveling in a caravan (no map)"
  # Terrain override - substructure means gravship, regardless of roof
  # or map_kind label.
  if p.terrain_kind == "substructure":
    suffix = f", on a {p.map_kind}" if p.map_kind else ""
    return f"inside a gravship (built on substructure){suffix}"
  if p.terrain_kind == "bridge":
    suffix = f", {p.map_kind}" if p.map_kind else ""
    return f"outdoors on a bridge{suffix}"
  # Roof + map_kind composition.
  parts: list[str] = []
  if p.outdoor is True:
    parts.append("outdoors")
  elif p.outdoor is False:
    if p.roof_kind:
      parts.append(p.roof_kind)
    else:
      parts.append("indoors")
  if p.map_kind:
    parts.append(p.map_kind)
  if not parts:
    return None
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
  inner: list[str | None] = [
    _sub("Time of day", _time_of_day_value(m)),
    _sub("Weather", m.weather),
    _sub("Biome", m.biome),
  ]
  inner_filtered = [s for s in inner if s]
  if not inner_filtered:
    return []
  return ["Colony/environment:"] + inner_filtered


def _apparel_section(
  items: Iterable[ApparelItem],
  def_descriptions: dict[str, str] | None = None,
  def_labels: dict[str, str] | None = None,
  def_cost_materials: dict[str, str] | None = None,
  def_tech_levels: dict[str, str] | None = None,
  def_apparel_layers: dict[str, str] | None = None,
) -> list[str]:
  # Sort outer -> inner to match the inline "Worn armor/clothing"
  # ordering so the LLM sees the same silhouette story twice.
  def _outer_key(it: ApparelItem) -> int:
    layer = (def_apparel_layers or {}).get(it.def_name)
    return layer_rank(layer)
  items_list = sorted(items, key=_outer_key)
  rows = describe_apparel(items_list, def_labels)
  if not rows:
    return []
  out = ["Apparel visual descriptions:"]
  for item, (label, _summary) in zip(items_list, rows):
    body = long_form_apparel_phrase(item, def_descriptions, def_labels)
    qual = qualifier_for_apparel(item, def_cost_materials)
    head = f"- {label}"
    if qual:
      head += f" [{qual}]"
    head += _layer_tag(item.def_name, def_apparel_layers)
    head += _tech_tag(item.def_name, def_tech_levels)
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
  def_cost_materials: dict[str, str] | None = None,
  def_tech_levels: dict[str, str] | None = None,
  def_apparel_layers: dict[str, str] | None = None,
) -> str:
  """Build the [PORTRAIT SUBJECT] block for a single pawn.

  Topic sections (Identity / Face / Body / Apparel / Pose & state /
  Environment) each carry their own ``Guidance:`` paragraph so the
  downstream LLM reads instructions adjacent to the data they
  govern, instead of cross-referencing one big trailing block."""
  name = p.label or p.nickname or p.name_full
  lines: list[str] = ["[PORTRAIT SUBJECT]"]
  # Identity.
  identity = [ln for ln in (
    _line("Name", name),
    _line("Role", p.role.capitalize() if p.role else None),
    _line("Royal title",
          _royal_title_line(p.royal_titles, def_labels)),
    _line("Race/xenotype",
          _race_xenotype(p, def_descriptions, def_labels)),
    _line("Gender", p.gender),
    _line("Age", _age_str(p.bio_age, p.chrono_age)),
  ) if ln]
  if identity:
    lines.append("Identity:")
    lines.extend(identity)
    lines.append("")
  # Face.
  head = _head_and_face_block(p, def_labels, def_categories)
  if head:
    lines.append("Head and face:")
    lines.extend(head)
    lines.append("")
  # Body.
  body = [s for s in (
    _sub("Visible genes/body traits",
         ", ".join(describe_genes(
           p.genes, def_labels, endogenes_only=True,
         )) or None),
    _sub("Visible implants/injuries/body changes",
         ", ".join(describe_hediffs(p.hediffs, def_labels)) or None),
  ) if s]
  if body:
    lines.append("Body:")
    lines.extend(body)
    lines.append("")
  # Apparel — worn line, visual descriptions, carried/inventory all in
  # one section so the LLM doesn't have to cross-reference them.
  apparel = [s for s in (
    *(_sub(label, value)
      for label, value in _gear_lines(
        p, def_labels, def_cost_materials, def_tech_levels,
        def_apparel_layers)),
    _sub("Carrying infant in arms", _carrying_infant(p)),
  ) if s]
  visual = _apparel_section(
    p.apparel, def_descriptions, def_labels, def_cost_materials,
    def_tech_levels, def_apparel_layers,
  )
  if apparel or visual:
    lines.append("Apparel:")
    lines.extend(apparel)
    lines.extend(visual)
    lines.append("")
  # Pose, action, and state — what they're doing, mood/behavior cues.
  pose_lines = [s for s in (
    _sub("Pose/activity", p.current_job),
    _sub("Setting", _setting_value(p)),
    _sub("Immediate setting", p.location),
    _sub("Favorite color/accent",
         describe_favorite_color(p.favorite_color)),
    _sub("Traits affecting expression",
         ", ".join(p.traits) if p.traits else None),
    _sub("Personality/expression", _personality(p)),
    _sub("Mood", p.mood),
    _sub("Physical state", _physical_state(p)),
    _sub("Inspiration",
         _inspiration_value(p.inspiration, def_descriptions, def_labels)),
    _sub("Chemical/drug state",
         ", ".join(describe_chemical_state(p.hediffs, def_labels))
         or None),
    _sub("Shambler state",
         ", ".join(describe_shambler_state(p.hediffs, def_labels))
         or None),
    _sub("Creepjoiner state",
         _creepjoiner_value(p.creepjoiner, def_labels)),
    _sub("Pilot state", _pilot_state_value(p, def_labels)),
    _sub("Commanded mechs",
         _commanded_mechs_value(p.commanded_mechs, def_labels)),
    _sub("Bonded animals",
         _bonded_animals_value(p.bonded_animals, def_labels)),
  ) if s]
  if pose_lines:
    lines.append("Pose, action, and state:")
    lines.extend(pose_lines)
    lines.append("")
  # Environment — ideology + colony/map context.
  env_lines = _ideo_block_lines(p.ideo) + _map_block_lines(map_context)
  if env_lines:
    lines.append("Environment:")
    lines.extend(env_lines)
    lines.append("")
  # Drop trailing blank line before the closing tag if present.
  while lines and lines[-1] == "":
    lines.pop()
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
  def_cost_materials: dict[str, str] | None = None,
  def_tech_levels: dict[str, str] | None = None,
  def_apparel_layers: dict[str, str] | None = None,
) -> list[str]:
  lines: list[str] = ["[PERSON]"]
  name = p.label or p.nickname or p.name_full
  # Identity.
  identity = [ln for ln in (
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
  ) if ln]
  if identity:
    lines.append("Identity:")
    lines.extend(identity)
    lines.append("")
  # Body.
  body = [s for s in (
    _sub("Visible genes/body traits",
         ", ".join(describe_genes(
           p.genes, def_labels, endogenes_only=True,
         )) or None),
    _sub("Visible implants/injuries/body changes",
         ", ".join(describe_hediffs(p.hediffs, def_labels)) or None),
  ) if s]
  if body:
    lines.append("Body:")
    lines.extend(body)
    lines.append("")
  # Apparel — worn + visual descriptions + carried in one section.
  apparel = [s for s in (
    *(_sub(label, value)
      for label, value in _gear_lines(
        p, def_labels, def_cost_materials, def_tech_levels,
        def_apparel_layers)),
    _sub("Carrying infant in arms", _carrying_infant(p)),
  ) if s]
  visual = _apparel_section(
    p.apparel, def_descriptions, def_labels, def_cost_materials,
    def_tech_levels, def_apparel_layers,
  )
  if apparel or visual:
    lines.append("Apparel:")
    lines.extend(apparel)
    lines.extend(visual)
    lines.append("")
  # Pose, action, and state.
  pose_lines = [s for s in (
    _sub("Pose/activity before portrait", p.current_job),
    _sub("Setting", _setting_value(p)),
    _sub("Favorite color/accent",
         describe_favorite_color(p.favorite_color)),
    _sub("Traits affecting expression",
         ", ".join(p.traits) if p.traits else None),
    _sub("Personality/expression", _personality(p)),
    _sub("Mood", p.mood),
    _sub("Physical state", _physical_state(p)),
    _sub("Inspiration",
         _inspiration_value(p.inspiration, def_descriptions, def_labels)),
    _sub("Chemical/drug state",
         ", ".join(describe_chemical_state(p.hediffs, def_labels))
         or None),
    _sub("Shambler state",
         ", ".join(describe_shambler_state(p.hediffs, def_labels))
         or None),
    _sub("Creepjoiner state",
         _creepjoiner_value(p.creepjoiner, def_labels)),
    _sub("Pilot state", _pilot_state_value(p, def_labels)),
    _sub("Commanded mechs",
         _commanded_mechs_value(p.commanded_mechs, def_labels)),
    _sub("Bonded animals",
         _bonded_animals_value(p.bonded_animals, def_labels)),
  ) if s]
  if pose_lines:
    lines.append("Pose, action, and state:")
    lines.extend(pose_lines)
    lines.append("")
  while lines and lines[-1] == "":
    lines.pop()
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
  def_cost_materials: dict[str, str] | None = None,
  def_tech_levels: dict[str, str] | None = None,
  def_apparel_layers: dict[str, str] | None = None,
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
      _line("Ideology primary color",
            rgba_to_name(focus.ideo.color)
            if focus.ideo.color else None),
      _line("Ideology apparel color",
            rgba_to_name(focus.ideo.apparel_color)
            if focus.ideo.apparel_color else None),
      _line("Ideology style aesthetic",
            _style_categories_value(focus.ideo)),
      _line("Ideology memes", _meme_list(focus.ideo.memes)),
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
    def_cost_materials, def_tech_levels, def_apparel_layers,
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
        def_categories, def_cost_materials, def_tech_levels,
        def_apparel_layers,
      ))
  lines.append("[/FAMILY PORTRAIT SUBJECT]")
  block = "\n".join(lines)
  if include_instruction:
    return block + "\n\n" + FAMILY_PROMPT_INSTRUCTION
  return block
