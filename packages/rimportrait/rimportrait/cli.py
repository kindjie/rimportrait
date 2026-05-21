"""Command-line entry point.

Reads a .rws save and renders a portrait. With ``--out-dir``, runs the
full pipeline (block -> LLM-polished prompt -> image). Without it,
emits the structured block to stdout (cheap default, no API spend).
``--block-only`` and ``--prompt-only`` stop the pipeline early.

Builds a mod-aware def index from the save's own ``<meta><modIds>`` +
``<modSteamIds>`` list so apparel/hair/weapon descriptions come from
the user's actual mod set.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
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

# Mode tokens. Resolved once from CLI flags and threaded through.
MODE_BLOCK = "block"
MODE_PROMPT = "prompt"
MODE_IMAGE = "image"


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


class _RimportraitParser(argparse.ArgumentParser):
  """Argparse parser with a friendlier error path.

  Standard argparse prints the (usually wrapped) usage line plus a
  one-line error and exits 2. This subclass keeps the same exit code
  but appends a hint pointing at ``--help`` and, when the failure is
  a missing positional, a concrete quick-start invocation.
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
          f"{self.prog} colony.rws NAME --out-dir out/"
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
Turn a RimWorld .rws save into AI portrait imagery.

Default behaviour: emit a structured [PORTRAIT SUBJECT] block to
stdout (cheap, no API spend). With --out-dir, run the full pipeline
(block -> LLM-polished prompt -> image) and write both files there.
--block-only and --prompt-only stop the pipeline early.
"""

_EPILOG = """\
Examples:
  # Block to stdout (debug / inspection - no API spend)
  rimportrait colony.rws Stark

  # Full pipeline: prompt + image written under out/
  rimportrait colony.rws Stark --out-dir out/
  # -> out/Stark.portrait.txt    (the LLM-generated prompt)
  # -> out/Stark.portrait.jpeg   (the image)

  # Family portrait centred on Stark
  rimportrait colony.rws Stark --family --out-dir out/

  # All colonists at once (no positional pawn name)
  rimportrait colony.rws --out-dir out/

  # Just the prompt (skip image gen)
  rimportrait colony.rws Stark --prompt-only

  # Just the block (skip LLM)
  rimportrait colony.rws Stark --block-only

  # Style controls
  rimportrait colony.rws Stark --out-dir out/ --preset renaissance
  rimportrait colony.rws Stark --out-dir out/ --style "moody candlelit"

  # Model tier / explicit override
  rimportrait colony.rws Stark --out-dir out/ --model fast
  rimportrait colony.rws Stark --out-dir out/ \\
    --provider openai --model gpt-image-2

Environment:
  GEMINI_API_KEY    Required when --provider is google (default)
  OPENAI_API_KEY    Required when --provider is openai

Optional extras (workspace install - rimportrait is not on PyPI):
  uv pip install -e 'packages/rimportrait[google]'   # google-genai (text+image)
  uv pip install -e 'packages/rimportrait[openai]'   # openai (text+image)
  uv pip install -e 'packages/rimportrait[llm]'      # both
"""


def _build_parser() -> argparse.ArgumentParser:
  p = _RimportraitParser(
    prog="rimportrait",
    description=_DESCRIPTION,
    epilog=_EPILOG,
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )
  p.add_argument(
    "savefile", type=Path,
    help="Path to a .rws save file.",
  )
  p.add_argument(
    "pawn", nargs="?", default=None, metavar="PAWN",
    help=(
      "Pawn label / nickname (omit to iterate every colonist). With "
      "--family, this is the focus pawn the portrait is centred on."
    ),
  )
  p.add_argument(
    "--family", action="store_true",
    help="Render a family portrait centred on PAWN.",
  )

  p.add_argument(
    "--out-dir", type=Path, default=None,
    help=(
      "Write outputs here. Presence triggers the full image pipeline "
      "by default; --block-only / --prompt-only stop earlier."
    ),
  )
  mode = p.add_mutually_exclusive_group()
  mode.add_argument(
    "--block-only", action="store_true",
    help="Stop at the rendered block; skip LLM and image (no API calls).",
  )
  mode.add_argument(
    "--block-and-instruction-only", action="store_true",
    help=(
      "Like --block-only, but also append the composed LLM system "
      "instruction (--preset / --style applied). Useful for pasting "
      "block + instruction together into a chat UI."
    ),
  )
  mode.add_argument(
    "--prompt-only", action="store_true",
    help="Run LLM, skip image gen. Writes the prompt only.",
  )

  p.add_argument(
    "--preset", choices=sorted(style.PRESETS.keys()), default=None,
    metavar="NAME",
    help=(
      "Named style bundle (e.g. renaissance, anime). See --help "
      "for the full list."
    ),
  )
  p.add_argument(
    "--style", default=None, metavar="STYLE",
    help=(
      "Freeform style addition (e.g. 'oil painting', "
      "'moody candlelit'). Overrides --preset's style line."
    ),
  )

  p.add_argument(
    "--provider", choices=llm.PROVIDERS, default="openai",
    help=(
      "LLM provider (default: openai). Reads API key from "
      "OPENAI_API_KEY (openai) or GEMINI_API_KEY (google)."
    ),
  )
  p.add_argument(
    "--model", default=None, metavar="TIER|MODEL_ID",
    help=(
      "Model tier ('fast' or 'pro', default 'pro') or an explicit "
      "model ID. Explicit IDs only override the matching step "
      "(image IDs contain 'image' / 'imagen' / 'dall-e'); the other "
      "step uses the pro default."
    ),
  )

  p.add_argument(
    "--rimworld-dir", type=Path, default=None, metavar="PATH",
    help=(
      "Advanced: override the RimWorld Data directory. Workshop / "
      "Mods siblings are auto-derived. Auto-detected on macOS Steam."
    ),
  )
  p.add_argument(
    "--no-defs", action="store_true",
    help="Advanced: skip mod loading. Labels fall back to humanised slugs.",
  )
  return p


def _resolve_mode(args: argparse.Namespace) -> str:
  """Pick the rendering mode from flags. Single source of truth.

  Both --block-only and --block-and-instruction-only stop before the
  LLM call; the latter just appends the composed instruction. The
  --with-instruction post-processing in _render_one keys off
  args.block_and_instruction_only directly."""
  if args.block_only or args.block_and_instruction_only:
    return MODE_BLOCK
  if args.prompt_only:
    return MODE_PROMPT
  if args.out_dir is None:
    # No output dir + no explicit verb -> safe block default.
    return MODE_BLOCK
  return MODE_IMAGE


def _emit_text(
  out_dir: Path | None,
  text: str,
  pawn: PawnRecord,
  kind: str,
) -> None:
  """Write text to stdout (no out-dir) or to a .txt file in out-dir."""
  if out_dir is None:
    sys.stdout.write(text)
    sys.stdout.write("\n\n")
    return
  out_dir.mkdir(parents=True, exist_ok=True)
  fname = f"{_slug(pawn.label or pawn.name_full)}.{kind}.txt"
  (out_dir / fname).write_text(text + "\n")


def _resolve_paths(args: argparse.Namespace) -> ModPaths:
  """Auto-detect with a single optional override.

  ``--rimworld-dir`` overrides the Data directory; the corresponding
  Workshop and Mods siblings are derived from auto-detection (which
  reads ``libraryfolders.vdf`` to find them).
  """
  defaults = autodetect_mod_paths()
  return ModPaths(
    rimworld_data=args.rimworld_dir or defaults.rimworld_data,
    workshop_dir=defaults.workshop_dir,
    mods_dir=defaults.mods_dir,
  )


def _build_index(
  save: Save, args: argparse.Namespace
) -> tuple[dict[str, object] | None,
           dict[str, str] | None,
           dict[str, str] | None,
           dict[str, str] | None,
           dict[str, str] | None,
           dict[str, str] | None,
           dict[str, str] | None]:
  if args.no_defs:
    return (None, None, None, None, None, None, None)
  paths = _resolve_paths(args)
  if paths.rimworld_data is None and paths.workshop_dir is None \
      and paths.mods_dir is None:
    return (None, None, None, None, None, None, None)
  index = build_def_index_from_save(save, paths)
  if not index:
    return (None, None, None, None, None, None, None)
  # Populate Save's roof/terrain shortHash -> defName lookups so
  # roof_kind / terrain_kind on PawnRecord can resolve to readable
  # labels (otherwise they'd be None even when the def index is
  # loaded).
  from rimsave import (
    index_to_apparel_layers,
    index_to_cost_materials,
    index_to_tech_levels,
    register_def_short_hashes,
  )
  register_def_short_hashes(save, index)
  return (
    index,
    index_to_descriptions(index),
    index_to_labels(index),
    index_to_categories(index),
    index_to_cost_materials(index),
    index_to_tech_levels(index),
    index_to_apparel_layers(index),
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
  save: Save, pawn: PawnRecord
) -> MapContext | None:
  return map_context_for(save, pawn)


def _composed_instruction(
  args: argparse.Namespace, kind: str
) -> str:
  """Build the LLM system instruction: base (portrait / family /
  action) + per-image-model overlay + --preset / --style addendum.

  This is the text the LLM would actually receive (or the text
  appended to stdout when --with-instruction is set)."""
  image_model = llm.resolve_model(args.provider, "image", args.model)
  resolved = style.resolve(args.preset, args.style)
  effective_kind = kind
  if kind == "portrait" and resolved.base:
    effective_kind = resolved.base
  return style.compose_instruction(
    instruction_for(effective_kind, image_model=image_model),
    kind, resolved,
  )


def _llm_polish(
  args: argparse.Namespace, block: str, kind: str
) -> str:
  """Run the block through the LLM. Caller checks the mode first."""
  system = _composed_instruction(args, kind)
  return llm.complete(
    args.provider, system=system, user=block, model=args.model,
  )


def _write_image(
  args: argparse.Namespace, prompt: str, pawn: PawnRecord, kind: str
) -> None:
  """Generate the image and write it next to the prompt."""
  png, ext = llm.generate_image(
    args.provider, prompt, kind, model=args.model,
  )
  out_dir = args.out_dir
  assert out_dir is not None  # validated in main
  out_dir.mkdir(parents=True, exist_ok=True)
  fname = f"{_slug(pawn.label or pawn.name_full)}.{kind}.{ext}"
  (out_dir / fname).write_bytes(png)


def _render_one(
  args: argparse.Namespace,
  mode: str,
  p: PawnRecord,
  kind: str,
  block: str,
) -> None:
  """Drive the pipeline for a single pawn given a pre-rendered block.

  Block mode emits just the block, unless
  --block-and-instruction-only is set, in which case the composed
  system instruction is appended too (paste-into-chat workflow).
  Prompt mode runs the LLM; image mode runs LLM then image gen."""
  if mode == MODE_BLOCK:
    text = block
    if args.block_and_instruction_only:
      text = block + "\n\n" + _composed_instruction(args, kind)
    _emit_text(args.out_dir, text, p, kind)
    return
  prompt = _llm_polish(args, block, kind)
  _emit_text(args.out_dir, prompt, p, kind)
  if mode == MODE_IMAGE:
    _write_image(args, prompt, p, kind)


def main(argv: list[str] | None = None) -> int:
  args = _build_parser().parse_args(argv)
  mode = _resolve_mode(args)

  if args.family and not args.pawn:
    print(_error(
      "--family needs a focus pawn. Pass it as the positional "
      "argument: `rimportrait save.rws NAME --family`."
    ), file=sys.stderr)
    return 2

  if mode in (MODE_PROMPT, MODE_IMAGE):
    needed = _PROVIDER_KEY_VARS[args.provider]
    if not any(os.environ.get(v) for v in needed):
      pretty = " or ".join(needed)
      print(_error(
        f"--provider {args.provider} needs {pretty} in the "
        "environment. Export one of: "
        + " ".join(f"{v}=..." for v in needed)
      ), file=sys.stderr)
      return 2

  if not args.savefile.exists():
    print(_error(
      f"save not found: {args.savefile}\n"
      "  " + _dim(
        "check the path; RimWorld saves usually live in "
        "~/Library/Application Support/RimWorld by Ludeon Studios/"
        "Saves/ on macOS."
      )
    ), file=sys.stderr)
    return 2

  save = load_save(args.savefile)
  # The trailing instruction is now handled exclusively by the
  # --with-instruction post-processor in _render_one, so the block
  # itself is always rendered instruction-free regardless of mode.
  (def_index, defs_desc, defs_label, defs_cat, defs_cost, defs_tech,
   defs_layer) = _build_index(save, args)
  body_parts = _build_body_parts(args)

  try:
    if args.family:
      focus = find_pawn(save, args.pawn, def_index, body_parts)
      if focus is None:
        names = _list_pawn_names(save, def_index, body_parts)
        print(
          _error(_format_pawn_suggestion(args.pawn, names)),
          file=sys.stderr,
        )
        return 4
      members = family_members(save, focus, def_index, body_parts)
      block = render_family(
        focus, members, _context(save, focus),
        include_instruction=False,
        def_descriptions=defs_desc, def_labels=defs_label,
        def_categories=defs_cat,
        def_cost_materials=defs_cost,
        def_tech_levels=defs_tech,
        def_apparel_layers=defs_layer,
      )
      _render_one(args, mode, focus, "family", block)
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
        p, _context(save, p),
        include_instruction=False,
        def_descriptions=defs_desc, def_labels=defs_label,
        def_categories=defs_cat,
        def_cost_materials=defs_cost,
        def_tech_levels=defs_tech,
        def_apparel_layers=defs_layer,
      )
      _render_one(args, mode, p, "portrait", block)
      return 0

    for p in iter_colonists(save, def_index, body_parts):
      block = render_portrait(
        p, _context(save, p),
        include_instruction=False,
        def_descriptions=defs_desc, def_labels=defs_label,
        def_categories=defs_cat,
        def_cost_materials=defs_cost,
        def_tech_levels=defs_tech,
        def_apparel_layers=defs_layer,
      )
      _render_one(args, mode, p, "portrait", block)
    return 0
  except Exception as e:
    print(_error(str(e)), file=sys.stderr)
    return 3


if __name__ == "__main__":
  raise SystemExit(main())
