# 隐私与遥测

“遥测”指软件在用户不主动操作时，把使用统计、错误、设备或行为信息发送到
远端。Quintara 默认关闭遥测：不埋点、不上传崩溃、不采集账户或路径。

联网动作只有两类：

1. 用户点击/调用 BaoStock 更新时，向 BaoStock 登录并请求数据；
2. 用户显式打开版本检查时，请求 GitHub release 元数据。

请求、账户和缓存不写入产品结果 manifest。环境诊断只写在本地，导出前由用户
决定是否分享。

`quintara diagnostics --output diagnostics.zip` 可生成本地 ZIP；其中只有脱敏诊断 JSON
和说明文件，默认不包含原始行情 CSV，也没有上传步骤。
