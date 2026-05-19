"""Load RimWorld ThingDef descriptions from a Data directory.

The save XML stores def names only. The in-game tooltip descriptions
live in RimWorld's `Data/{Core,Royalty,Ideology,Biotech,Anomaly,Odyssey}
/Defs/**/*.xml`. We scan them once and cache by defName.

This handles inherited descriptions via the ParentName attribute:
many apparel defs use ApparelMakeableBase as a parent. We resolve a
chain up to 5 deep, sufficient for Core/DLC content.

Mac default path is auto-detected; pass --rimworld-dir to override.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from lxml import etree


_DEFAULT_MAC_PATH = Path(
  "~/Library/Application Support/Steam/steamapps/common/"
  "RimWorld/RimWorldMac.app/Data"
).expanduser()

# Rich-text tags RimWorld embeds in description text; mirrors RimTalk's
# StripFormattingTags filter.
_FORMAT_TAG = re.compile(r"</?(color(=#?[0-9A-Fa-f]+)?|b|i)>")


def autodetect_rimworld_dir() -> Path | None:
  if _DEFAULT_MAC_PATH.exists():
    return _DEFAULT_MAC_PATH
  return None


def _strip_tags(text: str) -> str:
  # RimWorld defs encode line breaks as the literal 2-char sequence \n
  # (backslash + n) which the game converts at load time.
  text = text.replace("\\n", "\n").replace("\\t", "\t")
  return _FORMAT_TAG.sub("", text).strip()


def _iter_dlc_dirs(root: Path) -> Iterable[Path]:
  for name in ("Core", "Royalty", "Ideology", "Biotech", "Anomaly",
               "Odyssey"):
    p = root / name / "Defs"
    if p.is_dir():
      yield p


def load_def_descriptions(rimworld_data_dir: Path) -> dict[str, str]:
  """Scan all ThingDefs and return {defName: description}.

  Resolves ParentName inheritance up to 5 levels. Strips inline
  rich-text tags from the description.
  """
  parents: dict[str, str] = {}
  own_desc: dict[str, str] = {}
  own_label: dict[str, str] = {}

  parser = etree.XMLParser(recover=True, huge_tree=True)
  for defs_dir in _iter_dlc_dirs(rimworld_data_dir):
    for xml_file in defs_dir.rglob("*.xml"):
      try:
        tree = etree.parse(str(xml_file), parser)
      except etree.XMLSyntaxError:
        continue
      for td in tree.iter("ThingDef"):
        def_name = td.findtext("defName")
        if def_name:
          desc = td.findtext("description")
          if desc:
            own_desc[def_name] = _strip_tags(desc)
          label = td.findtext("label")
          if label:
            own_label[def_name] = label.strip()
          parent_name = td.attrib.get("ParentName")
          if parent_name:
            parents[def_name] = parent_name

  # Resolve inheritance: any def that has no description gets its
  # parent's description (walk up the chain).
  out: dict[str, str] = dict(own_desc)
  for def_name in list(parents):
    if def_name in out:
      continue
    cur = parents.get(def_name)
    for _ in range(5):
      if cur is None:
        break
      if cur in own_desc:
        out[def_name] = own_desc[cur]
        break
      cur = parents.get(cur)
  return out


def load_def_labels(rimworld_data_dir: Path) -> dict[str, str]:
  """Same idea, but returns {defName: label} for nicer display names."""
  parents: dict[str, str] = {}
  own: dict[str, str] = {}
  parser = etree.XMLParser(recover=True, huge_tree=True)
  for defs_dir in _iter_dlc_dirs(rimworld_data_dir):
    for xml_file in defs_dir.rglob("*.xml"):
      try:
        tree = etree.parse(str(xml_file), parser)
      except etree.XMLSyntaxError:
        continue
      for td in tree.iter("ThingDef"):
        def_name = td.findtext("defName")
        if not def_name:
          continue
        lab = td.findtext("label")
        if lab:
          own[def_name] = lab.strip()
        pn = td.attrib.get("ParentName")
        if pn:
          parents[def_name] = pn
  out = dict(own)
  for def_name in list(parents):
    if def_name in out:
      continue
    cur = parents.get(def_name)
    for _ in range(5):
      if cur is None:
        break
      if cur in own:
        out[def_name] = own[cur]
        break
      cur = parents.get(cur)
  return out
