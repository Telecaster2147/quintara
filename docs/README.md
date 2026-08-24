# Quintara 文档索引

Quintara 是对 `/home/olm/bigdata/bigdata` 现有大数据比赛生产内核的产品化包装。

## 文档

- [总体产品设计](PRODUCT_DESIGN.md)
- [生产内核对齐契约](KERNEL_ALIGNMENT.md)
- [内核 lineage 与差分边界](KERNEL_LINEAGE.md)
- [PIT 与 BaoStock 来源决策](ADR-001-PIT-AND-BAOSTOCK.md)
- [Windows / WSL 适配审计](WINDOWS_WSL_COMPATIBILITY.md)
- [Codex Skills 配置记录](SKILLS.md)
- [需求拷问记录](REQUIREMENTS_GRILL.md)
- [首次使用](FIRST_USE.md)
- [CSV 字段字典](CSV_FIELD_DICTIONARY.md)
- [OpenSpec 规范入口](openspec/README.md)
- [需求追踪矩阵](openspec/TRACEABILITY.md)

## 当前阶段

需求访谈已经闭合。当前规范权威顺序为：

1. `REQUIREMENTS_GRILL.md` 中最新的 CONFIRMED/SUPERSEDED 决策；
2. `openspec/openspec/changes/quintara-stable-v1/` 中通过严格校验的 Proposal、Specs、Design、Tasks；
3. 其余总体设计和适配文档作为背景与历史审计材料。

OpenSpec 变更已进入实现阶段。产品入口位于仓库根目录的 `src/quintara`，
安装、CLI、GUI、数据生命周期和测试说明见根目录 `README.md` 与本目录运维文档。
