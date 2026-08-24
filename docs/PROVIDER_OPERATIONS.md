# 供应方生产数据运维与许可决策

## 发布合同

- Channel schema：`quintara-channel-v1`；release 记录语义版本、固定 HTTPS origin、平台、长度、ETag、SHA-256 与 dataset manifest URL。
- Dataset schema：`quintara-dataset-v1`；必须包含数据集 ID/版本、平台、`quintara-close5-open1-v1` 标签、研究路线、逐文件长度/SHA-256、来源、许可和 PIT 闭包材料。
- 首个稳定 channel 托管在项目 GitHub Pages：`https://telecaster2147.github.io/quintara/data/stable/channel.json`；不可变包放在 GitHub Release `data-v1`，channel 只引用固定版本及摘要。应用固定 Pages origin，下载重定向后的 Release asset 身份也写入 channel。
- 签名策略：v2 首发同时校验固定 HTTPS 发布端、channel 离线签名和逐文件 SHA-256；签名公钥随应用发布并通过应用升级轮换。实现中的摘要/端点门禁已就位，生产密钥接入属于候选发布凭证步骤。
- CDN：channel `no-cache`，manifest 短缓存且 ETag 强校验，内容寻址对象 `immutable,max-age=31536000`；相同 URL 的 ETag/长度变化使断点内容失效。

## 故障与发布

下载支持 Range 分块、字节进度、协作取消、断点续传及指数退避。磁盘需容纳包和 staging 两份。文件逐一校验；失败目录隔离，不改动活动 generation。安装介质 ZIP/目录经过同一个 manifest 验证器和 `DataManager.publish` 路径，因此与精简安装器联网下载等价。

受控故障矩阵包括断网、对象 ETag 变化、损坏分块、空间不足、许可缺失和取消。channel/manifest 变更先在 staging channel 发布，通过离线介质等价测试后再提升 stable。

首个离线介质范围决定为 **最近五个完整自然年到最近已审阅交易日** 的标准 PIT 路线：它覆盖默认五年训练、体积可控，并避免携带应用不会默认使用的更早材料。最终介质大小、截止日、许可依据和 100 只历史截面证据写入 release evidence；未满足任一项时仅交付精简安装器。

## 许可审查记录

Quintara 自有 fixture 可随仓库许可分发。BaoStock 是上游查询来源；应用不把 BaoStock 客户端访问能力解释为历史数据再分发许可。任何生产历史包在发布前必须保存：数据权利人、抓取/加工日期、允许的地域与交付方式、归属文字、保留期限及书面再分发依据。内置介质和联网下载分别审查；依据缺失时 stable channel 保持空索引，用户仍可导入自己的 CSV 或自行更新。
