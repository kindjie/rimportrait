"""Integration tests against a real .rws save.

These tests run against whatever save is dropped at the repo root as
`sample.rws`. They never hard-code pawn names or save-specific details
- selectors find a representative colonist by structural property
(has gradient hair, has direct family relations, etc.) so the suite
works for anyone's save.

Tests skip cleanly when no sample is present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rimsave import (
  family_members,
  iter_colonists,
  load_save,
  map_context_for,
)
from rimsave.records import PawnRecord
from rimportrait.render import render_family, render_portrait


SAVE_PATH = Path(__file__).resolve().parents[3] / "sample.rws"

requires_save = pytest.mark.skipif(
  not SAVE_PATH.exists(),
  reason="sample.rws not present; drop a RimWorld save at the repo root",
)


@pytest.fixture(scope="module")
def save():
  return load_save(SAVE_PATH)


def _first_with_gradient_hair(save) -> PawnRecord | None:
  for p in iter_colonists(save):
    if p.gradient_hair is not None and p.gradient_hair.enabled:
      return p
  return None


def _first_with_family(save) -> PawnRecord | None:
  family_defs = {
    "Spouse", "Lover", "Fiance",
    "Parent", "Child", "Sibling",
  }
  for p in iter_colonists(save):
    if any(r.def_name in family_defs for r in p.relations):
      return p
  return None


@requires_save
def test_save_indices_populated(save):
  assert len(save.pawns_by_id) > 0
  assert len(save.ideos_by_id) > 0


@requires_save
def test_colonists_extracted(save):
  colonists = list(iter_colonists(save))
  assert len(colonists) > 0
  for c in colonists[:5]:
    assert c.label, "colonist should have a usable label"
    assert c.role == "colonist"
    assert c.race == "Human" or c.xenotype is not None


@requires_save
def test_render_runs_against_real_pawns(save):
  colonists = list(iter_colonists(save))
  for c in colonists[:10]:
    block = render_portrait(
      c, map_context_for(save, c), include_instruction=False
    )
    assert "[PORTRAIT SUBJECT]" in block
    assert "[/PORTRAIT SUBJECT]" in block
    assert "Name:" in block


@requires_save
def test_gradient_hair_extracted_when_present(save):
  pawn = _first_with_gradient_hair(save)
  if pawn is None:
    pytest.skip("no colonist with active GradientHair in this save")
  gh = pawn.gradient_hair
  assert gh is not None
  assert gh.enabled is True
  # When enabled the mod stores at least one of colorB or mask.
  assert gh.color_b is not None or gh.mask is not None


@requires_save
def test_family_render_runs(save):
  focus = _first_with_family(save)
  if focus is None:
    pytest.skip("no colonist with direct family relations in this save")
  members = family_members(save, focus)
  block = render_family(
    focus, members, map_context_for(save, focus),
    include_instruction=False,
  )
  assert "[FAMILY PORTRAIT SUBJECT]" in block
  assert f"Focus pawn: {focus.label}" in block
  assert "[/FAMILY PORTRAIT SUBJECT]" in block


@requires_save
def test_ideo_resolved_for_some_colonist(save):
  for p in iter_colonists(save):
    if p.ideo is not None:
      assert p.ideo.name
      return
  pytest.skip("no colonist with an ideology in this save")
