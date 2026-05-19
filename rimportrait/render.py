"""Render PawnRecord/family groups into prompt-context blocks.

Block format and the trailing 'Final prompt instruction' strings come
verbatim from the user's spec. Both renderers omit lines whose values
are unavailable rather than emitting empty placeholders - keeps blocks
tight for downstream LLM consumption.
"""

from __future__ import annotations

from collections.abc import Iterable

from .colors import describe_rgba
from .records import (
  ApparelItem,
  GradientHair,
  IdeoRecord,
  MapContext,
  PawnRecord,
  Relation,
  Weapon,
)
from .translate.apparel import (
  describe_apparel,
  describe_apparel_item,
  is_utility_apparel,
  long_form_apparel_phrase,
  qualifier_for_apparel,
)
from .translate.favorite_color import describe_favorite_color
from .translate.genes import describe_genes
from .translate.hair import describe_gradient_mask, describe_hair_style
from .translate._common import humanise
from .translate.hediffs import describe_hediffs
from .translate.inventory import describe_inventory
from .translate.weapons import describe_weapon, qualifier_for_weapon
from .translate.xenotype import describe_xenotype
from .wealth import wealth_tier


SINGLE_PROMPT_INSTRUCTION = (
  "Create one polished image-generation prompt for a RimWorld pawn "
  "portrait.\n"
  "Translate the subject block into a visual prompt; do not repeat "
  "the block.\n"
  "Output one paragraph only, 70-130 words preferred, no JSON, no "
  "bullet points, no labels.\n"
  "Start with \"Portrait of [name], ...\"\n"
  "End with \"realistic gritty RimWorld sci-fi colony portrait, "
  "grounded expression, no UI.\"\n"
  "Include only strongest visible details. Prioritize xenotype/race, "
  "age, role, visible face, hair/beard, expression, posture, visible "
  "implants/injuries, armor/headgear, weapon, immediate setting, and "
  "colony situation. Keep background secondary. Avoid "
  "anime/manga/cartoon/chibi/glossy fantasy/pinup/exaggerated heroic "
  "style."
)


FAMILY_PROMPT_INSTRUCTION = (
  "Create one polished image-generation prompt for a RimWorld family "
  "portrait.\n"
  "Translate the family subject block into a believable visual "
  "portrait prompt; do not repeat the block.\n"
  "Output one paragraph only, 90-160 words preferred, no JSON, no "
  "bullet points, no labels.\n"
  "Start with \"Family portrait of...\"\n"
  "End with \"realistic gritty RimWorld sci-fi colony family "
  "portrait, grounded expressions, no UI.\"\n"
  "Show the family together with relationship-aware posing. Parents, "
  "spouses, lovers, and children should be visually grouped. Use "
  "protective gestures, shared glances, tension, affection, "
  "distance, or awkwardness based on relationships and "
  "personalities. Children should look age-appropriate and must not "
  "be sexualized. Helmets should usually be removed/carried/pushed "
  "back so faces are visible. Use gear and weapons as portrait "
  "props, not action clutter."
)


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
  it: ApparelItem, labels: dict[str, str] | None = None
) -> str:
  base = describe_apparel_item(it, labels)
  qual = qualifier_for_apparel(it)
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
  for it in p.apparel:
    target = utility if is_utility_apparel(it.def_name) else armor
    target.append(_apparel_phrase(it, labels))
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


def _compact_head_and_face(p: PawnRecord) -> str | None:
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
  if p.face_tattoo:
    bits.append(f"face tattoo {p.face_tattoo}")
  if p.body_tattoo:
    bits.append(f"body tattoo {p.body_tattoo}")
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

def _head_and_face_block(p: PawnRecord) -> list[str]:
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
    _sub("Face tattoo", p.face_tattoo),
    _sub("Body tattoo", p.body_tattoo),
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


def _map_block_lines(m: MapContext | None) -> list[str]:
  if m is None:
    return []
  threat = ", ".join(m.active_threats) if m.active_threats else None
  inner: list[str | None] = [
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
) -> str:
  """Build the [PORTRAIT SUBJECT] block for a single pawn."""
  name = p.label or p.nickname or p.name_full
  lines: list[str] = ["[PORTRAIT SUBJECT]"]
  for ln in (
    _line("Name", name),
    _line("Role", p.role.capitalize() if p.role else None),
    _line("Race/xenotype",
          _race_xenotype(p, def_descriptions, def_labels)),
    _line("Gender", p.gender),
    _line("Age", _age_str(p.bio_age, p.chrono_age)),
  ):
    if ln:
      lines.append(ln)
  head = _head_and_face_block(p)
  if head:
    lines.append("Head and face:")
    lines.extend(head)
  for ln in (
    _line("Traits affecting expression",
          ", ".join(p.traits) if p.traits else None),
    _line("Personality/expression", _personality(p)),
    _line("Mood", p.mood),
    _line("Pose/activity", p.current_job),
    _line("Immediate setting", p.location),
    _line("Favorite color/accent",
          describe_favorite_color(p.favorite_color)),
    _line("Visible genes/body traits",
          ", ".join(describe_genes(p.genes, def_labels)) or None),
    _line("Visible implants/injuries/body changes",
          ", ".join(describe_hediffs(p.hediffs, def_labels)) or None),
    *(_line(label, value)
      for label, value in _gear_lines(p, def_labels)),
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
) -> list[str]:
  lines: list[str] = ["[PERSON]"]
  name = p.label or p.nickname or p.name_full
  for ln in (
    _line("Name", name),
    _line("Relation to focus pawn", relation_to_focus),
    _line("Role", p.role.capitalize() if p.role else None),
    _line("Race/xenotype",
          _race_xenotype(p, def_descriptions, def_labels)),
    _line("Gender", p.gender),
    _line("Age", _age_str(p.bio_age, p.chrono_age)),
    _line("Head and face", _compact_head_and_face(p)),
    _line("Traits affecting expression",
          ", ".join(p.traits) if p.traits else None),
    _line("Personality/expression", _personality(p)),
    _line("Mood", p.mood),
    _line("Pose/activity before portrait", p.current_job),
    _line("Favorite color/accent",
          describe_favorite_color(p.favorite_color)),
    _line("Visible genes/body traits",
          ", ".join(describe_genes(p.genes, def_labels)) or None),
    _line("Visible implants/injuries/body changes",
          ", ".join(describe_hediffs(p.hediffs, def_labels)) or None),
    *(_line(label, value)
      for label, value in _gear_lines(p, def_labels)),
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
  if members:
    lines.append("Family/direct relations from focus pawn:")
    for rel, other in members:
      other_name = other.label or other.nickname or other.name_full
      lines.append(f"- {rel.def_name}: {other_name}")
    lines.append("Family members:")
    for rel, other in members:
      lines.extend(_person_block(
        other, rel.def_name, def_descriptions, def_labels
      ))
  lines.append("[/FAMILY PORTRAIT SUBJECT]")
  block = "\n".join(lines)
  if include_instruction:
    return block + "\n\n" + FAMILY_PROMPT_INSTRUCTION
  return block
