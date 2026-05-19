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
- Ideology style aesthetic + memes are emitted as raw def names with
  priorities verbatim, per the project's data-first principle. No
  curated translation tables — the downstream LLM does the visual
  translation step.
- Curated visual translation tables retired across translate modules
  (apparel, weapons, inventory, genes, hediffs, xenotype, favorite
  color, hair). Each translate function now accepts an optional
  ``labels``/``descriptions`` dict (sourced from the mod-aware def
  index) and falls back through `mod description -> mod label ->
  humanised slug`. Tests assert both the no-labels (humanised) path
  and the labels-provided path where relevant.
- `test_xenotype.py` — unit coverage for the xenotype fallback chain:
  description -> label -> xenogene list -> humanised slug. Endogenes
  are excluded from the gene-list fallback so only the xenotype's
  defining genes appear.
- Royal title rendering is covered in `test_render.py`. RoyalTitleDef
  is part of the mod-aware def index, so per-faction label overrides
  (e.g. Empire's Count -> archon) flow through automatically; tests
  assert both the label-provided and no-labels (def-name) paths and
  the semicolon-joined multi-title shape.
- `test_condition.py` — coarse condition-label mapper for apparel /
  weapon health vs MaxHitPoints: omit at >= 80%, "worn" at 50-80%,
  "battered" at 25-50%, "ruined" below 25%. The mapper is integrated
  into qualifier_for_apparel and qualifier_for_weapon and tested in
  the render block too.
- Carried-infant coherence covered in test_render.py: baby carriers
  (vanilla `Apparel_BabyCarrier` + any modded `*BabyCarrier`) gain
  an `empty` qualifier when carriedBaby is null, and a "Carrying
  infant in arms" line appears when an infant ref resolves. Falls
  back to the bare pawn id if the carried pawn can't be resolved.
- Inspiration rendering covered in test_render.py: emits the active
  inspiration def with mod-aware description fallback. InspirationDef
  is added to the mod-aware index so labels (shoot frenzy etc.) flow
  through automatically.
- `test_chemical_state.py` — drug-high hediff partitioning. Vanilla
  `*High` suffix, `Drunk`, and modded `HighOn*` prefix recognised by
  `is_drug_high`. `describe_chemical_state` returns only those;
  `describe_hediffs` excludes them so they appear on a dedicated
  "Chemical/drug state" line near Inspiration rather than mixing
  with permanent body changes.
- Mechanitor entourage covered in test_render.py: extractor follows
  mechanitor/controlGroups/li/assignedMechs to mech ThingDef names,
  renderer groups them with a count×label breakdown sorted by count
  desc. The conventional `Mech_` prefix is stripped from humanised
  fallback labels.
- Psycaster state covered in test_render.py: Abilities line lists
  every def from abilities/abilities/li + learnedAbilities/li
  threaded through the mod-aware label index. Psyfocus is gated on
  a psylink-style hediff (PsychicAmplifier or Psylink*) so the line
  only fires for actual psycasters; rendered as a band label plus
  percentage (full / high / moderate / low / depleted at 0.95 /
  0.75 / 0.50 / 0.25 thresholds).
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
