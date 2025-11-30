# Supabase 数据库表结构

本文档描述充电桩使用情况数据库的表结构设计。

## 数据库设计

系统采用“最新快照 + 历史记录”的三张表模型：

- **`latest` 表**：为每个站点保存一行最新快照，字段与 `usage` 表完全一致。
- **`stations` 表**：存储站点基础信息（几乎不变），给历史 usage 数据提供外键。
- **`usage` 表**：存储使用情况历史快照（每次抓取记录）。

> 如果只需要最新状态，可以在 `.env` 中设置 `SUPABASE_HISTORY_ENABLED=false`，此时后台任务只会维护 `latest` 表，`usage` 表可选。

## 表结构

### 1. `latest` 表（最新快照）

为每个站点保存一条最新的使用情况数据，字段设计与 `usage` 表保持一致，区别在于：

- `latest` 中 `hash_id` 唯一（`PRIMARY KEY`），只保留最近一次抓取；
- `usage` 按时间累积全部快照，可用于历史分析。

#### SQL 建表语句

```sql
CREATE TABLE IF NOT EXISTS latest (
    hash_id TEXT PRIMARY KEY,
    snapshot_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    free INTEGER NOT NULL DEFAULT 0,
    used INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    error INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_latest_station ON latest(hash_id);
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `hash_id` | TEXT | 站点唯一标识，与 `stations.hash_id`、`usage.hash_id` 一致 |
| `snapshot_time` | TIMESTAMPTZ | 最近一次抓取完成时间 |
| `free` | INTEGER | 可用充电桩数量 |
| `used` | INTEGER | 已用充电桩数量 |
| `total` | INTEGER | 总充电桩数量 |
| `error` | INTEGER | 故障充电桩数量 |

### 2. `stations` 表（站点基础信息）

存储站点的基本信息，这些信息一般不会频繁变化。

#### stations 建表语句

```sql
CREATE TABLE IF NOT EXISTS stations (
    hash_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    campus_id INTEGER,
    campus_name TEXT,
    lat NUMERIC(10, 6),
    lon NUMERIC(10, 6),
    device_ids JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stations_provider ON stations(provider);
CREATE INDEX IF NOT EXISTS idx_stations_campus ON stations(campus_id);
```

#### stations 表字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `hash_id` | TEXT | 站点唯一标识，`md5(provider:name)` |
| `name` | TEXT | 站点名称 |
| `provider` | TEXT | 服务商标识（如 `neptune`） |
| `campus_id` | INTEGER | 校区 ID（如 2143, 1774） |
| `campus_name` | TEXT | 校区名称（可选） |
| `lat` | NUMERIC(10,6) | 纬度 |
| `lon` | NUMERIC(10,6) | 经度 |
| `device_ids` | JSONB | 与站点关联的 `device_ids` 列表（用于 provider+devid 查询） |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

### 3. `usage` 表（使用情况历史快照）

存储每次抓取时的站点使用情况数据，用于历史分析和趋势统计。

#### usage 表建表语句

```sql
CREATE TABLE IF NOT EXISTS usage (
    id BIGSERIAL PRIMARY KEY,
    hash_id TEXT NOT NULL,
    snapshot_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    free INTEGER NOT NULL DEFAULT 0,
    used INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    error INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT fk_usage_station FOREIGN KEY (hash_id) REFERENCES stations(hash_id) ON DELETE CASCADE
);

-- 创建索引（非常重要，用于查询性能）
CREATE INDEX IF NOT EXISTS idx_usage_station_time ON usage(hash_id, snapshot_time DESC);
CREATE INDEX IF NOT EXISTS idx_usage_time ON usage(snapshot_time DESC);
```

#### usage 表字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | BIGSERIAL | 主键，自增 |
| `hash_id` | TEXT | 站点唯一标识（外键 → `stations.hash_id`） |
| `snapshot_time` | TIMESTAMPTZ | 抓取时间（UTC+8） |
| `free` | INTEGER | 可用充电桩数量 |
| `used` | INTEGER | 已使用充电桩数量 |
| `total` | INTEGER | 总充电桩数量 |
| `error` | INTEGER | 故障充电桩数量 |

## 索引说明

### `stations` 表索引

- `idx_stations_provider`: 按服务商查询站点
- `idx_stations_campus`: 按校区查询站点

### `usage` 表索引

- `idx_usage_station_time`: 按站点和时间查询（最重要的索引）
  - 用于查询特定站点的历史数据
  - 使用 `DESC` 排序，便于获取最新数据
- `idx_usage_time`: 按时间查询所有站点数据
  - 用于时间范围查询和统计分析

## 外键约束

`usage` 表的 `hash_id` 字段通过外键关联到 `stations` 表的 `hash_id` 字段：

- `ON DELETE CASCADE`: 当站点被删除时，相关的使用情况记录也会被自动删除

## 使用示例

### 读取最新缓存

```sql
SELECT *
FROM latest;
```

### 查询某个站点的最新使用情况

```sql
SELECT * FROM usage
WHERE hash_id = '29e30f45'
ORDER BY snapshot_time DESC
LIMIT 1;
```

### 查询某个站点最近 24 小时的使用情况

```sql
SELECT * FROM usage
WHERE hash_id = '29e30f45'
  AND snapshot_time >= NOW() - INTERVAL '24 hours'
ORDER BY snapshot_time DESC;
```

### 查询所有站点的最新使用情况

```sql
SELECT DISTINCT ON (hash_id) *
FROM usage
ORDER BY hash_id, snapshot_time DESC;
```

### 统计某个站点的平均使用率

```sql
SELECT 
    hash_id,
    AVG(used::numeric / NULLIF(total, 0)) * 100 AS avg_usage_rate
FROM usage
WHERE hash_id = '29e30f45'
  AND snapshot_time >= NOW() - INTERVAL '7 days'
GROUP BY hash_id;
```

## Row Level Security (RLS) 配置

Supabase 默认启用 RLS，需要配置策略才能写入数据。有两种方案：

### 方案 1：使用 Service Role Key（推荐）

**适用于服务端应用**，Service Role Key 会绕过 RLS 策略。

1. 在 Supabase Dashboard 中获取 Service Role Key：
   - 进入项目设置 → API
   - 复制 `service_role` key（注意：这是**私密密钥**，不要暴露给客户端）

2. 在 `.env` 文件中配置：

   ```bash
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-service-role-key-here
   ```

### 方案 2：配置 RLS 策略

如果使用 `anon` key，需要配置 RLS 策略允许写入：

```sql
-- 为 stations 表启用 RLS（如果未启用）
ALTER TABLE stations ENABLE ROW LEVEL SECURITY;

-- 允许匿名用户插入和更新 stations 表
CREATE POLICY "Allow insert stations" ON stations
    FOR INSERT
    WITH CHECK (true);

CREATE POLICY "Allow update stations" ON stations
    FOR UPDATE
    USING (true)
    WITH CHECK (true);

-- 为 usage 表启用 RLS（如果未启用）
ALTER TABLE usage ENABLE ROW LEVEL SECURITY;

-- 允许匿名用户插入 usage 表
CREATE POLICY "Allow insert usage" ON usage
    FOR INSERT
    WITH CHECK (true);
```

### 允许其他客户端读取 latest 表（可选）

本项目的后台服务使用 **Service Role Key** 调用 Supabase，因此无需额外配置 RLS 就能读写 `latest` 缓存。如果你计划对外暴露 `anon` key 供其他客户端读取 `latest` 表，可手动启用 RLS 并添加只读策略：

```sql
ALTER TABLE latest ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow select latest" ON latest
    FOR SELECT
    USING (true);
```

> 根据实际需求调整 `USING` 条件，例如利用 `auth.jwt()` 限制来源域名。生产环境不要将 Service Role Key 暴露给前端。

## 注意事项

1. **数据量增长**：由于每次抓取都会插入记录，`usage` 表会快速增长。建议定期清理旧数据或使用分区表。

2. **时间格式**：所有时间字段使用 `TIMESTAMPTZ`（带时区的时间戳），确保时区一致性。

3. **数据完整性**：插入 `usage` 记录前，确保对应的站点已存在于 `stations` 表中。

4. **性能优化**：批量插入时使用 `batch_insert_usage()` 函数，比单条插入效率更高。

5. **错误处理**：写入 `usage` 失败不应影响主流程（`latest` 表的保存）。

6. **安全性**：**强烈建议使用 Service Role Key**，它专为服务端应用设计，会绕过 RLS 策略，适合后台任务使用。
