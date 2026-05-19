# Tests

## Layout
- `test_colors.py` — RGBA parsing + descriptive-name table, including
  the exact phrasings from the spec.
- `test_wealth.py` — wealth-tier boundary behaviour.
- `test_stuff.py` — material (stuff) def humanisation:
  Leather_*/Wool*/Blocks* prefixes plus camelcase fallback.
- `test_inventory.py` — inventory item phrasing: curated def table,
  humanise fallback, stuff qualifier, stackCount prefix.
- Worn gear is rendered as three prominence buckets — "Worn
  armor/clothing", "Utility belts/gear" (belts, bandoliers, carriers,
  gunlinks, jump packs; substring-matched to catch modded variants),
  "Wielded weapon" — each line emitted only when non-empty.
- `test_render.py` — render layer over hand-built `PawnRecord` /
  `MapContext` fixtures. The `_sample_pawn` fixture (near-black hair,
  bright cyan gradient mid-to-tip, curly beard, ideology blue-gray)
  acts as the canonical end-to-end shape check. Additional cases
  cover apparel/weapon stuff+color+style qualifiers and the no-signal
  fallback (no parens, no brackets).
- `test_extract_integration.py` — runs against `sample.rws` at the
  repo root when present. Selectors find a representative colonist by
  structural property (e.g. first with gradient hair, first with
  family relations) so the suite works for anyone's save.

## Running
```
pip install -e .[dev]   # or: uv pip install -e .[dev]
pytest
```

## Scope
- Pure layers only (colors, wealth, translation tables, render).
- The extraction layer is unit-tested only after a sample `.rws` is
  wired in - fixtures need real save structure to avoid false
  confidence.
