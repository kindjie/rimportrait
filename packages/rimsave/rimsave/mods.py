"""Mod discovery and def extraction across base game + DLC + Workshop + local mods.

The active mod set + load order comes from the save itself
(`<meta><modIds>+<modSteamIds>+<modNames>`), so no `.rml` argument is
needed. Each mod's `Defs/` is walked - honouring versioned folders
(1.6/Defs over root Defs) and ParentName/Abstract XML inheritance -
and merged in load order so later mods override earlier ones, matching
RimWorld's runtime semantics.

Covered def types: ThingDef (apparel + weapons), HairDef, BeardDef,
GeneDef, HediffDef, XenotypeDef. Bones for adding more are
straightforward - extend `_INTERESTING_DEF_TYPES`.

Auto-detects the macOS Steam install. Pass `--workshop-dir` /
`--mods-dir` / `--rimworld-dir` to override for other platforms or
non-default layouts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from .load import Save


# ThingDef covers apparel + weapons + many other props. We surface the
# whole pool and let callers query by defName - filtering on type is
# expensive on big mod loadouts and not needed for portrait rendering.
_INTERESTING_DEF_TYPES = (
  "ThingDef",
  "HairDef",
  "BeardDef",
  "GeneDef",
  "HediffDef",
  "XenotypeDef",
  "BodyPartDef",
  "RoyalTitleDef",
  "InspirationDef",
  "AbilityDef",
  "TattooDef",
  # Anomaly creepjoiner def families (note the inconsistent
  # capitalisation in CreepjoinerRejectionDef vs the others — that's
  # the actual tag name in RimWorld's Anomaly Defs).
  "CreepJoinerFormKindDef",
  "CreepJoinerBenefitDef",
  "CreepJoinerDownsideDef",
  "CreepjoinerRejectionDef",
  "CreepJoinerAggressiveDef",
  # Setting-detection defs (per-cell map data resolves through these).
  "RoofDef",
  "TerrainDef",
)


_OFFICIAL_DLCS: dict[str, str] = {
  "ludeon.rimworld": "Core",
  "ludeon.rimworld.royalty": "Royalty",
  "ludeon.rimworld.ideology": "Ideology",
  "ludeon.rimworld.biotech": "Biotech",
  "ludeon.rimworld.anomaly": "Anomaly",
  "ludeon.rimworld.odyssey": "Odyssey",
}


_VERSION_DIR = re.compile(r"^\d+\.\d+$")

# RimTalk's StripFormattingTags equivalent.
_FORMAT_TAG = re.compile(r"</?(color(=#?[0-9A-Fa-f]+)?|b|i)>")


def _strip_tags(text: str | None) -> str | None:
  if not text:
    return None
  text = text.replace("\\n", "\n").replace("\\t", "\t")
  return _FORMAT_TAG.sub("", text).strip() or None


# --- mod list from save ----------------------------------------------

@dataclass(frozen=True)
class ModEntry:
  package_id: str
  steam_id: str  # "0" for non-Workshop (Core/DLC/local)
  name: str
  order: int


def iter_mods_from_save(save: Save) -> list[ModEntry]:
  # save.root is the <savegame> element; meta is its direct child.
  meta = save.root.find("meta")
  if meta is None:
    meta = save.root.find(".//meta")
  if meta is None:
    return []
  ids = [li.text or "" for li in meta.iterfind("modIds/li")]
  steams = [li.text or "" for li in meta.iterfind("modSteamIds/li")]
  names = [li.text or "" for li in meta.iterfind("modNames/li")]
  out: list[ModEntry] = []
  for i, pid in enumerate(ids):
    out.append(ModEntry(
      package_id=pid.lower(),
      steam_id=steams[i] if i < len(steams) else "0",
      name=names[i] if i < len(names) else pid,
      order=i,
    ))
  return out


# --- path autodetect -------------------------------------------------

@dataclass(frozen=True)
class ModPaths:
  rimworld_data: Path | None
  workshop_dir: Path | None
  mods_dir: Path | None


_RIMWORLD_APPID = "294100"
_VDF_PATH_RE = re.compile(r'"path"\s*"([^"]+)"')


def _candidate_steam_roots() -> list[Path]:
  """Per-platform default Steam install roots.

  macOS, native Linux, SteamOS / Steam Deck (internal + SD card),
  Windows on C:/D:/E:. Non-existent paths are filtered out, so the
  same function works on every platform without branching.
  """
  home = Path.home()
  roots: list[Path] = [
    home / "Library/Application Support/Steam",          # macOS
    home / ".steam/steam",                                # Linux symlink
    home / ".local/share/Steam",                          # Linux real
    home / ".var/app/com.valvesoftware.Steam"             # Flatpak Steam
         / "data/Steam",
  ]
  # Steam Deck SD card libraries: /run/media/deck/<volume>/
  for media_parent in (Path("/run/media/deck"), Path("/run/media")):
    if media_parent.is_dir():
      for child in media_parent.iterdir():
        if (child / "steamapps").is_dir():
          roots.append(child)
  # Windows default drives. On non-Windows these just don't exist.
  for drive in ("C:", "D:", "E:"):
    roots.append(Path(f"{drive}/Program Files (x86)/Steam"))
    roots.append(Path(f"{drive}/SteamLibrary"))
  seen: set[Path] = set()
  out: list[Path] = []
  for r in roots:
    if r in seen:
      continue
    seen.add(r)
    if r.exists():
      out.append(r)
  return out


def _parse_library_folders(vdf_path: Path) -> list[Path]:
  """Extract extra library paths from a Steam libraryfolders.vdf.

  VDF stores Windows paths as ``"C:\\\\Path"``; we unescape the
  double-backslash so the resulting Path matches on disk.
  """
  if not vdf_path.is_file():
    return []
  try:
    text = vdf_path.read_text(encoding="utf-8", errors="ignore")
  except OSError:
    return []
  out: list[Path] = []
  for m in _VDF_PATH_RE.finditer(text):
    raw = m.group(1).replace("\\\\", "\\")
    p = Path(raw)
    if p.is_dir():
      out.append(p)
  return out


def _probe_rimworld_paths(steam_root: Path) -> ModPaths | None:
  """Given a Steam root, return ModPaths if RimWorld lives there.

  Tries both layouts: macOS (Data inside ``RimWorldMac.app``) and
  Linux/Windows (Data is a sibling of the game binary).
  """
  rimworld = steam_root / "steamapps/common/RimWorld"
  if not rimworld.is_dir():
    return None
  data_path: Path | None = None
  for candidate in (
    rimworld / "RimWorldMac.app/Data",  # macOS
    rimworld / "Data",                  # Linux / Windows
  ):
    if (candidate / "Core").is_dir():
      data_path = candidate
      break
  if data_path is None:
    return None
  mods_path: Path | None = None
  for candidate in (
    rimworld / "RimWorldMac.app/Mods",
    rimworld / "Mods",
  ):
    if candidate.is_dir():
      mods_path = candidate
      break
  workshop = steam_root / f"steamapps/workshop/content/{_RIMWORLD_APPID}"
  return ModPaths(
    rimworld_data=data_path,
    workshop_dir=workshop if workshop.is_dir() else None,
    mods_dir=mods_path,
  )


def autodetect_mod_paths() -> ModPaths:
  """Find the first Steam install on this machine that contains RimWorld.

  Probes platform-default Steam roots, then any additional library
  folders advertised in each root's libraryfolders.vdf. Returns
  ``ModPaths(None, None, None)`` if RimWorld isn't found anywhere.
  """
  roots = list(_candidate_steam_roots())
  for r in list(roots):
    for vdf in (
      r / "config/libraryfolders.vdf",
      r / "steamapps/libraryfolders.vdf",
    ):
      for extra in _parse_library_folders(vdf):
        if extra not in roots:
          roots.append(extra)
  for r in roots:
    paths = _probe_rimworld_paths(r)
    if paths is not None:
      return paths
  return ModPaths(rimworld_data=None, workshop_dir=None, mods_dir=None)


# --- mod folder resolution -------------------------------------------

def _read_about_package_id(mod_root: Path) -> str | None:
  about = mod_root / "About" / "About.xml"
  if not about.is_file():
    return None
  try:
    tree = etree.parse(
      str(about), etree.XMLParser(recover=True)
    )
  except etree.XMLSyntaxError:
    return None
  for tag in ("packageId", "PackageId"):
    el = tree.find(f".//{tag}")
    if el is not None and el.text:
      return el.text.strip().lower()
  return None


def _build_package_id_index(*dirs: Path | None) -> dict[str, Path]:
  """Scan each dir for child folders containing About/About.xml.

  Returns {packageId(lower): mod_root}. RimWorld's save sometimes
  stores Workshop mods with steamId='0', so we must also be able to
  resolve them by their About.xml package ID. Workshop dirs and local
  Mods dirs use the same About.xml format, so the same scanner works.
  """
  out: dict[str, Path] = {}
  for d in dirs:
    if d is None or not d.is_dir():
      continue
    for child in d.iterdir():
      if not child.is_dir():
        continue
      pid = _read_about_package_id(child)
      if pid and pid not in out:
        out[pid] = child
  return out


def resolve_mod_roots(
  mods: list[ModEntry], paths: ModPaths
) -> list[tuple[ModEntry, Path | None]]:
  """For each mod entry, return the root folder if found, else None.

  Lookup order:
    1. Official DLC under RimWorldMac.app/Data/
    2. Workshop folder by Steam ID
    3. Any folder under Workshop or local Mods whose About.xml
       packageId matches (covers Workshop mods where the save records
       steamId='0').
  """
  package_index = _build_package_id_index(
    paths.workshop_dir, paths.mods_dir
  )
  out: list[tuple[ModEntry, Path | None]] = []
  for m in mods:
    root: Path | None = None
    if m.package_id in _OFFICIAL_DLCS and paths.rimworld_data is not None:
      candidate = paths.rimworld_data / _OFFICIAL_DLCS[m.package_id]
      if candidate.is_dir():
        root = candidate
    if root is None and m.steam_id and m.steam_id != "0" \
        and paths.workshop_dir is not None:
      candidate = paths.workshop_dir / m.steam_id
      if candidate.is_dir():
        root = candidate
    if root is None and m.package_id in package_index:
      root = package_index[m.package_id]
    out.append((m, root))
  return out


# --- versioned folder + xml iteration --------------------------------

def _iter_def_files(
  mod_root: Path, active_version: str = "1.6"
) -> list[Path]:
  """Return Defs/*.xml from root + active version, skipping older versions.

  Folder layouts handled:
    <root>/Defs/...
    <root>/<ver>/Defs/...
  Other version dirs (1.0, 1.5, etc.) are skipped to avoid duplicate
  defs from historical compatibility shims.
  """
  files: list[Path] = []
  for sub in ("Defs",):
    p = mod_root / sub
    if p.is_dir():
      files.extend(p.rglob("*.xml"))
  for child in mod_root.iterdir() if mod_root.is_dir() else ():
    if not child.is_dir():
      continue
    if not _VERSION_DIR.match(child.name):
      continue
    if child.name != active_version:
      continue
    for sub in ("Defs",):
      p = child / sub
      if p.is_dir():
        files.extend(p.rglob("*.xml"))
  return files


# --- raw def parsing + inheritance -----------------------------------

@dataclass(frozen=True)
class DefRecord:
  def_name: str
  def_type: str
  label: str | None
  description: str | None
  tex_path: str | None
  source: str  # package_id
  max_health: int | None = None
  category: str | None = None
  # Fixed material ingredients from <costList> in the def XML. For
  # apparel with <stuffCategories> instead, this is empty - the
  # runtime stuff descriptor on the ApparelItem already says what
  # material was used. costList is the "no stuff slot" path:
  # prestige cataphract uses Plasteel+Gold, royal regalia uses
  # Cloth+Gold, etc. Tuple is (def_name, ...) preserving XML order.
  cost_list: tuple[str, ...] = ()
  # RimWorld's <techLevel> tag, lowercased. One of:
  # animal / neolithic / medieval / industrial / spacer / ultra /
  # archotech. ParentName-inherited (most spacer apparel inherits from
  # ArmorMachineable / ApparelMakeableBase which set techLevel=Spacer).
  tech_level: str | None = None
  # Apparel <layers> entries (e.g. ("Middle", "Shell")) - preserves
  # the order written in XML. Empty for non-apparel defs. Used by the
  # render layer to order worn items outer-to-inner and to surface
  # the silhouette layer (Shell / Middle / OnSkin / Belt / Overhead /
  # EyeCover).
  apparel_layers: tuple[str, ...] = ()


@dataclass
class _RawDef:
  def_type: str
  name_attr: str | None  # abstract template name
  parent_name: str | None
  abstract: bool
  def_name: str
  label: str | None
  description: str | None
  tex_path: str | None
  source: str
  max_health: int | None = None
  category: str | None = None
  cost_list: tuple[str, ...] = ()
  tech_level: str | None = None
  apparel_layers: tuple[str, ...] = ()


def _parse_raw_defs(mod_root: Path, source: str) -> list[_RawDef]:
  out: list[_RawDef] = []
  parser = etree.XMLParser(recover=True, huge_tree=True)
  for path in _iter_def_files(mod_root):
    try:
      tree = etree.parse(str(path), parser)
    except etree.XMLSyntaxError:
      continue
    root = tree.getroot()
    if root is None:
      continue
    for el in root.iter():
      if el.tag not in _INTERESTING_DEF_TYPES:
        continue
      name_attr = el.attrib.get("Name") or el.attrib.get("name")
      parent = el.attrib.get("ParentName") or el.attrib.get("parentName")
      abstract = (el.attrib.get("Abstract")
                  or el.attrib.get("abstract") or "").lower() == "true"
      def_name = (el.findtext("defName") or "").strip()
      label = el.findtext("label")
      description = el.findtext("description")
      tex_path = (
        el.findtext("texPath")
        or el.findtext("graphicData/texPath")
      )
      max_health_raw = el.findtext("statBases/MaxHitPoints")
      max_health: int | None = None
      if max_health_raw:
        try:
          max_health = int(float(max_health_raw.strip()))
        except ValueError:
          max_health = None
      category_raw = el.findtext("category")
      category = category_raw.strip() if category_raw else None
      tech_raw = el.findtext("techLevel")
      tech_level = tech_raw.strip().lower() if tech_raw else None
      apparel_layers: tuple[str, ...] = ()
      layers_el = el.find("apparel/layers")
      if layers_el is not None:
        layers_acc: list[str] = []
        for li in layers_el:
          if not isinstance(li.tag, str):
            continue
          if (li.text or "").strip():
            layers_acc.append(li.text.strip())
        apparel_layers = tuple(layers_acc)
      cost_el = el.find("costList")
      cost_list: tuple[str, ...] = ()
      if cost_el is not None:
        # Capture each (material_def, amount) so callers can sort
        # bulk-first (75 plasteel + 9 gold reads as "plasteel with
        # gold accents", not the XML order "gold + plasteel").
        # Filter out lxml comment / PI nodes whose .tag is callable.
        entries: list[tuple[str, int]] = []
        for c in cost_el:
          if not isinstance(c.tag, str):
            continue
          amount = 0
          try:
            amount = int(float((c.text or "0").strip()))
          except ValueError:
            pass
          entries.append((c.tag, amount))
        # Sort by amount descending (stable; preserves XML order on
        # ties). Plasteel (75) lands before Gold (9).
        entries.sort(key=lambda kv: -kv[1])
        cost_list = tuple(name for name, _ in entries)
      out.append(_RawDef(
        def_type=el.tag,
        name_attr=name_attr.strip() if name_attr else None,
        parent_name=parent.strip() if parent else None,
        abstract=abstract,
        def_name=def_name,
        label=label.strip() if label else None,
        description=_strip_tags(description),
        tex_path=tex_path.strip() if tex_path else None,
        source=source,
        max_health=max_health,
        category=category,
        cost_list=cost_list,
        tech_level=tech_level,
        apparel_layers=apparel_layers,
      ))
  return out


def _resolve_inheritance(raws: list[_RawDef]) -> list[DefRecord]:
  """Resolve ParentName chains; emit concrete (non-abstract) defs."""
  by_name: dict[str, _RawDef] = {
    r.name_attr: r for r in raws if r.name_attr
  }

  def inherit(r: _RawDef, attr: str, seen: set[str] | None = None) -> str | None:
    val = getattr(r, attr)
    if val:
      return val
    if r.parent_name is None:
      return None
    seen = seen or set()
    if r.parent_name in seen:
      return None
    seen.add(r.parent_name)
    parent = by_name.get(r.parent_name)
    if parent is None:
      return None
    return inherit(parent, attr, seen)

  def inherit_int(
    r: _RawDef, attr: str, seen: set[str] | None = None
  ) -> int | None:
    val = getattr(r, attr)
    if val is not None:
      return val
    if r.parent_name is None:
      return None
    seen = seen or set()
    if r.parent_name in seen:
      return None
    seen.add(r.parent_name)
    parent = by_name.get(r.parent_name)
    if parent is None:
      return None
    return inherit_int(parent, attr, seen)

  def inherit_tuple(
    r: _RawDef, attr: str, seen: set[str] | None = None
  ) -> tuple[str, ...]:
    val = getattr(r, attr)
    if val:
      return val
    if r.parent_name is None:
      return ()
    seen = seen or set()
    if r.parent_name in seen:
      return ()
    seen.add(r.parent_name)
    parent = by_name.get(r.parent_name)
    if parent is None:
      return ()
    return inherit_tuple(parent, attr, seen)

  out: list[DefRecord] = []
  for r in raws:
    if r.abstract or not r.def_name:
      continue
    out.append(DefRecord(
      def_name=r.def_name,
      def_type=r.def_type,
      label=inherit(r, "label"),
      description=inherit(r, "description"),
      tex_path=inherit(r, "tex_path"),
      source=r.source,
      max_health=inherit_int(r, "max_health"),
      category=inherit(r, "category"),
      cost_list=inherit_tuple(r, "cost_list"),
      tech_level=inherit(r, "tech_level"),
      apparel_layers=inherit_tuple(r, "apparel_layers"),
    ))
  return out


# --- public entry point ----------------------------------------------

def build_def_index_from_save(
  save: Save, paths: ModPaths | None = None
) -> dict[str, DefRecord]:
  """Walk the save's mod list and return {defName: DefRecord} in load order.

  Last-wins per RimWorld semantics: a mod loaded later overrides
  earlier mods' defs with the same defName.
  """
  if paths is None:
    paths = autodetect_mod_paths()
  resolved = resolve_mod_roots(iter_mods_from_save(save), paths)
  index: dict[str, DefRecord] = {}
  for mod, root in resolved:
    if root is None:
      continue
    raws = _parse_raw_defs(root, mod.package_id)
    for rec in _resolve_inheritance(raws):
      index[rec.def_name] = rec  # last-wins
  return index


# --- shim adapters for the existing render-layer interface -----------

def index_to_descriptions(
  index: dict[str, DefRecord],
) -> dict[str, str]:
  return {k: v.description for k, v in index.items() if v.description}


def index_to_labels(
  index: dict[str, DefRecord],
) -> dict[str, str]:
  return {k: v.label for k, v in index.items() if v.label}


def index_to_texpaths(
  index: dict[str, DefRecord],
) -> dict[str, str]:
  return {k: v.tex_path for k, v in index.items() if v.tex_path}


def index_to_categories(
  index: dict[str, DefRecord],
) -> dict[str, str]:
  return {k: v.category for k, v in index.items() if v.category}


def _humanise_material(name: str, labels: dict[str, str]) -> str:
  """Material def name -> readable noun. Uses the mod-aware label if
  one exists ('Plasteel' -> 'plasteel'), else lowercases CamelCase
  ('ComponentIndustrial' -> 'component industrial')."""
  if name in labels and labels[name]:
    return labels[name].lower()
  acc: list[str] = []
  for i, ch in enumerate(name):
    if i > 0 and ch.isupper() and not name[i - 1].isupper():
      acc.append(" ")
    acc.append(ch.lower())
  return "".join(acc) or name


# RimWorld apparel layers ordered outer -> inner for rendering. Items
# higher in this list visually sit on top. Belt and the head/eye
# layers are separate visual channels but their relative ordering
# against torso layers doesn't matter for outer-to-inner sorting; we
# place them above Shell so accessories like utility belts and
# helmets are listed before the torso shell.
_LAYER_OUTER_TO_INNER: tuple[str, ...] = (
  "Overhead",
  "EyeCover",
  "Belt",
  "Shell",
  "Middle",
  "OnSkin",
)


def outermost_layer(layers: tuple[str, ...]) -> str | None:
  """Pick the visually outermost layer from an apparel def's layer
  list. Unknown layer names (mods can define their own) sort to the
  inside, last."""
  if not layers:
    return None
  ranks = {name: i for i, name in enumerate(_LAYER_OUTER_TO_INNER)}
  unknown_rank = len(_LAYER_OUTER_TO_INNER)
  return min(layers, key=lambda L: ranks.get(L, unknown_rank))


def layer_rank(layer: str | None) -> int:
  """Rank for sorting; lower = outer. None / unknown sort last."""
  if layer is None:
    return len(_LAYER_OUTER_TO_INNER) + 1
  ranks = {name: i for i, name in enumerate(_LAYER_OUTER_TO_INNER)}
  return ranks.get(layer, len(_LAYER_OUTER_TO_INNER))


def index_to_apparel_layers(
  index: dict[str, DefRecord],
) -> dict[str, str]:
  """Return {def_name: outermost_layer} for any def whose XML carried
  an <apparel><layers> entry. Used by the render layer to surface the
  silhouette layer on each worn item and sort the apparel line
  outer-to-inner."""
  out: dict[str, str] = {}
  for def_name, rec in index.items():
    layer = outermost_layer(rec.apparel_layers)
    if layer is not None:
      out[def_name] = layer
  return out


def index_to_tech_levels(
  index: dict[str, DefRecord],
) -> dict[str, str]:
  """Return {def_name: tech_level} for every def carrying a techLevel.

  Values are lower-cased: ``neolithic``, ``medieval``, ``industrial``,
  ``spacer``, ``ultra``, ``archotech`` (plus ``animal``). Used by the
  render layer to tag each apparel/weapon with its authoritative era
  so the LLM doesn't have to infer from the def name."""
  return {k: v.tech_level for k, v in index.items() if v.tech_level}


def index_to_cost_materials(
  index: dict[str, DefRecord],
) -> dict[str, str]:
  """Produce {def_name: 'material1 + material2'} for any def whose
  XML had a ``<costList>``. Materials are humanised and joined with
  '+'. Items with no costList (or with only one ingredient that's
  already implied by a stuff slot) are omitted."""
  labels = index_to_labels(index)
  out: dict[str, str] = {}
  for def_name, rec in index.items():
    if not rec.cost_list:
      continue
    parts = [_humanise_material(m, labels) for m in rec.cost_list]
    out[def_name] = " + ".join(parts)
  return out
