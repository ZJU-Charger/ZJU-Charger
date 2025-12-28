# Logfire Dashboard 指南

本指南结合当前服务端的日志/指标配置，介绍如何在 [Logfire](https://logfire.pydantic.dev/) 上启用内置看板、复制模板并构建与 ZJU Charger 后端匹配的自定义仪表盘。

## 1. 启用标准看板

1. 登录 Logfire Web 控制台，进入 **Dashboards** 选项卡。
2. 点击 **+ Dashboard** → 选择 **Standard**，启用官方提供的 `Usage Overview` 等看板。它们会自动展示数据量、成本等基础指标，适合作为健康监控的起点。
3. 如果需要在自定义看板中修改布局，可点击标准看板右上角的 “Download dashboard as code”，下载 JSON 作为模板再导入到 **Custom** → **Import JSON**。

> 标准看板不可直接编辑；复制后即可任意调整 Panel/查询。

## 2. 新建自定义看板

1. **Dashboards → + Dashboard → Custom**，输入名称（如 “Charger API 概览”）。
2. 新看板默认包含一个 Panel Group，可通过 **Panel Group** 按钮新增分区，建议拆分为 “流量 / 错误 / 降级”。
3. 在每个分区内点击 **Panel** → 选择图表类型（Time Series、Table、Bar 等），粘贴 SQL 或 Metric 查询后保存。可打开 **Edit layout** 拖动/缩放位置，完成后点击 **Save**。

## 3. 推荐变量与设置

为了快速筛选不同环境/服务，可在右侧 **Variables** 面板添加：

- `service_name`（List 型）：`SELECT DISTINCT service_name FROM records ORDER BY service_name`。
- `endpoint`（List 型）：`SELECT DISTINCT attributes->>'endpoint' FROM records WHERE attributes ? 'endpoint' ORDER BY 1`。
- `resolution`（内置）：用于 `time_bucket($resolution, start_timestamp)` 自动调整时间粒度。

引用方式：在 SQL 中写 `$service_name`、`$endpoint`，如 `WHERE service_name = $service_name`。

## 4. 面板示例

下列查询均针对 Logfire 默认 `records`（日志/Span）与 `metrics` 表，配合后端埋点字段：

### 4.1 API 请求趋势（Time Series）

```sql
SELECT
    time_bucket($resolution, start_timestamp) AS x,
    count() AS count,
    attributes->>'endpoint' AS endpoint
FROM records
WHERE service_name = $service_name
GROUP BY x, endpoint
ORDER BY x
```

**图表设置**：Time Series，多线显示不同 endpoint，颜色区分。

### 4.2 请求耗时分布（Histogram 或 Table）

```sql
SELECT
    approx_percentile_cont(0.95) WITHIN GROUP (ORDER BY duration) AS p95_ms,
    approx_percentile_cont(0.50) WITHIN GROUP (ORDER BY duration) AS p50_ms,
    attributes->>'endpoint' AS endpoint
FROM records
WHERE service_name = $service_name
  AND duration IS NOT NULL
GROUP BY endpoint
ORDER BY p95_ms DESC
```

可用于 Table 面板，快速定位慢接口。

### 4.3 状态码分布（Bar Chart）

配合自定义 Metric `api.requests`：

```sql
SELECT
    COUNT() AS count,
    metrics->>'api.requests.attributes.status_code' AS status_code
FROM records
WHERE service_name = $service_name
GROUP BY status_code
ORDER BY count DESC
LIMIT 10
```

如需可视化 2xx/4xx/5xx 占比，也可使用 Pie/Donut 图。

### 4.4 Fallback/降级监控

后端在 `/api/status` 路径记录了 `data_source` 属性（`cache`/`fallback`）与 `filter_mode`。可用下述查询统计最近触发次数：

```sql
SELECT
    COUNT() AS count,
    attributes->>'data_source' AS data_source,
    attributes->>'filter_mode' AS filter_mode
FROM records
WHERE service_name = $service_name
  AND attributes->>'endpoint' = '/api/status'
GROUP BY data_source, filter_mode
ORDER BY count DESC
```

若某段时间 `fallback` 占比升高，可进一步 drill-down 查看日志详情。

### 4.5 自定义警报 / Night Block 检查

若想确认夜间暂停时间内确实没有触发抓取，可针对 `BackgroundFetcher` 记录单独建表：

```sql
SELECT
    time_bucket($resolution, start_timestamp) AS x,
    count() AS fetch_runs
FROM records
WHERE service_name = $service_name
  AND span_name = '执行抓取与写入流程'
GROUP BY x
ORDER BY x
```

当连续多个时间桶 `fetch_runs = 0` 时，即可触发告警或在看板上展示红线。

## 5. 布局建议

- **Row 1：流量** – 请求趋势、状态码、限流命中等指标。
- **Row 2：健康度** – P95 延迟、错误日志按 endpoint 聚合。
- **Row 3：降级** – Fallback 次数、`stale` 响应统计。
- **Row 4：Fetcher** – 后台抓取成功/失败计数、最新 `snapshot_time`。

可在每个 Panel 的 Description 中说明指标来源（如 `api.requests` metric、`fallback` log），便于团队成员快速理解。

## 6. 版本管控

自定义看板 JSON 可导出后存入仓库（建议放在 `docs/logfire-dashboards/`），便于在不同环境复用。部署新环境时：

1. 在 Logfire 新项目导入 JSON。
2. 调整变量默认值（如 `service_name`）。
3. 验证查询是否有数据，必要时修改 `WHERE` 条件。

利用本文的查询模板结合 Logfire 的变量/布局功能，即可快速完成可观测性看板配置，并实时掌握 API 健康、降级情况以及后台抓取成功率。
