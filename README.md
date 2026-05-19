# rimportrait + rimsave

A uv workspace with two Python packages built around RimWorld save
files:

- **`packages/rimsave/`** — save-parsing **library**. Reads `.rws`
  XML and the user's mod set, returns typed records (`PawnRecord`,
  `IdeoRecord`, `MapContext`, …). No image-prompt opinion; usable on
  its own.
- **`packages/rimportrait/`** — image-prompt **renderer + CLI**.
  Depends on `rimsave`; turns its records into `[PORTRAIT SUBJECT]`
  blocks for downstream image-generation LLMs. Replaces an in-game
  RimTalk + Scriban templating workflow.

API contracts are not stable until v1.0.0 — record shapes and exports
can change in minor versions.

## Install

Requires Python 3.11+. Uses `uv` for environment management.

```sh
uv sync           # installs both packages editable into the workspace venv
uv run rimportrait SAVE.rws --pawn NAME
```

## Usage

```sh
# All colonists to stdout
rimportrait sample.rws

# Single portrait (NAME matches the pawn's label or nickname)
rimportrait sample.rws --pawn NAME

# Family portrait
rimportrait sample.rws --family NAME

# One file per pawn
rimportrait sample.rws --out-dir out/

# Add the data the save doesn't serialise
rimportrait sample.rws --pawn NAME \
  --wealth 350000 \
  --biome "temperate forest" \
  --rimworld-dir /path/to/RimWorld/Data

# Without the trailing image-prompt instruction text
rimportrait sample.rws --pawn NAME --no-instruction

# Generate the image-gen prompt in-process via Google Gemini (default)
export GEMINI_API_KEY=...
uv run rimportrait sample.rws --pawn NAME --generate
# (defaults: --provider google, --model gemini-flash-latest)

# OpenAI alternative
export OPENAI_API_KEY=...
uv run rimportrait sample.rws --pawn NAME --generate --provider openai

# Generate the image too, in one shot
uv run rimportrait sample.rws --pawn NAME \
  --generate --image --out-dir out/
# writes out/NAME.portrait.txt  (the LLM-generated prompt)
# writes out/NAME.portrait.jpeg (Google) or .png (OpenAI)

# Use Google's Nano Banana Pro instead of the default Nano Banana 2
uv run rimportrait sample.rws --pawn NAME \
  --generate --image --image-model gemini-3-pro-image-preview \
  --out-dir out/

# Steer the aesthetic with style/composition/camera knobs
uv run rimportrait sample.rws --pawn NAME --generate --image \
  --style "oil painting" \
  --shot "posed three-quarter, restrained background" \
  --camera "classical portrait framing, warm palette" \
  --out-dir out/

# Or pick a named preset (overrides applied on top)
uv run rimportrait sample.rws --pawn NAME --generate --image \
  --preset propaganda --out-dir out/
```

Output is a `[PORTRAIT SUBJECT]` or `[FAMILY PORTRAIT SUBJECT]` block
followed by a prompt-instruction for a downstream image-prompt LLM —
unless `--generate` is set, in which case rimportrait calls the LLM
itself and emits the returned one-paragraph image prompt instead of
the block. The Google default (`gemini-flash-latest`) is a rolling
alias that follows Google's current Flash release; the OpenAI default
(`gpt-4o-mini`) is a version-pinned snapshot. Override either with
`--model NAME`.

The LLM dependencies are optional extras (the same SDKs cover both
the text step and the image step):
```sh
uv pip install -e 'packages/rimportrait[google]'   # google-genai SDK
uv pip install -e 'packages/rimportrait[openai]'   # openai SDK
uv pip install -e 'packages/rimportrait[llm]'      # both
```

Image-model defaults: **`gemini-3.1-flash-image-preview`** ("Nano
Banana 2") for Google and **`gpt-image-2`** for OpenAI. Override
either with `--image-model NAME`. The image step requires
`--generate` and `--out-dir` — binary doesn't go to stdout, and the
LLM-polished paragraph is what the image models are tuned for.
Portrait renders use a 3:4 frame (1024×1536 OpenAI / 3:4 Google);
family renders use a 4:3 frame so groups fit.

Three style knobs steer the aesthetic by modifying the LLM system
instruction (and therefore the resulting paragraph + image):

- `--style "..."` — visual style (realistic, anime, oil painting,
  graphic novel inks, propaganda poster, …).
- `--shot "..."` — composition / shot type (posed three-quarter,
  mid-action, candid, environmental wide, …).
- `--camera "..."` — camera / lens guidance (85mm portrait shallow
  DoF, low-angle wide, chiaroscuro lighting, …).

Or pick a starter preset and override individual knobs as needed:

| Preset | Style |
|---|---|
| `moody-portrait` | realistic gritty, 85mm shallow DoF, low-key lighting |
| `action`         | realistic gritty, mid-action, 35mm wide deep focus |
| `oil-painting`   | oil painting, classical framing, warm chiaroscuro |
| `comic`          | graphic novel inks, halftone, high contrast |
| `propaganda`     | stark Soviet poster, heroic low angle, hard edges |

Preset phrasing is provisional — additions and refinements live in
`packages/rimportrait/rimportrait/style.py`.

## Library use (rimsave)

`rimsave` is usable standalone — no rendering, no CLI, just typed
records from a `.rws` file:

```python
from rimsave import (
  load_save, iter_colonists, find_pawn, map_context_for,
  autodetect_mod_paths, build_def_index_from_save,
  index_to_labels, index_to_descriptions,
)

save = load_save("colony.rws")
defs = build_def_index_from_save(save, autodetect_mod_paths())
labels = index_to_labels(defs)
for pawn in iter_colonists(save, defs):
  print(pawn.label, pawn.role, [labels.get(g.def_name, g.def_name)
                                for g in pawn.genes])
```

See `packages/rimsave/rimsave/__init__.py` for the full surface
(record types live in `rimsave.records`).

## Rendered fields

A `[PORTRAIT SUBJECT]` block emits the following lines when the source
data is present (each line is omitted cleanly when empty):

- **Identity** — Name, Role, Royal title (faction-overridden labels
  like Empire's *Count → archon* flow through), Race/xenotype, Gender,
  Age.
- **Head and face** — hair color/gradient, beard, face/body tattoos
  resolved to `label (Category style)` via `TattooDef.category`.
- **State** — Traits, Personality (RimTalk Persona → backstory
  fallback), Mood, Physical state (Food/Rest/Deathrest below 50 %, with
  a severe tier below 25 %), Inspiration, Chemical/drug state,
  Shambler state, Creepjoiner state, Pilot state, Commanded mechs (mech
  entourage with count×label), Connections (tree/dryad bonds), Bonded
  animals, Abilities, Psyfocus (band label + %), Pose/activity,
  Immediate setting.
- **Aesthetics** — Favorite color/accent, Visible genes/body traits,
  Visible implants/injuries/body changes (hediff body-part indices
  resolved to readable labels like *right tibia*, *little toe*).
- **Gear** — three prominence buckets: **Worn armor/clothing**,
  **Utility belts/gear** (belts/bandoliers/carriers/gunlinks/jump packs,
  substring-matched to catch modded variants), **Wielded weapon**. Each
  item carries stuff (material) + color + ideology style +
  condition (worn / battered / ruined) qualifiers. Carried infants are
  surfaced separately, baby carriers are marked `empty` when unused.
- **Inventory** — Carrying (pack/inventory) summary with stack counts.
- **Ideology** — Name, primary color, apparel color, description,
  style aesthetic, memes.
- **Map context** — biome, wealth tier, location summary.
- **Apparel detail** — descriptive paragraph per worn item using
  mod-aware descriptions.

## Data-first principle

Visual translation is left to the downstream image-prompt LLM. This
project's job is to emit RimWorld def names plus the mod-aware
`label` / `description` / `category` for each one — no curated phrase
tables, no hand-written enums. Every translate function follows the
same fallback chain:

```
mod description → mod label → humanised def slug
```

That means anything moddable (apparel, weapons, hair, genes, hediffs,
xenotypes, inspirations, abilities, mechs, animals, tattoos, royal
titles, creepjoiner forms/benefits/downsides/aggressives/rejections,
inventory items, materials, …) round-trips through the mod-aware def
index automatically. Adding a new modded def to your game adds it to
the output with no code changes.

## Mod-dependent fields

A few fields require a specific mod to be present at all; they're
omitted cleanly when absent.

| Field | Source mod | Behaviour when absent |
|---|---|---|
| `Hair gradient: ...` | GradientHair | line omitted |
| `Personality/expression: ...` | RimTalk (its `Hediff_Persona`) | falls back to backstory if the save has readable backstory titles, otherwise omitted |
| Xenotype description | Biotech + (modded xenotype) | falls back to xenotype label → its defining xenogene list → humanised slug |

## Mod-aware def coverage

The mod-aware def index is implemented by `rimsave` and exposed via
`build_def_index_from_save` / `index_to_labels` /
`index_to_descriptions` / `index_to_categories`. The save's own
`<meta><modIds>`/`<modSteamIds>`/`<modNames>` is parsed to learn the
active mod set and load order, then every mod's `Defs/` is walked for
descriptions, labels, categories, and texture paths. Covered def types include apparel, weapons, hair, genes,
hediffs, xenotypes, ideologies, inspirations, abilities, mechs,
animals (`ThingDef` with `race`), tattoos, royal titles, creepjoiner
form/benefit/downside/aggressive/rejection defs, and `BodyDef`
(walked pre-order so hediff `<part><index>N</index>` integers resolve
to readable part labels like *right tibia*).

- ParentName/Abstract XML inheritance is resolved (with cycle guard),
  including the `category` field used to surface tattoo genres (Punk /
  Tribal / Royal / Floral / …)
- Versioned folders (`1.6/Defs`, `1.5/Defs`, ...) — only the active
  version is read, avoiding duplicate defs from historical shims
- Last-wins per load order, matching the game's runtime semantics
- Workshop mods recorded with `steamId=0` are still resolved by
  scanning each Workshop folder's `About/About.xml` for its
  `<packageId>`
- A lazy id→ThingDef index across all `<thing>` entries (not just
  pawns) backs cross-thing references like connections and bonded
  animals

Auto-detected Steam install paths (returned values are platform-correct;
`libraryfolders.vdf` is parsed so non-default library locations like
`D:\SteamLibrary` are picked up too):

| Platform | Steam root tried | RimWorld layout |
|---|---|---|
| macOS | `~/Library/Application Support/Steam` | `.../common/RimWorld/RimWorldMac.app/{Data,Mods}` |
| Linux (native) | `~/.steam/steam`, `~/.local/share/Steam` | `.../common/RimWorld/{Data,Mods}` |
| Linux (Flatpak) | `~/.var/app/com.valvesoftware.Steam/data/Steam` | same |
| SteamOS / Steam Deck | as Linux, plus `/run/media/deck/<volume>/`, `/run/media/<volume>/` | same |
| Windows | `C:\Program Files (x86)\Steam`, `D:\SteamLibrary`, `E:\SteamLibrary` | `.../common/RimWorld/{Data,Mods}` |

Always overridable:

| Override | Purpose |
|---|---|
| `--rimworld-dir` | Path to the Data directory (or its parent — common layouts are probed) |
| `--workshop-dir` | Path to `steamapps/workshop/content/294100` |
| `--mods-dir` | Path to sideloaded mods |
| `--no-defs` | Skip mod loading entirely |

## Current limitations

- **Validated against macOS Steam.** Auto-detection covers macOS,
  Linux (native + Flatpak), SteamOS / Steam Deck (internal SSD + SD
  cards), and Windows (default + library folders via
  `libraryfolders.vdf`), but only the macOS path has been exercised
  end-to-end on a real save. On other platforms the overrides
  (`--rimworld-dir`/`--workshop-dir`/`--mods-dir`) are reliable.
- **RimWorld 1.5/1.6 save shape only.** Validated against a Biotech +
  Ideology + Royalty + Anomaly + Odyssey save with the GradientHair
  mod. Older versions likely need selector tweaks.
- **Map wealth isn't serialised by RimWorld** — it is computed at
  runtime. Pass `--wealth <number>` from the in-game UI to populate
  the tier line; otherwise the line is omitted.
- **Biome auto-decode deferred.** Biome lives in `tileBiomeDeflate`
  (base64+zlib), keyed by a tile-index that varies per mod loadout.
  Pass `--biome "..."` for now.
- **Pose/activity is the raw job def** (e.g. `HaulToCell`) — no
  target/verb resolution yet.
- **Immediate setting (outdoors/indoors + temperature) not yet
  extracted.** Temperature isn't reliably in the save; outdoor/indoor
  is recoverable from `roofGrid` but not yet implemented.
- **Apparel descriptions need a RimWorld install for best results.**
  Without `--rimworld-dir` and without the auto-detect succeeding,
  every field that would have used a mod-aware `description`/`label`
  falls back to a humanised def slug (e.g. `Apparel_TribalA` →
  `tribal a`). The block still renders cleanly — it just reads
  rougher.
- **Filtering is minimal by design.** Genes/hediffs are partitioned
  into clusters (chemical, shambler, pilot, drug-high, …) and trivial
  skips like withdrawals/tolerances are dropped, but otherwise the
  block surfaces what the save contains and trusts the downstream LLM
  to do the visual interpretation. See *Data-first principle* above.

## Tests

```sh
uv run pytest
```

Pytest is configured to discover tests from both packages
(`packages/rimsave/tests` + `packages/rimportrait/tests`). Integration
tests look for `sample.rws` at the repo root and skip cleanly when
absent.

## License

MIT
