from __future__ import annotations

from rimportrait.colors import RGBA
from rimportrait.records import (
  ApparelItem,
  CarriedInfant,
  Gene,
  GradientHair,
  Hediff,
  IdeoRecord,
  InventoryItem,
  MapContext,
  PawnRecord,
  Relation,
  RoyalTitle,
  Weapon,
)
from rimportrait.render import (
  FAMILY_PROMPT_INSTRUCTION,
  SINGLE_PROMPT_INSTRUCTION,
  render_family,
  render_portrait,
)


def _sample_pawn() -> PawnRecord:
  """Synthetic fixture exercising the spec-critical fields.

  Near-black hair + bright cyan mid-to-tip gradient, curly beard,
  ideology in muted blue-gray. Used to sanity-check that the
  rendered block surfaces every flagged field.
  """
  return PawnRecord(
    pawn_id="42",
    name_full="John Doe",
    label="John",
    role="colonist",
    gender="Male",
    bio_age=29,
    chrono_age=29,
    xenotype="Baseliner",
    traits=("Smug", "Tough"),
    hair_def="SDfluffysideparts",
    hair_label="SD Zayne",
    hair_texture_path="Hairs/fluffySidePartS",
    hair_color=RGBA(0.204, 0.204, 0.204, 1.0),
    beard_def="BeardCurly",
    beard_label="curly",
    face_tattoo="Face_Tear",
    body_tattoo="Body_Fullbody",
    favorite_color="LightPurple",
    gradient_hair=GradientHair(
      enabled=True,
      color_b=RGBA(0.399, 0.926, 0.931, 1.0),
      mask="GradientHair/MaskBMidHigh",
    ),
    genes=(Gene("Beauty_Pretty"),),
    hediffs=(),
    apparel=(
      ApparelItem("Apparel_FlakJacket", "flak jacket"),
      ApparelItem("Apparel_FlakPants", "flak pants"),
    ),
    equipment=(Weapon("Gun_BeamRepeater", "beam repeater"),),
    ideo=IdeoRecord(
      name="Reclaimed Path",
      color=RGBA(0.263, 0.388, 0.580, 1.0),
      apparel_color=RGBA(0.290, 0.405, 0.580, 1.0),
      style_summary="anti-authoritarian commune with reused materials",
    ),
  )


def _map() -> MapContext:
  return MapContext(
    biome="Temperate forest",
    weather="Clear",
    wealth=350_000,
    population=8,
    active_threats=(),
  )


def test_portrait_contains_identity():
  out = render_portrait(_sample_pawn(), _map(), include_instruction=False)
  assert "[PORTRAIT SUBJECT]" in out
  assert "Name: John" in out
  assert "Role: Colonist" in out
  assert "Gender: Male" in out
  assert "Age: 29" in out


def test_portrait_includes_hair_style_and_color():
  out = render_portrait(_sample_pawn(), _map(), include_instruction=False)
  # Hair label + texture path are emitted as game data; the curated
  # visual phrase has been retired per the data-first principle.
  assert "Hair style: SD Zayne" in out
  assert "Hair texture path: Hairs/fluffySidePartS" in out
  assert "very dark charcoal / near-black" in out


def test_portrait_includes_gradient_hair():
  out = render_portrait(_sample_pawn(), _map(), include_instruction=False)
  assert "Hair gradient: enabled" in out
  assert "bright cyan / aqua / turquoise" in out
  # Gradient mask is emitted as the raw RimWorld texture path.
  assert "GradientHair/MaskBMidHigh" in out


def test_portrait_includes_beard_and_tattoos():
  out = render_portrait(_sample_pawn(), _map(), include_instruction=False)
  assert "Beard: curly" in out
  assert "Face tattoo: Face_Tear" in out
  assert "Body tattoo: Body_Fullbody" in out


def test_portrait_includes_ideology_colors():
  out = render_portrait(_sample_pawn(), _map(), include_instruction=False)
  assert "Ideology/culture: Reclaimed Path" in out
  assert "muted steel blue / blue-gray" in out
  assert "muted blue-gray" in out


def test_portrait_renders_ideology_style_and_memes_raw():
  pawn = PawnRecord(
    pawn_id="106",
    name_full="Theo Ideo",
    label="Theo",
    role="colonist",
    ideo=IdeoRecord(
      name="Made-Up Creed",
      style_categories=(("Techist", 4), ("Rustic", 2)),
      memes=("Structure_Archist", "Loyalist", "Transhumanist"),
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  # Style categories are emitted with priority verbatim, no curated
  # phrasing (the downstream LLM does the translation step).
  assert (
    "Ideology style aesthetic: Techist (priority 4), Rustic (priority 2)"
  ) in out
  assert (
    "Ideology memes: Structure_Archist, Loyalist, Transhumanist"
  ) in out


def test_portrait_omits_ideology_style_and_memes_when_empty():
  pawn = PawnRecord(
    pawn_id="107",
    name_full="Plain Ideo",
    label="Plain",
    role="colonist",
    ideo=IdeoRecord(name="Bare Faith"),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Ideology style aesthetic:" not in out
  assert "Ideology memes:" not in out


def test_portrait_wealth_tier_is_descriptive_not_numeric():
  out = render_portrait(_sample_pawn(), _map(), include_instruction=False)
  assert "prosperous colony" in out
  assert "350000" not in out
  assert "350,000" not in out


def test_portrait_favorite_color_translated():
  out = render_portrait(_sample_pawn(), _map(), include_instruction=False)
  # ColorDef -> RGBA -> Lab-nearest palette phrase. LightPurple's RGBA
  # falls nearest to the curated palette's "muted violet" entry.
  assert "Favorite color/accent: muted violet" in out


def test_portrait_apparel_section_present():
  out = render_portrait(_sample_pawn(), _map(), include_instruction=False)
  assert "Apparel visual descriptions:" in out
  assert "flak jacket" in out


def test_portrait_surfaces_apparel_stuff_color_and_style():
  pawn = PawnRecord(
    pawn_id="100",
    name_full="Mat Roe",
    label="Mat",
    role="colonist",
    apparel=(
      ApparelItem(
        "Apparel_CollarShirt",
        stuff="Leather_Human",
        color=RGBA(0.55, 0.40, 0.75, 1.0),  # muted violet
      ),
      ApparelItem(
        "Apparel_ArmorMarineHelmetPrestige",
        stuff=None,
        color=RGBA(0.33, 0.33, 0.33, 1.0),  # dark charcoal gray
        style_def="PrestigeMarineHelmet_Samurai",
      ),
    ),
    equipment=(
      Weapon(
        "Gun_AssaultRifle",
        stuff="Plasteel",
        color=RGBA(0.40, 0.93, 0.93, 1.0),
      ),
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  # Inline gear summary: material, color, style appear in parens.
  assert "human leather" in out
  assert "muted violet" in out
  assert "Samurai style" in out
  assert "plasteel" in out
  assert "bright cyan / aqua / turquoise" in out
  # Long apparel section: qualifier bracketed.
  assert "[human leather, muted violet]" in out
  assert (
    "[dark charcoal gray, Samurai style]" in out
  )


def test_carrying_line_lists_inventory_items_distinct_from_equipped():
  pawn = PawnRecord(
    pawn_id="102",
    name_full="Sup Plier",
    label="Sup",
    role="colonist",
    equipment=(Weapon("Gun_AssaultRifle"),),
    inventory=(
      InventoryItem("MealSimple", stack_count=3),
      InventoryItem("Shell_HighExplosive", stack_count=12),
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  # Wielded weapon is on its own labeled line (humanised def name,
  # since no labels dict is threaded in this test); pack items appear
  # under the Carrying line; the two must not mix.
  assert "Wielded weapon: assault rifle" in out
  assert (
    "Carrying (pack/inventory): 3× meal simple, "
    "12× shell high explosive"
  ) in out
  weapon_line = [
    ln for ln in out.splitlines() if ln.startswith("Wielded weapon:")
  ][0]
  assert "meal simple" not in weapon_line
  assert "shell high explosive" not in weapon_line


def test_gear_lines_split_armor_utility_and_weapon():
  pawn = PawnRecord(
    pawn_id="104",
    name_full="Stack Edpawn",
    label="Stack",
    role="colonist",
    apparel=(
      ApparelItem("Apparel_CollarShirt"),
      ApparelItem("Apparel_PowerArmor"),
      ApparelItem("Apparel_Bandolier"),
      ApparelItem("Apparel_Gunlink"),
      ApparelItem("SBC_BabyCarrier"),
      ApparelItem("Apparel_ArmorMarineHelmetPrestige"),
      ApparelItem("Apparel_Cape"),
    ),
    equipment=(Weapon("Gun_ChargeLance"),),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  armor_line = [
    ln for ln in out.splitlines() if ln.startswith("Worn armor/clothing:")
  ][0]
  utility_line = [
    ln for ln in out.splitlines() if ln.startswith("Utility belts/gear:")
  ][0]
  weapon_line = [
    ln for ln in out.splitlines() if ln.startswith("Wielded weapon:")
  ][0]
  # Armor/clothing bucket: humanised def names (no labels threaded
  # in this synthetic test; downstream LLM does the visual step).
  assert "collar shirt" in armor_line
  assert "power armor" in armor_line
  assert "armor marine helmet prestige" in armor_line
  assert "cape" in armor_line
  # Utility bucket: belt/bandolier/carrier/gunlink patterns matched
  # against def name, including modded SBC_BabyCarrier.
  assert "bandolier" in utility_line
  assert "gunlink" in utility_line
  assert "baby carrier" in utility_line
  # No cross-contamination between buckets.
  assert "bandolier" not in armor_line
  assert "collar shirt" not in utility_line
  assert "charge lance" in weapon_line
  assert "charge lance" not in armor_line
  assert "charge lance" not in utility_line


def test_gear_lines_omit_empty_buckets():
  unarmed = PawnRecord(
    pawn_id="105",
    name_full="Bare Hands",
    label="Bare",
    role="colonist",
    apparel=(ApparelItem("Apparel_CollarShirt"),),
  )
  out = render_portrait(unarmed, None, include_instruction=False)
  assert "Worn armor/clothing:" in out
  assert "Utility belts/gear:" not in out
  assert "Wielded weapon:" not in out


def test_carrying_line_omitted_when_inventory_empty():
  pawn = PawnRecord(
    pawn_id="103",
    name_full="Empty Pack",
    label="Empty",
    role="colonist",
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Carrying" not in out


def test_chemical_state_line_renders_drug_highs_only():
  pawn = PawnRecord(
    pawn_id="600",
    name_full="Junkie Joe",
    label="Junkie",
    role="colonist",
    hediffs=(
      Hediff("YayoHigh"),
      Hediff("Drunk"),
      Hediff("ArchotechEye", body_part="left eye"),
      Hediff("PsychiteTolerance"),  # skip-listed
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Chemical/drug state: yayo high, drunk" in out
  # Body-change line still emits the bionic but excludes the highs.
  assert "Visible implants/injuries/body changes: archotech eye" in out
  assert "yayo high" not in (
    [ln for ln in out.splitlines()
     if ln.startswith("Visible implants")][0]
  )


def test_chemical_state_line_omitted_when_no_highs():
  pawn = PawnRecord(
    pawn_id="601",
    name_full="Sober Sam",
    label="Sober",
    role="colonist",
    hediffs=(Hediff("ArchotechEye"),),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Chemical/drug state:" not in out


def test_inspiration_renders_def_name_when_no_mod_data():
  pawn = PawnRecord(
    pawn_id="500",
    name_full="Inspire Dee",
    label="Inspire",
    role="colonist",
    inspiration="Inspired_Taming",
  )
  out = render_portrait(pawn, None, include_instruction=False)
  # Falls back to humanised def-name suffix, so the inspiration def
  # and its slug both appear with the standard dash separator.
  assert "Inspiration: Inspired_Taming" in out


def test_inspiration_renders_mod_description_when_available():
  pawn = PawnRecord(
    pawn_id="501",
    name_full="Inspire Dee",
    label="Inspire",
    role="colonist",
    inspiration="Frenzy_Shoot",
  )
  descriptions = {"Frenzy_Shoot": "A wild-eyed surge of ranged focus."}
  out = render_portrait(
    pawn, None, include_instruction=False,
    def_descriptions=descriptions,
  )
  assert (
    "Inspiration: Frenzy_Shoot - A wild-eyed surge of ranged focus."
    in out
  )


def test_inspiration_omitted_when_pawn_has_no_inspiration():
  pawn = PawnRecord(
    pawn_id="502",
    name_full="Plain",
    label="Plain",
    role="colonist",
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Inspiration:" not in out


def test_baby_carrier_marked_empty_when_no_infant():
  pawn = PawnRecord(
    pawn_id="400",
    name_full="Empty Cradle",
    label="Empty",
    role="colonist",
    apparel=(
      ApparelItem("Apparel_BabyCarrier", stuff="WoolAlpaca"),
      ApparelItem("SBC_BabyCarrier"),  # modded variant
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  utility_line = [
    ln for ln in out.splitlines() if ln.startswith("Utility belts/gear:")
  ][0]
  assert "(alpaca wool, empty)" in utility_line  # vanilla carrier
  assert "sbc baby carrier (empty)" in utility_line  # modded carrier
  assert "Carrying infant in arms:" not in out


def test_baby_carrier_not_marked_empty_when_carrying_infant():
  pawn = PawnRecord(
    pawn_id="401",
    name_full="With Baby",
    label="With Baby",
    role="colonist",
    apparel=(
      ApparelItem("Apparel_BabyCarrier", stuff="WoolAlpaca"),
    ),
    carried_infant=CarriedInfant(
      pawn_id="Human123", name="Tot", bio_age=0.4,
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  utility_line = [
    ln for ln in out.splitlines() if ln.startswith("Utility belts/gear:")
  ][0]
  # Carrier is occupied -> no "empty" marker. Material qualifier
  # still appears alone.
  assert "(alpaca wool)" in utility_line
  assert "empty" not in utility_line
  assert "Carrying infant in arms: Tot (infant, age 0.4)" in out


def test_carrying_infant_line_omitted_when_none():
  pawn = PawnRecord(
    pawn_id="402",
    name_full="Solo",
    label="Solo",
    role="colonist",
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Carrying infant in arms:" not in out


def test_carrying_infant_falls_back_to_pawn_id_when_unresolved():
  pawn = PawnRecord(
    pawn_id="403",
    name_full="Unknown Carry",
    label="Unknown Carry",
    role="colonist",
    carried_infant=CarriedInfant(pawn_id="Human999"),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Carrying infant in arms: Human999 (infant)" in out


def test_condition_label_surfaces_in_apparel_qualifier():
  pawn = PawnRecord(
    pawn_id="300",
    name_full="Worn Out",
    label="Worn Out",
    role="colonist",
    apparel=(
      # Pristine: omitted from qualifier.
      ApparelItem("Apparel_CollarShirt", health=95, max_health=100),
      # 0.6 ratio: "worn".
      ApparelItem("Apparel_PowerArmor", health=180, max_health=300),
      # 0.3 ratio: "battered".
      ApparelItem("Apparel_Cape", health=60, max_health=200),
      # 0.1 ratio: "ruined".
      ApparelItem("Apparel_Bandolier", health=10, max_health=100),
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  armor_line = [
    ln for ln in out.splitlines() if ln.startswith("Worn armor/clothing:")
  ][0]
  utility_line = [
    ln for ln in out.splitlines() if ln.startswith("Utility belts/gear:")
  ][0]
  # Pristine item has no qualifier appended.
  assert "collar shirt (" not in armor_line
  # Bandolier is in the utility bucket.
  assert "worn" in armor_line       # power armor
  assert "battered" in armor_line   # cape
  assert "ruined" in utility_line   # bandolier


def test_condition_label_surfaces_on_weapon_qualifier():
  pawn = PawnRecord(
    pawn_id="301",
    name_full="Tired Trigger",
    label="Tired",
    role="colonist",
    equipment=(
      Weapon("Gun_AssaultRifle", health=40, max_health=100),
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  weapon_line = [
    ln for ln in out.splitlines() if ln.startswith("Wielded weapon:")
  ][0]
  assert "battered" in weapon_line


def test_portrait_apparel_qualifier_omitted_when_no_signal():
  pawn = PawnRecord(
    pawn_id="101",
    name_full="No Stuff",
    label="No Stuff",
    role="colonist",
    apparel=(ApparelItem("Apparel_BasicShirt"),),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  # No qualifier means no bracketed segment on the bullet line and no
  # parenthesised qualifier on the inline summary item. Without
  # mod-aware labels the def name humanises to "basic shirt".
  assert "- basic shirt: basic shirt" in out
  assert "basic shirt (" not in out


def test_portrait_omits_missing_fields():
  bare = PawnRecord(
    pawn_id="1",
    name_full="Jane Smith",
    label="Jane",
    role="colonist",
  )
  out = render_portrait(bare, None, include_instruction=False)
  assert "Hair style:" not in out
  assert "Apparel visual descriptions:" not in out
  assert "Ideology/culture:" not in out
  assert "Colony/environment:" not in out


def test_portrait_instruction_appended_when_requested():
  out = render_portrait(_sample_pawn(), _map(), include_instruction=True)
  assert SINGLE_PROMPT_INSTRUCTION in out
  assert out.index("[/PORTRAIT SUBJECT]") < out.index(
    SINGLE_PROMPT_INSTRUCTION
  )


def test_visible_gene_emerges_in_block():
  pawn = PawnRecord(
    pawn_id="2",
    name_full="Sam Roe",
    label="Sam",
    role="colonist",
    genes=(Gene("Fangs"), Gene("Beauty_Beautiful")),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  # Without mod-aware labels, genes humanise from their def names;
  # the downstream LLM does the visual translation step.
  assert "fangs" in out
  assert "beauty beautiful" in out


def test_genes_use_mod_aware_label_when_provided():
  pawn = PawnRecord(
    pawn_id="2b",
    name_full="Sam Roe",
    label="Sam",
    role="colonist",
    genes=(Gene("Fangs"), Gene("Beauty_Beautiful")),
  )
  labels = {"Fangs": "fangs", "Beauty_Beautiful": "beautiful"}
  out = render_portrait(
    pawn, None, include_instruction=False, def_labels=labels
  )
  assert "Visible genes/body traits: fangs, beautiful" in out


def test_visible_hediff_emerges_archotech():
  pawn = PawnRecord(
    pawn_id="3",
    name_full="Mrs. Smith",
    label="Mrs. Smith",
    role="colonist",
    hediffs=(
      Hediff("ArchotechEye", body_part="left eye"),
      Hediff("ImmunityToFlu"),  # ignored pattern (skip-list)
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  # Humanised def name; skip-list still drops Immunity* hediffs.
  assert "archotech eye (left eye)" in out
  assert "ImmunityToFlu" not in out


def test_family_block_structure():
  focus = _sample_pawn()
  spouse = PawnRecord(
    pawn_id="50",
    name_full="Jane Doe",
    label="Jane",
    role="colonist",
    gender="Female",
    bio_age=27,
    xenotype="Baseliner",
    hair_color=RGBA(0.45, 0.30, 0.18, 1.0),
  )
  child = PawnRecord(
    pawn_id="51",
    name_full="Tim Doe",
    label="Tim",
    role="colonist",
    gender="Male",
    bio_age=6,
    xenotype="Baseliner",
  )
  members = [
    (Relation("Spouse", "50"), spouse),
    (Relation("Child", "51"), child),
  ]
  out = render_family(focus, members, _map(), include_instruction=True)
  assert "[FAMILY PORTRAIT SUBJECT]" in out
  assert "Focus pawn: John" in out
  assert "Shared ideology/culture: Reclaimed Path" in out
  assert "Shared environment:" in out
  assert "Family/direct relations from focus pawn:" in out
  assert "- Spouse: Jane" in out
  assert "- Child: Tim" in out
  assert "Family members:" in out
  assert "[PERSON]" in out
  assert "Relation to focus pawn: Spouse" in out
  assert "Head and face: hair color" in out or "Head and face:" in out
  assert FAMILY_PROMPT_INSTRUCTION in out
  assert "[/FAMILY PORTRAIT SUBJECT]" in out


def test_personality_falls_back_to_backstory_when_mod_absent():
  pawn = PawnRecord(
    pawn_id="9",
    name_full="Pat Roe",
    label="Pat",
    role="colonist",
    backstory_child="Slum kid",
    backstory_adult="Imperial spy",
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Personality/expression: childhood: Slum kid" in out
  assert "adulthood: Imperial spy" in out


def test_personality_uses_rimtalk_text_when_present():
  pawn = PawnRecord(
    pawn_id="10",
    name_full="Pat Roe",
    label="Pat",
    role="colonist",
    personality="Pat is curt, methodical, and impossible to surprise.",
    backstory_child="Slum kid",
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Pat is curt, methodical" in out
  # Backstory must not also be concatenated when RimTalk text is set.
  assert "childhood: Slum kid" not in out


def test_personality_omitted_when_mod_absent_and_no_backstory():
  pawn = PawnRecord(
    pawn_id="11",
    name_full="Pat Roe",
    label="Pat",
    role="colonist",
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Personality/expression:" not in out


def test_gradient_line_omitted_when_mod_absent():
  pawn = PawnRecord(
    pawn_id="12",
    name_full="Pat Roe",
    label="Pat",
    role="colonist",
    hair_color=RGBA(0.2, 0.2, 0.2, 1.0),
    gradient_hair=None,
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Hair gradient:" not in out


def test_gradient_line_omitted_when_mod_present_but_disabled():
  pawn = PawnRecord(
    pawn_id="13",
    name_full="Pat Roe",
    label="Pat",
    role="colonist",
    hair_color=RGBA(0.2, 0.2, 0.2, 1.0),
    gradient_hair=GradientHair(enabled=False, color_b=None, mask=None),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Hair gradient:" not in out


def test_unknown_xenotype_emits_def_name_only_when_no_mod_data():
  pawn = PawnRecord(
    pawn_id="14",
    name_full="Pat Roe",
    label="Pat",
    role="colonist",
    xenotype="ModdedXenotype",
  )
  out = render_portrait(pawn, None, include_instruction=False)
  # No labels/descriptions threaded: just the def name. The previous
  # "custom xenotype" curated hint was retired with the curated tables.
  assert "Race/xenotype: ModdedXenotype" in out


def test_xenotype_renders_mod_aware_description_when_provided():
  pawn = PawnRecord(
    pawn_id="14b",
    name_full="Pat Roe",
    label="Pat",
    role="colonist",
    xenotype="Sanguophage",
  )
  descriptions = {
    "Sanguophage": "an ageless transhuman with vampiric traits",
  }
  out = render_portrait(
    pawn, None, include_instruction=False,
    def_descriptions=descriptions,
  )
  assert (
    "Race/xenotype: Sanguophage - "
    "an ageless transhuman with vampiric traits"
  ) in out


def test_royal_title_renders_label_override_when_provided():
  pawn = PawnRecord(
    pawn_id="200",
    name_full="No Bil",
    label="No Bil",
    role="colonist",
    royal_titles=(
      RoyalTitle(
        def_name="Count",
        faction_id="Faction_7",
        faction_name="Faction Alpha",
      ),
    ),
  )
  labels = {"Count": "archon"}
  out = render_portrait(
    pawn, None, include_instruction=False, def_labels=labels
  )
  assert (
    "Royal title: Count - archon, of Faction Alpha" in out
  )


def test_royal_title_falls_back_to_def_name_without_labels():
  pawn = PawnRecord(
    pawn_id="201",
    name_full="No Bil",
    label="No Bil",
    role="colonist",
    royal_titles=(
      RoyalTitle(
        def_name="Knight",
        faction_id="Faction_7",
        faction_name="Faction Alpha",
      ),
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Royal title: Knight, of Faction Alpha" in out


def test_royal_title_omitted_when_pawn_has_no_titles():
  pawn = PawnRecord(
    pawn_id="202",
    name_full="Plain Pawn",
    label="Plain",
    role="colonist",
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "Royal title:" not in out


def test_multiple_royal_titles_render_semicolon_joined():
  pawn = PawnRecord(
    pawn_id="203",
    name_full="Bi Lateral",
    label="Bi",
    role="colonist",
    royal_titles=(
      RoyalTitle(def_name="Count", faction_name="Empire A"),
      RoyalTitle(def_name="Baron", faction_name="Empire B"),
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert (
    "Royal title: Count, of Empire A; Baron, of Empire B" in out
  )


def test_xenotype_falls_back_to_xenogene_list_when_no_description():
  pawn = PawnRecord(
    pawn_id="14c",
    name_full="Vam Pyre",
    label="Vam",
    role="colonist",
    xenotype="Sanguophage",
    genes=(
      Gene("Fangs", is_xenogene=True),
      Gene("Bloodfeeder", is_xenogene=True),
      Gene("Hair_DarkBlack", is_xenogene=False),
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  # No descriptions/labels threaded -> gene-list fallback engages and
  # enumerates xenogenes only; the endogene is excluded.
  assert "Race/xenotype: Sanguophage - fangs, bloodfeeder" in out


def test_family_empty_members_still_emits_envelope():
  focus = PawnRecord(
    pawn_id="42",
    name_full="John Doe",
    label="John",
    role="colonist",
  )
  out = render_family(focus, [], None, include_instruction=False)
  assert "[FAMILY PORTRAIT SUBJECT]" in out
  assert "Focus pawn: John" in out
  assert "[PERSON]" not in out
  assert "[/FAMILY PORTRAIT SUBJECT]" in out
