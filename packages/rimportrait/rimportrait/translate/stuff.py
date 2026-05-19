"""RimWorld stuff (material) def -> short visual phrase.

Stuff defs in saves are bare names like ``Leather_Plain``, ``WoolAlpaca``,
``BlocksLimestone``, ``Plasteel``. We humanise them into prompt-friendly
phrases ("plain leather", "alpaca wool", "limestone stone blocks").
"""

from __future__ import annotations


def describe_stuff(stuff: str | None) -> str | None:
  if not stuff:
    return None
  if stuff.startswith("Leather_"):
    return f"{_humanise(stuff[len('Leather_'):])} leather"
  if stuff.startswith("Wool"):
    return f"{_humanise(stuff[len('Wool'):])} wool"
  if stuff.startswith("Blocks"):
    return f"{_humanise(stuff[len('Blocks'):])} stone blocks"
  return _humanise(stuff)


def _humanise(s: str) -> str:
  acc: list[str] = []
  for i, ch in enumerate(s):
    if i > 0 and ch.isupper() and not s[i - 1].isupper():
      acc.append(" ")
    acc.append(ch)
  return "".join(acc).lower()
