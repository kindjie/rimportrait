"""Gene def -> visible-anatomy or attitude/bearing description.

Per spec: three buckets.
  VISIBLE_ANATOMY -> contributes a visible feature to the portrait.
  ATTITUDE_BEARING -> influences expression, posture, or mood.
  IGNORE -> internal mechanics; never surface in prompts.

Unknown genes default to IGNORE to avoid polluting prompts with raw
def names. Add to the tables as new xenotypes/mods appear in saves.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..records import Gene


VISIBLE_ANATOMY: dict[str, str | None] = {
  # Eye / face / mouth
  "Fangs": "visible fangs",
  "FangsThin": "visible thin fangs",
  "FangsLarge": "large visible fangs",
  "Eyes_Glowing": "faintly glowing eyes",
  "Eyes_Aggressive": "intense aggressive eyes",
  # Skin / fur
  "FurryBody": "shaggy full-body fur",
  "FurryBodyThin": "light body fur",
  "Skin_PaleGrayWhite": "pale grayish-white skin",
  "Skin_RedFire": "fire-touched reddish skin",
  "Skin_DarkGray": "dark gray skin",
  # Cranial / horns
  "Horns_Pointy": "pointed horns",
  "Horns_Curled": "curled horns",
  "Headbone_CenterHorn": "single central head horn",
  "Headbone_DoubleHorn": "twin head horns",
  # Limbs / appendages
  "Tail_Furry": "furry tail",
  "Tail_Smooth": "smooth tail",
  "Tail_Reptilian": "reptilian tail",
  "Ears_Pointed": "pointed ears",
  "Ears_Floppy": "floppy animal ears",
  "Ears_Cat": "cat-like ears",
  # Build
  "Body_Standard": None,  # baseline, no visible cue
  "Body_Hulk": "hulking heavy build",
  "Body_Thin": "thin wiry build",
  "Body_Fat": "heavy soft build",
}


ATTITUDE_BEARING: dict[str, str] = {
  "Ageless": "ageless presence with no signs of aging",
  "Beauty_VeryUgly": "rough harshly-featured face",
  "Beauty_Ugly": "plain rough-featured face",
  "Beauty_Pretty": "attractive features",
  "Beauty_Beautiful": "strikingly beautiful features",
  "AggressionH": "aggressive bearing, simmering hostility",
  "AggressionN": "guarded restrained demeanour",
  "Robust": "robust resilient build",
  "MoveSpeed_Quick": "quick alert stance",
  "MoveSpeed_VeryQuick": "lean fast-moving stance",
  "MeleeDamage_Strong": "strong heavy-shouldered build",
  "SocialAbility_VeryAble": "confident socially commanding presence",
  "DarkVision": "dilated low-light-adapted eyes",
}


def _is_visible(def_name: str) -> bool:
  return def_name in VISIBLE_ANATOMY


def _is_bearing(def_name: str) -> bool:
  return def_name in ATTITUDE_BEARING


def visible_features(genes: Iterable[Gene]) -> list[str]:
  out: list[str] = []
  for g in genes:
    if _is_visible(g.def_name):
      desc = VISIBLE_ANATOMY[g.def_name]
      if desc:
        out.append(desc)
  return out


def attitude_features(genes: Iterable[Gene]) -> list[str]:
  out: list[str] = []
  for g in genes:
    if _is_bearing(g.def_name):
      out.append(ATTITUDE_BEARING[g.def_name])
  return out


def describe_genes(genes: Iterable[Gene]) -> list[str]:
  """Combined visible-only output for the 'Visible genes/body traits' line."""
  return visible_features(genes) + attitude_features(genes)
