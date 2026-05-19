"""Load a .rws save and build lookup indexes.

Validated against RimWorld 1.5/1.6 saves with Biotech + Ideology + the
GradientHair mod. Selectors are derived from observed save structure
rather than community wiki text - both match here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree


PAWN_ID_PREFIXES = ("Thing_", "")


@dataclass
class Save:
  root: etree._Element
  pawns_by_id: dict[str, etree._Element] = field(default_factory=dict)
  ideos_by_id: dict[int, etree._Element] = field(default_factory=dict)
  factions_by_id: dict[str, etree._Element] = field(default_factory=dict)
  player_faction_id: str | None = None
  current_tick: int = 0


def _strip_thing_prefix(ref: str) -> str:
  for p in PAWN_ID_PREFIXES:
    if p and ref.startswith(p):
      return ref[len(p):]
  return ref


def _index_pawns(root: etree._Element) -> dict[str, etree._Element]:
  out: dict[str, etree._Element] = {}
  for thing in root.iter("thing"):
    if thing.attrib.get("Class") != "Pawn":
      continue
    pid = thing.findtext("id")
    if pid:
      out[pid] = thing
  return out


def _index_ideos(root: etree._Element) -> dict[int, etree._Element]:
  out: dict[int, etree._Element] = {}
  for li in root.iterfind(".//ideoManager/ideos/li"):
    raw = li.findtext("id")
    if raw is None:
      continue
    try:
      out[int(raw)] = li
    except ValueError:
      continue
  return out


def _index_factions(root: etree._Element) -> dict[str, etree._Element]:
  out: dict[str, etree._Element] = {}
  for f in root.iterfind(".//factionManager/allFactions/li"):
    fid = f.findtext("loadID")
    if fid:
      out[f"Faction_{fid}"] = f
  return out


def _player_faction_id(root: etree._Element) -> str | None:
  pf = root.findtext(".//scenario/playerFaction/factionDef")
  if pf:
    return None  # def, not a loadID
  for f in root.iterfind(".//factionManager/allFactions/li"):
    if f.findtext("isPlayer") == "True":
      fid = f.findtext("loadID")
      if fid:
        return f"Faction_{fid}"
  return None


def _current_tick(root: etree._Element) -> int:
  v = root.findtext(".//tickManager/ticksGame")
  try:
    return int(v) if v else 0
  except ValueError:
    return 0


def load_save(path: str | Path) -> Save:
  p = Path(path)
  parser = etree.XMLParser(recover=True, huge_tree=True)
  tree = etree.parse(str(p), parser)
  root = tree.getroot()
  return Save(
    root=root,
    pawns_by_id=_index_pawns(root),
    ideos_by_id=_index_ideos(root),
    factions_by_id=_index_factions(root),
    player_faction_id=_player_faction_id(root),
    current_tick=_current_tick(root),
  )


def resolve_pawn_ref(save: Save, ref: str) -> etree._Element | None:
  if not ref:
    return None
  return save.pawns_by_id.get(_strip_thing_prefix(ref))


def resolve_ideo_ref(save: Save, ref: str) -> etree._Element | None:
  if not ref or not ref.startswith("Ideo_"):
    return None
  try:
    n = int(ref[len("Ideo_"):])
  except ValueError:
    return None
  return save.ideos_by_id.get(n)
