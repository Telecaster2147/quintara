# PyInstaller spec for the independent console-subsystem CLI binary.
from pathlib import Path

root = Path.cwd()
hiddenimports = ["quintara._kernel.data", "quintara._kernel.utils"]

a = Analysis(
    [str(root / "packaging/cli_entrypoint.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(str(root / "src/quintara/model_config.json"), "quintara")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "hypothesis", "PySide6", "quintara.gui", "quintara.qml_gui", "quintara.qml_backend"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="quintara-cli", console=True)
