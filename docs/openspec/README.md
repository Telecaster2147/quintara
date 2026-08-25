# Quintara OpenSpec

本目录是 Quintara 的规范驱动开发入口。产品所有者决策来自
[`../REQUIREMENTS_GRILL.md`](../REQUIREMENTS_GRILL.md)，OpenSpec 将这些决策转换为可验证的
行为、架构和实施任务。

## 当前变更

- 变更：[`quintara-product-experience-v2`](openspec/changes/quintara-product-experience-v2/)
- 工作流：`spec-driven`
- 状态：4/4 规划工件完成，严格校验通过，等待独立的实施轮次
- 范围：开发者参考数据/用户 CSV 的首次选择与本地训练、Qt Quick/QML 产品体验、
  长任务恢复、结果工作区、Quintara 品牌图标、Windows GUI/CLI 双入口和真实跨平台 GUI 发布证据

## 已有基线

- 变更：[`quintara-stable-v1`](openspec/changes/quintara-stable-v1/)
- 工作流：`spec-driven`
- 状态：4/4 规划工件完成，严格校验通过
- 实施状态：稳定版骨架、数据生命周期、内核适配、CLI/GUI、测试和发布链已落地；
  `tasks.md` 保留 42 项需要真实 PIT 供应商、原生包/干净主机或跨平台深测的后续门禁。

## 工件

- [v2 Proposal](openspec/changes/quintara-product-experience-v2/proposal.md)：本轮目标、边界、能力和影响
- [v2 Design](openspec/changes/quintara-product-experience-v2/design.md)：QML 架构、生产数据包、状态机、存储、迁移和测试设计
- [v2 Tasks](openspec/changes/quintara-product-experience-v2/tasks.md)：12 个依赖有序里程碑的实施与验收清单
- [v2 Specs](openspec/changes/quintara-product-experience-v2/specs/)：6 项产品体验与数据交付能力规范
- [Proposal](openspec/changes/quintara-stable-v1/proposal.md)：目标、非目标、能力和影响
- [Design](openspec/changes/quintara-stable-v1/design.md)：架构、状态机、存储、身份、平台和测试设计
- [Tasks](openspec/changes/quintara-stable-v1/tasks.md)：依赖顺序的实现与验收清单
- [Specs](openspec/changes/quintara-stable-v1/specs/)：13项能力的规范要求与场景
- [Traceability](TRACEABILITY.md)：Grill 决策到 OpenSpec 能力的追踪

## 本地命令

从本目录执行：

```bash
openspec status --change quintara-stable-v1
openspec validate quintara-stable-v1 --strict
openspec status --change quintara-product-experience-v2
openspec validate quintara-product-experience-v2 --strict
openspec show quintara-stable-v1
```

本变更既是实现合同也是验收清单。已完成项必须有源码、测试或发布证据；保留的未勾选项
代表当前稳定版明确的外部依赖或后续增强，不在发布说明中伪装成已完成能力。
