# PyInstaller spec for macOS .app bundle.
# Build: `pyinstaller pyinstaller-macos.spec`
# Output: dist/rimportrait.app

# pyright: reportUndefinedVariable=false
import sys
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
  datas=[
    ('packages/rimportrait/rimportrait/assets/logo.png',
     'rimportrait/assets'),
    ('packages/rimportrait/rimportrait/assets/icon.png',
     'rimportrait/assets'),
  ],
  hiddenimports=[
    'rimsave', 'rimportrait',
    'keyring.backends.macOS',
    'openai', 'google.genai',
    'PIL.Image', 'PIL.ImageTk',
  ],
  hookspath=[],
  hooksconfig={},
  runtime_hooks=[],
  excludes=[],
  win_no_prefer_redirects=False,
  win_private_assemblies=False,
  cipher=block_cipher,
  noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
  pyz, a.scripts, [],
  exclude_binaries=True,
  name='rimportrait',
  debug=False,
  bootloader_ignore_signals=False,
  strip=False,
  upx=False,
  console=False,
)
coll = COLLECT(
  exe, a.binaries, a.zipfiles, a.datas,
  strip=False, upx=False, name='rimportrait',
)
app = BUNDLE(
  coll,
  name='rimportrait.app',
  bundle_identifier='dev.owx.rimportrait',
  info_plist={
    'CFBundleShortVersionString': '0.1.0',
    'NSHighResolutionCapable': True,
  },
)
