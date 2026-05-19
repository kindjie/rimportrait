from __future__ import annotations

from rimsave.records import Gene
from rimportrait.translate.xenotype import describe_xenotype


def test_none_xenotype_returns_none():
  assert describe_xenotype(None) is None
  assert describe_xenotype("") is None


def test_description_wins_over_label_and_gene_fallback():
  out = describe_xenotype(
    "Sanguophage",
    descriptions={"Sanguophage": "ageless predatory transhuman"},
    labels={"Sanguophage": "vampire"},
    genes=(Gene("Fangs", is_xenogene=True),),
  )
  assert out == "ageless predatory transhuman"


def test_label_used_when_no_description():
  out = describe_xenotype(
    "Sanguophage",
    labels={"Sanguophage": "vampire"},
    genes=(Gene("Fangs", is_xenogene=True),),
  )
  assert out == "vampire"


def test_gene_list_fallback_uses_xenogenes_only():
  out = describe_xenotype(
    "Sanguophage",
    genes=(
      Gene("Fangs", is_xenogene=True),
      Gene("Bloodfeeder", is_xenogene=True),
      Gene("Hair_DarkBlack", is_xenogene=False),
      Gene("Body_Standard", is_xenogene=False),
    ),
  )
  assert out == "fangs, bloodfeeder"


def test_gene_list_fallback_threads_labels():
  out = describe_xenotype(
    "Sanguophage",
    labels={"Bloodfeeder": "blood-feeder"},
    genes=(
      Gene("Fangs", is_xenogene=True),
      Gene("Bloodfeeder", is_xenogene=True),
    ),
  )
  assert out == "fangs, blood-feeder"


def test_baseliner_with_no_xenogenes_falls_back_to_humanised_slug():
  # Baseliner pawns carry only endogenes; the xenogene-list fallback
  # returns nothing, so the helper falls through to humanise(name).
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
