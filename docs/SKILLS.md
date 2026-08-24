# Quintara Codex Skills 配置记录

记录日期：2026-08-23

## 1. 工作方式

Codex skills 不是常驻后台服务。skill 安装后，由其 `description` 在相关任务中自动触发；
新安装 skill 在下一轮/重启 Codex 后进入技能发现列表。Quintara 不强制所有 skill 在每个
任务中同时加载，而是按阶段启用，避免互相冲突和不必要上下文。

## 2. 已存在并按需启用

| Skill | Quintara 用途 | 触发阶段 |
|---|---|---|
| `grill-me` | 深入访谈、收敛产品需求 | 总体设计之后 |
| `ask-questions-if-underspecified` | 实施前关闭关键歧义 | 需求/接口设计 |
| `property-based-testing` | CSV、归一化、合并、权重和发布不变量 | 测试设计 |
| `sharp-edges` | 配置、更新、任务和 API 易误用审查 | API/配置设计 |
| `code-review-expert` | 高质量变更评审 | 每个实现阶段 |
| `insecure-defaults` | 本地文件、凭据、更新和权限默认值 | 发布前 |
| `security-threat-model` | 桌面进程、更新链路、数据导入威胁建模 | 发布前 |
| `supply-chain-risk-auditor` | Python、前端和安装依赖风险 | 发布前 |
| `semgrep` | Python/Qt 应用静态扫描 | 实现后 |
| `security-best-practices` | 桌面应用、文件与网络边界检查 | 实现期 |
| `openai-docs` | 核对 Codex skills 机制和官方目录 | 工具配置 |

以上 skills 已位于当前 Codex 用户技能目录；相关任务出现时按描述自动使用。

## 3. 本次新安装

| Skill | 来源 | 安装位置 | 用途 |
|---|---|---|---|
| `cli-creator` | `openai/skills` curated | `/home/olm/.codex/skills/cli-creator` | CLI 命令、JSON、doctor、凭据与测试契约 |
| `playwright` | `openai/skills` curated | `/home/olm/.codex/skills/playwright` | 已安装但当前独立桌面 GUI 路线不使用 |
| `modern-python` | `trailofbits/skills` | `/home/olm/.codex/skills/modern-python` | uv、ruff、类型检查、pytest 和现代 Python 工程 |
| `planning-with-files` | `OthmanAdi/planning-with-files`，Trail of Bits curated 清单推荐 | `/home/olm/.codex/skills/planning-with-files` | 长周期产品化计划与跨会话记录 |

`security-best-practices` 已预先安装，因此未重复下载。

## 4. 安装验证

每个新 skill 应满足：

- 安装目录存在；
- 根目录包含 `SKILL.md`；
- YAML frontmatter 包含 `name` 和 `description`；
- 来源与预期仓库一致；
- 新会话中出现在可发现技能列表。

官方安装说明：<https://github.com/openai/skills/blob/main/README.md>

## 5. 使用顺序

1. 已使用 `grill-me` 完成稳定版需求闭合；
2. 使用 `planning-with-files` 和 OpenSpec 固化长期计划和决策；
3. 用 `modern-python` 建立项目骨架和质量工具；
4. 用 `cli-creator` 设计 CLI；
5. 用 Qt 自动化测试桌面 GUI；
6. 关键校验器使用 `property-based-testing`；
7. 发布前执行 code review、默认值、安全、供应链和静态扫描。
