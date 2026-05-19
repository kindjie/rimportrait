from __future__ import annotations

from rimsave.records import Hediff
from rimportrait.translate.hediffs import (
  describe_chemical_state,
  describe_hediffs,
  describe_pilot_state,
  describe_shambler_state,
  is_drug_high,
  is_pilot_state,
  is_shambler_state,
)


def test_is_drug_high_recognises_vanilla_high_suffix():
  assert is_drug_high("YayoHigh")
  assert is_drug_high("GoJuiceHigh")
  assert is_drug_high("LuciferiumHigh")
  assert is_drug_high("WakeUpHigh")
  assert is_drug_high("SmokeleafHigh")
  assert is_drug_high("PenoxycylineHigh")
  assert is_drug_high("AmbrosiaHigh")


def test_is_drug_high_recognises_drunk_and_modded():
  assert is_drug_high("Drunk")
  assert is_drug_high("HighOnSomethingModded")


def test_is_drug_high_rejects_non_drug_defs():
  # Non-hediff defs (memes / pawnkinds) happen to start with "High",
  # but this predicate is only called on hediffs so the rejection
  # here matters mostly as a guard against accidental cross-use.
  assert not is_drug_high("HighCulture")
  assert not is_drug_high("HighLife")
  assert not is_drug_high("ArchotechEye")
  assert not is_drug_high("BionicArm")
  assert not is_drug_high("PsychiteTolerance")


def test_describe_hediffs_excludes_drug_highs():
  out = describe_hediffs((
    Hediff("YayoHigh"),
    Hediff("ArchotechEye", body_part="left eye"),
    Hediff("Drunk"),
  ))
  assert out == ["archotech eye (left eye)"]


def test_describe_chemical_state_returns_drug_highs_only():
  out = describe_chemical_state((
    Hediff("YayoHigh"),
    Hediff("ArchotechEye", body_part="left eye"),
    Hediff("Drunk"),
    Hediff("PsychiteTolerance"),  # filtered by skip-list
  ))
  assert out == ["yayo high", "drunk"]


def test_describe_chemical_state_threads_labels():
  out = describe_chemical_state(
    (Hediff("YayoHigh"),),
    labels={"YayoHigh": "high on yayo"},
  )
  assert out == ["high on yayo"]


def test_is_shambler_state_recognises_vanilla_and_corpse():
  assert is_shambler_state("Shambler")
  assert is_shambler_state("ShamblerCorpse")
  assert not is_shambler_state("ArchotechEye")
  assert not is_shambler_state("BionicArm")


def test_describe_shambler_state_returns_shambler_only():
  out = describe_shambler_state((
    Hediff("Shambler"),
    Hediff("ArchotechEye", body_part="left eye"),
    Hediff("YayoHigh"),
  ))
  assert out == ["shambler"]


def test_describe_hediffs_excludes_shambler_state():
  out = describe_hediffs((
    Hediff("Shambler"),
    Hediff("ArchotechEye", body_part="left eye"),
  ))
  assert out == ["archotech eye (left eye)"]


def test_describe_shambler_state_threads_labels():
  out = describe_shambler_state(
    (Hediff("Shambler"),),
    labels={"Shambler": "reanimated shambler"},
  )
  assert out == ["reanimated shambler"]


def test_is_pilot_state_recognises_pilot_assistant():
  assert is_pilot_state("PilotAssistant")
  assert is_pilot_state("PilotImplantModded")
  assert not is_pilot_state("ArchotechEye")
  assert not is_pilot_state("BionicArm")


def test_describe_pilot_state_returns_pilot_only():
  out = describe_pilot_state((
    Hediff("PilotAssistant"),
    Hediff("ArchotechEye", body_part="left eye"),
    Hediff("Shambler"),
  ))
  assert out == ["pilot assistant"]


def test_describe_hediffs_excludes_pilot_state():
  out = describe_hediffs((
    Hediff("PilotAssistant"),
    Hediff("BionicArm"),
  ))
  assert out == ["bionic arm"]


def test_describe_pilot_state_threads_labels():
  out = describe_pilot_state(
    (Hediff("PilotAssistant"),),
    labels={"PilotAssistant": "pilot assistant"},
  )
  assert out == ["pilot assistant"]
