"""Audit one versioned icon family across Qt, Linux and Windows packaging touchpoints."""
from __future__ import annotations

import json
import struct
from pathlib import Path

from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 20, 24, 32, 48, 64, 128, 256)


def read_ico(path: Path) -> list[tuple[int, int]]:
    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    if (reserved, kind) != (0, 1):
        raise ValueError("ICO header is invalid")
    values = []
    for index in range(count):
        width, height, _colors, _reserved, _planes, _bits, byte_count, offset = struct.unpack_from("<BBBBHHII", data, 6 + index * 16)
        width = width or 256
        height = height or 256
        payload = data[offset : offset + byte_count]
        image = QImage.fromData(payload, "PNG")
        if image.isNull() or image.width() != width or image.height() != height:
            raise ValueError(f"ICO entry {width}x{height} is not a matching PNG")
        values.append((width, height))
    return values


def main() -> int:
    assets = ROOT / "src/quintara/assets"
    ico = assets / "icons/quintara.ico"
    entries = read_ico(ico)
    pngs = {size: (assets / "icons" / f"quintara-{size}.png").is_file() for size in SIZES}
    review = json.loads((assets / "icons/review.json").read_text(encoding="utf-8"))
    checks = {
        "ico_entries": entries == [(size, size) for size in SIZES],
        "png_family": all(pngs.values()),
        "source_record": (assets / "icon-source/README.md").is_file(),
        "qt_window_path": "quintara-icon.png" in (ROOT / "src/quintara/qml_gui.py").read_text(encoding="utf-8"),
        "pyinstaller_path": "quintara.ico" in (ROOT / "packaging/quintara.spec").read_text(encoding="utf-8"),
        "installer_path": "SetupIconFile" in (ROOT / "packaging/windows/Quintara.iss").read_text(encoding="utf-8"),
        "shortcut_icon": "IconFilename" in (ROOT / "packaging/windows/Quintara.iss").read_text(encoding="utf-8"),
        "linux_desktop_path": (
            "hicolor/${size}x${size}/apps" in (ROOT / "packaging/install_linux.sh").read_text(encoding="utf-8")
            and "quintara-${size}.png" in (ROOT / "packaging/install_linux.sh").read_text(encoding="utf-8")
        ),
        "review_checks": all(review.get("checks", {}).values()),
    }
    evidence = {"schema_version": 1, "sizes": list(SIZES), "entries": entries, "checks": checks, "passed": all(checks.values())}
    output = ROOT / "dist/icon-release-audit.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
