"""Resolve hediff body-part indices to human-readable part labels.

RimWorld serialises a hediff's body part as a flat integer index
``<part><index>N</index></part>`` that points into the pawn's race
body tree. We rebuild the same pre-order walk used at runtime over
each ``BodyDef`` so the index resolves to the part's customLabel
(when present) or its bare def name.

Mod-friendly: every ``Bodies/*.xml`` file across the RimWorld data
dir plus the active mods is walked, so modded races get their body
indices resolved automatically.
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree


def _walk_core(core_el: etree._Element) -> list[str]:
  """Return body-part labels in RimWorld's pre-order traversal order."""
  out: list[str] = []

  def visit(node: etree._Element) -> None:
    label = (
      (node.findtext("customLabel") or node.findtext("def") or "")
      .strip()
    )
    out.append(label)
    parts = node.find("parts")
    if parts is not None:
      for child in parts.iterfind("li"):
        visit(child)

  visit(core_el)
  return out


def parse_body_part_index(
  search_roots: list[Path],
) -> dict[str, dict[int, str]]:
  """Scan ``Bodies/*.xml`` files under each root for ``BodyDef`` entries.

  Returns {bodyDef -> {index -> part label}}. Body defs without a
  ``corePart`` are skipped. Missing roots are tolerated silently so
  the caller can pass speculative paths.
  """
  parser = etree.XMLParser(recover=True, huge_tree=True)
  out: dict[str, dict[int, str]] = {}
  for root_dir in search_roots:
    if not root_dir.is_dir():
      continue
    for xml_file in root_dir.rglob("Bodies_*.xml"):
      try:
        tree = etree.parse(str(xml_file), parser)
      except etree.XMLSyntaxError:
        continue
      for body in tree.iter("BodyDef"):
        name = body.findtext("defName")
        if not name:
          continue
        core = body.find("corePart")
        if core is None:
          continue
        labels = _walk_core(core)
        out[name.strip()] = {i: lbl for i, lbl in enumerate(labels)}
  return out


def humanlike_body_part_search_roots(
  rimworld_data_dir: Path | None,
) -> list[Path]:
  """Default search roots for the vanilla DLC body defs."""
  if rimworld_data_dir is None:
    return []
  return [
    rimworld_data_dir / dlc / "Defs" / "Bodies"
    for dlc in ("Core", "Royalty", "Ideology", "Biotech", "Anomaly",
                "Odyssey")
  ]
