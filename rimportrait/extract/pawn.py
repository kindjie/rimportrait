"""Pawn / map-context / family extraction over a loaded Save."""

from __future__ import annotations

import re
from collections.abc import Iterator

from lxml import etree

from ..colors import RGBA
from ..records import (
  ApparelItem,
  Gene,
  GradientHair,
  Hediff,
  IdeoRecord,
  MapContext,
  PawnRecord,
  Relation,
  Weapon,
)
from ..translate.colordef import apparel_variant, lookup_color_def
from .load import Save, resolve_ideo_ref


TICKS_PER_YEAR = 3_600_000


# RimWorld trait def + degree -> human label. Seeded with the common
# variants; extend as needed.
_TRAIT_LABELS: dict[tuple[str, int], str] = {
  ("Beauty", -2): "Very Ugly",
  ("Beauty", -1): "Ugly",
  ("Beauty", 1): "Pretty",
  ("Beauty", 2): "Beautiful",
  ("SpeedOffset", 1): "Fast Walker",
  ("SpeedOffset", 2): "Jogger",
  ("SpeedOffset", -1): "Slowpoke",
  ("Industriousness", -2): "Lazy",
  ("Industriousness", -1): "Slothful",
  ("Industriousness", 1): "Hard Worker",
  ("Industriousness", 2): "Industrious",
  ("Nerves", -2): "Volatile",
  ("Nerves", -1): "Nervous",
  ("Nerves", 1): "Steadfast",
  ("Nerves", 2): "Iron-Willed",
  ("NaturalMood", -2): "Depressive",
  ("NaturalMood", -1): "Pessimist",
  ("NaturalMood", 1): "Optimist",
  ("NaturalMood", 2): "Sanguine",
  ("Neurotic", 1): "Neurotic",
  ("Neurotic", 2): "Very Neurotic",
  ("PsychicSensitivity", -2): "Psychically Deaf",
  ("PsychicSensitivity", -1): "Psychically Dull",
  ("PsychicSensitivity", 1): "Psychically Sensitive",
  ("PsychicSensitivity", 2): "Psychically Hypersensitive",
}


# Faction-relative role classification.
def _role_from_kind(kind: str | None) -> str:
  if not kind:
    return "unknown"
  k = kind.lower()
  if "colonist" in k:
    return "colonist"
  if "slave" in k:
    return "slave"
  if "prisoner" in k:
    return "prisoner"
  if "guest" in k or "visitor" in k:
    return "guest"
  return kind


def _name(el: etree._Element) -> tuple[str, str | None, str | None]:
  name_el = el.find("name")
  if name_el is None:
    return ("Unknown", None, None)
  first = name_el.findtext("first") or ""
  nick = name_el.findtext("nick")
  last = name_el.findtext("last") or ""
  full = " ".join(s for s in (first, last) if s) or (nick or "Unknown")
  return (full, nick, nick or first or None)


def _traits(el: etree._Element) -> tuple[str, ...]:
  out: list[str] = []
  for li in el.iterfind("story/traits/allTraits/li"):
    d = li.findtext("def") or ""
    raw_deg = li.findtext("degree")
    deg = int(raw_deg) if raw_deg and raw_deg.lstrip("-").isdigit() else 0
    key = (d, deg)
    if key in _TRAIT_LABELS:
      out.append(_TRAIT_LABELS[key])
    elif deg == 0:
      out.append(d)
    else:
      out.append(f"{d}({deg})")
  return tuple(out)


def _gradient_hair(el: etree._Element) -> GradientHair | None:
  gh = el.find("gradientHair")
  if gh is None:
    return None
  if gh.attrib.get("IsNull") == "True":
    return GradientHair(enabled=False, color_b=None, mask=None)
  color_b = RGBA.parse(gh.findtext("colorB"))
  mask = gh.findtext("mask")
  return GradientHair(enabled=True, color_b=color_b, mask=mask)


def _genes(el: etree._Element) -> tuple[Gene, ...]:
  out: list[Gene] = []
  for path in ("genes/xenogenes/li", "genes/endogenes/li"):
    for li in el.iterfind(path):
      d = li.findtext("def")
      if d:
        out.append(Gene(def_name=d))
  return tuple(out)


def _hediffs(el: etree._Element) -> tuple[Hediff, ...]:
  out: list[Hediff] = []
  for li in el.iterfind("healthTracker/hediffSet/hediffs/li"):
    d = li.findtext("def")
    if not d:
      continue
    part = li.findtext("part/label") or li.findtext("Part") or None
    out.append(Hediff(def_name=d, body_part=part))
  return tuple(out)


def _apparel(el: etree._Element) -> tuple[ApparelItem, ...]:
  out: list[ApparelItem] = []
  for li in el.iterfind("apparel/wornApparel/innerList/li"):
    d = li.findtext("def")
    if d:
      out.append(ApparelItem(def_name=d))
  return tuple(out)


def _equipment(el: etree._Element) -> tuple[Weapon, ...]:
  out: list[Weapon] = []
  for li in el.iterfind("equipment/equipment/innerList/li"):
    d = li.findtext("def")
    if d:
      out.append(Weapon(def_name=d))
  return tuple(out)


def _relations(el: etree._Element) -> tuple[Relation, ...]:
  out: list[Relation] = []
  for li in el.iterfind("social/directRelations/li"):
    d = li.findtext("def")
    other = li.findtext("otherPawn")
    if d and other and other.lower() != "null":
      out.append(Relation(def_name=d, other_pawn_id=other))
  return tuple(out)


def _ideo(el: etree._Element, save: Save) -> IdeoRecord | None:
  ref = el.findtext("ideo/ideo")
  if not ref:
    return None
  ideo_el = resolve_ideo_ref(save, ref)
  if ideo_el is None:
    return None
  # ColorDef name -> canonical RGBA matches what the in-game UI shows.
  # primaryFactionColor in the save is a faction-level override; use
  # ColorDef when present, fall back to primaryFactionColor otherwise.
  color_def = ideo_el.findtext("colorDef")
  primary = (
    lookup_color_def(color_def)
    or RGBA.parse(ideo_el.findtext("primaryFactionColor"))
  )
  apparel = apparel_variant(primary) if primary is not None else None
  return IdeoRecord(
    name=ideo_el.findtext("name") or "(unnamed ideology)",
    color=primary,
    apparel_color=apparel,
    description=_strip_tags(ideo_el.findtext("description")),
    style_summary=ideo_el.findtext("adjective"),
  )


def _age(el: etree._Element) -> tuple[float | None, float | None]:
  raw = el.findtext("ageTracker/ageBiologicalTicks")
  if not raw:
    return (None, None)
  try:
    bio_ticks = int(raw)
  except ValueError:
    return (None, None)
  bio_years = bio_ticks / TICKS_PER_YEAR
  # Chronological: birth absolute tick vs current tick. Sanguophages
  # etc. accumulate chronological age while biological stays low.
  chrono_years: float | None = None
  birth_raw = el.findtext("ageTracker/birthAbsTicks")
  if birth_raw:
    try:
      birth_ticks = int(birth_raw)
      # Note: current tick lives on the Save; we don't have it here.
      # Caller passes via PawnRecord later if needed. Leave None.
      _ = birth_ticks
    except ValueError:
      pass
  return (bio_years, chrono_years)


def _current_job(el: etree._Element) -> str | None:
  return (
    el.findtext("jobs/curJob/def")
    or el.findtext("mindState/lastJobTag")
  )


def _personality(el: etree._Element) -> str | None:
  """Pull the RimTalk Persona hediff text when present.

  RimTalk stores an LLM-generated personality summary as a custom
  Hediff_Persona on each pawn. The text is in the <Personality>
  element. When the mod isn't installed this returns None.
  """
  for li in el.iterfind("healthTracker/hediffSet/hediffs/li"):
    if "Persona" not in li.attrib.get("Class", ""):
      continue
    text = li.findtext("Personality")
    if text and text.strip():
      return text.strip()
  return None


def _gender(el: etree._Element) -> str | None:
  """RimWorld omits <gender> for Humans when value is Male (default).

  For non-Human pawns gender is always serialised. For Humans,
  absence means Male; we surface that explicitly because downstream
  prompts want it.
  """
  v = el.findtext("gender")
  if v:
    return v
  if el.findtext("def") == "Human":
    return "Male"
  return None


_BACKSTORY_CODE = re.compile(r"^[A-Z][A-Za-z]*\d+$")

# Matches RimWorld's inline rich-text tags: <color=#ARGBHEX>...</color>,
# <b>, <i>. Mirrors what RimTalk's StripFormattingTags filter removes.
_FORMAT_TAG = re.compile(r"</?(color(=#?[0-9A-Fa-f]+)?|b|i)>")


def _strip_tags(text: str | None) -> str | None:
  if not text:
    return None
  return _FORMAT_TAG.sub("", text)


def _readable_backstory(v: str | None) -> str | None:
  """Suppress raw backstory def-name codes (ColonyChild59, Colonist97).

  Without RimWorld's backstory DB these codes carry no signal; readable
  custom backstory titles ('Imperial spy', 'Slum kid') still pass.
  """
  if not v:
    return None
  if _BACKSTORY_CODE.match(v):
    return None
  return v


def _mood(el: etree._Element) -> str | None:
  level = el.findtext("needs/needs/li[def='Mood']/curLevel")
  if not level:
    return None
  try:
    v = float(level)
  except ValueError:
    return None
  if v < 0.25:
    return "broken / extremely low mood"
  if v < 0.4:
    return "miserable"
  if v < 0.55:
    return "stressed"
  if v < 0.7:
    return "content"
  return "happy"


def _skin_color(el: etree._Element) -> RGBA | None:
  raw = (
    el.findtext("story/skinColorOverride")
    or el.findtext("skinColorOverride")
  )
  return RGBA.parse(raw)


def _xenotype(el: etree._Element) -> str | None:
  return el.findtext("genes/xenotype")


def _race(el: etree._Element) -> str | None:
  return el.findtext("def")


def _favorite_color(el: etree._Element) -> str | None:
  return el.findtext("story/favoriteColorDef")


def _hair(el: etree._Element) -> tuple[str | None, RGBA | None]:
  return (
    el.findtext("story/hairDef"),
    RGBA.parse(el.findtext("story/hairColor")),
  )


def _enrich_hair_from_index(
  hair_def: str | None,
  def_index: dict[str, object] | None,
) -> tuple[str | None, str | None]:
  """Return (label, tex_path) for a hairDef using a mod-aware def index.

  Falls back to (None, None) when no index is provided or the def is
  unknown. The renderer already handles missing values gracefully.
  """
  if not hair_def or not def_index:
    return (None, None)
  rec = def_index.get(hair_def)
  if rec is None:
    return (None, None)
  label = getattr(rec, "label", None)
  tex_path = getattr(rec, "tex_path", None)
  return (label, tex_path)


def _beard(el: etree._Element) -> str | None:
  v = el.findtext("style/beardDef")
  if not v or v.lower() == "nobeard":
    return None
  return v


def _tattoo(el: etree._Element, kind: str) -> str | None:
  v = el.findtext(f"style/{kind}")
  if not v or v.lower().startswith("notattoo"):
    return None
  return v


def pawn_from_element(
  el: etree._Element,
  save: Save,
  def_index: dict[str, object] | None = None,
) -> PawnRecord:
  pid = el.findtext("id") or ""
  full, nick, label = _name(el)
  kind = el.findtext("kindDef")
  hair_def, hair_color = _hair(el)
  hair_label_idx, hair_tex_path_idx = _enrich_hair_from_index(
    hair_def, def_index
  )
  bio, chrono = _age(el)
  return PawnRecord(
    pawn_id=pid,
    name_full=full,
    nickname=nick,
    label=label or full,
    role=_role_from_kind(kind),
    gender=_gender(el),
    bio_age=bio,
    chrono_age=chrono,
    xenotype=_xenotype(el),
    race=_race(el),
    traits=_traits(el),
    backstory_child=_readable_backstory(el.findtext("story/childhood")),
    backstory_adult=_readable_backstory(el.findtext("story/adulthood")),
    personality=_personality(el),
    mood=_mood(el),
    current_job=_current_job(el),
    location=None,
    hair_def=hair_def,
    hair_label=hair_label_idx or hair_def,
    hair_texture_path=hair_tex_path_idx,
    hair_color=hair_color,
    beard_def=_beard(el),
    beard_label=_beard(el),
    face_tattoo=_tattoo(el, "faceTattoo"),
    body_tattoo=_tattoo(el, "bodyTattoo"),
    skin_color=_skin_color(el),
    favorite_color=_favorite_color(el),
    gradient_hair=_gradient_hair(el),
    genes=_genes(el),
    hediffs=_hediffs(el),
    apparel=_apparel(el),
    equipment=_equipment(el),
    ideo=_ideo(el, save),
    relations=_relations(el),
  )


# --- iteration helpers ------------------------------------------------

def iter_pawns(
  save: Save, def_index: dict[str, object] | None = None
) -> Iterator[PawnRecord]:
  for el in save.pawns_by_id.values():
    yield pawn_from_element(el, save, def_index)


def iter_by_role(
  save: Save, role: str, def_index: dict[str, object] | None = None
) -> Iterator[PawnRecord]:
  for p in iter_pawns(save, def_index):
    if p.role == role:
      yield p


def iter_colonists(
  save: Save, def_index: dict[str, object] | None = None
) -> Iterator[PawnRecord]:
  yield from iter_by_role(save, "colonist", def_index)


def find_pawn(
  save: Save, name: str, def_index: dict[str, object] | None = None
) -> PawnRecord | None:
  target = name.strip().lower()
  for p in iter_pawns(save, def_index):
    candidates = [
      (p.label or "").lower(),
      (p.nickname or "").lower(),
      (p.name_full or "").lower(),
    ]
    if target in candidates or any(target == c for c in candidates):
      return p
  return None


def family_members(
  save: Save,
  focus: PawnRecord,
  def_index: dict[str, object] | None = None,
) -> list[tuple[Relation, PawnRecord]]:
  """Return direct relations of focus as (Relation, PawnRecord) pairs.

  Filters to recognised family/bond relation defs per the user's spec
  (Spouse, Lover, Fiance, Parent, Child, Sibling, Bond, etc.).
  """
  family_defs = {
    "Spouse", "Fiance", "Lover", "ExSpouse", "ExLover",
    "Parent", "Child", "Sibling", "HalfSibling",
    "Grandparent", "Grandchild", "Cousin", "NephewOrNiece",
    "UncleOrAunt", "Bond",
  }
  out: list[tuple[Relation, PawnRecord]] = []
  for rel in focus.relations:
    if rel.def_name not in family_defs:
      continue
    el = save.pawns_by_id.get(_strip(rel.other_pawn_id))
    if el is None:
      continue
    out.append((rel, pawn_from_element(el, save, def_index)))
  return out


def _strip(ref: str) -> str:
  return ref[len("Thing_"):] if ref.startswith("Thing_") else ref


# --- map context ------------------------------------------------------

_WEATHER_LABELS: dict[str, str] = {
  "Clear": "clear",
  "Fog": "fog",
  "Rain": "rain",
  "FoggyRain": "foggy rain",
  "DryThunderstorm": "dry thunderstorm",
  "RainyThunderstorm": "rainy thunderstorm",
  "SnowGentle": "gentle snowfall",
  "SnowHard": "hard snowfall",
  "Flashstorm": "flashstorm",
  "ToxicFallout": "toxic fallout",
}


def _weather_label(def_name: str | None) -> str | None:
  if not def_name:
    return None
  if def_name in _WEATHER_LABELS:
    return _WEATHER_LABELS[def_name]
  # Fallback: split CamelCase, lowercase.
  acc: list[str] = []
  for i, ch in enumerate(def_name):
    if i > 0 and ch.isupper() and not def_name[i - 1].isupper():
      acc.append(" ")
    acc.append(ch.lower())
  return "".join(acc)


def _map_for_pawn(save: Save, pawn_el: etree._Element) -> etree._Element | None:
  map_id_raw = pawn_el.findtext("map")
  if not map_id_raw:
    return None
  for m in save.root.iterfind(".//maps/li"):
    if m.findtext("uniqueID") == map_id_raw:
      return m
  return None


def _colonist_count(save: Save) -> int:
  n = 0
  for p in iter_pawns(save):
    if p.role == "colonist":
      n += 1
  return n


def map_context_for(
  save: Save, pawn: PawnRecord, wealth_override: float | None = None
) -> MapContext | None:
  pawn_el = save.pawns_by_id.get(pawn.pawn_id)
  if pawn_el is None:
    return None
  map_el = _map_for_pawn(save, pawn_el)
  raw_weather = (
    map_el.findtext("weatherManager/curWeather")
    if map_el is not None else None
  )
  # Match RimTalk's `weather.label` (lowercase, human-readable). Save
  # serialises the def name (CamelCase); we convert.
  weather = _weather_label(raw_weather)
  threats: tuple[str, ...] = ()
  if map_el is not None:
    threat_defs: list[str] = []
    for cond in map_el.iterfind(
      "gameConditionManager/activeConditions/li"
    ):
      d = cond.findtext("def")
      if d:
        threat_defs.append(d)
    threats = tuple(threat_defs)
  return MapContext(
    biome=None,  # tile-biome decoding deferred
    weather=weather,
    wealth=wealth_override,
    population=_colonist_count(save),
    active_threats=threats,
  )
