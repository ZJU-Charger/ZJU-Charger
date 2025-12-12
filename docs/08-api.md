# API 参考指南

- [Swagger UI](https://charger.philfan.cn/docs)  
- [ReDoc](https://charger.philfan.cn/redoc)

> 注意：旧版 `/api/web` 接口已淘汰，统一使用本文列出的 REST 端点。

## GET `/api`

返回 API 元信息与简要说明，可用于健康检查或在前端展示欢迎语。  
示例：

```bash
curl http://127.0.0.1:8000/api
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
      "campus": 1,
      "latitude": 30.2696,
      "longitude": 120.1293,
      "devids": ["8120"]
    }
  ]
}
```

## GET `/api/status`

主查询接口，永远从 Supabase `latest` 表读取实时快照；后台抓取程序会异步刷新该表。返回字段包括 `free/used/total/error` 以及 `devids/campus_name` 等。支持的查询参数：

- `provider`: 按服务商过滤（例如 `neptune`）。
- `hash_id`: 返回指定站点，必须是 8 位十六进制字符串（如 `3e262917`）。
- `devid`: 与 `provider` 同时使用，按设备号定位站点。

如果携带任意过滤条件却查不到数据，API 会返回 `404 未找到匹配站点或设备`；只有在完全不带过滤参数时才可能收到 `"stale": true` 的内存快照。

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

# 错误示例：devid 不存在会返回 404
curl -i "http://127.0.0.1:8000/api/status?provider=neptune&devid=bad_id"


# 错误示例：携带 devid 但遗漏 provider（返回 400）
curl -i "http://127.0.0.1:8000/api/status?devid=8120"

# 错误示例：hash_id 长度不足 8（返回 422）
curl -i "http://127.0.0.1:8000/api/status?hash_id=1234"

# 错误示例：hash_id 含非法字符（返回 422）
curl -i "http://127.0.0.1:8000/api/status?hash_id=../etc/passwd"

# 错误示例：provider 含非法字符（返回 422）
curl -i "http://127.0.0.1:8000/api/status?provider=../etc/passwd"
```

## DingTalk & 其他 Webhook

项目暴露了 `/ding/webhook` 等钉钉机器人接口，具体签名、事件与示例请参考 [docs/05-dingbot.md](./05-dingbot.md)。

---

如需了解数据库表结构或历史数据使用方式，请结合 [docs/07-supabase-schema.md](./07-supabase-schema.md)。
