"""Load a .rws save and build lookup indexes.

Validated against RimWorld 1.5/1.6 saves with Biotech + Ideology + the
GradientHair mod. Selectors are derived from observed save structure
rather than community wiki text - both match here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from .world import (
  MapData,
  decompress_grid_ushorts,
  hour_for_tick,
  parse_pos,
  parse_size,
  time_period_for_hour,
)


PAWN_ID_PREFIXES = ("Thing_", "")


@dataclass
class Save:
  root: etree._Element
  pawns_by_id: dict[str, etree._Element] = field(default_factory=dict)
  ideos_by_id: dict[int, etree._Element] = field(default_factory=dict)
  factions_by_id: dict[str, etree._Element] = field(default_factory=dict)
  player_faction_id: str | None = None
  current_tick: int = 0
  maps: list[MapData] = field(default_factory=list)
  map_elements: list[etree._Element] = field(default_factory=list)
  pawn_to_map: dict[str, int] = field(default_factory=dict)
  time_hour: int | None = None
  time_period: str | None = None
  _things_by_id: dict[str, str] | None = None

  def thing_def(self, ref: str) -> str | None:
    """Resolve a Thing_<id> reference to its <def> string.

    Lazy-builds a flat id->def index across every <thing> in the save
    on first call (covers Pawns, Buildings, Plants, Items). Used by
    fields like ``connections/connectedThings`` that reference
    non-pawn things by id.
    """
    if not ref:
      return None
    if self._things_by_id is None:
      idx: dict[str, str] = {}
      for el in self.root.iter("thing"):
        tid = el.findtext("id")
        d = el.findtext("def")
        if tid and d:
          idx[tid] = d
      self._things_by_id = idx
    if ref.startswith("Thing_"):
      ref = ref[len("Thing_"):]
    return self._things_by_id.get(ref)

  def pawn_outdoor(self, pawn_id: str | None) -> bool | None:
    """Return True if the pawn is at an unroofed cell, False if
    roofed, None if their position or map is unknown."""
    if not pawn_id or not self.maps:
      return None
    map_idx = self.pawn_to_map.get(pawn_id)
    if map_idx is None:
      return None
    pawn_el = self.pawns_by_id.get(pawn_id)
    if pawn_el is None:
      return None
    pos = parse_pos(pawn_el.findtext("pos"))
    if pos is None:
      return None
    return self.maps[map_idx].is_outdoor(*pos)


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


def _index_maps_and_pawns(
  root: etree._Element,
) -> tuple[list[MapData], list[etree._Element], dict[str, int]]:
  """Decode each map's roof grid + build a pawn_id -> map index.

  Pawns live inside their map's ``<things>`` container. We walk each
  map ``<li>`` (those with ``<mapInfo>``), decode its roof grid, and
  index every pawn under that map. The map element is returned in
  parallel so callers needing other map-scoped fields (weather,
  game-condition threats, etc.) don't need to redo the containment
  walk.
  """
  maps: list[MapData] = []
  map_elements: list[etree._Element] = []
  pawn_to_map: dict[str, int] = {}
  for map_el in root.iter("li"):
    info = map_el.find("mapInfo")
    if info is None:
      continue
    size = parse_size(info.findtext("size"))
    if size is None:
      continue
    size_x, size_z = size
    roof_b64 = None
    roof_el = map_el.find(".//roofGrid/roofsDeflate")
    if roof_el is not None and roof_el.text:
      roof_b64 = roof_el.text.strip()
    if not roof_b64:
      continue
    try:
      roof = decompress_grid_ushorts(roof_b64)
    except Exception:
      continue
    if len(roof) != size_x * size_z:
      continue
    idx = len(maps)
    maps.append(MapData(size_x=size_x, size_z=size_z, roof=roof))
    map_elements.append(map_el)
    for thing in map_el.iter("thing"):
      if thing.attrib.get("Class") != "Pawn":
        continue
      pid = thing.findtext("id")
      if pid:
        pawn_to_map[pid] = idx
  return maps, map_elements, pawn_to_map


def load_save(path: str | Path) -> Save:
  p = Path(path)
  parser = etree.XMLParser(recover=True, huge_tree=True)
  tree = etree.parse(str(p), parser)
  root = tree.getroot()
  tick = _current_tick(root)
  hour = hour_for_tick(tick) if tick else None
  period = time_period_for_hour(hour) if hour is not None else None
  maps, map_elements, pawn_to_map = _index_maps_and_pawns(root)
  return Save(
    root=root,
    pawns_by_id=_index_pawns(root),
    ideos_by_id=_index_ideos(root),
    factions_by_id=_index_factions(root),
    player_faction_id=_player_faction_id(root),
    current_tick=tick,
    maps=maps,
    map_elements=map_elements,
    pawn_to_map=pawn_to_map,
    time_hour=hour,
    time_period=period,
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
