# Synthetic fixture

这些 CSV 只用于离线单元/集成/差分测试，不是随安装包交付的历史行情数据，也不代表真实市场。
`generate.py` 使用固定种子重新生成，`manifest.json` 记录输入 hash。产品首次运行仍从用户选择的
BaoStock/PIT 来源下载本地数据。
