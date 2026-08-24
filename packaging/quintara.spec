# PyInstaller spec for the Windows/Linux desktop GUI binary.
from pathlib import Path

root = Path.cwd()
hiddenimports = ["quintara._kernel.data", "quintara._kernel.utils", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickControls2"]

a = Analysis(
    [str(root / "packaging/entrypoint.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[
        (str(root / "src/quintara/model_config.json"), "quintara"),
        (str(root / "src/quintara/qml"), "quintara/qml"),
        (str(root / "src/quintara/assets"), "quintara/assets"),
        (str(root / "docs/LEGAL_NOTICE.md"), "licenses"),
        (str(root / "docs/PRIVACY.md"), "licenses"),
        (str(root / "docs/THIRD_PARTY_NOTICES.md"), "licenses"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "hypothesis"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="Quintara",
    console=False,
    icon=str(root / "src/quintara/assets/icons/quintara.ico"),
)
