# SQLite 数据库表结构

本文档描述充电桩使用情况数据库的表结构设计。

## 数据库设计

系统采用"最新快照 + 历史记录"的三张表模型：

- **`latest` 表**：为每个站点保存一行最新快照，字段与 `usage` 表完全一致。
- **`stations` 表**：存储站点基础信息（几乎不变），给历史 usage 数据提供外键。
- **`usage` 表**：存储使用情况历史快照（每次抓取记录）。

> 如果只需要最新状态，可以在 `.env` 中设置 `HISTORY_ENABLED=false`，此时后台任务只会维护 `latest` 表，`usage` 表可选。

## 表结构

### 1. `latest` 表（最新快照）

为每个站点保存一条最新的使用情况数据，字段设计与 `usage` 表保持一致，区别在于：

- `latest` 中 `hash_id` 唯一（`PRIMARY KEY`），只保留最近一次抓取；
- `usage` 按时间累积全部快照，可用于历史分析。

#### SQL 建表语句

```sql
CREATE TABLE IF NOT EXISTS latest (
    hash_id TEXT PRIMARY KEY,
    snapshot_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    free INTEGER NOT NULL DEFAULT 0,
    used INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    error INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (hash_id) REFERENCES stations(hash_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_latest_station ON latest(hash_id);
```

#### 字段说明

| 字段            | 类型    | 说明                                                      |
| --------------- | ------- | --------------------------------------------------------- |
| `hash_id`       | TEXT    | 站点唯一标识，与 `stations.hash_id`、`usage.hash_id` 一致 |
| `snapshot_time` | TEXT    | 最近一次抓取完成时间（ISO 8601 格式字符串）               |
| `free`          | INTEGER | 可用充电桩数量                                            |
| `used`          | INTEGER | 已用充电桩数量                                            |
| `total`         | INTEGER | 总充电桩数量                                              |
| `error`         | INTEGER | 故障充电桩数量                                            |

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
    lat REAL,
    lon REAL,
    device_ids TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_stations_provider ON stations(provider);
CREATE INDEX IF NOT EXISTS idx_stations_campus ON stations(campus_id);
```

#### stations 表字段说明

| 字段          | 类型    | 说明                                          |
| ------------- | ------- | --------------------------------------------- |
| `hash_id`     | TEXT    | 站点唯一标识，`md5(provider:name)`            |
| `name`        | TEXT    | 站点名称                                      |
| `provider`    | TEXT    | 服务商标识（如 `neptune`）                    |
| `campus_id`   | INTEGER | 校区 ID（如 1=玉泉，2=紫金港）                |
| `campus_name` | TEXT    | 校区名称（可选）                              |
| `lat`         | REAL    | 纬度                                          |
| `lon`         | REAL    | 经度                                          |
| `device_ids`  | TEXT    | 与站点关联的 `device_ids` 列表（JSON 字符串） |
| `created_at`  | TEXT    | 创建时间                                      |
| `updated_at`  | TEXT    | 更新时间                                      |

### 3. `usage` 表（使用情况历史快照）

存储每次抓取时的站点使用情况数据，用于历史分析和趋势统计。

#### usage 表建表语句

```sql
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash_id TEXT NOT NULL,
    snapshot_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    free INTEGER NOT NULL DEFAULT 0,
    used INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    error INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (hash_id) REFERENCES stations(hash_id) ON DELETE CASCADE
);

-- 创建索引（非常重要，用于查询性能）
CREATE INDEX IF NOT EXISTS idx_usage_station_time ON usage(hash_id, snapshot_time DESC);
CREATE INDEX IF NOT EXISTS idx_usage_time ON usage(snapshot_time DESC);
```

#### usage 表字段说明

| 字段            | 类型    | 说明                                      |
| --------------- | ------- | ----------------------------------------- |
| `id`            | INTEGER | 主键，自增                                |
| `hash_id`       | TEXT    | 站点唯一标识（外键 → `stations.hash_id`） |
| `snapshot_time` | TEXT    | 抓取时间（ISO 8601 格式字符串）           |
| `free`          | INTEGER | 可用充电桩数量                            |
| `used`          | INTEGER | 已使用充电桩数量                          |
| `total`         | INTEGER | 总充电桩数量                              |
| `error`         | INTEGER | 故障充电桩数量                            |

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
SELECT * FROM latest;
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
  AND datetime(snapshot_time) >= datetime('now', '-24 hours')
ORDER BY snapshot_time DESC;
```

### 查询所有站点的最新使用情况

```sql
SELECT * FROM usage
GROUP BY hash_id
HAVING snapshot_time = MAX(snapshot_time);
```

### 统计某个站点的平均使用率

```sql
SELECT
    hash_id,
    CAST(SUM(used) AS REAL) / NULLIF(SUM(total), 0) * 100 AS avg_usage_rate
FROM usage
WHERE hash_id = '29e30f45'
  AND datetime(snapshot_time) >= datetime('now', '-7 days')
GROUP BY hash_id;
```

## 数据库文件位置

- **默认路径**：`data/charger.db`（相对于项目根目录）
- **自定义路径**：通过 `.env` 文件中的 `SQLITE_DB_PATH` 环境变量指定

## 数据库初始化

系统首次启动时会自动：

1. 创建 `data` 目录（如果不存在）
2. 创建数据库文件（如果不存在）
3. 执行 `db/schema.sql` 初始化表结构

## 注意事项

1. **数据量增长**：由于每次抓取都会插入记录，`usage` 表会快速增长。建议定期清理旧数据或设置 `HISTORY_ENABLED=false`。

2. **时间格式**：所有时间字段使用 ISO 8601 格式的字符串存储（如 `2025-03-11T12:34:56+08:00`），确保时区一致性。

3. **数据完整性**：插入 `usage` 记录前，确保对应的站点已存在于 `stations` 表中。

4. **性能优化**：批量插入时使用 `batch_insert_usage()` 函数，比单条插入效率更高。

5. **错误处理**：写入 `usage` 失败不应影响主流程（`latest` 表的保存）。

6. **并发限制**：SQLite 在高并发写入场景下有限制，但本项目设计为单线程后台写入，无需担心。

7. **备份建议**：建议定期备份 `data/charger.db` 文件以防止数据丢失。

## 数据库维护

### 清理旧数据

```sql
-- 删除 30 天前的历史数据
DELETE FROM usage
WHERE datetime(snapshot_time) < datetime('now', '-30 days');
```

### 数据库压缩

```bash
# 使用 SQLite 命令行工具压缩数据库
sqlite3 data/charger.db "VACUUM;"
```

### 备份数据库

```bash
# 方法 1：直接复制文件（需确保数据库未被写入）
cp data/charger.db data/charger-backup-$(date +%Y%m%d).db

# 方法 2：使用 SQLite 命令备份
sqlite3 data/charger.db ".backup data/charger-backup-$(date +%Y%m%d).db"
```
