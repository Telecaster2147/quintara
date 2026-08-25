# PyInstaller spec for the Windows/Linux desktop GUI binary.
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs

root = Path.cwd()
hiddenimports = ["quintara._kernel.data", "quintara._kernel.utils", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickControls2"]
lightgbm_binaries = collect_dynamic_libs("lightgbm")


def windows_runtime_binaries():
    if sys.platform != "win32":
        return []
    search_roots = [
        Path(sys.base_prefix),
        Path(sys.base_prefix) / "Lib/site-packages/PySide6",
        Path(sys.base_prefix) / "Lib/site-packages/shiboken6",
        Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32",
    ]
    resolved = []
    for name in ("vcomp140.dll", "msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
        source = next((base / name for base in search_roots if (base / name).is_file()), None)
        if source is not None:
            resolved.append((str(source), "."))
    return resolved


lightgbm_binaries += windows_runtime_binaries()

a = Analysis(
    [str(root / "packaging/entrypoint.py")],
    pathex=[str(root / "src")],
    binaries=lightgbm_binaries,
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
