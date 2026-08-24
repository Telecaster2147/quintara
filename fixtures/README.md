# Synthetic fixture

这些 CSV 只用于离线单元/集成/差分测试，不是随安装包交付的历史行情数据，也不代表真实市场。
`generate.py` 使用固定种子生成 120 只股票、70 个交易日，使夹具跨过自定义股票池 100 只门禁。
`synthetic_routes.json` 为 `PIT_BASELINE`、`CUSTOM_UNIVERSE`、`NON_PIT_FALLBACK` 提供相互隔离的
路线身份；`manifest.json` 记录输入 hash。产品首次运行仍由用户选择供应方数据或自己的 CSV。
