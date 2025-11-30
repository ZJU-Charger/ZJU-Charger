# API 参考指南

本项目的 FastAPI 服务默认监听 `http://<host>:<port>`（开发环境为 `http://127.0.0.1:8000`）。所有接口支持 JSON 响应，并可以通过自动化文档查看：  

- Swagger UI: `http://<host>:<port>/docs`  
- ReDoc: `http://<host>:<port>/redoc`

> 以下示例均假设服务器运行在本机 `8000` 端口，如需远程访问请替换主机名和端口。

## GET `/api`

返回 API 元信息与简要说明，可用于健康检查或在前端展示欢迎语。  
示例：

```bash
curl http://127.0.0.1:8000/api
```

## GET `/api/config`

提供前端定时刷新等运行参数，目前仅返回 `fetch_interval`（单位：秒），前端会据此设置轮询频率。  

```bash
curl http://127.0.0.1:8000/api/config
```

## GET `/api/providers`

列出当前注册的服务商。响应格式为 `[{ "id": "neptune", "name": "neptune" }, ...]`，前端将这些 ID 用作筛选条件。  

```bash
curl http://127.0.0.1:8000/api/providers
```

## GET `/api/stations`

返回站点基础信息（元数据），包含 `hash_id/name/provider/campus/坐标/device_ids` 等字段，用于在实时数据缺失时补全列表。  

```bash
curl http://127.0.0.1:8000/api/stations
```

响应示例（节选）：

```json
{
  "updated_at": "2025-11-30T15:50:00+08:00",
  "stations": [
    {
      "id": "3e262917",
      "name": "玉泉教三北侧",
      "provider": "neptune",
      "campus": 2143,
      "latitude": 30.2696,
      "longitude": 120.1293,
      "devids": ["8120"]
    }
  ]
}
```

## GET `/api/status`

主查询接口，会优先读取 Supabase `latest` 缓存，失败时实时抓取。返回字段包括 `free/used/total/error` 以及 `devids/campus_name` 等。支持的查询参数：

- `provider`: 按服务商过滤（例如 `neptune`）。
- `hash_id`: 返回指定站点。
- `devid`: 与 `provider` 同时使用，按设备号定位站点。

示例：

```bash
# 查询所有站点
curl http://127.0.0.1:8000/api/status

# 查询尼普顿站点
curl "http://127.0.0.1:8000/api/status?provider=neptune"

# 按 hash_id 查询
curl "http://127.0.0.1:8000/api/status?hash_id=3e262917"

# 按 provider + devid 查询
curl "http://127.0.0.1:8000/api/status?provider=neptune&devid=8120"
```

## DingTalk & 其他 Webhook

项目暴露了 `/ding/webhook` 等钉钉机器人接口，具体签名、事件与示例请参考 [docs/05-dingbot.md](./05-dingbot.md)。

---

如需了解数据库表结构或历史数据使用方式，请结合 [docs/07-supabase-schema.md](./07-supabase-schema.md)。*** End Patch
