# PyInstaller spec for Windows single-file exe.
# Build: `pyinstaller pyinstaller-windows.spec`
# Output: dist/rimportrait.exe

# pyright: reportUndefinedVariable=false
from pathlib import Path

block_cipher = None
project_root = Path.cwd()

a = Analysis(
  ['packages/rimportrait/rimportrait/gui.py'],
  pathex=[
    str(project_root / 'packages/rimportrait'),
    str(project_root / 'packages/rimsave'),
  ],
  binaries=[],
  datas=[('docs/logo.png', 'docs')],
  hiddenimports=[
    'rimsave', 'rimportrait',
    'keyring.backends.Windows',
    'openai', 'google.genai',
    'PIL.Image', 'PIL.ImageTk',
  ],
  hookspath=[],
  hooksconfig={},
  runtime_hooks=[],
  excludes=[],
  cipher=block_cipher,
  noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
  pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
  name='rimportrait',
  debug=False,
  bootloader_ignore_signals=False,
  strip=False,
  upx=False,
  upx_exclude=[],
  runtime_tmpdir=None,
  console=False,
  disable_windowed_traceback=False,
  argv_emulation=False,
  target_arch=None,
  codesign_identity=None,
  entitlements_file=None,
)
