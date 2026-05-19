from __future__ import annotations

from rimportrait.translate.stuff import describe_stuff


def test_leather_variants_humanised():
  assert describe_stuff("Leather_Plain") == "plain leather"
  assert describe_stuff("Leather_Patch") == "patch leather"
  assert describe_stuff("Leather_Human") == "human leather"
  assert describe_stuff("Leather_Wolf") == "wolf leather"


def test_wool_variants_humanised():
  assert describe_stuff("WoolSheep") == "sheep wool"
  assert describe_stuff("WoolAlpaca") == "alpaca wool"
  assert describe_stuff("WoolMegasloth") == "megasloth wool"


def test_blocks_stone_variants():
  assert describe_stuff("BlocksLimestone") == "limestone stone blocks"
  assert describe_stuff("BlocksGranite") == "granite stone blocks"


def test_bare_materials_camel_split():
  assert describe_stuff("Plasteel") == "plasteel"
  assert describe_stuff("Steel") == "steel"
  assert describe_stuff("DevilstrandCloth") == "devilstrand cloth"


def test_none_or_empty():
  assert describe_stuff(None) is None
  assert describe_stuff("") is None
