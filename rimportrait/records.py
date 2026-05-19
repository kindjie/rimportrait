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


@dataclass(frozen=True)
class Weapon:
  def_name: str
  label: str | None = None
  stuff: str | None = None
  color: RGBA | None = None
  style_def: str | None = None


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


@dataclass(frozen=True)
class Relation:
  def_name: str
  other_pawn_id: str
  opinion: int | None = None


@dataclass(frozen=True)
class IdeoRecord:
  name: str
  color: RGBA | None = None
  apparel_color: RGBA | None = None
  description: str | None = None
  style_summary: str | None = None


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
