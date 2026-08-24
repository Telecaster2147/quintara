# CSV 字段字典与单位

导入行情 CSV 时，Quintara 接受中文 BaoStock 字段名或通过 `--mapping` 显式映射到下列规范字段。
每个导入都必须声明单位；声明只写入 manifest，不会修改源文件。

| 规范字段 | 常见列名 | 单位 |
| --- | --- | --- |
| `stock_id` | `股票代码`, `code` | 六位证券代码 |
| `date` | `日期`, `date` | `YYYY-MM-DD` 交易日 |
| `open`, `close`, `high`, `low` | `开盘`, `收盘`, `最高`, `最低` | 人民币价格 |
| `volume` | `成交量` | 用户声明的股/手量纲 |
| `amount` | `成交额` | 用户声明的人民币金额量纲 |
| `amplitude` | `振幅` | 百分比数值 |
| `change_amount` | `涨跌额` | 人民币价格差 |
| `turnover` | `换手率` | 百分比数值 |
| `change_pct` | `涨跌幅` | 百分比数值 |

示例：

```bash
quintara csv validate market.csv \
  --units '{"open":"price","close":"price","high":"price","low":"price","volume":"volume","amount":"amount","turnover":"percentage","change_pct":"percentage"}'
```

必需键为 `(stock_id,date)`；代码必须六位，OHLC 必须为正且满足 high/low 基本范围，
每个股票至少六个交易会话。失败报告会保留源 hash、字段、行数和最多 100 个问题样本。
需要单独下载问题行时可执行：

```bash
quintara csv validate market.csv --issue-sample ./diagnostics/issues.csv
```
额外财务/估值/行业字段可以留在源文件，但 stable v1 不会进入模型特征矩阵。
