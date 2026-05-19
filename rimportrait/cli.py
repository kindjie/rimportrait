"""Command-line entry point.

Reads a .rws save and emits portrait/family blocks to stdout or to
--out-dir as one file per pawn. Builds a mod-aware def index from the
save's own <meta><modIds> + <modSteamIds> list so apparel/hair/weapon
descriptions and texture paths come from the user's actual mod set.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import replace
from pathlib import Path

from .extract import (
  ModPaths,
  Save,
  autodetect_mod_paths,
  build_def_index_from_save,
  family_members,
  find_pawn,
  humanlike_body_part_search_roots,
  index_to_descriptions,
  index_to_labels,
  iter_by_role,
  iter_colonists,
  load_save,
  map_context_for,
  parse_body_part_index,
)
from .records import MapContext, PawnRecord
from .render import render_family, render_portrait


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(s: str) -> str:
  return _SAFE_NAME.sub("_", s).strip("_") or "pawn"


def _build_parser() -> argparse.ArgumentParser:
  p = argparse.ArgumentParser(
    prog="rimportrait",
    description=(
      "Generate AI-image prompt context blocks from RimWorld .rws "
      "save files."
    ),
  )
  p.add_argument("save", type=Path, help="Path to a .rws save file.")
  p.add_argument(
    "--out-dir", type=Path, default=None,
    help=(
      "Write one block per pawn to this directory (default: stdout)."
    ),
  )
  p.add_argument(
    "--pawn", metavar="NAME", default=None,
    help="Render only the pawn matching this label/nickname.",
  )
  p.add_argument(
    "--family", metavar="FOCUS", default=None,
    help="Render a family portrait block with FOCUS as the focus pawn.",
  )
  p.add_argument(
    "--include-prisoners", action="store_true",
    help="Include prisoners in default iteration.",
  )
  p.add_argument(
    "--include-guests", action="store_true",
    help="Include visitors/guests in default iteration.",
  )
  p.add_argument(
    "--wealth", type=float, default=None,
    help=(
      "Colony wealth value. RimWorld does not serialise wealth; pass "
      "the in-game number for the tier line."
    ),
  )
  p.add_argument(
    "--biome", default=None,
    help=(
      "Biome label (e.g. 'temperate forest'). Not stored as a plain "
      "field in saves; pass it in to populate the line."
    ),
  )
  p.add_argument(
    "--rimworld-dir", type=Path, default=None,
    help=(
      "Path to RimWorld's Data directory (contains Core/, Royalty/, "
      "Ideology/, Biotech/, ...). Auto-detects on macOS."
    ),
  )
  p.add_argument(
    "--workshop-dir", type=Path, default=None,
    help=(
      "Path to Steam Workshop content for RimWorld "
      "(steamapps/workshop/content/294100). Auto-detects on macOS."
    ),
  )
  p.add_argument(
    "--mods-dir", type=Path, default=None,
    help=(
      "Path to RimWorld's local Mods directory (sideloaded mods). "
      "Auto-detects on macOS."
    ),
  )
  p.add_argument(
    "--no-defs", action="store_true",
    help=(
      "Skip mod-aware def loading entirely. Apparel/hair/weapon "
      "descriptions fall back to short curated phrases."
    ),
  )
  p.add_argument(
    "--no-instruction", action="store_true",
    help=(
      "Emit only the block, without the trailing image-prompt "
      "instruction text."
    ),
  )
  return p


def _emit(
  out_dir: Path | None,
  block: str,
  pawn: PawnRecord,
  kind: str,
) -> None:
  if out_dir is None:
    sys.stdout.write(block)
    sys.stdout.write("\n\n")
    return
  out_dir.mkdir(parents=True, exist_ok=True)
  fname = f"{_slug(pawn.label or pawn.name_full)}.{kind}.txt"
  (out_dir / fname).write_text(block + "\n")


def _gather_default(
  save: Save,
  include_prisoners: bool,
  include_guests: bool,
  def_index: dict[str, object] | None,
  body_parts: dict[str, dict[int, str]] | None,
) -> list[PawnRecord]:
  out = list(iter_colonists(save, def_index, body_parts))
  if include_prisoners:
    out.extend(iter_by_role(save, "prisoner", def_index, body_parts))
  if include_guests:
    out.extend(iter_by_role(save, "guest", def_index, body_parts))
  return out


def _resolve_paths(args: argparse.Namespace) -> ModPaths:
  defaults = autodetect_mod_paths()
  return ModPaths(
    rimworld_data=args.rimworld_dir or defaults.rimworld_data,
    workshop_dir=args.workshop_dir or defaults.workshop_dir,
    mods_dir=args.mods_dir or defaults.mods_dir,
  )


def _build_index(
  save: Save, args: argparse.Namespace
) -> tuple[dict[str, object] | None,
           dict[str, str] | None,
           dict[str, str] | None]:
  if args.no_defs:
    return (None, None, None)
  paths = _resolve_paths(args)
  if paths.rimworld_data is None and paths.workshop_dir is None \
      and paths.mods_dir is None:
    return (None, None, None)
  index = build_def_index_from_save(save, paths)
  if not index:
    return (None, None, None)
  return (
    index,  # for extractors (hair_texture_path enrichment)
    index_to_descriptions(index),
    index_to_labels(index),
  )


def _build_body_parts(
  args: argparse.Namespace,
) -> dict[str, dict[int, str]] | None:
  if args.no_defs:
    return None
  paths = _resolve_paths(args)
  roots = humanlike_body_part_search_roots(paths.rimworld_data)
  if not roots:
    return None
  index = parse_body_part_index(roots)
  return index or None


def _context(
  save: Save, pawn: PawnRecord, args: argparse.Namespace
) -> MapContext | None:
  ctx = map_context_for(save, pawn, wealth_override=args.wealth)
  if args.biome and ctx is not None:
    ctx = replace(ctx, biome=args.biome)
  elif args.biome:
    ctx = MapContext(biome=args.biome, wealth=args.wealth)
  return ctx


def main(argv: list[str] | None = None) -> int:
  args = _build_parser().parse_args(argv)
  if not args.save.exists():
    print(f"error: save not found: {args.save}", file=sys.stderr)
    return 2
  save = load_save(args.save)
  inst = not args.no_instruction
  def_index, defs_desc, defs_label = _build_index(save, args)
  body_parts = _build_body_parts(args)

  if args.family:
    focus = find_pawn(save, args.family, def_index, body_parts)
    if focus is None:
      print(f"error: no pawn named {args.family!r}", file=sys.stderr)
      return 4
    members = family_members(save, focus, def_index, body_parts)
    block = render_family(
      focus, members, _context(save, focus, args),
      include_instruction=inst,
      def_descriptions=defs_desc, def_labels=defs_label,
    )
    _emit(args.out_dir, block, focus, "family")
    return 0

  if args.pawn:
    p = find_pawn(save, args.pawn, def_index, body_parts)
    if p is None:
      print(f"error: no pawn named {args.pawn!r}", file=sys.stderr)
      return 4
    block = render_portrait(
      p, _context(save, p, args),
      include_instruction=inst,
      def_descriptions=defs_desc, def_labels=defs_label,
    )
    _emit(args.out_dir, block, p, "portrait")
    return 0

  for p in _gather_default(
    save, args.include_prisoners, args.include_guests,
    def_index, body_parts,
  ):
    block = render_portrait(
      p, _context(save, p, args),
      include_instruction=inst,
      def_descriptions=defs_desc, def_labels=defs_label,
    )
    _emit(args.out_dir, block, p, "portrait")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
