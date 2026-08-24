# ADR-001：BaoStock 行情与 PIT 成员来源边界

日期：2026-08-23

## 决定

- `query_history_k_data_plus` 用于日行情和 extra-feature 原始存储；`query_stock_basic`
  用于上市/退市基础信息。
- `query_hs300_stocks(date=...)` 可按 BaoStock 的 `updateDate` 返回指定日期的成分快照，但不自动宣称为历史
  PIT 区间。产品更新没有可验证的历史 PIT 侧车时写入 `NON_PIT_FALLBACK` 元数据，
  并要求用户显式确认后才能创建该路线。
- 若用户提供经过验证的 `pit_membership_csv`（含 `stock_id,index_code,start_date,end_date`），
  更新 generation 才能走 `PIT_BASELINE`，并继续执行逐日期 exact-member gate。
- extra features 可以随 generation 保存，stable v1 的 feature allowlist 不读取它们。

## 依据

BaoStock 的 Python API 对 `query_hs300_stocks(date=...)` 明确提供日期参数，返回
`updateDate/code/code_name`；官方下载规划将它标识为 `(code, update_date)` 成分表。
这使它适合作为 PIT 侧车的原始候选来源，但产品仍要求保存完整的有效区间和来源 hash，
不能只拿一次当前快照就推断 2015 至今的历史有效区间。参见上游 API/下载规划：
<https://github.com/zxygithub/baostock/blob/master/docs/data_download_plan.md>。

BaoStock 官方站点提供知识库和 API 入口：<https://www.baostock.com/>。产品不会在代码中
复述或扩大上游服务条款；发布前由维护者重新核对当前条款和归属信息。

## 影响

这条边界让产品宁可阻止不完整 PIT 声明，也不把当前成分快照伪装成历史 PIT。用户仍可
在明确的 survivorship-bias 警告下使用 `NON_PIT_FALLBACK`，且其 route、manifest 和结果
身份永久分离。
