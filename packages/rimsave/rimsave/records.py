"""Typed records passed between extract -> translate -> render layers.

Pure data containers. Extract fills them from .rws XML; render reads
them. Translation helpers operate on fields (xenotype name, RGBA, etc.)
so records stay free of game-specific phrasing logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from .colors import RGBA


@dataclass(frozen=True)
class GradientHair:
  enabled: bool
  color_b: RGBA | None
  mask: str | None


@dataclass(frozen=True)
class ApparelItem:
  def_name: str
  label: str | None = None
  stuff: str | None = None
  color: RGBA | None = None
  style_def: str | None = None
  health: int | None = None
  max_health: int | None = None


@dataclass(frozen=True)
class Weapon:
  def_name: str
  label: str | None = None
  stuff: str | None = None
  color: RGBA | None = None
  style_def: str | None = None
  health: int | None = None
  max_health: int | None = None


@dataclass(frozen=True)
class InventoryItem:
  def_name: str
  stack_count: int = 1
  stuff: str | None = None


@dataclass(frozen=True)
class Hediff:
  def_name: str
  label: str | None = None
  body_part: str | None = None


@dataclass(frozen=True)
class Gene:
  def_name: str
  label: str | None = None
  is_xenogene: bool = False


@dataclass(frozen=True)
class Relation:
  def_name: str
  other_pawn_id: str
  opinion: int | None = None


@dataclass(frozen=True)
class RoyalTitle:
  def_name: str
  faction_id: str | None = None
  faction_name: str | None = None


@dataclass(frozen=True)
class CarriedInfant:
  pawn_id: str
  name: str | None = None
  bio_age: float | None = None


@dataclass(frozen=True)
class BondedAnimal:
  """Animal pawn bonded to a colonist via a Bond direct-relation.

  Species comes from the animal pawn's ``<def>`` (e.g. Wolf_Timber,
  Thrumbo, Warg). The renderer threads this through the mod-aware
  label index so modded animal species get clean labels.
  """
  def_name: str
  name: str | None = None
  gender: str | None = None
  bio_age: float | None = None


@dataclass(frozen=True)
class CreepJoinerState:
  """Anomaly creepjoiner quest state.

  Pawns from a CreepJoiner quest carry latent benefit/downside/
  rejection/aggressive options; the active form (DealMaker, etc.)
  is the visible persona. ``triggered_downside`` and ``has_left``
  reflect whether the dark side has fired and whether they've left
  the colony.
  """
  form: str | None = None
  benefit: str | None = None
  downside: str | None = None
  rejection: str | None = None
  aggressive: str | None = None
  triggered_downside: bool = False
  has_left: bool = False


@dataclass(frozen=True)
class IdeoRecord:
  name: str
  color: RGBA | None = None
  apparel_color: RGBA | None = None
  description: str | None = None
  style_summary: str | None = None
  # (category, priority) pairs sorted by priority descending. Highest
  # priority is the dominant visual aesthetic the LLM should weight.
  style_categories: tuple[tuple[str, int], ...] = ()
  memes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MapContext:
  biome: str | None = None
  weather: str | None = None
  wealth: float | None = None
  population: int | None = None
  active_threats: tuple[str, ...] = ()


@dataclass(frozen=True)
class PawnRecord:
  pawn_id: str
  name_full: str
  nickname: str | None = None
  label: str | None = None
  role: str = "unknown"
  gender: str | None = None
  bio_age: float | None = None
  chrono_age: float | None = None
  xenotype: str | None = None
  race: str | None = None
  traits: tuple[str, ...] = ()
  backstory_child: str | None = None
  backstory_adult: str | None = None
  personality: str | None = None
  mood: str | None = None
  current_job: str | None = None
  location: str | None = None
  hair_def: str | None = None
  hair_label: str | None = None
  hair_texture_path: str | None = None
  hair_color: RGBA | None = None
  beard_def: str | None = None
  beard_label: str | None = None
  beard_color: RGBA | None = None
  face_tattoo: str | None = None
  body_tattoo: str | None = None
  skin_color: RGBA | None = None
  eye_color: RGBA | None = None
  favorite_color: str | None = None
  gradient_hair: GradientHair | None = None
  genes: tuple[Gene, ...] = ()
  hediffs: tuple[Hediff, ...] = ()
  apparel: tuple[ApparelItem, ...] = ()
  equipment: tuple[Weapon, ...] = ()
  inventory: tuple[InventoryItem, ...] = ()
  ideo: IdeoRecord | None = None
  relations: tuple[Relation, ...] = ()
  royal_titles: tuple[RoyalTitle, ...] = ()
  carried_infant: CarriedInfant | None = None
  inspiration: str | None = None
  # Mech ThingDef names this pawn commands as a mechanitor, in the
  # save's control-group order. Empty when the pawn is not a
  # mechanitor or has no assigned mechs.
  commanded_mechs: tuple[str, ...] = ()
  # Ability defs (psycasts + xenotype abilities + learned). Order is
  # save order. Renderer threads these through mod-aware labels.
  abilities: tuple[str, ...] = ()
  # Current psyfocus in [0..1] when meaningful (only emitted when a
  # psycaster hediff is present). None otherwise.
  psyfocus: float | None = None
  creepjoiner: CreepJoinerState | None = None
  # Tree/dryad/etc. ``connectedThings`` resolved to their ThingDef
  # names so the renderer can label them via the mod-aware def
  # index. Empty when the pawn has no active connection.
  connections: tuple[str, ...] = ()
  # Animals bonded to this pawn via the ``Bond`` direct-relation.
  bonded_animals: tuple[BondedAnimal, ...] = ()
  # Raw curLevel values (0..1) for the portrait-visible physical
  # needs. None when the need isn't tracked on this pawn (e.g.
  # Deathrest only exists on sanguophages).
  food_need: float | None = None
  rest_need: float | None = None
  deathrest_need: float | None = None
