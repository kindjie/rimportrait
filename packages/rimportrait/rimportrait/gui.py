"""Tkinter GUI organised around the three pipeline stages.

The window stacks three cards inside a scrollable frame, with a
collapsible Account & model section at top and a collapsible log
footer at the bottom:

  1. Load save data — pick a save + pawn; renders the structured
     `[PORTRAIT SUBJECT]` block in memory and previews it.
  2. Generate prompt — preset + style note; runs the LLM polish on
     the cached block and writes the result into an editable text
     box the user can tweak before paying for an image.
  3. Generate image — output folder; runs the image model on the
     (possibly edited) prompt and shows a thumbnail.

Cards downstream gate on upstream output: changing the pawn
invalidates the prompt and image; clearing the prompt disables
the image button. Each card runs in its own background thread;
progress lines stream through `cli._STATUS_SINK` into a per-card
status label and a hidden log Text widget that auto-opens on
errors.

Entry point: `rimportrait-gui` in `pyproject.toml`. Requires the
`[gui]` extra: keyring, Pillow, platformdirs.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import threading
import time
import traceback
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from rimsave import (
  autodetect_mod_paths,
  autodetect_saves_dir,
  family_members,
  find_pawn,
  installed_rimworld_version,
  load_save,
  map_context_for,
  read_save_game_version,
)

from . import cli, llm, style
from .render import render_family, render_portrait


APP_NAME = "rimportrait"
KEYRING_SERVICE = "rimportrait"
DEFAULT_OUTPUT = Path.home() / "Pictures" / "rimportrait"

# Only RimWorld version we currently test the def index against.
TESTED_VERSION = "1.6"

# CLI provider key -> env var the underlying SDKs read.
_PROVIDER_ENV = {
  "openai": "OPENAI_API_KEY",
  "google": "GEMINI_API_KEY",
}

# Where to send the user to mint a key, one-click from the GUI.
_PROVIDER_KEY_URL = {
  "openai": "https://platform.openai.com/api-keys",
  "google": "https://aistudio.google.com/app/apikey",
}


# --- pure helpers --------------------------------------------------

@dataclass
class SaveEntry:
  path: Path
  mtime: float
  game_version: str | None = None
  untested: bool = False

  @property
  def label(self) -> str:
    age = _ago(time.time() - self.mtime)
    parts = [self.path.stem]
    if self.game_version:
      tag = f"save {_short_version(self.game_version)}"
      if self.untested:
        tag += " ⚠"
      parts.append(f"— {tag}")
    parts.append(f"({age})")
    return "  ".join(parts)


def _short_version(v: str) -> str:
  head = v.split(" ", 1)[0]
  bits = head.split(".")
  if len(bits) >= 2 and all(b.isdigit() for b in bits[:2]):
    return f"{bits[0]}.{bits[1]}"
  return v


def _major_minor(v: str | None) -> tuple[str, str] | None:
  if not v:
    return None
  head = v.split(" ", 1)[0]
  bits = head.split(".")
  if len(bits) >= 2 and all(b.isdigit() for b in bits[:2]):
    return (bits[0], bits[1])
  return None


def _ago(seconds: float) -> str:
  if seconds < 60:
    return "just now"
  if seconds < 3600:
    n = int(seconds // 60)
    return "1 min ago" if n == 1 else f"{n} min ago"
  if seconds < 86400:
    n = int(seconds // 3600)
    return "1 hr ago" if n == 1 else f"{n} hr ago"
  n = int(seconds // 86400)
  return "1 day ago" if n == 1 else f"{n} days ago"


def _config_path() -> Path:
  try:
    from platformdirs import user_config_dir
    base = Path(user_config_dir(APP_NAME))
  except ImportError:
    base = Path.home() / ".config" / APP_NAME
  base.mkdir(parents=True, exist_ok=True)
  return base / "config.json"


def _load_config() -> dict:
  path = _config_path()
  if not path.is_file():
    return {}
  try:
    return json.loads(path.read_text())
  except (OSError, json.JSONDecodeError):
    return {}


def _save_config(cfg: dict) -> None:
  _config_path().write_text(json.dumps(cfg, indent=2))


def _keychain_get(provider: str) -> str:
  try:
    import keyring
    return keyring.get_password(KEYRING_SERVICE, provider) or ""
  except Exception:
    return ""


def _keychain_set(provider: str, value: str) -> tuple[bool, str]:
  """Returns (ok, error_message). On macOS the first call triggers a
  Keychain auth prompt; if the user cancels or denies, the backend
  raises and we surface the real reason instead of a generic note."""
  try:
    import keyring
  except ImportError:
    return (False, "keyring package not installed (install the "
                    "[gui] extra)")
  try:
    keyring.set_password(KEYRING_SERVICE, provider, value)
    return (True, "")
  except Exception as e:
    return (False, f"{type(e).__name__}: {e}")


_ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def _asset_path(name: str) -> Path | None:
  """Resolve a packaged asset by name.

  Assets ship inside the package (``rimportrait/assets/``) so they
  travel with the wheel and are picked up by PyInstaller via the
  package collector — no per-bundle `datas=` entry needed."""
  p = _ASSETS_DIR / name
  return p if p.is_file() else None


def _logo_path() -> Path | None:
  """Wordmark image for the GUI header (wider-than-tall)."""
  return _asset_path("logo.png")


def _icon_path() -> Path | None:
  """Square icon image for window / dock badge."""
  return _asset_path("icon.png") or _logo_path()


def _list_saves(saves_dir: Path) -> list[SaveEntry]:
  if not saves_dir.is_dir():
    return []
  entries: list[SaveEntry] = []
  for child in saves_dir.iterdir():
    if child.suffix.lower() != ".rws" or not child.is_file():
      continue
    gv = read_save_game_version(child)
    mm = _major_minor(gv)
    untested = bool(mm and ".".join(mm) != TESTED_VERSION)
    entries.append(SaveEntry(
      path=child, mtime=child.stat().st_mtime,
      game_version=gv, untested=untested,
    ))
  entries.sort(key=lambda e: e.mtime, reverse=True)
  return entries


_ANSI_RE = None


def _strip_ansi(s: str) -> str:
  global _ANSI_RE
  if _ANSI_RE is None:
    import re
    _ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
  return _ANSI_RE.sub("", s)


def _slug(s: str) -> str:
  return cli._slug(s)


# --- widgets -------------------------------------------------------

class _Collapsible(ttk.Frame):
  """Header label + arrow that hides/shows a body frame.

  Tk lacks a native disclosure widget; this is the minimal version
  the cards use for the data-block preview, the Account section,
  and the log footer."""

  def __init__(
    self, parent, title: str, *, open: bool = False,
  ) -> None:
    super().__init__(parent)
    self._open = open
    self._title = title
    self._btn = ttk.Button(
      self, command=self.toggle, style="Toolbutton",
    )
    self._btn.pack(fill="x", anchor="w")
    self.body = ttk.Frame(self)
    self._refresh_button()
    if open:
      self.body.pack(fill="x", expand=True, padx=(16, 0), pady=(2, 0))

  def _refresh_button(self) -> None:
    arrow = "▾" if self._open else "▸"
    self._btn.configure(text=f"{arrow} {self._title}")

  def set_title(self, title: str) -> None:
    self._title = title
    self._refresh_button()

  def toggle(self) -> None:
    self._open = not self._open
    if self._open:
      self.body.pack(fill="x", expand=True, padx=(16, 0), pady=(2, 0))
    else:
      self.body.forget()
    self._refresh_button()

  def open(self) -> None:
    if not self._open:
      self.toggle()


class _ScrollableFrame(ttk.Frame):
  """Vertically scrollable container. Place children in `.inner`."""

  def __init__(self, parent) -> None:
    super().__init__(parent)
    self._canvas = tk.Canvas(self, highlightthickness=0)
    sb = ttk.Scrollbar(
      self, orient="vertical", command=self._canvas.yview,
    )
    self._canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    self._canvas.pack(side="left", fill="both", expand=True)
    self.inner = ttk.Frame(self._canvas)
    self._win = self._canvas.create_window(
      (0, 0), window=self.inner, anchor="nw",
    )
    self.inner.bind(
      "<Configure>",
      lambda _e: self._canvas.configure(
        scrollregion=self._canvas.bbox("all"),
      ),
    )
    self._canvas.bind(
      "<Configure>",
      lambda e: self._canvas.itemconfigure(self._win, width=e.width),
    )
    # Mouse-wheel scrolling. On macOS event.delta is small (~±1 per
    # notch); on Windows it's 120-per-notch; on X11 wheel events come
    # in as Button-4/Button-5 instead. Dividing macOS deltas as if
    # they were Windows-sized rounds most events to zero — that was
    # the source of the laggy feel.
    import sys as _sys
    if _sys.platform == "darwin":
      self._wheel_step = lambda d: -d
    else:
      self._wheel_step = lambda d: -int(d / 120) or (-1 if d > 0 else 1)
    self._canvas.bind_all("<MouseWheel>", self._on_wheel)
    self._canvas.bind_all(
      "<Button-4>", lambda _e: self._canvas.yview_scroll(-3, "units"),
    )
    self._canvas.bind_all(
      "<Button-5>", lambda _e: self._canvas.yview_scroll(3, "units"),
    )

  def _on_wheel(self, event) -> None:
    # Route the wheel to the right widget: a Text under the cursor
    # scrolls its own content; a Combobox popdown (which Tk doesn't
    # track via winfo_containing, raising KeyError) handles its own
    # scroll and we must NOT also scroll the canvas behind it.
    try:
      target = self._canvas.winfo_containing(event.x_root, event.y_root)
    except KeyError:
      return  # popdown / menu is open — let it handle the wheel
    step = self._wheel_step(event.delta)
    cur = target
    while cur is not None and cur is not self._canvas:
      if isinstance(cur, tk.Text):
        # Chain to the outer canvas once the Text hits its limit:
        # scrolling down (step>0) at the bottom (yview[1]==1.0),
        # or up (step<0) at the top (yview[0]==0.0).
        top, bottom = cur.yview()
        if (step > 0 and bottom >= 1.0) or (step < 0 and top <= 0.0):
          break
        cur.yview_scroll(step, "units")
        return
      cur = cur.master
    self._canvas.yview_scroll(step, "units")


def _help(parent, text: str) -> ttk.Label:
  """Inline grey one-liner under a field's label."""
  return ttk.Label(parent, text=text, foreground="#888")


# --- the App -------------------------------------------------------

class App:
  def __init__(self, root: tk.Tk) -> None:
    self.root = root
    self.cfg = _load_config()
    self.saves_dir = self._resolve_saves_dir()
    self.installed_version = installed_rimworld_version(
      autodetect_mod_paths()
    )
    self.saves: list[SaveEntry] = (
      _list_saves(self.saves_dir) if self.saves_dir else []
    )

    # Per-stage caches.
    self.selected_save: Path | None = None
    self.save_obj = None
    self.def_index = None
    self.defs_desc = None
    self.defs_label = None
    self.defs_cat = None
    self.defs_cost = None
    self.defs_tech = None
    self.defs_layer = None
    self.body_parts = None
    self.pawn_names: list[str] = []
    self.block: str | None = None
    self.block_signature: tuple | None = None
    self.prompt: str | None = None
    self.prompt_dirty = False
    self.last_image: Path | None = None
    self.preview_imgref: object | None = None

    # Per-stage worker bookkeeping.
    self.progress_q: queue.Queue[str] = queue.Queue()
    self.active_stage: str | None = None  # "card1" | "card2" | "card3"
    self._t_start: float = 0.0

    root.title("RimPortrait")
    root.geometry("780x900")
    self._apply_window_icon()

    self._build_layout()
    self._populate_saves()
    self._prefill_key()
    self._on_provider_change()  # decide whether to open Account
    # React to provider/tier flips with a fresh model-label render.
    self.provider_var.trace_add("write", self._refresh_model_labels)
    self.tier_var.trace_add("write", self._refresh_model_labels)
    self._refresh_model_labels()
    self._refresh_card2_enabled()
    self._refresh_card3_enabled()
    self._poll_log_queue()

  # ----- layout --------------------------------------------------

  def _build_layout(self) -> None:
    sf = _ScrollableFrame(self.root)
    sf.pack(fill="both", expand=True)
    container = sf.inner
    container.columnconfigure(0, weight=1)

    self._build_header(container)
    self._build_account(container)
    self._build_card1(container)
    self._build_card2(container)
    self._build_card3(container)
    self._build_log_footer(container)

  def _apply_window_icon(self) -> None:
    """Set the OS window/dock icon from docs/logo.png if present.

    Pillow does the PNG load; tk.PhotoImage natively only handles
    GIF/PNG on newer Tk but Pillow's ImageTk normalises across
    builds. The reference is kept on self so the image isn't
    garbage-collected and blanked."""
    path = _icon_path()
    if path is None:
      return
    try:
      from PIL import Image, ImageTk
      img = Image.open(path)
      self._icon_imgref = ImageTk.PhotoImage(img)
      self.root.iconphoto(True, self._icon_imgref)
    except Exception:
      pass

  def _build_header(self, parent) -> None:
    """Centered logo + tagline above the Account section.

    The logo carries the "RimPortrait" wordmark; the tagline is
    the one piece of context the brand mark itself doesn't convey."""
    path = _logo_path()
    if path is None:
      return
    try:
      from PIL import Image, ImageTk
      img = Image.open(path).convert("RGBA")
      img.thumbnail((160, 160))
      self._header_imgref = ImageTk.PhotoImage(img)
    except Exception:
      return
    # Use tk.Label (not ttk.Label) for both rows here — on macOS
    # the themed widget pads its content vertically, leaving a
    # large gap between the badge and the tagline that ipady=0
    # can't override. tk.Label respects ipady=0 cleanly.
    bar = ttk.Frame(parent, padding=(10, 8, 10, 0))
    bar.pack(fill="x")
    tk.Label(
      bar, image=self._header_imgref, borderwidth=0, highlightthickness=0,
    ).pack(pady=0, ipady=0)
    tk.Label(
      bar, text="Turn a RimWorld save into an AI portrait.",
      foreground="#888", borderwidth=0, highlightthickness=0,
    ).pack(pady=(2, 0), ipady=0)

  # ----- Account & model -----------------------------------------

  def _build_account(self, parent) -> None:
    self.account = _Collapsible(parent, "Account & model", open=False)
    self.account.pack(fill="x", padx=10, pady=(8, 4))
    body = self.account.body
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text="Provider:").grid(row=0, column=0, sticky="e")
    pf = ttk.Frame(body)
    pf.grid(row=0, column=1, columnspan=2, sticky="w")
    self.provider_var = tk.StringVar(value="openai")
    for p in llm.PROVIDERS:
      ttk.Radiobutton(
        pf, text=p, variable=self.provider_var, value=p,
        command=self._on_provider_change,
      ).pack(side="left", padx=4)
    _help(body, "Which LLM service to use. Each needs its own key.").grid(
      row=1, column=1, columnspan=2, sticky="w", padx=4, pady=(0, 4),
    )

    ttk.Label(body, text="API key:").grid(row=2, column=0, sticky="e")
    self.key_var = tk.StringVar()
    ttk.Entry(
      body, textvariable=self.key_var, show="*",
    ).grid(row=2, column=1, sticky="ew", padx=4)
    kbtns = ttk.Frame(body)
    kbtns.grid(row=2, column=2, sticky="w")
    ttk.Button(
      kbtns, text="Save to keychain", command=self._save_key,
    ).pack(side="left")
    ttk.Button(
      kbtns, text="Get a key →", command=self._open_key_page,
    ).pack(side="left", padx=(4, 0))
    _help(
      body,
      "Stored in your OS keychain (macOS Keychain / Windows "
      "Credential Manager). Set once.",
    ).grid(row=3, column=1, columnspan=2, sticky="w", padx=4, pady=(0, 4))

    ttk.Label(body, text="Tier:").grid(row=4, column=0, sticky="e")
    tf = ttk.Frame(body)
    tf.grid(row=4, column=1, columnspan=2, sticky="w")
    self.tier_var = tk.StringVar(value="pro")
    for t in ("pro", "fast"):
      ttk.Radiobutton(
        tf, text=t, variable=self.tier_var, value=t,
      ).pack(side="left", padx=4)
    _help(
      body, "Pro = best results, slower & costlier. Fast = quicker.",
    ).grid(row=5, column=1, columnspan=2, sticky="w", padx=4)

  # ----- Card 1: Load save data ----------------------------------

  def _build_card1(self, parent) -> None:
    card = ttk.LabelFrame(parent, text="1. Load save data", padding=8)
    card.pack(fill="x", padx=10, pady=4)
    card.columnconfigure(1, weight=1)

    ttk.Label(card, text="Save:").grid(row=0, column=0, sticky="e")
    self.save_var = tk.StringVar()
    self.save_combo = ttk.Combobox(
      card, textvariable=self.save_var, state="readonly",
    )
    self.save_combo.grid(row=0, column=1, sticky="ew", padx=4)
    self.save_combo.bind("<<ComboboxSelected>>", self._on_save_selected)
    ttk.Button(
      card, text="Other...", command=self._browse_save,
    ).grid(row=0, column=2)
    _help(card, "Which colony save to read.").grid(
      row=1, column=1, columnspan=2, sticky="w", padx=4, pady=(0, 4),
    )

    bits = [f"Tested against RimWorld {TESTED_VERSION}"]
    if self.installed_version:
      bits.append(
        f"your install: {_short_version(self.installed_version)}"
      )
    else:
      bits.append("install not detected — mod-aware labels disabled")
    ttk.Label(
      card, text="  ·  ".join(bits), foreground="#888",
    ).grid(row=2, column=1, columnspan=2, sticky="w", padx=4)

    ttk.Label(card, text="Pawn:").grid(row=3, column=0, sticky="e")
    self.pawn_var = tk.StringVar()
    self.pawn_combo = ttk.Combobox(
      card, textvariable=self.pawn_var, state="disabled",
    )
    self.pawn_combo.grid(row=3, column=1, sticky="ew", padx=4)
    self.pawn_combo.bind("<<ComboboxSelected>>", self._on_pawn_changed)
    self.family_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
      card, text="Family", variable=self.family_var,
      command=self._on_pawn_changed,
    ).grid(row=3, column=2)
    _help(card, "Which colonist the portrait is of.").grid(
      row=4, column=1, columnspan=2, sticky="w", padx=4, pady=(0, 4),
    )

    self.card1_status = ttk.Label(
      card, text="Pick a save to begin.", foreground="#aaa",
    )
    self.card1_status.grid(
      row=5, column=0, columnspan=3, sticky="w", padx=2, pady=(4, 2),
    )

    self.block_panel = _Collapsible(card, "Show data block", open=False)
    self.block_panel.grid(
      row=6, column=0, columnspan=3, sticky="ew", padx=2,
    )
    self.block_text = tk.Text(
      self.block_panel.body, height=14, wrap="word",
      font=("Menlo", 10),
    )
    self.block_text.pack(fill="x", expand=True)
    self.block_text.configure(state="disabled")

  # ----- Card 2: Generate prompt ---------------------------------

  def _build_card2(self, parent) -> None:
    card = ttk.LabelFrame(parent, text="2. Generate prompt", padding=8)
    card.pack(fill="x", padx=10, pady=4)
    card.columnconfigure(1, weight=1)
    self._card2 = card

    ttk.Label(card, text="Preset:").grid(row=0, column=0, sticky="e")
    self.preset_var = tk.StringVar(value="(none)")
    self.preset_combo = ttk.Combobox(
      card, textvariable=self.preset_var, state="readonly",
      values=["(none)"] + sorted(style.PRESETS.keys()),
    )
    self.preset_combo.grid(row=0, column=1, sticky="ew", padx=4)
    _help(
      card,
      "Art-style bundle. e.g. 'renaissance' = oil-painting feel, "
      "'anime' = cel-shaded, '(none)' = plain photo-real.",
    ).grid(row=1, column=1, sticky="w", padx=4, pady=(0, 4))

    ttk.Label(card, text="Style note:").grid(row=2, column=0, sticky="e")
    self.style_var = tk.StringVar()
    ttk.Entry(card, textvariable=self.style_var).grid(
      row=2, column=1, sticky="ew", padx=4,
    )
    _help(
      card,
      "Optional extra style words appended to the preset "
      "(e.g. 'moody candlelit', 'overcast').",
    ).grid(row=3, column=1, sticky="w", padx=4, pady=(0, 4))

    action2 = self._build_action_row(
      card, row=4,
      btn_text="Generate prompt",
      command=self._start_generate_prompt,
      model_var_key="card2",
    )
    (
      self.card2_btn, self.card2_spinner, self.card2_model_label,
      self.card2_action_holder,
    ) = action2

    self.card2_status = ttk.Label(
      card, text="Load a save first.", foreground="#aaa",
    )
    self.card2_status.grid(
      row=5, column=0, columnspan=3, sticky="w", padx=2,
    )

    ttk.Label(
      card, text="Prompt (editable):", foreground="#aaa",
    ).grid(row=6, column=0, columnspan=3, sticky="w", padx=2, pady=(6, 0))
    self.prompt_text = tk.Text(
      card, height=10, wrap="word", font=("Menlo", 10),
    )
    self.prompt_text.grid(
      row=7, column=0, columnspan=3, sticky="ew", padx=2,
    )
    # Dirty tracking: programmatic inserts clear dirty; user edits
    # set it via the <<Modified>> event.
    self.prompt_text.bind("<<Modified>>", self._on_prompt_modified)
    self.prompt_text.bind("<KeyRelease>", lambda _e: self._refresh_card3_enabled())

  # ----- Card 3: Generate image ----------------------------------

  def _build_card3(self, parent) -> None:
    card = ttk.LabelFrame(parent, text="3. Generate image", padding=8)
    card.pack(fill="x", padx=10, pady=4)
    card.columnconfigure(1, weight=1)
    self._card3 = card

    ttk.Label(card, text="Output:").grid(row=0, column=0, sticky="e")
    self.out_var = tk.StringVar(value=str(DEFAULT_OUTPUT))
    ttk.Entry(card, textvariable=self.out_var).grid(
      row=0, column=1, sticky="ew", padx=4,
    )
    ttk.Button(
      card, text="Browse...", command=self._browse_out,
    ).grid(row=0, column=2)
    _help(card, "Folder the PNG is written to.").grid(
      row=1, column=1, sticky="w", padx=4, pady=(0, 4),
    )

    action3 = self._build_action_row(
      card, row=2,
      btn_text="Generate image",
      command=self._start_generate_image,
      model_var_key="card3",
    )
    (
      self.card3_btn, self.card3_spinner, self.card3_model_label,
      self.card3_action_holder,
    ) = action3

    self.card3_status = ttk.Label(
      card, text="Generate a prompt first.", foreground="#aaa",
    )
    self.card3_status.grid(
      row=3, column=0, columnspan=3, sticky="w", padx=2,
    )

    self.preview = ttk.Label(
      card, text="(image preview will appear here)",
      anchor="center", foreground="#666",
    )
    self.preview.grid(
      row=4, column=0, columnspan=3, sticky="ew", pady=(8, 2),
    )
    self.preview.bind("<Button-1>", self._open_image)

  # ----- action row helper (model label + button/spinner) -------

  def _build_action_row(
    self, card, *, row: int, btn_text: str, command, model_var_key: str,
  ):
    """Build a right-aligned [ model · settings ] [ button|spinner ] row.

    The button and the indeterminate Progressbar share a
    fixed-size holder so swapping one for the other doesn't
    reflow the surrounding grid (which would otherwise feel
    jarring as the spinner is a different intrinsic width)."""
    row_frame = ttk.Frame(card)
    row_frame.grid(
      row=row, column=0, columnspan=3, sticky="ew", padx=2, pady=4,
    )
    row_frame.columnconfigure(0, weight=1)

    model_label = ttk.Label(row_frame, text="", foreground="#888")
    model_label.grid(row=0, column=0, sticky="e", padx=(0, 8))

    holder = ttk.Frame(row_frame, width=170, height=28)
    holder.grid(row=0, column=1, sticky="e")
    holder.grid_propagate(False)
    holder.columnconfigure(0, weight=1)
    holder.rowconfigure(0, weight=1)

    btn = ttk.Button(holder, text=btn_text, command=command)
    btn.grid(row=0, column=0, sticky="nsew")
    spinner = ttk.Progressbar(holder, mode="indeterminate")
    # Don't grid the spinner yet — it's hidden until generation runs.

    return btn, spinner, model_label, holder

  def _show_spinner(self, btn, spinner) -> None:
    btn.grid_remove()
    spinner.grid(row=0, column=0, sticky="ew", padx=4)
    spinner.start(12)

  def _hide_spinner(self, btn, spinner) -> None:
    spinner.stop()
    spinner.grid_remove()
    btn.grid()

  def _refresh_model_labels(self, *_args) -> None:
    """Update the small "openai · pro · <model-id>" hint next to each
    Generate button. Called once at init and again whenever provider
    or tier changes."""
    provider = self.provider_var.get()
    tier = self.tier_var.get()
    try:
      text_model = llm.resolve_model(provider, "text", tier)
      image_model = llm.resolve_model(provider, "image", tier)
    except Exception:
      text_model = image_model = "?"
    base = f"{provider} · {tier}"
    image_extras = ""
    quality = llm.image_quality_for(provider, tier)
    if quality:
      image_extras = f"  ·  q={quality}  ·  mod=low"
    elif provider == "google":
      image_extras = "  ·  safety=permissive"
    if hasattr(self, "card2_model_label"):
      self.card2_model_label.configure(text=f"{base} · {text_model}")
    if hasattr(self, "card3_model_label"):
      self.card3_model_label.configure(
        text=f"{base} · {image_model}{image_extras}",
      )

  # ----- log footer ----------------------------------------------

  def _build_log_footer(self, parent) -> None:
    self.log_panel = _Collapsible(parent, "Show log details", open=False)
    self.log_panel.pack(fill="x", padx=10, pady=(4, 10))
    self.log = tk.Text(
      self.log_panel.body, height=8, wrap="none",
      font=("Menlo", 10), background="#111", foreground="#ddd",
    )
    self.log.pack(fill="x", expand=True)
    self.log.configure(state="disabled")

  # ----- save discovery & pawn list ------------------------------

  def _resolve_saves_dir(self) -> Path | None:
    saved = self.cfg.get("saves_dir")
    if saved and Path(saved).is_dir():
      return Path(saved)
    return autodetect_saves_dir()

  def _populate_saves(self) -> None:
    if not self.saves:
      self.save_combo["values"] = ["(no saves found — click Other...)"]
      self.save_combo.current(0)
      return
    self.save_combo["values"] = [e.label for e in self.saves]
    self.save_combo.current(0)
    self._on_save_selected(None)

  def _browse_save(self) -> None:
    initial = str(self.saves_dir) if self.saves_dir else str(Path.home())
    chosen = filedialog.askopenfilename(
      title="Pick a RimWorld save",
      filetypes=[("RimWorld save", "*.rws"), ("All files", "*.*")],
      initialdir=initial,
    )
    if not chosen:
      return
    path = Path(chosen)
    self.cfg["saves_dir"] = str(path.parent)
    _save_config(self.cfg)
    self.saves_dir = path.parent
    self.saves = _list_saves(self.saves_dir)
    self.saves.sort(key=lambda e: (e.path != path, -e.mtime))
    self._populate_saves()

  def _on_save_selected(self, _evt) -> None:
    idx = self.save_combo.current()
    if idx < 0 or idx >= len(self.saves):
      return
    entry = self.saves[idx]
    if entry.untested:
      ok = messagebox.askyesno(
        APP_NAME,
        f"This save is from RimWorld "
        f"{_short_version(entry.game_version or '?')}.\n\n"
        f"rimportrait is only tested against {TESTED_VERSION}; "
        "labels may drift (apparel layers, tech levels, body parts). "
        "Continue anyway?",
        icon="warning",
      )
      if not ok:
        self.card1_status.configure(text="Pick a different save.")
        return
    self.selected_save = entry.path
    self._invalidate_block()
    self.card1_status.configure(
      text=f"Loading {entry.path.name}…",
    )
    self._start_load_save(entry.path)

  def _on_pawn_changed(self, *_args) -> None:
    self._invalidate_block()
    if self.save_obj is None or not self.pawn_var.get():
      return
    self._render_block_inline()

  def _invalidate_block(self) -> None:
    self.block = None
    self.block_signature = None
    self._refresh_card2_enabled()
    if self.card2_status.cget("text") and self.block is None:
      self.card2_status.configure(
        text="Block changed — click Generate prompt to refresh.",
      )

  # ----- Card 1 worker (load) ------------------------------------

  def _start_load_save(self, save_path: Path) -> None:
    self.active_stage = "card1"
    self._t_start = time.monotonic()
    cli.set_status_sink(self._sink)

    # Reset downstream state when the underlying save changes.
    self.save_obj = None
    self.def_index = None
    self.pawn_names = []
    self.pawn_combo["state"] = "disabled"
    self.pawn_combo["values"] = []
    self.pawn_var.set("")

    def work():
      try:
        cli.reset_clock()
        cli._status(f"Loading save", f"({save_path.name})")
        save = load_save(save_path)
        ns = argparse.Namespace(no_defs=False, rimworld_dir=None)
        cli._status("Building mod-aware def index")
        (idx, dd, dl, dc, dco, dt, dla) = cli._build_index(save, ns)
        if idx is not None:
          cli._status("Def index ready", f"({len(idx)} defs)")
        else:
          cli._status("No mod folder — falling back to slug labels")
        cli._status("Parsing body-part index")
        bp = cli._build_body_parts(ns)
        cli._status("Listing pawns")
        names = cli._list_pawn_names(save, idx, bp)
        cli._status(f"Found {len(names)} pawns")
      except Exception:
        self.progress_q.put("!card1-error!" + traceback.format_exc())
        return
      # Stash heavy objects FIRST so _handle_card1_done's inline
      # block render sees them. Polling consumes one item per tick.
      self.progress_q.put(("__stash__", save, idx, dd, dl, dc, dco, dt, dla, bp))  # type: ignore
      payload = {
        "names": names,
        "n_defs": len(idx) if idx else 0,
        "has_mods": idx is not None,
      }
      self.progress_q.put("!card1-done!" + json.dumps(payload))

    threading.Thread(target=work, daemon=True).start()

  def _render_block_inline(self) -> None:
    """Synchronously render the block for the current pawn into the
    preview area. Cheap (no API calls); called every time the pawn
    or family flag changes."""
    if self.save_obj is None:
      return
    pawn_name = self.pawn_var.get().strip()
    if not pawn_name:
      return
    try:
      p = find_pawn(
        self.save_obj, pawn_name, self.def_index, self.body_parts,
      )
      if p is None:
        self.card1_status.configure(text=f"✗ pawn not found: {pawn_name}")
        return
      ctx = map_context_for(self.save_obj, p)
      common = dict(
        include_instruction=False,
        def_descriptions=self.defs_desc, def_labels=self.defs_label,
        def_categories=self.defs_cat,
        def_cost_materials=self.defs_cost,
        def_tech_levels=self.defs_tech,
        def_apparel_layers=self.defs_layer,
      )
      if self.family_var.get():
        members = family_members(
          self.save_obj, p, self.def_index, self.body_parts,
        )
        block = render_family(p, members, ctx, **common)
        kind = "family"
      else:
        block = render_portrait(p, ctx, **common)
        kind = "portrait"
    except Exception as e:
      self.card1_status.configure(text=f"✗ render failed: {e}")
      return
    self.block = block
    self.block_signature = (
      str(self.selected_save), pawn_name, self.family_var.get(), kind,
    )
    self._set_block_preview(block)
    self.card1_status.configure(
      text=f"✓ {kind} block ready ({len(block):,} chars)",
    )
    self._refresh_card2_enabled()
    self.card2_status.configure(
      text="Block changed — click Generate prompt to refresh.",
    )

  def _set_block_preview(self, block: str) -> None:
    self.block_text.configure(state="normal")
    self.block_text.delete("1.0", "end")
    self.block_text.insert("1.0", block)
    self.block_text.configure(state="disabled")
    self.block_panel.set_title(f"Show data block ({len(block):,} chars)")

  # ----- Card 2 worker (LLM polish) ------------------------------

  def _start_generate_prompt(self) -> None:
    if not self.block:
      messagebox.showerror(APP_NAME, "Load a save and pick a pawn first.")
      return
    if self.prompt_dirty:
      ok = messagebox.askyesno(
        APP_NAME,
        "You've edited the prompt. Regenerating will overwrite your "
        "edits. Continue?",
        icon="warning",
      )
      if not ok:
        return
    provider = self.provider_var.get()
    key = self.key_var.get().strip()
    if not key:
      self.account.open()
      messagebox.showerror(
        APP_NAME,
        f"Paste your {provider} API key in the Account section first.",
      )
      return
    os.environ[_PROVIDER_ENV[provider]] = key

    preset_name = self.preset_var.get()
    preset = (
      style.PRESETS.get(preset_name) if preset_name != "(none)" else None
    )
    kind = "family" if self.family_var.get() else "portrait"
    effective_kind = kind
    if kind == "portrait" and preset is not None and preset.base:
      effective_kind = preset.base
    image_model = llm.resolve_model(provider, "image", self.tier_var.get())
    system = style.compose_instruction(
      kind, preset,
      image_model=image_model, effective_kind=effective_kind,
      user_style=self.style_var.get().strip() or None,
    )
    block = self.block
    tier = self.tier_var.get()

    self._show_spinner(self.card2_btn, self.card2_spinner)
    self.card2_status.configure(text="Generating prompt…")
    self.active_stage = "card2"
    self._t_start = time.monotonic()
    cli.set_status_sink(self._sink)

    def work():
      try:
        cli.reset_clock()
        text_model = llm.resolve_model(provider, "text", tier)
        cli._status(
          f"Calling LLM ({provider} {text_model})",
          f"system={len(system):,} chars  user={len(block):,} chars",
        )
        out = llm.complete(
          provider, system=system, user=block, model=tier,
        )
        cli._status(
          f"LLM returned {len(out):,} chars",
        )
      except Exception:
        self.progress_q.put("!card2-error!" + traceback.format_exc())
        return
      self.progress_q.put("!card2-done!" + json.dumps({
        "prompt": out,
        "model": llm.resolve_model(provider, "text", tier),
      }))

    threading.Thread(target=work, daemon=True).start()

  def _on_prompt_modified(self, _evt) -> None:
    # <<Modified>> fires for every change including our own inserts;
    # we clear the modified flag after programmatic writes by calling
    # edit_modified(False), so any time this fires it's a user edit.
    if self.prompt_text.edit_modified():
      self.prompt_dirty = True
      self.prompt_text.edit_modified(False)
      self._refresh_card3_enabled()

  def _set_prompt(self, prompt: str) -> None:
    self.prompt_text.delete("1.0", "end")
    self.prompt_text.insert("1.0", prompt)
    self.prompt_text.edit_modified(False)
    self.prompt = prompt
    self.prompt_dirty = False
    self._refresh_card3_enabled()

  def _current_prompt(self) -> str:
    return self.prompt_text.get("1.0", "end-1c").strip()

  def _refresh_card2_enabled(self) -> None:
    enabled = self.block is not None
    self.card2_btn["state"] = "normal" if enabled else "disabled"
    if not enabled:
      self.card2_status.configure(text="Load a save first.")

  def _refresh_card3_enabled(self) -> None:
    enabled = bool(self._current_prompt())
    self.card3_btn["state"] = "normal" if enabled else "disabled"
    # Only refresh status when nothing has run yet — once the user
    # has generated an image, the success line stays put.
    if self.last_image is not None:
      return
    if enabled:
      self.card3_status.configure(text="Ready — click Generate image.")
    else:
      self.card3_status.configure(text="Generate a prompt first.")

  # ----- Card 3 worker (image gen) -------------------------------

  def _start_generate_image(self) -> None:
    prompt = self._current_prompt()
    if not prompt:
      messagebox.showerror(APP_NAME, "Generate a prompt first.")
      return
    provider = self.provider_var.get()
    key = self.key_var.get().strip()
    if not key:
      self.account.open()
      messagebox.showerror(
        APP_NAME,
        f"Paste your {provider} API key in the Account section first.",
      )
      return
    os.environ[_PROVIDER_ENV[provider]] = key

    out_dir = Path(self.out_var.get()).expanduser()
    try:
      out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
      messagebox.showerror(APP_NAME, f"Can't create output folder: {e}")
      return

    pawn_name = self.pawn_var.get().strip() or "pawn"
    kind = "family" if self.family_var.get() else "portrait"
    tier = self.tier_var.get()

    self._show_spinner(self.card3_btn, self.card3_spinner)
    self.card3_status.configure(text="Generating image…")
    self.active_stage = "card3"
    self._t_start = time.monotonic()
    cli.set_status_sink(self._sink)

    def work():
      try:
        cli.reset_clock()
        image_model = llm.resolve_model(provider, "image", tier)
        quality = llm.image_quality_for(provider, tier) or "—"
        cli._status(
          f"Calling image API ({provider} {image_model})",
          f"prompt={len(prompt):,} chars  tier={tier}  q={quality}",
        )
        png, ext = llm.generate_image(
          provider, prompt, kind, model=tier,
        )
        cli._status(f"Got {len(png):,} bytes of {ext}")
      except Exception:
        self.progress_q.put("!card3-error!" + traceback.format_exc())
        return
      stem = _slug(pawn_name)
      image_path = out_dir / f"{stem}.{kind}.{ext}"
      prompt_path = out_dir / f"{stem}.{kind}.txt"
      try:
        # Preserve previous run(s) by moving the existing image
        # AND its paired prompt into a `history/` subfolder under
        # a shared timestamp. Pairing is by filename: the image
        # and its prompt always share the same `<stem>.<kind>.<stamp>`
        # prefix, so you can find which prompt produced which
        # image months later.
        if image_path.exists() or prompt_path.exists():
          history_dir = out_dir / "history"
          history_dir.mkdir(parents=True, exist_ok=True)
          # Use the image's mtime (or the prompt's, if no image)
          # so both archived files share the timestamp.
          src = image_path if image_path.exists() else prompt_path
          stamp = time.strftime(
            "%Y-%m-%dT%H%M%S", time.localtime(src.stat().st_mtime),
          )
          if image_path.exists():
            arch_img = history_dir / f"{stem}.{kind}.{stamp}.{ext}"
            image_path.rename(arch_img)
            cli._status(f"Archived previous image -> {arch_img.name}")
          if prompt_path.exists():
            arch_txt = history_dir / f"{stem}.{kind}.{stamp}.txt"
            prompt_path.rename(arch_txt)
            cli._status(f"Archived previous prompt -> {arch_txt.name}")
        image_path.write_bytes(png)
        prompt_path.write_text(prompt + "\n")
        cli._status(f"Wrote {image_path.name} + {prompt_path.name}")
        out_path = image_path
      except OSError:
        self.progress_q.put("!card3-error!" + traceback.format_exc())
        return
      self.progress_q.put(
        "!card3-done!" + json.dumps({"path": str(out_path)})
      )

    threading.Thread(target=work, daemon=True).start()

  # ----- Account actions -----------------------------------------

  def _on_provider_change(self) -> None:
    self._prefill_key()
    if not self.key_var.get():
      self.account.open()

  def _prefill_key(self) -> None:
    self.key_var.set(_keychain_get(self.provider_var.get()))

  def _open_key_page(self) -> None:
    import webbrowser
    url = _PROVIDER_KEY_URL.get(self.provider_var.get())
    if url:
      webbrowser.open(url)

  def _save_key(self) -> None:
    ok, err = _keychain_set(self.provider_var.get(), self.key_var.get())
    if ok:
      self._append_log("Saved API key to keychain.")
    else:
      messagebox.showwarning(
        APP_NAME,
        f"Couldn't save to the OS keychain:\n\n{err}\n\n"
        "The key still works for this session — it's just not "
        "remembered across launches.",
      )

  def _browse_out(self) -> None:
    chosen = filedialog.askdirectory(
      title="Pick output folder", initialdir=self.out_var.get(),
    )
    if chosen:
      self.out_var.set(chosen)

  def _open_image(self, _evt) -> None:
    if self.last_image and self.last_image.is_file():
      import subprocess
      import sys as _sys
      if _sys.platform == "darwin":
        subprocess.Popen(["open", str(self.last_image)])
      elif _sys.platform == "win32":
        os.startfile(str(self.last_image))  # type: ignore[attr-defined]
      else:
        subprocess.Popen(["xdg-open", str(self.last_image)])

  # ----- progress sink + queue polling ---------------------------

  def _sink(self, line: str) -> None:
    # Called from worker threads; just queue and let the polling
    # loop touch widgets on the main thread.
    self.progress_q.put(line)

  def _elapsed(self) -> str:
    return f"{time.monotonic() - self._t_start:.1f}s"

  def _poll_log_queue(self) -> None:
    try:
      while True:
        item = self.progress_q.get_nowait()
        if isinstance(item, tuple) and item and item[0] == "__stash__":
          # Heavy objects from card1 worker.
          (_, save, idx, dd, dl, dc, dco, dt, dla, bp) = item
          self.save_obj = save
          self.def_index = idx
          self.defs_desc, self.defs_label = dd, dl
          self.defs_cat, self.defs_cost = dc, dco
          self.defs_tech, self.defs_layer = dt, dla
          self.body_parts = bp
          continue
        if not isinstance(item, str):
          continue
        if item.startswith("!card1-done!"):
          payload = json.loads(item[len("!card1-done!"):])
          self._handle_card1_done(payload)
        elif item.startswith("!card1-error!"):
          self._handle_error("card1", item[len("!card1-error!"):])
        elif item.startswith("!card2-done!"):
          payload = json.loads(item[len("!card2-done!"):])
          self._handle_card2_done(payload)
        elif item.startswith("!card2-error!"):
          self._handle_error("card2", item[len("!card2-error!"):])
        elif item.startswith("!card3-done!"):
          payload = json.loads(item[len("!card3-done!"):])
          self._handle_card3_done(payload)
        elif item.startswith("!card3-error!"):
          self._handle_error("card3", item[len("!card3-error!"):])
        else:
          # Regular status line from cli._status.
          self._append_log(_strip_ansi(item))
          self._update_active_status(item)
    except queue.Empty:
      pass
    self.root.after(80, self._poll_log_queue)

  def _update_active_status(self, line: str) -> None:
    text = _strip_ansi(line).strip()
    # Drop the leading [Xs] timestamp for the short status line.
    if text.startswith("["):
      _, _, rest = text.partition("]")
      text = rest.strip() or text
    target = {
      "card1": self.card1_status,
      "card2": self.card2_status,
      "card3": self.card3_status,
    }.get(self.active_stage or "")
    if target is not None:
      target.configure(text=text)

  def _handle_card1_done(self, payload: dict) -> None:
    names: list[str] = payload["names"]
    self.pawn_names = names
    self.pawn_combo["values"] = names
    self.pawn_combo["state"] = "readonly"
    if names and not self.pawn_var.get():
      self.pawn_combo.current(0)
    mods_note = (
      f"{payload['n_defs']:,} mod defs"
      if payload["has_mods"]
      else "no mod folder — using slug labels"
    )
    self.card1_status.configure(
      text=f"✓ Loaded · {len(names)} pawns · {mods_note}"
           f"  ({self._elapsed()})",
    )
    self.active_stage = None
    cli.set_status_sink(None)
    if names:
      self._render_block_inline()

  def _handle_card2_done(self, payload: dict) -> None:
    self._set_prompt(payload["prompt"])
    self._hide_spinner(self.card2_btn, self.card2_spinner)
    self.card2_status.configure(
      text=f"✓ Generated in {self._elapsed()}  ·  {payload['model']}",
    )
    self.active_stage = None
    cli.set_status_sink(None)

  def _handle_card3_done(self, payload: dict) -> None:
    path = Path(payload["path"])
    self.last_image = path
    self._show_preview(path)
    self._hide_spinner(self.card3_btn, self.card3_spinner)
    self.card3_status.configure(
      text=f"✓ Wrote {path.name} in {self._elapsed()}",
    )
    self.active_stage = None
    cli.set_status_sink(None)

  def _handle_error(self, stage: str, tb: str) -> None:
    self.active_stage = None
    cli.set_status_sink(None)
    self._append_log(tb)
    self.log_panel.open()
    short = (tb.strip().splitlines() or ["(unknown error)"])[-1]
    spinners = {
      "card2": (self.card2_btn, self.card2_spinner),
      "card3": (self.card3_btn, self.card3_spinner),
    }
    if stage in spinners:
      self._hide_spinner(*spinners[stage])
    target = {
      "card1": self.card1_status,
      "card2": self.card2_status,
      "card3": self.card3_status,
    }[stage]
    target.configure(text=f"✗ {short}")
    messagebox.showerror(APP_NAME, short)

  def _append_log(self, line: str) -> None:
    self.log.configure(state="normal")
    self.log.insert("end", line + "\n")
    self.log.see("end")
    self.log.configure(state="disabled")

  def _show_preview(self, path: Path) -> None:
    try:
      from PIL import Image, ImageTk
      img = Image.open(path)
      img.thumbnail((640, 420))
      photo = ImageTk.PhotoImage(img)
      self.preview_imgref = photo
      self.preview.configure(image=photo, text="")
    except Exception:
      self.preview.configure(
        text=f"Image ready: {path.name}\n(click to open)", image="",
      )
      self.preview_imgref = None


def main() -> int:
  # Rename the OS process so Activity Monitor / `ps` / Dock show
  # "rimportrait" instead of "python3". Silent no-op on the off
  # chance setproctitle isn't available (fresh-install edge).
  try:
    import setproctitle
    setproctitle.setproctitle("rimportrait")
  except Exception:
    pass
  root = tk.Tk()
  App(root)
  root.mainloop()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
