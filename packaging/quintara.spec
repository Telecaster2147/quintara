# PyInstaller spec for the standalone Qt/CLI binary.
from pathlib import Path

root = Path.cwd()
hiddenimports = ["quintara._kernel.data", "quintara._kernel.utils", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"]

a = Analysis(
    [str(root / "packaging/entrypoint.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(str(root / "src/quintara/model_config.json"), "quintara")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="Quintara", console=True)
