"""Hediff def -> label phrase.

A hediff is anything the game models as a 'health diff' on a pawn:
implants, injuries, missing parts, diseases, tolerances. Per the
data-first principle we surface the mod-aware label of every hediff
the pawn carries; a skip-list excludes obviously-non-visual mechanical
states (immunities, tolerances, withdrawals) to bound prompt context.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..records import Hediff
from ._common import label_for


_HEDIFF_PREFIXES: tuple[str, ...] = ("Hediff_",)


# Skip-list of obviously-mechanical hediff patterns. Substring match
# so mod variants are caught alongside vanilla; allow-list shape was
# deliberately retired so modded body changes aren't dropped silently.
_IGNORED_PATTERNS: tuple[str, ...] = (
  "Immunity",
  "Tolerance",
  "Dependency",
  "Resistance",
  "Hangover",
  "Catharsis",
  "Withdrawal",
  "Pregnant",
)


def _is_ignored(def_name: str) -> bool:
  return any(p in def_name for p in _IGNORED_PATTERNS)


def describe_hediffs(
  hediffs: Iterable[Hediff],
  labels: dict[str, str] | None = None,
) -> list[str]:
  out: list[str] = []
  for h in hediffs:
    if _is_ignored(h.def_name):
      continue
    base = h.label or label_for(h.def_name, labels, _HEDIFF_PREFIXES)
    if h.body_part:
      base = f"{base} ({h.body_part})"
    out.append(base)
  return out
