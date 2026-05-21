"""Save-file extraction layer.

Public surface:
  load_save(path) -> Save
  iter_pawns(save) -> Iterable[PawnRecord]
  iter_colonists(save) -> Iterable[PawnRecord]
  iter_by_role(save, role) -> Iterable[PawnRecord]
  find_pawn(save, name) -> PawnRecord | None
  family_members(save, focus) -> list[(Relation, PawnRecord)]
  map_context_for(save, pawn) -> MapContext | None
"""

from __future__ import annotations

from .body_parts import (
  humanlike_body_part_search_roots,
  parse_body_part_index,
)
from .defs import autodetect_rimworld_dir, load_def_descriptions, load_def_labels
from .load import (
  CaravanInfo,
  Save,
  load_save,
  read_save_game_version,
  register_def_short_hashes,
)
from .mods import (
  DefRecord,
  ModEntry,
  ModPaths,
  autodetect_mod_paths,
  autodetect_saves_dir,
  build_def_index_from_save,
  index_to_categories,
  index_to_cost_materials,
  index_to_descriptions,
  index_to_apparel_layers,
  index_to_labels,
  index_to_tech_levels,
  installed_rimworld_version,
  layer_rank,
  index_to_texpaths,
  iter_mods_from_save,
)
from .pawn import (
  family_members,
  find_pawn,
  iter_by_role,
  iter_colonists,
  iter_pawns,
  map_context_for,
  pawn_from_element,
)


class ExtractorNotImplemented(NotImplementedError):
  """Kept for backward compatibility with the earlier CLI stub."""


__all__ = [
  "DefRecord",
  "CaravanInfo",
  "ExtractorNotImplemented",
  "ModEntry",
  "ModPaths",
  "Save",
  "autodetect_mod_paths",
  "autodetect_rimworld_dir",
  "autodetect_saves_dir",
  "build_def_index_from_save",
  "family_members",
  "find_pawn",
  "humanlike_body_part_search_roots",
  "index_to_apparel_layers",
  "index_to_categories",
  "index_to_cost_materials",
  "index_to_descriptions",
  "index_to_labels",
  "index_to_tech_levels",
  "index_to_texpaths",
  "installed_rimworld_version",
  "iter_by_role",
  "iter_colonists",
  "iter_mods_from_save",
  "iter_pawns",
  "layer_rank",
  "load_def_descriptions",
  "load_def_labels",
  "load_save",
  "map_context_for",
  "read_save_game_version",
  "parse_body_part_index",
  "pawn_from_element",
  "register_def_short_hashes",
]
