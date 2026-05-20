# rimportrait tests

Render-layer and translate-module tests. Save-extraction tests live in
`packages/rimsave/tests/`.

## Files
- `test_stuff.py` — material (stuff) def humanisation:
  Leather_*/Wool*/Blocks* prefixes plus camelcase fallback.
- `test_inventory.py` — inventory item phrasing: humanise fallback,
  stuff qualifier, stackCount prefix.
- `test_condition.py` — coarse condition-label mapper for apparel /
  weapon health vs MaxHitPoints: omit at >= 80%, "worn" at 50-80%,
  "battered" at 25-50%, "ruined" below 25%. Integrated into
  qualifier_for_apparel and qualifier_for_weapon.
- `test_xenotype.py` — xenotype fallback chain: description -> label
  -> xenogene list -> humanised slug. Endogenes are excluded from the
  gene-list fallback so only the xenotype's defining genes appear.
- `test_chemical_state.py` — drug-high, Shambler, and Odyssey pilot
  hediff partitioning. Each `is_X` / `describe_X` pair pulls its
  cluster out of `describe_hediffs` so body-changes line stays clean.
- `test_llm.py` — `--generate` provider dispatch + missing-SDK error
  shape. Real provider SDK calls are monkeypatched so the suite stays
  offline-safe and doesn't require either optional dep to be
  installed.
- `test_image.py` — `--image` dispatch + per-kind size/aspect routing
  (portrait → 1024×1536 / 3:4, family → 1536×1024 / 4:3) +
  missing-SDK error shape. Real provider SDK calls are monkeypatched
  so the suite stays offline-safe.
- `test_style.py` — `--style`/`--shot`/`--camera`/`--scene`/`--time`/
  `--preset` resolution + instruction composition. Asserts the
  Style/Composition/Camera/Scene/Time block is appended and that the
  prescribed "End with" closer is rewritten only when `--style` is
  set (family kind gets "family portrait" descriptor). Override
  precedence: explicit CLI flags beat preset values. Includes a
  guard asserting the `action` preset names the save-side fields it
  pulls from (`Pose/activity`, `Inspiration`) so the explicit
  "lean on save signals" intent doesn't silently rot.
- `test_render.py` — render layer over hand-built `PawnRecord` /
  `MapContext` fixtures. The `_sample_pawn` fixture acts as the
  canonical end-to-end shape check. Additional cases cover
  apparel/weapon stuff+color+style qualifiers, no-signal fallback,
  three-bucket gear prominence (Worn armor/clothing, Utility
  belts/gear, Wielded weapon), carried-infant + empty baby carrier,
  royal title faction overrides, inspiration, mechanitor entourage,
  abilities + psyfocus, creepjoiner state, connections, bonded
  animals, physical state, tattoo `label (Category style)`, and
  ideology style aesthetic + memes.

## Data-first principle
Curated visual translation tables are retired across all translate
modules (apparel, weapons, inventory, genes, hediffs, xenotype,
favorite color, hair). Every translate function accepts an optional
`labels` / `descriptions` dict (sourced from the mod-aware def index)
and falls back through `mod description -> mod label -> humanised
slug`. Tests assert both the no-labels (humanised) and labels-provided
paths where relevant.

## Running
```
uv run pytest packages/rimportrait/tests
```
