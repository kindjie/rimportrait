# rimsave tests

Pure save-parsing tests — XML extraction, mod-aware def index,
RimWorld primitives. No prompt/render coverage.

## Files
- `test_colors.py` — RGBA parsing + descriptive-name table.
- `test_wealth.py` — wealth-tier boundary behaviour.
- `test_mods.py` — mod load-order resolution from
  `<meta><modIds>`/`<modSteamIds>`, ParentName/Abstract inheritance,
  versioned `1.6/Defs` selection, last-wins per load order.
- `test_body_parts.py` — pre-order BodyDef walk that resolves hediff
  `<part><index>N</index>` integers to part labels via the RimWorld
  Data dir + active mods. CustomLabel beats def name when set.
- `test_extract_integration.py` — runs against `sample.rws` at the
  repo root when present. Selectors find a representative colonist by
  structural property (e.g. first with gradient hair, first with
  family relations) so the suite works for anyone's save.

## Scope
- Only XML-shape and def-index behaviour. Anything that turns a record
  into prose lives in `packages/rimportrait/tests/`.
- Integration tests skip cleanly when `sample.rws` is absent.

## Running
```
uv run pytest packages/rimsave/tests
```
