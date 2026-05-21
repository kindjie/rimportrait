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
  classify_roof_def,
  decompress_grid_ushorts,
  hour_for_tick,
  is_bridge_def,
  is_substructure_def,
  parse_pos,
  parse_size,
  resolve_short_hash,
  stable_string_hash,
  time_period_for_hour,
)


def read_save_game_version(path: Path) -> str | None:
  """Return the save's ``<meta><gameVersion>`` without a full parse.

  Uses iterparse + early termination so listing dozens of saves in a
  GUI stays cheap (the dropdown reads this for every .rws on
  startup; a full lxml tree per save would block the window for
  seconds on large colonies)."""
  try:
    ctx = etree.iterparse(
      str(path), events=("end",),
      huge_tree=True, recover=True,
    )
  except (OSError, etree.XMLSyntaxError):
    return None
  try:
    for _, elem in ctx:
      if elem.tag == "gameVersion":
        return (elem.text or "").strip() or None
      # gameVersion is the first child of <meta>; bail at </meta>
      # so we don't walk the whole save when it's missing.
      if elem.tag == "meta":
        return None
  except etree.XMLSyntaxError:
    return None
  finally:
    del ctx
  return None


# WorldObject def -> coarse human label for the colony's setting.
_MAP_KIND_LABELS: dict[str, str] = {
  "Settlement": "terrestrial settlement",
  "SpaceSettlement": "space settlement (orbital)",
  "AsteroidBasic": "asteroid base",
  "AsteroidMiningSite": "asteroid mining site",
  "EscapeShip": "escape ship in transit",
  "GravshipLaunch": "gravship in launch",
}


@dataclass(frozen=True)
class CaravanInfo:
  """Minimal record of a pawn's caravan membership.

  tile is the world tile the caravan currently occupies; pawn count
  is just informational.
  """
  caravan_id: str
  tile: int | None
  pawn_count: int


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
  map_kinds: list[str | None] = field(default_factory=list)
  # World tile id of each map's parent WorldObject. Used to look up
  # the biome via tile_to_biome (which is sourced from past tales -
  # there is no in-save current-biome field per map).
  map_tiles: list[int | None] = field(default_factory=list)
  tile_to_biome: dict[int, str] = field(default_factory=dict)
  pawn_to_map: dict[str, int] = field(default_factory=dict)
  pawn_to_caravan: dict[str, CaravanInfo] = field(default_factory=dict)
  # Resolved {shortHash: defName} populated when a mod-aware def
  # index is built via setting_detection().
  roof_short_to_def: dict[int, str] = field(default_factory=dict)
  terrain_short_to_def: dict[int, str] = field(default_factory=dict)
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

  def biome_for_pawn(self, pawn_id: str | None) -> str | None:
    """BiomeDef name of the pawn's map's parent world tile, sourced
    from past tales surroundings. Returns None when the pawn is not
    on a map or no tale has recorded a biome for that tile."""
    if not pawn_id:
      return None
    idx = self.pawn_to_map.get(pawn_id)
    if idx is None or idx >= len(self.map_tiles):
      return None
    tile = self.map_tiles[idx]
    if tile is None:
      return None
    return self.tile_to_biome.get(tile)

  def map_kind_for_pawn(self, pawn_id: str | None) -> str | None:
    """Coarse setting label derived from the pawn's map's parent
    WorldObject def. None if the pawn is not on any map."""
    if not pawn_id:
      return None
    idx = self.pawn_to_map.get(pawn_id)
    if idx is None or idx >= len(self.map_kinds):
      return None
    return self.map_kinds[idx]

  def roof_kind_for_pawn(self, pawn_id: str | None) -> str | None:
    """Readable roof label for the pawn's tile (None when outdoors
    or when the pawn's position is unknown)."""
    if not pawn_id:
      return None
    map_idx = self.pawn_to_map.get(pawn_id)
    pawn_el = self.pawns_by_id.get(pawn_id)
    if map_idx is None or pawn_el is None:
      return None
    pos = parse_pos(pawn_el.findtext("pos"))
    if pos is None:
      return None
    short = self.maps[map_idx].roof_at(*pos)
    if short == 0:
      return None
    def_name = resolve_short_hash(short, self.roof_short_to_def)
    return classify_roof_def(def_name)

  def terrain_kind_for_pawn(
    self, pawn_id: str | None
  ) -> str | None:
    """Returns 'substructure' if the pawn is on a gravship
    foundation, 'bridge' if on a bridge, else None. Used as an
    override on top of the roof/map composition.
    """
    if not pawn_id:
      return None
    map_idx = self.pawn_to_map.get(pawn_id)
    pawn_el = self.pawns_by_id.get(pawn_id)
    if map_idx is None or pawn_el is None:
      return None
    pos = parse_pos(pawn_el.findtext("pos"))
    if pos is None:
      return None
    short = self.maps[map_idx].terrain_at(*pos)
    if short == 0:
      return None
    def_name = resolve_short_hash(short, self.terrain_short_to_def)
    if is_substructure_def(def_name):
      return "substructure"
    if is_bridge_def(def_name):
      return "bridge"
    return None

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


def _decompress_optional(b64: str | None) -> tuple[int, ...]:
  if not b64:
    return ()
  try:
    return decompress_grid_ushorts(b64.strip())
  except Exception:
    return ()


def _world_object_index(
  root: etree._Element,
) -> dict[str, tuple[str, int | None]]:
  """Map WorldObject ID -> (def, tile). The id field is ``<ID>``
  (not the ``<loadID>`` we use elsewhere); map ``mapInfo/parent``
  references resolve through this index. ``tile`` is the world tile
  the WorldObject sits on (None if missing or unparseable)."""
  out: dict[str, tuple[str, int | None]] = {}
  for container in root.iter("worldObjects"):
    parent = container.getparent()
    if parent is None or parent.tag != "worldObjects":
      continue
    for li in container.iterfind("li"):
      wid = li.findtext("ID") or li.findtext("loadID")
      d = li.findtext("def")
      if not (wid and d):
        continue
      tile_raw = li.findtext("tile") or ""
      tile: int | None = None
      try:
        tile = int(tile_raw.split(",")[0])
      except (ValueError, IndexError):
        pass
      out[wid] = (d, tile)
  return out


def _index_biome_by_tile(root: etree._Element) -> dict[int, str]:
  """Build {world_tile_id: BiomeDef name} from past tales.

  The save's <tales> section records the surroundings of past
  events. Each ``<surroundings>`` element carries a ``<tile>`` and a
  ``<biome>`` def name. Biome does not change for a tile, so the
  first reading per tile is authoritative; we still take the most
  common as a defensive measure against any stale entries.
  """
  counts: dict[int, dict[str, int]] = {}
  for surr in root.iter("surroundings"):
    tile_raw = surr.findtext("tile") or ""
    biome = (surr.findtext("biome") or "").strip()
    if not biome:
      continue
    try:
      tile = int(tile_raw.split(",")[0])
    except (ValueError, IndexError):
      continue
    bucket = counts.setdefault(tile, {})
    bucket[biome] = bucket.get(biome, 0) + 1
  return {
    tile: max(b.items(), key=lambda kv: kv[1])[0]
    for tile, b in counts.items()
  }


def _index_maps_and_pawns(
  root: etree._Element,
) -> tuple[
  list[MapData],
  list[etree._Element],
  list[str | None],
  list[int | None],
  dict[str, int],
]:
  """Decode each map's roof + terrain grids + map-kind labels +
  parent tile + a pawn_id -> map index.
  """
  wo_index = _world_object_index(root)
  maps: list[MapData] = []
  map_elements: list[etree._Element] = []
  map_kinds: list[str | None] = []
  map_tiles: list[int | None] = []
  pawn_to_map: dict[str, int] = {}
  for map_el in root.iter("li"):
    info = map_el.find("mapInfo")
    if info is None:
      continue
    size = parse_size(info.findtext("size"))
    if size is None:
      continue
    size_x, size_z = size
    roof_el = map_el.find(".//roofGrid/roofsDeflate")
    roof_b64 = (
      roof_el.text.strip()
      if roof_el is not None and roof_el.text else None
    )
    if not roof_b64:
      continue
    roof = _decompress_optional(roof_b64)
    if len(roof) != size_x * size_z:
      continue
    terrain_el = map_el.find(".//terrainGrid/topGridDeflate")
    terrain_b64 = (
      terrain_el.text.strip()
      if terrain_el is not None and terrain_el.text else None
    )
    terrain = _decompress_optional(terrain_b64)
    if len(terrain) != size_x * size_z:
      terrain = ()  # silently drop on size mismatch
    parent_ref = info.findtext("parent") or ""
    parent_id = parent_ref.removeprefix("WorldObject_")
    wo = wo_index.get(parent_id)
    parent_def: str | None = wo[0] if wo else None
    parent_tile: int | None = wo[1] if wo else None
    map_kind = (
      _MAP_KIND_LABELS.get(parent_def or "")
      or (f"unknown setting ({parent_def})" if parent_def else None)
    )
    idx = len(maps)
    maps.append(MapData(
      size_x=size_x, size_z=size_z, roof=roof, terrain=terrain,
    ))
    map_elements.append(map_el)
    map_kinds.append(map_kind)
    map_tiles.append(parent_tile)
    for thing in map_el.iter("thing"):
      if thing.attrib.get("Class") != "Pawn":
        continue
      pid = thing.findtext("id")
      if pid:
        pawn_to_map[pid] = idx
  return maps, map_elements, map_kinds, map_tiles, pawn_to_map


def _index_caravans(root: etree._Element) -> dict[str, CaravanInfo]:
  """Map pawn_id -> CaravanInfo for any pawn currently in a caravan
  (and therefore not on any map)."""
  out: dict[str, CaravanInfo] = {}
  for container in root.iter("worldObjects"):
    for li in container.iter("li"):
      if (li.findtext("def") or "") != "Caravan":
        continue
      lid = li.findtext("loadID") or ""
      tile_raw = li.findtext("tile") or ""
      tile: int | None = None
      try:
        tile = int(tile_raw.split(",")[0])
      except (ValueError, IndexError):
        pass
      pawn_refs: list[str] = []
      for pref in li.iterfind(".//pawns//li"):
        # Caravan pawn refs are 'Thing_HumanXYZ' or similar; strip
        # the 'Thing_' prefix where present.
        text = (pref.text or "").strip()
        if not text:
          continue
        if text.startswith("Thing_"):
          text = text[len("Thing_"):]
        pawn_refs.append(text)
      info = CaravanInfo(
        caravan_id=lid, tile=tile, pawn_count=len(pawn_refs),
      )
      for pid in pawn_refs:
        out[pid] = info
  return out


def load_save(path: str | Path) -> Save:
  p = Path(path)
  parser = etree.XMLParser(recover=True, huge_tree=True)
  tree = etree.parse(str(p), parser)
  root = tree.getroot()
  tick = _current_tick(root)
  hour = hour_for_tick(tick) if tick else None
  period = time_period_for_hour(hour) if hour is not None else None
  maps, map_elements, map_kinds, map_tiles, pawn_to_map = \
    _index_maps_and_pawns(root)
  pawn_to_caravan = _index_caravans(root)
  tile_to_biome = _index_biome_by_tile(root)
  return Save(
    root=root,
    pawns_by_id=_index_pawns(root),
    ideos_by_id=_index_ideos(root),
    factions_by_id=_index_factions(root),
    player_faction_id=_player_faction_id(root),
    current_tick=tick,
    maps=maps,
    map_elements=map_elements,
    map_kinds=map_kinds,
    map_tiles=map_tiles,
    pawn_to_map=pawn_to_map,
    pawn_to_caravan=pawn_to_caravan,
    tile_to_biome=tile_to_biome,
    time_hour=hour,
    time_period=period,
  )


def register_def_short_hashes(
  save: Save, def_index: dict[str, object] | None
) -> None:
  """Populate Save's roof / terrain shortHash -> defName lookups
  from a mod-aware def index. Call this after
  ``build_def_index_from_save`` if you want roof_kind / terrain_kind
  resolution on PawnRecord. Idempotent.
  """
  if not def_index:
    return
  roof: dict[int, str] = {}
  terrain: dict[int, str] = {}
  for def_name, rec in def_index.items():
    # rec is a DefRecord; def_type tells us which table to fill.
    def_type = getattr(rec, "def_type", None)
    h = stable_string_hash(def_name)
    if def_type == "RoofDef":
      roof[h] = def_name
    elif def_type == "TerrainDef":
      terrain[h] = def_name
  save.roof_short_to_def = roof
  save.terrain_short_to_def = terrain


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
