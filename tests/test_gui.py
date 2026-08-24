from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from quintara.gui import MainWindow


def test_qt_shell_has_required_navigation(app_root):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(app_root)
    labels = [window.tabs.tabText(index) for index in range(window.tabs.count())]
    assert {"概览", "数据", "股票池", "训练与预测", "结果", "运行历史", "设置", "环境诊断"}.issubset(labels)
    assert not window.service.paths.lock.exists()
    window.close()
    app.processEvents()
