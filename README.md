# rimportrait

Parse RimWorld `.rws` saves into structured prompt-context blocks for AI
image generation. Translates game-specific concepts (xenotypes, defs,
RGBA colors, GradientHair, ideologies, hediffs) into visual descriptions
so an image model can produce realistic gritty RimWorld sci-fi
portraits without knowing the game.

Replaces an in-game RimTalk + Scriban templating workflow with an
out-of-game Python script.

## Install

Requires Python 3.11+. Uses `uv` for environment management.

```sh
uv run --with lxml python -m rimportrait.cli SAVE.rws --pawn NAME
```

Or install editable:

```sh
uv pip install -e .
rimportrait SAVE.rws --pawn NAME
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
```

Output is a `[PORTRAIT SUBJECT]` or `[FAMILY PORTRAIT SUBJECT]` block
followed by a prompt-instruction for a downstream image-prompt LLM.

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

The save's own `<meta><modIds>`/`<modSteamIds>`/`<modNames>` is
parsed to learn the active mod set and load order, then every mod's
`Defs/` is walked for descriptions, labels, categories, and texture
paths. Covered def types include apparel, weapons, hair, genes,
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
uv run --with lxml --with pytest pytest
```

Integration tests look for `sample.rws` at the repo root and skip
cleanly when absent.

## License

MIT
