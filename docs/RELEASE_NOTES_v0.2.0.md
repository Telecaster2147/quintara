# Quintara 0.2.0 候选发布说明

- 新增现代 Qt Quick 中文工作台、五步向导、浅色/深色主题、紧凑导航、无障碍焦点及研究罗盘桌面图标。
- 新增供应方数据包/断点下载合同、受管 CSV、可迁移内容根、统一长任务恢复、命名股票池、Top-5 与原子 CSV 导出。
- Windows GUI 与 CLI 拆分，桌面启动及 GUI 后台任务使用无控制台策略。
- v1 数据/模型/结果保持只读兼容；缺少完整路线/标签/哈希身份的旧 generation 标记待重新验证，身份交叉复用继续 fail-closed。
- Windows 10 22H2、WSLg 和实验 NVIDIA GPU 路径列为 best-effort；生产 channel 启用取决于数据再分发书面依据和签名/CDN 凭证。
- Linux 正式发行物固定由 Ubuntu 22.04/glibc 2.35 builder 生成；`elf_compat_audit.py` 通过后才可用于 Debian 12/13 交付。当前本地 Ubuntu 24 调试 bundle 仍标记为预发布。

回滚演练：保留上一应用发行物与 `active.json`/catalog 引用；应用回滚不改写 generation。若新 catalog 指针失败，原子恢复上一指针并重新验证 manifest 哈希。
