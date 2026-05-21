"""Minimal Tkinter GUI for non-technical users.

Single window over the existing pipeline (`cli._render_one`). On
launch it scans the platform-default RimWorld Saves directory
(``rimsave.autodetect_saves_dir``), pre-selects the most recent
save, and reads the provider's API key from the OS keychain via
``keyring``. The user clicks Generate; the pipeline runs in a
worker thread and progress lines from ``cli._status`` stream into
a Text widget via a swappable sink.

Entry point: ``rimportrait-gui`` (defined in pyproject.toml).
Requires the ``[gui]`` extra: keyring, Pillow, platformdirs.
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
  installed_rimworld_version,
  read_save_game_version,
)

from . import cli, llm, style


APP_NAME = "rimportrait"
KEYRING_SERVICE = "rimportrait"
DEFAULT_OUTPUT = Path.home() / "Pictures" / "rimportrait"

# The only RimWorld version we test the mod-aware def index against.
# Saves from other versions usually still render, but def lookups
# (apparel layers, tech levels, body parts) may drift, so we flag
# them in the save dropdown and mention it under the save row.
TESTED_VERSION = "1.6"


# Maps the GUI provider radio onto the env-var that the underlying
# llm.py code path reads. Mirrors cli._PROVIDER_KEY_VARS but flat.
_PROVIDER_ENV = {
  "openai": "OPENAI_API_KEY",
  "google": "GEMINI_API_KEY",
}


@dataclass
class SaveEntry:
  path: Path
  mtime: float
  game_version: str | None = None
  untested: bool = False  # save not from the tested RimWorld version

  @property
  def label(self) -> str:
    age = _ago(time.time() - self.mtime)
    parts = [self.path.stem]
    if self.game_version:
      short = _short_version(self.game_version)
      tag = f"save {short}"
      if self.untested:
        tag += " ⚠"
      parts.append(f"— {tag}")
    parts.append(f"({age})")
    return "  ".join(parts)


def _short_version(v: str) -> str:
  """'1.5.4297 rev1126' -> '1.5'. Falls back to the full string when
  the format is unrecognised (modded builds, alphas)."""
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
    return f"{n} min ago" if n != 1 else "1 min ago"
  if seconds < 86400:
    n = int(seconds // 3600)
    return f"{n} hr ago" if n != 1 else "1 hr ago"
  n = int(seconds // 86400)
  return f"{n} days ago" if n != 1 else "1 day ago"


# --- persistent per-user config -------------------------------------

def _config_path() -> Path:
  """Return the on-disk path for the GUI's small JSON config.

  Stores the manually-chosen saves dir + RimWorld dir so the user
  isn't re-prompted on every launch. Uses platformdirs when present;
  falls back to ``~/.config/rimportrait/config.json`` so the GUI
  doesn't crash if the extra wasn't installed."""
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


# --- keychain glue (graceful when keyring missing) -----------------

def _keychain_get(provider: str) -> str:
  try:
    import keyring
    return keyring.get_password(KEYRING_SERVICE, provider) or ""
  except Exception:
    return ""


def _keychain_set(provider: str, value: str) -> bool:
  try:
    import keyring
    keyring.set_password(KEYRING_SERVICE, provider, value)
    return True
  except Exception:
    return False


# --- saves discovery -----------------------------------------------

def _list_saves(saves_dir: Path) -> list[SaveEntry]:
  """Enumerate .rws files in saves_dir, decorated with game version.

  Version is iterparse-bounded to the save's `<meta>` block so this
  stays fast even with dozens of saves. Saves outside ``TESTED_VERSION``
  get an ``untested`` flag the label uses to show ⚠."""
  if not saves_dir.is_dir():
    return []
  entries: list[SaveEntry] = []
  for child in saves_dir.iterdir():
    if child.suffix.lower() != ".rws" or not child.is_file():
      continue
    gv = read_save_game_version(child)
    save_mm = _major_minor(gv)
    untested = bool(save_mm and ".".join(save_mm) != TESTED_VERSION)
    entries.append(SaveEntry(
      path=child, mtime=child.stat().st_mtime,
      game_version=gv, untested=untested,
    ))
  entries.sort(key=lambda e: e.mtime, reverse=True)
  return entries


# --- the window ----------------------------------------------------

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
    self.selected_save: Path | None = None
    self.pawn_names: list[str] = []
    self.progress_q: queue.Queue[str] = queue.Queue()
    self.last_image: Path | None = None
    self.preview_imgref: object | None = None  # keep ref alive

    root.title(f"{APP_NAME}  —  RimWorld portrait generator")
    root.geometry("720x720")
    self._build_form()
    self._build_log()
    self._build_preview()
    self._populate_saves()
    self._prefill_key()
    self._poll_log_queue()

  # form ------------------------------------------------------------

  def _build_form(self) -> None:
    f = ttk.Frame(self.root, padding=10)
    f.pack(fill="x")
    f.columnconfigure(1, weight=1)

    row = 0
    ttk.Label(f, text="Save:").grid(row=row, column=0, sticky="e")
    self.save_var = tk.StringVar()
    self.save_combo = ttk.Combobox(
      f, textvariable=self.save_var, state="readonly",
    )
    self.save_combo.grid(row=row, column=1, sticky="ew", padx=4)
    self.save_combo.bind("<<ComboboxSelected>>", self._on_save_selected)
    ttk.Button(
      f, text="Other...", command=self._browse_save,
    ).grid(row=row, column=2)

    row += 1
    bits = [f"Tested against RimWorld {TESTED_VERSION}"]
    if self.installed_version:
      bits.append(
        f"your install: {_short_version(self.installed_version)}"
      )
    else:
      bits.append("install not detected — mod-aware labels disabled")
    ttk.Label(
      f, text="  ·  ".join(bits), foreground="#888",
    ).grid(row=row, column=1, columnspan=2, sticky="w", padx=4)

    row += 1
    ttk.Label(f, text="Pawn:").grid(row=row, column=0, sticky="e")
    self.pawn_var = tk.StringVar()
    self.pawn_combo = ttk.Combobox(
      f, textvariable=self.pawn_var, state="disabled",
    )
    self.pawn_combo.grid(row=row, column=1, sticky="ew", padx=4)
    self.family_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
      f, text="Family", variable=self.family_var,
    ).grid(row=row, column=2)

    row += 1
    ttk.Label(f, text="Preset:").grid(row=row, column=0, sticky="e")
    self.preset_var = tk.StringVar(value="(none)")
    self.preset_combo = ttk.Combobox(
      f, textvariable=self.preset_var, state="readonly",
      values=["(none)"] + sorted(style.PRESETS.keys()),
    )
    self.preset_combo.grid(row=row, column=1, sticky="ew", padx=4)

    row += 1
    ttk.Label(f, text="Style note:").grid(row=row, column=0, sticky="e")
    self.style_var = tk.StringVar()
    ttk.Entry(f, textvariable=self.style_var).grid(
      row=row, column=1, columnspan=2, sticky="ew", padx=4,
    )

    row += 1
    ttk.Label(f, text="Provider:").grid(row=row, column=0, sticky="e")
    pf = ttk.Frame(f)
    pf.grid(row=row, column=1, columnspan=2, sticky="w")
    self.provider_var = tk.StringVar(value="openai")
    for p in llm.PROVIDERS:
      ttk.Radiobutton(
        pf, text=p, variable=self.provider_var, value=p,
        command=self._prefill_key,
      ).pack(side="left", padx=4)
    ttk.Label(pf, text="    Tier:").pack(side="left")
    self.tier_var = tk.StringVar(value="pro")
    for t in ("pro", "fast"):
      ttk.Radiobutton(
        pf, text=t, variable=self.tier_var, value=t,
      ).pack(side="left")

    row += 1
    ttk.Label(f, text="API key:").grid(row=row, column=0, sticky="e")
    self.key_var = tk.StringVar()
    ttk.Entry(
      f, textvariable=self.key_var, show="*",
    ).grid(row=row, column=1, sticky="ew", padx=4)
    ttk.Button(
      f, text="Save to keychain", command=self._save_key,
    ).grid(row=row, column=2)

    row += 1
    ttk.Label(f, text="Output:").grid(row=row, column=0, sticky="e")
    self.out_var = tk.StringVar(value=str(DEFAULT_OUTPUT))
    ttk.Entry(f, textvariable=self.out_var).grid(
      row=row, column=1, sticky="ew", padx=4,
    )
    ttk.Button(
      f, text="Browse...", command=self._browse_out,
    ).grid(row=row, column=2)

    row += 1
    ttk.Label(f, text="Mode:").grid(row=row, column=0, sticky="e")
    mf = ttk.Frame(f)
    mf.grid(row=row, column=1, columnspan=2, sticky="w")
    self.mode_var = tk.StringVar(value="image")
    for m, lbl in (
      ("image", "Image"),
      ("prompt", "Prompt only"),
      ("block", "Block only"),
    ):
      ttk.Radiobutton(
        mf, text=lbl, variable=self.mode_var, value=m,
      ).pack(side="left", padx=4)

    row += 1
    self.generate_btn = ttk.Button(
      f, text="Generate", command=self._start_generate,
    )
    self.generate_btn.grid(
      row=row, column=0, columnspan=3, sticky="e", pady=8,
    )

  def _build_log(self) -> None:
    self.log = tk.Text(
      self.root, height=10, wrap="none", font=("Menlo", 11),
      background="#111", foreground="#ddd",
    )
    self.log.pack(fill="both", expand=False, padx=10, pady=(0, 6))
    self.log.configure(state="disabled")

  def _build_preview(self) -> None:
    self.preview = ttk.Label(
      self.root, text="(image preview will appear here)",
      anchor="center",
    )
    self.preview.pack(fill="both", expand=True, padx=10, pady=10)
    self.preview.bind("<Button-1>", self._open_image)

  # init helpers ----------------------------------------------------

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

  def _prefill_key(self) -> None:
    self.key_var.set(_keychain_get(self.provider_var.get()))

  # actions ---------------------------------------------------------

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
    # Reorder so the chosen file is first.
    self.saves.sort(key=lambda e: (e.path != path, -e.mtime))
    self._populate_saves()

  def _on_save_selected(self, _evt) -> None:
    idx = self.save_combo.current()
    if idx < 0 or idx >= len(self.saves):
      return
    self.selected_save = self.saves[idx].path
    self._load_pawn_names_async()

  def _browse_out(self) -> None:
    chosen = filedialog.askdirectory(
      title="Pick output folder", initialdir=self.out_var.get(),
    )
    if chosen:
      self.out_var.set(chosen)

  def _save_key(self) -> None:
    ok = _keychain_set(self.provider_var.get(), self.key_var.get())
    if ok:
      self._append_log("Saved API key to keychain.")
    else:
      messagebox.showwarning(
        APP_NAME,
        "Couldn't reach the OS keychain. Install the [gui] extra "
        "(`pip install rimportrait[gui]`) or set the API key in "
        "your environment instead.",
      )

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

  # pawn discovery (worker thread) ---------------------------------

  def _load_pawn_names_async(self) -> None:
    if not self.selected_save:
      return
    self.pawn_combo["state"] = "disabled"
    self.pawn_combo["values"] = []
    self.pawn_var.set("")
    save_path = self.selected_save

    def work():
      try:
        from rimsave import (
          build_def_index_from_save, autodetect_mod_paths, load_save,
        )
        save = load_save(save_path)
        paths = autodetect_mod_paths()
        idx = None
        if paths.rimworld_data or paths.mods_dir or paths.workshop_dir:
          idx = build_def_index_from_save(save, paths)
        names = cli._list_pawn_names(save, idx, None)
      except Exception as exc:
        self.progress_q.put(f"!pawn-error!{exc}")
        return
      self.progress_q.put(f"!pawns!{json.dumps(names)}")

    threading.Thread(target=work, daemon=True).start()

  # generate (worker thread) ---------------------------------------

  def _start_generate(self) -> None:
    if not self.selected_save:
      messagebox.showerror(APP_NAME, "Pick a save first.")
      return
    idx = self.save_combo.current()
    if 0 <= idx < len(self.saves) and self.saves[idx].untested:
      gv = self.saves[idx].game_version or "?"
      ok = messagebox.askyesno(
        APP_NAME,
        f"This save is from RimWorld {_short_version(gv)}.\n\n"
        f"rimportrait is only tested against {TESTED_VERSION}; the "
        "output may be wrong (apparel layers, tech levels, body "
        "parts can drift). Generate anyway?",
        icon="warning",
      )
      if not ok:
        return
    mode = self.mode_var.get()
    provider = self.provider_var.get()
    if mode in ("image", "prompt"):
      key = self.key_var.get().strip()
      if not key:
        messagebox.showerror(
          APP_NAME,
          f"Paste your {provider} API key first (then click 'Save "
          "to keychain' to remember it).",
        )
        return
      os.environ[_PROVIDER_ENV[provider]] = key

    out_dir = Path(self.out_var.get()).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    preset = self.preset_var.get()
    if preset == "(none)":
      preset = None

    args = argparse.Namespace(
      savefile=self.selected_save,
      pawn=self.pawn_var.get().strip() or None,
      family=self.family_var.get(),
      out_dir=out_dir,
      block_only=(mode == "block"),
      block_and_instruction_only=False,
      prompt_only=(mode == "prompt"),
      preset=preset,
      style=self.style_var.get().strip() or None,
      provider=provider,
      model=self.tier_var.get(),
      rimworld_dir=None,
      no_defs=False,
    )

    self.generate_btn["state"] = "disabled"
    self._clear_log()
    cli.set_status_sink(lambda line: self.progress_q.put(line))
    cli.reset_clock()

    def work():
      rc = 1
      try:
        rc = cli.main_with_args(args)  # type: ignore[attr-defined]
      except SystemExit as se:
        rc = int(se.code) if isinstance(se.code, int) else 1
      except Exception:
        self.progress_q.put("!error!" + traceback.format_exc())
      finally:
        self.progress_q.put(f"!done!{rc}")

    threading.Thread(target=work, daemon=True).start()

  # log + queue plumbing -------------------------------------------

  def _poll_log_queue(self) -> None:
    try:
      while True:
        item = self.progress_q.get_nowait()
        if item.startswith("!pawns!"):
          names = json.loads(item[len("!pawns!"):])
          self.pawn_names = names
          self.pawn_combo["values"] = names
          self.pawn_combo["state"] = "readonly"
          if names and not self.pawn_var.get():
            self.pawn_combo.current(0)
        elif item.startswith("!pawn-error!"):
          self._append_log("Save scan failed: " + item[len("!pawn-error!"):])
        elif item.startswith("!error!"):
          self._append_log(item[len("!error!"):])
          messagebox.showerror(APP_NAME, item[len("!error!"):])
        elif item.startswith("!done!"):
          rc = item[len("!done!"):]
          self.generate_btn["state"] = "normal"
          cli.set_status_sink(None)
          if rc == "0":
            self._finish_success()
        else:
          self._append_log(_strip_ansi(item))
    except queue.Empty:
      pass
    self.root.after(80, self._poll_log_queue)

  def _append_log(self, line: str) -> None:
    self.log.configure(state="normal")
    self.log.insert("end", line + "\n")
    self.log.see("end")
    self.log.configure(state="disabled")

  def _clear_log(self) -> None:
    self.log.configure(state="normal")
    self.log.delete("1.0", "end")
    self.log.configure(state="disabled")

  def _finish_success(self) -> None:
    # Find the most recently written PNG/JPEG in out_dir.
    out_dir = Path(self.out_var.get()).expanduser()
    if not out_dir.is_dir():
      return
    images = [
      p for p in out_dir.iterdir()
      if p.suffix.lower() in (".png", ".jpg", ".jpeg")
    ]
    if not images:
      return
    latest = max(images, key=lambda p: p.stat().st_mtime)
    self.last_image = latest
    self._show_preview(latest)

  def _show_preview(self, path: Path) -> None:
    try:
      from PIL import Image, ImageTk
      img = Image.open(path)
      img.thumbnail((600, 400))
      photo = ImageTk.PhotoImage(img)
      self.preview_imgref = photo
      self.preview.configure(image=photo, text="")
    except Exception:
      self.preview.configure(
        text=f"Image ready: {path.name}\n(click to open)", image="",
      )
      self.preview_imgref = None


_ANSI_RE = None


def _strip_ansi(s: str) -> str:
  global _ANSI_RE
  if _ANSI_RE is None:
    import re
    _ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
  return _ANSI_RE.sub("", s)


def main() -> int:
  root = tk.Tk()
  App(root)
  root.mainloop()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
