"""Unit tests for the mod-discovery + def-index layer.

These tests synthesise small on-disk mod folders + a minimal Save
substitute so the behaviour is reproducible without depending on the
sample save or a real RimWorld install.
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from rimsave.load import Save
from rimsave.mods import (
  ModPaths,
  _parse_library_folders,
  _parse_raw_defs,
  _probe_rimworld_paths,
  _resolve_inheritance,
  build_def_index_from_save,
  iter_mods_from_save,
  resolve_mod_roots,
)


def _make_save(meta_xml: str) -> Save:
  root = etree.fromstring(
    f"<savegame>{meta_xml}</savegame>"
  )
  return Save(root=root)


def _write_mod(
  root: Path,
  package_id: str,
  defs_xml: str,
  versioned: str | None = None,
) -> Path:
  root.mkdir(parents=True, exist_ok=True)
  (root / "About").mkdir(exist_ok=True)
  (root / "About" / "About.xml").write_text(
    f"<ModMetaData><packageId>{package_id}</packageId></ModMetaData>"
  )
  defs_dir = root / (versioned or "") / "Defs" if versioned else root / "Defs"
  defs_dir.mkdir(parents=True, exist_ok=True)
  (defs_dir / "defs.xml").write_text(defs_xml)
  return root


def test_iter_mods_from_save_in_load_order():
  save = _make_save(
    "<meta>"
    "<modIds><li>a.one</li><li>B.Two</li></modIds>"
    "<modSteamIds><li>0</li><li>12345</li></modSteamIds>"
    "<modNames><li>One</li><li>Two</li></modNames>"
    "</meta>"
  )
  mods = iter_mods_from_save(save)
  assert [m.package_id for m in mods] == ["a.one", "b.two"]
  assert [m.steam_id for m in mods] == ["0", "12345"]
  assert [m.order for m in mods] == [0, 1]


def test_iter_mods_handles_missing_meta():
  save = _make_save("")
  assert iter_mods_from_save(save) == []


def test_cost_list_extracted_and_sorted_bulk_first(tmp_path: Path):
  """costList materials should be captured and ordered by amount
  descending (so '75 Plasteel + 9 Gold' reads as 'plasteel + gold',
  the bulk first)."""
  from rimsave.mods import index_to_cost_materials
  defs = """<Defs>
    <ThingDef>
      <defName>Apparel_PrestigeCataphractHelmet</defName>
      <label>prestige cataphract helmet</label>
      <costList>
        <Gold>9</Gold>
        <Plasteel>75</Plasteel>
      </costList>
    </ThingDef>
    <ThingDef>
      <defName>Apparel_Plain</defName>
      <label>plain shirt</label>
    </ThingDef>
  </Defs>"""
  mod = _write_mod(tmp_path / "mod_cost", "test.mod.cost", defs)
  raws = _parse_raw_defs(mod, "test.mod.cost")
  resolved = {r.def_name: r for r in _resolve_inheritance(raws)}
  # Sorted bulk-first: Plasteel (75) before Gold (9).
  assert resolved["Apparel_PrestigeCataphractHelmet"].cost_list == \
    ("Plasteel", "Gold")
  # No costList -> empty tuple.
  assert resolved["Apparel_Plain"].cost_list == ()
  # Helper produces the rendered material string.
  index = {r.def_name: r for r in _resolve_inheritance(raws)}
  materials = index_to_cost_materials(index)
  assert materials["Apparel_PrestigeCataphractHelmet"] == \
    "plasteel + gold"
  assert "Apparel_Plain" not in materials


def test_cost_list_ignores_xml_comments_inside(tmp_path: Path):
  """lxml exposes comment nodes with a callable .tag attribute;
  the costList parser must skip them."""
  defs = """<Defs>
    <ThingDef>
      <defName>Apparel_Mixed</defName>
      <costList>
        <Steel>50</Steel>
        <!-- a comment that lxml exposes as a node -->
        <Cloth>20</Cloth>
      </costList>
    </ThingDef>
  </Defs>"""
  mod = _write_mod(tmp_path / "mod_mixed", "test.mod.mixed", defs)
  raws = _parse_raw_defs(mod, "test.mod.mixed")
  resolved = {r.def_name: r for r in _resolve_inheritance(raws)}
  assert resolved["Apparel_Mixed"].cost_list == ("Steel", "Cloth")


def test_apparel_layers_extracted_and_outermost_picked(tmp_path: Path):
  """<apparel><layers> entries are captured in XML order; the
  outermost helper picks the visually-outer layer per RimWorld's
  Overhead/EyeCover/Belt/Shell/Middle/OnSkin ordering."""
  from rimsave.mods import index_to_apparel_layers, outermost_layer
  defs = """<Defs>
    <ThingDef>
      <defName>Apparel_FlakVest</defName>
      <apparel>
        <layers>
          <li>Middle</li>
          <li>Shell</li>
        </layers>
      </apparel>
    </ThingDef>
    <ThingDef>
      <defName>Apparel_Helmet</defName>
      <apparel>
        <layers><li>Overhead</li></layers>
      </apparel>
    </ThingDef>
    <ThingDef>
      <defName>Apparel_Shirt</defName>
      <apparel>
        <layers><li>OnSkin</li></layers>
      </apparel>
    </ThingDef>
    <ThingDef>
      <defName>Plain</defName>
    </ThingDef>
  </Defs>"""
  mod = _write_mod(tmp_path / "mod_layers", "test.mod.layers", defs)
  raws = _parse_raw_defs(mod, "test.mod.layers")
  index = {r.def_name: r for r in _resolve_inheritance(raws)}
  assert index["Apparel_FlakVest"].apparel_layers == ("Middle", "Shell")
  assert index["Plain"].apparel_layers == ()
  # Shell is outer than Middle.
  assert outermost_layer(("Middle", "Shell")) == "Shell"
  helper = index_to_apparel_layers(index)
  assert helper == {
    "Apparel_FlakVest": "Shell",
    "Apparel_Helmet": "Overhead",
    "Apparel_Shirt": "OnSkin",
  }


def test_apparel_layers_inherited_from_parent(tmp_path: Path):
  defs = """<Defs>
    <ThingDef Name="ApparelArmorBase" Abstract="True">
      <apparel>
        <layers><li>Middle</li><li>Shell</li></layers>
      </apparel>
    </ThingDef>
    <ThingDef ParentName="ApparelArmorBase">
      <defName>Apparel_PowerArmor</defName>
    </ThingDef>
  </Defs>"""
  mod = _write_mod(tmp_path / "mod_inh", "test.mod.layers.inh", defs)
  raws = _parse_raw_defs(mod, "test.mod.layers.inh")
  index = {r.def_name: r for r in _resolve_inheritance(raws)}
  assert index["Apparel_PowerArmor"].apparel_layers == ("Middle", "Shell")


def test_tech_level_extracted_and_inherited(tmp_path: Path):
  """techLevel comes from the def's <techLevel> tag, with
  ParentName chains followed for abstract bases (most spacer apparel
  inherits techLevel from ArmorMachineable / ApparelMakeableBase)."""
  from rimsave.mods import index_to_tech_levels
  defs = """<Defs>
    <ThingDef Name="ArmorMachineable" Abstract="True">
      <techLevel>Spacer</techLevel>
    </ThingDef>
    <ThingDef ParentName="ArmorMachineable">
      <defName>Apparel_PowerArmor</defName>
      <label>cataphract armor</label>
    </ThingDef>
    <ThingDef>
      <defName>Bow_Recurve</defName>
      <label>recurve bow</label>
      <techLevel>Neolithic</techLevel>
    </ThingDef>
    <ThingDef>
      <defName>Apparel_NoTech</defName>
      <label>shirt</label>
    </ThingDef>
  </Defs>"""
  mod = _write_mod(tmp_path / "mod_tech", "test.mod.tech", defs)
  raws = _parse_raw_defs(mod, "test.mod.tech")
  index = {r.def_name: r for r in _resolve_inheritance(raws)}
  # Direct tag, lowercased.
  assert index["Bow_Recurve"].tech_level == "neolithic"
  # Inherited from abstract parent.
  assert index["Apparel_PowerArmor"].tech_level == "spacer"
  # Missing tag stays None and is omitted from the helper map.
  assert index["Apparel_NoTech"].tech_level is None
  tech = index_to_tech_levels(index)
  assert tech == {
    "Apparel_PowerArmor": "spacer",
    "Bow_Recurve": "neolithic",
  }


def test_inheritance_walks_parent_chain(tmp_path: Path):
  defs = """<Defs>
    <ThingDef Name="GrandparentBase" Abstract="True">
      <description>A base item.</description>
      <label>base item</label>
    </ThingDef>
    <ThingDef ParentName="GrandparentBase" Name="ParentBase" Abstract="True">
      <texPath>Things/Items/Custom</texPath>
    </ThingDef>
    <ThingDef ParentName="ParentBase">
      <defName>Item_Real</defName>
    </ThingDef>
  </Defs>"""
  mod = _write_mod(tmp_path / "mod_a", "test.mod.a", defs)
  raws = _parse_raw_defs(mod, "test.mod.a")
  resolved = {r.def_name: r for r in _resolve_inheritance(raws)}
  assert "Item_Real" in resolved
  assert resolved["Item_Real"].description == "A base item."
  assert resolved["Item_Real"].label == "base item"
  assert resolved["Item_Real"].tex_path == "Things/Items/Custom"


def test_inheritance_handles_cycle(tmp_path: Path):
  defs = """<Defs>
    <ThingDef Name="A" ParentName="B" Abstract="True">
      <description>From A.</description>
    </ThingDef>
    <ThingDef Name="B" ParentName="A" Abstract="True">
      <label>from b</label>
    </ThingDef>
    <ThingDef ParentName="A">
      <defName>Cycle_Item</defName>
    </ThingDef>
  </Defs>"""
  mod = _write_mod(tmp_path / "mod_cycle", "test.cycle", defs)
  raws = _parse_raw_defs(mod, "test.cycle")
  resolved = {r.def_name: r for r in _resolve_inheritance(raws)}
  # The cycle is detected; whatever fields exist before the cycle
  # are inherited, others stay None.
  assert "Cycle_Item" in resolved
  assert resolved["Cycle_Item"].description == "From A."


def test_versioned_folder_skips_old_and_keeps_active(tmp_path: Path):
  active_defs = """<Defs>
    <ThingDef><defName>Active</defName><label>active</label></ThingDef>
  </Defs>"""
  old_defs = """<Defs>
    <ThingDef><defName>Old</defName><label>old</label></ThingDef>
  </Defs>"""
  mod_root = tmp_path / "mod_versioned"
  mod_root.mkdir()
  (mod_root / "About").mkdir()
  (mod_root / "About" / "About.xml").write_text(
    "<ModMetaData><packageId>test.versioned</packageId></ModMetaData>"
  )
  (mod_root / "1.6").mkdir()
  (mod_root / "1.6" / "Defs").mkdir()
  (mod_root / "1.6" / "Defs" / "active.xml").write_text(active_defs)
  (mod_root / "1.5").mkdir()
  (mod_root / "1.5" / "Defs").mkdir()
  (mod_root / "1.5" / "Defs" / "old.xml").write_text(old_defs)
  raws = _parse_raw_defs(mod_root, "test.versioned")
  names = {r.def_name for r in raws}
  assert "Active" in names
  assert "Old" not in names


def test_last_loaded_mod_overrides_earlier(tmp_path: Path):
  defs_a = """<Defs>
    <ThingDef><defName>Item</defName>
      <description>From A.</description><label>a item</label>
    </ThingDef>
  </Defs>"""
  defs_b = """<Defs>
    <ThingDef><defName>Item</defName>
      <description>From B.</description><label>b item</label>
    </ThingDef>
  </Defs>"""
  mods_dir = tmp_path / "Mods"
  _write_mod(mods_dir / "a", "test.a", defs_a)
  _write_mod(mods_dir / "b", "test.b", defs_b)
  save = _make_save(
    "<meta>"
    "<modIds><li>test.a</li><li>test.b</li></modIds>"
    "<modSteamIds><li>0</li><li>0</li></modSteamIds>"
    "<modNames><li>A</li><li>B</li></modNames>"
    "</meta>"
  )
  paths = ModPaths(
    rimworld_data=None, workshop_dir=None, mods_dir=mods_dir
  )
  index = build_def_index_from_save(save, paths)
  assert index["Item"].description == "From B."
  assert index["Item"].source == "test.b"


def test_resolve_mod_roots_falls_back_to_about_xml(tmp_path: Path):
  """Steam ID '0' in the save should still resolve via About.xml."""
  workshop = tmp_path / "workshop"
  _write_mod(
    workshop / "99999",
    "test.zero.steam.id",
    "<Defs/>",
  )
  save = _make_save(
    "<meta>"
    "<modIds><li>test.zero.steam.id</li></modIds>"
    "<modSteamIds><li>0</li></modSteamIds>"
    "<modNames><li>Zero</li></modNames>"
    "</meta>"
  )
  paths = ModPaths(
    rimworld_data=None, workshop_dir=workshop, mods_dir=None
  )
  resolved = resolve_mod_roots(iter_mods_from_save(save), paths)
  assert resolved[0][1] is not None
  assert resolved[0][1].name == "99999"


def test_probe_finds_mac_layout(tmp_path: Path):
  steam = tmp_path / "Steam"
  rimworld = steam / "steamapps/common/RimWorld"
  (rimworld / "RimWorldMac.app/Data/Core").mkdir(parents=True)
  (rimworld / "RimWorldMac.app/Mods").mkdir(parents=True)
  (steam / f"steamapps/workshop/content/294100").mkdir(parents=True)
  paths = _probe_rimworld_paths(steam)
  assert paths is not None
  assert paths.rimworld_data == rimworld / "RimWorldMac.app/Data"
  assert paths.mods_dir == rimworld / "RimWorldMac.app/Mods"
  assert paths.workshop_dir is not None


def test_probe_finds_linux_or_windows_layout(tmp_path: Path):
  steam = tmp_path / "Steam"
  rimworld = steam / "steamapps/common/RimWorld"
  (rimworld / "Data/Core").mkdir(parents=True)
  (rimworld / "Mods").mkdir(parents=True)
  paths = _probe_rimworld_paths(steam)
  assert paths is not None
  assert paths.rimworld_data == rimworld / "Data"
  assert paths.mods_dir == rimworld / "Mods"
  # No Workshop folder present -> workshop_dir is None.
  assert paths.workshop_dir is None


def test_probe_returns_none_when_no_rimworld(tmp_path: Path):
  assert _probe_rimworld_paths(tmp_path) is None


def test_parse_library_folders_extracts_existing_paths(tmp_path: Path):
  other = tmp_path / "Other"
  other.mkdir()
  vdf = tmp_path / "libraryfolders.vdf"
  vdf.write_text(f'''"libraryfolders"
{{
    "0"
    {{
        "path"      "{tmp_path}"
        "label"     ""
    }}
    "1"
    {{
        "path"      "{other}"
        "label"     "two"
    }}
    "2"
    {{
        "path"      "/nonexistent/path"
    }}
}}''')
  found = _parse_library_folders(vdf)
  assert tmp_path in found
  assert other in found
  # The bogus path is filtered because it doesn't exist on disk.
  assert all(p.exists() for p in found)


def test_parse_library_folders_unescapes_backslashes(tmp_path: Path):
  win_like = tmp_path / "SteamLibrary"
  win_like.mkdir()
  # Simulate Windows VDF where backslashes are escaped.
  escaped = str(win_like).replace("\\", "\\\\")
  vdf = tmp_path / "libraryfolders.vdf"
  vdf.write_text(f'"libraryfolders"\n{{\n"0" {{ "path" "{escaped}" }}\n}}')
  assert win_like in _parse_library_folders(vdf)


def test_strip_format_tags_in_description(tmp_path: Path):
  defs = """<Defs>
    <ThingDef><defName>Tagged</defName>
      <description>Worship &lt;color=#FF0000FF&gt;Caullux&lt;/color&gt;.\\n\\nAlways.</description>
    </ThingDef>
  </Defs>"""
  mod = _write_mod(tmp_path / "tagged", "test.tagged", defs)
  raws = _parse_raw_defs(mod, "test.tagged")
  resolved = {r.def_name: r for r in _resolve_inheritance(raws)}
  desc = resolved["Tagged"].description or ""
  assert "<color" not in desc
  assert "Worship Caullux." in desc
  assert "\n\n" in desc
