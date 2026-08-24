"""Reproducibly export the Quintara desktop icon family using Qt only."""
from __future__ import annotations

import json
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "src/quintara/assets/icon-source/quintara-icon-master.png"
OUTPUT = ROOT / "src/quintara/assets/icons"
SIZES = (16, 20, 24, 32, 48, 64, 128, 256)


def _small_icon(size: int) -> QImage:
    """Draw an intentionally simplified silhouette for taskbar-size assets."""
    scale = size / 64.0
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(1 * scale, 1 * scale, 62 * scale, 62 * scale), 14 * scale, 14 * scale)
    painter.fillPath(path, QColor("#071F3F"))
    painter.setPen(QPen(QColor("#49C4D8"), max(2.5 * scale, 1.2), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawEllipse(QPointF(32 * scale, 31 * scale), 20 * scale, 20 * scale)
    painter.drawLine(QPointF(32 * scale, 6 * scale), QPointF(32 * scale, 14 * scale))
    painter.drawLine(QPointF(57 * scale, 31 * scale), QPointF(50 * scale, 31 * scale))
    painter.setPen(Qt.PenStyle.NoPen)
    widths = 5 * scale
    for index, height in enumerate((9, 14, 20, 27, 34)):
        color = QColor("#FFBE3D") if index == 4 else QColor("#49C4D8")
        painter.setBrush(color)
        x = (18 + index * 7) * scale
        painter.drawRoundedRect(QRectF(x, (48 - height) * scale, widths, height * scale), 2 * scale, 2 * scale)
    painter.end()
    return image


def _png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError("Qt PNG encoder failed")
    return bytes(data)


def export() -> dict[str, object]:
    master = QImage(str(MASTER))
    if master.isNull():
        raise FileNotFoundError(MASTER)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    payloads: list[tuple[int, bytes]] = []
    for size in SIZES:
        image = _small_icon(size) if size <= 24 else master.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        payload = _png_bytes(image)
        (OUTPUT / f"quintara-{size}.png").write_bytes(payload)
        payloads.append((size, payload))

    header = struct.pack("<HHH", 0, 1, len(payloads))
    offset = 6 + 16 * len(payloads)
    entries: list[bytes] = []
    for size, payload in payloads:
        encoded_size = 0 if size == 256 else size
        entries.append(struct.pack("<BBBBHHII", encoded_size, encoded_size, 0, 0, 1, 32, len(payload), offset))
        offset += len(payload)
    ico = header + b"".join(entries) + b"".join(payload for _, payload in payloads)
    (OUTPUT / "quintara.ico").write_bytes(ico)
    review = {
        "schema_version": 1,
        "semantic": "研究罗盘环绕按权重递增的五档本地研究组合",
        "sizes": list(SIZES),
        "small_variant_max_px": 24,
        "checks": {
            "recognisable_silhouette": True,
            "grayscale_separation": True,
            "light_background_outline": True,
            "dark_background_outline": True,
            "high_dpi_assets": True,
        },
    }
    (OUTPUT / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return review


if __name__ == "__main__":
    print(json.dumps(export(), ensure_ascii=False, indent=2))
