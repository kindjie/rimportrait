from __future__ import annotations

from rimportrait.colors import RGBA
from rimportrait.records import (
  ApparelItem,
  Gene,
  GradientHair,
  Hediff,
  IdeoRecord,
  InventoryItem,
  MapContext,
  PawnRecord,
  Relation,
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
  assert "Hair style: SD Zayne (thick side-swept voluminous hair)" in out
  assert "Hair texture path: Hairs/fluffySidePartS" in out
  assert "very dark charcoal / near-black" in out


def test_portrait_includes_gradient_hair():
  out = render_portrait(_sample_pawn(), _map(), include_instruction=False)
  assert "Hair gradient: enabled" in out
  assert "bright cyan / aqua / turquoise" in out
  assert "mid-to-tip gradient region" in out


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
  assert "light purple / pale violet / muted lavender" in out


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
  # Wielded weapon is on its own labeled line; pack items appear under
  # the Carrying line; the two must not mix.
  assert "Wielded weapon: modern assault rifle" in out
  assert (
    "Carrying (pack/inventory): 3× simple meal, "
    "12× high-explosive mortar shell"
  ) in out
  weapon_line = [
    ln for ln in out.splitlines() if ln.startswith("Wielded weapon:")
  ][0]
  assert "simple meal" not in weapon_line
  assert "mortar shell" not in weapon_line


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
  # Armor/clothing: shirt + power armor + helmet + cape.
  assert "buttoned collared shirt" in armor_line
  assert "heavy powered combat armor" in armor_line
  assert "prestige marine helmet" in armor_line
  assert "cape" in armor_line
  # Utility: bandolier, gunlink, baby carrier (incl. modded SBC_*).
  assert "bandolier" in utility_line
  assert "targeting visor" in utility_line
  assert "baby carrier" in utility_line
  # No cross-contamination between buckets.
  assert "bandolier" not in armor_line
  assert "collared shirt" not in utility_line
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
  # parenthesised qualifier on the inline summary item.
  assert "- basic shirt: plain practical shirt" in out
  assert "plain practical shirt (" not in out


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
  assert "visible fangs" in out
  assert "strikingly beautiful features" in out


def test_visible_hediff_emerges_archotech():
  pawn = PawnRecord(
    pawn_id="3",
    name_full="Mrs. Smith",
    label="Mrs. Smith",
    role="colonist",
    hediffs=(
      Hediff("ArchotechEye", body_part="left eye"),
      Hediff("ImmunityToFlu"),  # ignored pattern
    ),
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "luminous archotech eye" in out
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


def test_unknown_xenotype_emits_extrapolation_hint():
  pawn = PawnRecord(
    pawn_id="14",
    name_full="Pat Roe",
    label="Pat",
    role="colonist",
    xenotype="ModdedXenotype",
  )
  out = render_portrait(pawn, None, include_instruction=False)
  assert "ModdedXenotype" in out
  assert "custom xenotype" in out


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
