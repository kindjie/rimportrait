# rimsave

Parse RimWorld `.rws` save files into typed Python records. Reads the
save's own `<meta><modIds>`/`<modSteamIds>` to learn the active mod
set and walks each mod's `Defs/` for labels, descriptions, categories,
and texture paths — so anything moddable (apparel, weapons, hair,
xenotypes, hediffs, royal titles, tattoos, …) round-trips through
mod-aware data.

## Surface
```python
from rimsave import (
  load_save, iter_colonists, iter_by_role, find_pawn,
  family_members, map_context_for,
  build_def_index_from_save, autodetect_mod_paths,
  index_to_labels, index_to_descriptions, index_to_categories,
  humanlike_body_part_search_roots, parse_body_part_index,
)
from rimsave.records import PawnRecord, IdeoRecord, MapContext, ...
```

API contracts are unstable until v1.0.0 — record shapes can change
in minor versions.

See the workspace root `README.md` for the full project context.
