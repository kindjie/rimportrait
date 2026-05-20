from __future__ import annotations

from rimsave.records import Gene
from rimportrait.translate.xenotype import describe_xenotype


def test_none_xenotype_returns_none():
  assert describe_xenotype(None) is None
  assert describe_xenotype("") is None


def test_description_wins_then_signature_is_appended():
  """Description provides the lore-level text; the per-pawn visible
  xenogene signature is appended on top so the LLM gets a concrete
  visual anchor even when the description leads with lore."""
  out = describe_xenotype(
    "Sanguophage",
    descriptions={"Sanguophage": "ageless predatory transhuman"},
    labels={"Sanguophage": "vampire"},
    genes=(Gene("Fangs", is_xenogene=True),),
  )
  assert out == (
    "ageless predatory transhuman Visible xenogene traits: fangs."
  )


def test_label_used_when_no_description_with_signature():
  out = describe_xenotype(
    "Sanguophage",
    labels={"Sanguophage": "vampire"},
    genes=(Gene("Fangs", is_xenogene=True),),
  )
  assert out == "vampire Visible xenogene traits: fangs."


def test_signature_includes_visible_xenogenes_only():
  """Only xenogenes that pass the visibility filter appear in the
  signature; endogenes (the pawn's baseline) and skip-listed
  mechanical genes are dropped. With no description threaded, the
  signature stands on its own (no duplicated humanised slug)."""
  out = describe_xenotype(
    "Sanguophage",
    genes=(
      Gene("Fangs", is_xenogene=True),
      Gene("Bloodfeeder", is_xenogene=True),  # mechanical, filtered
      Gene("Hair_DarkBlack", is_xenogene=False),  # endogene
      Gene("Body_Standard", is_xenogene=False),  # endogene
    ),
  )
  assert out == "Visible xenogene traits: fangs."


def test_signature_threads_mod_labels():
  out = describe_xenotype(
    "Sanguophage",
    labels={"Fangs": "razor fangs"},
    genes=(
      Gene("Fangs", is_xenogene=True),
    ),
  )
  # Sanguophage has a label entry (an empty one not provided), so
  # we fall through to the signature-only form.
  assert out == "Visible xenogene traits: razor fangs."


def test_baseliner_with_no_xenogenes_falls_back_to_humanised_slug():
  # Baseliner pawns carry only endogenes; no signature suffix is
  # appended because there are no xenogenes to surface.
  out = describe_xenotype(
    "Baseliner",
    genes=(
      Gene("Hair_DarkBlack", is_xenogene=False),
      Gene("Body_Standard", is_xenogene=False),
    ),
  )
  assert out == "baseliner"


def test_unknown_xenotype_with_no_genes_humanises():
  assert describe_xenotype("ModdedXenotype") == "modded xenotype"
