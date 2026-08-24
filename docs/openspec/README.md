# Quintara OpenSpec

本目录是 Quintara 的规范驱动开发入口。产品所有者决策来自
[`../REQUIREMENTS_GRILL.md`](../REQUIREMENTS_GRILL.md)，OpenSpec 将这些决策转换为可验证的
行为、架构和实施任务。

## 当前变更

- 变更：[`quintara-stable-v1`](openspec/changes/quintara-stable-v1/)
- 工作流：`spec-driven`
- 状态：4/4 规划工件完成，严格校验通过
- 实施状态：稳定版骨架、数据生命周期、内核适配、CLI/GUI、测试和发布链已落地；
  `tasks.md` 保留 42 项需要真实 PIT 供应商、原生包/干净主机或跨平台深测的后续门禁。

## 工件

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
openspec show quintara-stable-v1
```

本变更既是实现合同也是验收清单。已完成项必须有源码、测试或发布证据；保留的未勾选项
代表当前稳定版明确的外部依赖或后续增强，不在发布说明中伪装成已完成能力。
