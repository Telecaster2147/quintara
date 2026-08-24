# 错误目录

| 代码/消息 | 含义 | 处理 |
| --- | --- | --- |
| `CSV-FILE` | 文件不存在 | 检查路径 |
| `CSV-ENCODING` / `CSV-PARSE` | 编码或分隔符无法解析 | 导出 UTF-8 CSV 后重试 |
| `CSV-MAPPING` | 缺少必需行情字段 | 使用列映射或补齐字段 |
| `CSV-CODE`, `CSV-DATE`, `CSV-DUPLICATE` | 键字段问题 | 在源数据侧清理后重新验证 |
| `CSV-NUMERIC` | 必需行情数值无法解析或为非有限值 | 在源数据侧修正后重新验证 |
| `CSV-HISTORY` | 单只股票历史少于六个交易日 | 补足至少一个 T+1/T+5 标签窗口 |
| `CSV-ORDER` | 行顺序不是规范顺序（仅提示） | 可直接重新导入，Quintara 会生成排序后的快照 |
| `CSV-OHLC`, `CSV-RANGE` | OHLC 数值违反基本不变量 | 修正源数据 |
| `CSV-UNITS` | 单位声明缺失或与字段不匹配 | 在验证/导入命令中显式声明单位 |
| `NON_PIT_REQUIRED` | 当前只有静态成分快照 | 提供历史 PIT 成分，或显式选择无 PIT 回退 |
| `CUSTOM_UNIVERSE_SIZE` | 自定义池或有效截面少于 100 只 | 补足股票或切换到明确的基线路线 |
| `DATA-HASH-MISMATCH` | 已激活文件与 manifest hash 不一致 | 保留旧 generation，检查本地磁盘并重新更新 |
| `NO_ACTIVE_DATA` | 尚未发布数据快照 | 导入或更新数据 |
| `PIT cutoff` | 当前日期不满足成员合同 | 检查成员覆盖、上市日和交易日 |
| `DOC-ARCH`, `DOC-CPU`, `DOC-MEMORY`, `DOC-DISK` | 环境不满足稳定 CPU 路径的基础门槛 | 按 doctor 建议更换机器或释放资源 |
| `LockBusy` | 工作区已有任务 | 等待任务结束 |
| `BaoStock login/query failed` | 连接器认证或服务错误 | 检查账户、网络和服务状态 |
| `unresolved prediction tie` | 排名边界存在同分 | 检查输入规模、特征和随机种子 |
| `JOB_CANCELLED` | 用户请求停止，未发布结果 | 查看历史日志；下一次运行会从已验证 generation 开始 |
| `JOB_CACHE_HIT` | 数据和模型身份匹配，复用了已验证结果 | 直接查看对应结果；数据变化后会重新训练 |
