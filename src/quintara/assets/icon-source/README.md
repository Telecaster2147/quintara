# Quintara 图标来源与语义

母版 `quintara-icon-master.png` 由本项目在 2026-08-24 使用 OpenAI 图像生成工具按 Quintara 品牌需求生成，并由项目作者选定；作为项目自有美术资产随仓库许可证分发。

- **研究罗盘**：表达可追溯、方向明确的本地量化研究。
- **五档柱形**：表达结果是五只股票的排序组合，而非交易承诺。
- **青色与深海军蓝**：对应产品设计令牌；黄色仅用于最高档视觉锚点。
- **小尺寸版**：16/20/24 px 由 `packaging/export_icons.py` 使用 Qt 矢量绘制简化轮廓，避免直接缩放导致罗盘断裂。

运行 `.venv/bin/python packaging/export_icons.py` 可重复生成全部 PNG、Windows 多分辨率 ICO 和审阅清单。
