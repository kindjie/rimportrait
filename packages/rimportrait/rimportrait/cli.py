"""Command-line entry point.

Reads a .rws save and emits portrait/family blocks to stdout or to
--out-dir as one file per pawn. Builds a mod-aware def index from the
save's own <meta><modIds> + <modSteamIds> list so apparel/hair/weapon
descriptions and texture paths come from the user's actual mod set.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
from dataclasses import replace
from pathlib import Path

from rimsave import (
  ModPaths,
  Save,
  autodetect_mod_paths,
  build_def_index_from_save,
  family_members,
  find_pawn,
  humanlike_body_part_search_roots,
  index_to_categories,
  index_to_descriptions,
  index_to_labels,
  iter_by_role,
  iter_colonists,
  iter_pawns,
  load_save,
  map_context_for,
  parse_body_part_index,
)
from rimsave.records import MapContext, PawnRecord

from . import llm, style
from .render import instruction_for, render_family, render_portrait


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

# Which env vars satisfy each provider. Google's SDK accepts either.
_PROVIDER_KEY_VARS: dict[str, tuple[str, ...]] = {
  "google": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
  "openai": ("OPENAI_API_KEY",),
}


def _slug(s: str) -> str:
  return _SAFE_NAME.sub("_", s).strip("_") or "pawn"


# --- ANSI color helpers (stderr only) ------------------------------
# stdout intentionally stays plain because the rendered block / LLM
# prompt is the artifact users pipe downstream; ANSI escapes would
# corrupt that. Honors NO_COLOR / FORCE_COLOR / TERM=dumb per
# https://no-color.org and https://force-color.org conventions.


def _supports_color() -> bool:
  if os.environ.get("NO_COLOR"):
    return False
  if os.environ.get("FORCE_COLOR"):
    return True
  if os.environ.get("TERM") == "dumb":
    return False
  return sys.stderr.isatty()


def _c(sgr: str, s: str) -> str:
  return f"\x1b[{sgr}m{s}\x1b[0m" if _supports_color() else s


def _red(s: str) -> str: return _c("1;31", s)
def _yellow(s: str) -> str: return _c("1;33", s)
def _cyan(s: str) -> str: return _c("36", s)
def _dim(s: str) -> str: return _c("2", s)
def _bold(s: str) -> str: return _c("1", s)


def _error(msg: str) -> str:
  """Format an `error: <msg>` line for stderr."""
  return f"{_red('error:')} {msg}"


def _warning(msg: str) -> str:
  """Format a `warning: <msg>` line for stderr."""
  return f"{_yellow('warning:')} {msg}"


class _RimportraitParser(argparse.ArgumentParser):
  """Argparse parser with a friendlier error path.

  Standard argparse prints the (usually wrapped) usage line plus a
  one-line error and exits 2. That's terse to the point of being
  unhelpful when the user just ran ``rimportrait`` with no args.

  This subclass keeps the same exit code but appends a hint pointing
  at ``--help`` and, when the failure is a missing positional, a
  concrete quick-start invocation.
  """

  def error(self, message: str) -> None:  # type: ignore[override]
    self.print_usage(sys.stderr)
    sys.stderr.write(
      f"{_bold(self.prog)}: {_red('error:')} {message}\n\n"
    )
    if "the following arguments are required" in message:
      sys.stderr.write(_bold("Quick start:") + "\n")
      sys.stderr.write(
        "  " + _cyan(
          f"{self.prog} colony.rws --pawn NAME --generate "
          "--image --out-dir out/"
        ) + "\n\n"
      )
    sys.stderr.write(
      _dim(
        f"Run `{self.prog} --help` for the full flag list and "
        "examples."
      ) + "\n"
    )
    raise SystemExit(2)


def _list_pawn_names(
  save: Save,
  def_index: dict[str, object] | None,
  body_parts: dict[str, dict[int, str]] | None,
) -> list[str]:
  seen: set[str] = set()
  names: list[str] = []
  for p in iter_pawns(save, def_index, body_parts):
    name = p.label or p.nickname or p.name_full
    if name and name not in seen:
      seen.add(name)
      names.append(name)
  return sorted(names, key=str.casefold)


def _format_pawn_suggestion(asked: str, names: list[str]) -> str:
  if not names:
    return f"no pawn named {asked!r} (save contains no labelled pawns)"
  matches = difflib.get_close_matches(asked, names, n=3, cutoff=0.5)
  out = [f"no pawn named {asked!r}."]
  if matches:
    out.append(
      f"  {_yellow('did you mean:')} {_bold(', '.join(matches))}?"
    )
  shown = names if len(names) <= 20 else names[:20] + ["..."]
  out.append(f"  {_dim('available pawns: ' + ', '.join(shown))}")
  return "\n".join(out)


_DESCRIPTION = """\
Turn a RimWorld .rws save into AI-image-prompt context blocks.

Each colonist becomes a [PORTRAIT SUBJECT] block of structured
render-ready details (hair, gear, ideology, hediffs, gradient hair,
ApparelDef descriptions from the active mod set, ...). Optionally
chain through an LLM (--generate) for a polished one-paragraph image
prompt, and on through an image-gen model (--image) for a PNG/JPEG.
"""

_EPILOG = """\
Examples:
  # Default - dump a block per colonist to stdout
  rimportrait colony.rws

  # Block for one pawn (matches label or nickname)
  rimportrait colony.rws --pawn Stark

  # LLM-polished prompt via Google Gemini (default provider)
  rimportrait colony.rws --pawn Stark --generate

  # Prompt + image, both written to out/
  rimportrait colony.rws --pawn Stark --generate --image --out-dir out/
  # -> out/Stark.portrait.txt  (the prompt)
  # -> out/Stark.portrait.jpeg (the image, .png if --provider openai)

  # Family portrait centred on Stark, moody preset
  rimportrait colony.rws --family Stark --generate --image \\
    --preset moody-portrait --out-dir out/

  # Override individual style dimensions
  rimportrait colony.rws --pawn Stark --generate --image --out-dir out/ \\
    --style "oil painting" --shot "posed three-quarter" \\
    --scene "candlelit study" --time night

  # OpenAI instead of Google
  rimportrait colony.rws --pawn Stark --generate --provider openai

  # Manual context the save doesn't serialise
  rimportrait colony.rws --pawn Stark --wealth 350000 --biome "tropical rainforest"

Environment:
  GEMINI_API_KEY    Required for --generate / --image when --provider is google
  OPENAI_API_KEY    Required for --generate / --image when --provider is openai

Output behaviour:
  Without --out-dir, blocks/prompts go to stdout.
  With --out-dir, one file per pawn lands under it as <slug>.<kind>.txt
  where <kind> is portrait or family.
  --image requires --out-dir (binary can't go to stdout) and --generate
  (image models work best on the polished paragraph, not the raw block).

Optional extras:
  pip install 'rimportrait[google]'   # google-genai SDK (text + image)
  pip install 'rimportrait[openai]'   # openai SDK (text + image)
  pip install 'rimportrait[llm]'      # both
"""


def _build_parser() -> argparse.ArgumentParser:
  p = _RimportraitParser(
    prog="rimportrait",
    description=_DESCRIPTION,
    epilog=_EPILOG,
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )
  p.add_argument("save", type=Path, help="Path to a .rws save file.")

  selection = p.add_argument_group(
    "selection",
    "Pick which pawn(s) to render. Default is every colonist.",
  )
  selection.add_argument(
    "--pawn", metavar="NAME", default=None,
    help="Render only the pawn matching this label/nickname.",
  )
  selection.add_argument(
    "--family", metavar="FOCUS", default=None,
    help="Render a family portrait centred on FOCUS.",
  )
  selection.add_argument(
    "--include-prisoners", action="store_true",
    help="Include prisoners in the default iteration.",
  )
  selection.add_argument(
    "--include-guests", action="store_true",
    help="Include visitors/guests in the default iteration.",
  )

  output = p.add_argument_group(
    "output",
    "Where the rendered block (and any image) lands.",
  )
  output.add_argument(
    "--out-dir", type=Path, default=None,
    help=(
      "Write one file per pawn under this dir (default: stdout). "
      "Required for --image."
    ),
  )
  output.add_argument(
    "--no-instruction", action="store_true",
    help=(
      "Emit only the [PORTRAIT SUBJECT] block, dropping the trailing "
      "instruction paragraph. Incompatible with --generate."
    ),
  )

  context = p.add_argument_group(
    "save context",
    "Fields RimWorld doesn't serialise plainly or that need overrides.",
  )
  context.add_argument(
    "--wealth", type=float, default=None,
    help=(
      "Colony wealth value. RimWorld computes wealth at runtime; pass "
      "the in-game number to populate the tier line."
    ),
  )
  context.add_argument(
    "--biome", default=None,
    help=(
      "Biome label, e.g. 'temperate forest'. Not stored plainly in "
      "saves; pass it to populate the line."
    ),
  )

  mods = p.add_argument_group(
    "mod-aware def loading",
    "Where to find Core + active mods for ApparelDef / HairDef / "
    "XenotypeDef / HediffDef labels and descriptions. Auto-detects on "
    "macOS Steam installs.",
  )
  mods.add_argument(
    "--rimworld-dir", type=Path, default=None,
    help=(
      "Path to RimWorld's Data directory (contains Core/, Royalty/, "
      "Ideology/, Biotech/, ...)."
    ),
  )
  mods.add_argument(
    "--workshop-dir", type=Path, default=None,
    help=(
      "Path to Steam Workshop content for RimWorld "
      "(steamapps/workshop/content/294100)."
    ),
  )
  mods.add_argument(
    "--mods-dir", type=Path, default=None,
    help="Path to RimWorld's local Mods directory (sideloaded mods).",
  )
  mods.add_argument(
    "--no-defs", action="store_true",
    help=(
      "Skip mod-aware def loading. Labels/descriptions fall back to a "
      "humanised slug derived from the def name."
    ),
  )

  llm_grp = p.add_argument_group(
    "LLM text step (--generate)",
    "Pipe the block through an LLM to produce a polished, "
    "one-paragraph image-generation prompt.",
  )
  llm_grp.add_argument(
    "--generate", action="store_true",
    help=(
      "Pipe the block + instruction through an LLM and emit the "
      "returned paragraph in place of the block."
    ),
  )
  llm_grp.add_argument(
    "--provider", choices=llm.PROVIDERS, default="openai",
    help=(
      "LLM provider for --generate (default: openai). Reads API key "
      "from OPENAI_API_KEY (openai) or GEMINI_API_KEY (google)."
    ),
  )
  llm_grp.add_argument(
    "--model", default=None,
    help=(
      "Text model override. Defaults: gemini-3.1-pro-preview "
      "(google) / gpt-4o-mini (openai). Pass --fast to swap in the "
      "cheaper / faster Google flash variant without typing the "
      "model name."
    ),
  )

  img_grp = p.add_argument_group(
    "image step (--image)",
    "After --generate produces the paragraph, feed it to an image-gen "
    "model and write the resulting PNG/JPEG next to the .txt prompt.",
  )
  img_grp.add_argument(
    "--image", action="store_true",
    help=(
      "Render an image from the prompt. Requires --generate and "
      "--out-dir."
    ),
  )
  img_grp.add_argument(
    "--image-model", default=None,
    help=(
      "Image model override. Defaults: "
      "gemini-3-pro-image-preview (google, 'Nano Banana Pro'), "
      "gpt-image-2 (openai). Pass --fast for the cheaper Google "
      "Flash variant without typing the model name."
    ),
  )
  img_grp.add_argument(
    "--fast", action="store_true",
    help=(
      "Swap BOTH the text model and the image model for the "
      "provider's fast / cheap variant. Text: "
      "gemini-flash-latest (google) / gpt-4o-mini (openai - no "
      "separate fast tier). Image: gemini-3.1-flash-image-preview "
      "(google) / gpt-image-2 (openai - no separate fast tier). "
      "Ignored on a step when --model / --image-model is set "
      "explicitly for that step."
    ),
  )

  style_grp = p.add_argument_group(
    "style / composition / camera",
    "Steer the LLM toward a target aesthetic by appending a "
    "Style/Composition/Camera/Scene/Time block to the system "
    "instruction. All values are free-form except --preset and --time.",
  )
  style_grp.add_argument(
    "--preset", choices=sorted(style.PRESETS.keys()), default=None,
    help=(
      "Named bundle of style+shot+camera. Explicit --style / --shot / "
      "--camera flags override the preset's values."
    ),
  )
  style_grp.add_argument(
    "--style", default=None, metavar="STYLE",
    help=(
      "Visual style: 'realistic gritty', 'oil painting', 'anime', "
      "'graphic novel inks', 'propaganda poster', ..."
    ),
  )
  style_grp.add_argument(
    "--shot", default=None, metavar="SHOT",
    help=(
      "Composition / shot type: 'posed three-quarter', 'mid-action', "
      "'candid', 'environmental wide', ..."
    ),
  )
  style_grp.add_argument(
    "--camera", default=None, metavar="CAMERA",
    help=(
      "Camera / lens guidance: '85mm portrait, shallow DoF', "
      "'low-angle wide', 'chiaroscuro lighting', ..."
    ),
  )
  style_grp.add_argument(
    "--scene", default=None, metavar="SCENE",
    help=(
      "Environment / setting hint: 'crowded refugee corridor, smoke', "
      "'rain-slick alley', 'burning barn at night', ..."
    ),
  )
  style_grp.add_argument(
    "--time",
    choices=("dawn", "morning", "day", "golden-hour", "dusk", "night"),
    default=None,
    help=(
      "Time-of-day cue. Real-from-save extraction (game ticks -> "
      "in-game hour) is future work."
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
           dict[str, str] | None,
           dict[str, str] | None]:
  if args.no_defs:
    return (None, None, None, None)
  paths = _resolve_paths(args)
  if paths.rimworld_data is None and paths.workshop_dir is None \
      and paths.mods_dir is None:
    return (None, None, None, None)
  index = build_def_index_from_save(save, paths)
  if not index:
    return (None, None, None, None)
  return (
    index,  # for extractors (hair_texture_path enrichment)
    index_to_descriptions(index),
    index_to_labels(index),
    index_to_categories(index),
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


def _maybe_generate(
  args: argparse.Namespace, block: str, kind: str
) -> str:
  if not args.generate:
    return block
  # When --image is also set, look up which image model will be
  # called so the LLM can pick the model-tuned overlay. When --image
  # is off, fall back to the provider-agnostic default base
  # (the prompt may be consumed by any downstream tool).
  image_model: str | None = None
  if args.image:
    image_model = llm.resolve_image_model(
      args.provider, args.image_model, args.fast
    )
  resolved = style.resolve(
    args.preset, args.style, args.shot, args.camera,
    scene=args.scene, time=args.time,
  )
  # Preset can swap the base voice (e.g. --preset action -> action
  # base instead of portrait). Family render always uses family
  # base regardless of preset.base.
  effective_kind = kind
  if kind == "portrait" and resolved.base:
    effective_kind = resolved.base
  system = style.compose_instruction(
    instruction_for(effective_kind, image_model=image_model),
    kind, resolved,
  )
  return llm.complete(
    args.provider, system=system, user=block,
    model=args.model, fast=args.fast,
  )


def _maybe_image(
  args: argparse.Namespace, prompt: str, pawn: PawnRecord, kind: str
) -> None:
  if not args.image:
    return
  png, ext = llm.generate_image(
    args.provider, prompt, kind,
    model=args.image_model, fast=args.fast,
  )
  out_dir = args.out_dir
  assert out_dir is not None  # validated in main
  out_dir.mkdir(parents=True, exist_ok=True)
  fname = f"{_slug(pawn.label or pawn.name_full)}.{kind}.{ext}"
  (out_dir / fname).write_bytes(png)


def main(argv: list[str] | None = None) -> int:
  args = _build_parser().parse_args(argv)
  if args.generate and args.no_instruction:
    print(_error(
      "--no-instruction and --generate can't both be set. "
      "--generate replaces the block with an LLM-polished paragraph, "
      "so the instruction text is consumed as the LLM's system "
      "prompt rather than appended. Drop one of the two flags."
    ), file=sys.stderr)
    return 2
  if args.image and not args.generate:
    print(_error(
      "--image needs the polished paragraph that --generate "
      "produces (image models work best on prose, not the raw "
      "block). Add --generate."
    ), file=sys.stderr)
    return 2
  if args.image and args.out_dir is None:
    print(_error(
      "--image writes binary files; add --out-dir <path> to choose "
      "where they land."
    ), file=sys.stderr)
    return 2
  if args.generate:
    needed = _PROVIDER_KEY_VARS[args.provider]
    if not any(os.environ.get(v) for v in needed):
      pretty = " or ".join(needed)
      print(_error(
        f"--provider {args.provider} needs {pretty} in the "
        "environment. Export one of: "
        + " ".join(f"{v}=..." for v in needed)
      ), file=sys.stderr)
      return 2
  if (args.style or args.shot or args.camera or args.preset
      or args.scene or args.time) and not args.generate:
    print(_warning(
      "--style/--shot/--camera/--preset/--scene/--time have no "
      "effect without --generate"
    ), file=sys.stderr)
  if not args.save.exists():
    print(_error(
      f"save not found: {args.save}\n"
      "  " + _dim(
        "check the path; RimWorld saves usually live in "
        "~/Library/Application Support/RimWorld by Ludeon Studios/"
        "Saves/ on macOS."
      )
    ), file=sys.stderr)
    return 2
  save = load_save(args.save)
  # When piping through an LLM, the instruction is the system message
  # rather than appended to the block, so the rendered block must be
  # instruction-free.
  inst = not args.no_instruction and not args.generate
  def_index, defs_desc, defs_label, defs_cat = _build_index(save, args)
  body_parts = _build_body_parts(args)

  try:
    if args.family:
      focus = find_pawn(save, args.family, def_index, body_parts)
      if focus is None:
        names = _list_pawn_names(save, def_index, body_parts)
        print(
          _error(_format_pawn_suggestion(args.family, names)),
          file=sys.stderr,
        )
        return 4
      members = family_members(save, focus, def_index, body_parts)
      block = render_family(
        focus, members, _context(save, focus, args),
        include_instruction=inst,
        def_descriptions=defs_desc, def_labels=defs_label,
        def_categories=defs_cat,
      )
      text = _maybe_generate(args, block, "family")
      _emit(args.out_dir, text, focus, "family")
      _maybe_image(args, text, focus, "family")
      return 0

    if args.pawn:
      p = find_pawn(save, args.pawn, def_index, body_parts)
      if p is None:
        names = _list_pawn_names(save, def_index, body_parts)
        print(
          _error(_format_pawn_suggestion(args.pawn, names)),
          file=sys.stderr,
        )
        return 4
      block = render_portrait(
        p, _context(save, p, args),
        include_instruction=inst,
        def_descriptions=defs_desc, def_labels=defs_label,
        def_categories=defs_cat,
      )
      text = _maybe_generate(args, block, "portrait")
      _emit(args.out_dir, text, p, "portrait")
      _maybe_image(args, text, p, "portrait")
      return 0

    for p in _gather_default(
      save, args.include_prisoners, args.include_guests,
      def_index, body_parts,
    ):
      block = render_portrait(
        p, _context(save, p, args),
        include_instruction=inst,
        def_descriptions=defs_desc, def_labels=defs_label,
        def_categories=defs_cat,
      )
      text = _maybe_generate(args, block, "portrait")
      _emit(args.out_dir, text, p, "portrait")
      _maybe_image(args, text, p, "portrait")
    return 0
  except Exception as e:
    print(_error(str(e)), file=sys.stderr)
    return 3


if __name__ == "__main__":
  raise SystemExit(main())
