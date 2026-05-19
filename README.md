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

## Mod-dependent fields

Several fields are populated only when the relevant RimWorld mod is
installed; they're omitted cleanly when absent.

| Field | Source mod | Behaviour when absent |
|---|---|---|
| `Hair gradient: ...` | GradientHair | line omitted |
| `Personality/expression: ...` | RimTalk (its `Hediff_Persona`) | falls back to backstory if the save has readable backstory titles, otherwise omitted |
| Mod-specific apparel/hair/xenotype/gene/hediff defs | various | unknown defs degrade to humanised def name; unknown xenotypes get an "infer from listed genes" hint; unknown genes/invisible hediffs are dropped per the spec's visible-only rule |

## Mod-aware def coverage

The save's own `<meta><modIds>`/`<modSteamIds>`/`<modNames>` is
parsed to learn the active mod set and load order, then every mod's
`Defs/` is walked for descriptions, labels, and texture paths.

- ParentName/Abstract XML inheritance is resolved (with cycle guard)
- Versioned folders (`1.6/Defs`, `1.5/Defs`, ...) — only the active
  version is read, avoiding duplicate defs from historical shims
- Last-wins per load order, matching the game's runtime semantics
- Workshop mods recorded with `steamId=0` are still resolved by
  scanning each Workshop folder's `About/About.xml` for its
  `<packageId>`

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
- **Apparel descriptions require a RimWorld install.** Without
  `--rimworld-dir` and without the auto-detect succeeding, the
  Apparel visual descriptions section falls back to short curated
  phrases.
- **Spec-driven filtering by design.** Genes are filtered to visible
  anatomy + attitude-bearing; hediffs to visible body changes; gear
  is stripped of quality/HP. If you want raw RimTalk-style output,
  this isn't that — it's a deliberate cleanup pass for image prompts.

## Tests

```sh
uv run --with lxml --with pytest pytest
```

Integration tests look for `sample.rws` at the repo root and skip
cleanly when absent.

## License

MIT
