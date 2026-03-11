# 从 Supabase 迁移到 SQLite

本文档说明如何将 ZJU Charger 项目从 Supabase 数据库迁移到本地 SQLite 数据库。

## 迁移概述

本次迁移将数据库从云端 Supabase 服务迁移到本地 SQLite 文件数据库，主要变更：

- **数据库类型**：从 Supabase (PostgreSQL) 迁移到 SQLite
- **依赖变化**：移除 `supabase` Python 包依赖
- **配置变更**：环境变量从 `SUPABASE_*` 变更为 `SQLITE_*` 和 `HISTORY_ENABLED`
- **功能保持**：所有业务功能保持不变，只是存储方式从云端变为本地

## 迁移步骤

### 第一步：备份现有数据（如果需要）

如果你的 Supabase 数据库中有需要保留的历史数据，请先执行备份：

1. 登录 Supabase Dashboard
2. 进入你的项目
3. 点击左侧菜单 "Database" → "Backups"
4. 创建手动备份

或者使用 Supabase CLI：

```bash
# 安装 Supabase CLI（如果尚未安装）
npm install -g supabase

# 备份数据库
supabase db dump -f backup-$(date +%Y%m%d).sql
```

### 第二步：更新代码依赖

1. 拉取最新代码或确保你已使用新的代码版本

2. 重新安装依赖（移除了 supabase 包）：

```bash
# 使用 uv
uv sync --frozen

# 或使用 pip
pip install -r requirements.txt
```

### 第三步：更新环境变量配置

编辑 `.env` 文件，将 Supabase 配置替换为 SQLite 配置：

**旧的配置（Supabase）：**

```env
# Supabase 数据库配置（旧）
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key-here
SUPABASE_HISTORY_ENABLED=true
```

**新的配置（SQLite）：**

```env
# SQLite 数据库配置（新）
# 留空则使用默认路径：项目根目录/data/charger.db
SQLITE_DB_PATH=

# 历史记录模式配置
# 是否启用历史 usage 表记录，关闭后只维护 latest 缓存表
HISTORY_ENABLED=true
```

### 第四步：初始化 SQLite 数据库

启动服务器，系统会自动初始化 SQLite 数据库：

```bash
# 使用启动脚本
./serve.sh

# 或直接运行
uv run python -m server.run_server
```

首次启动时，系统会：

1. 创建 `data` 目录（如果不存在）
2. 创建 `data/charger.db` 数据库文件（如果不存在）
3. 根据 `db/schema.sql` 初始化表结构（`stations`、`latest`、`usage`）

### 第五步：数据迁移（可选）

如果你需要将 Supabase 中的历史数据迁移到 SQLite，可以使用以下 Python 脚本：

```python
#!/usr/bin/env python3
"""
从 Supabase 迁移数据到 SQLite
"""

import sqlite3
from supabase import create_client
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Supabase 配置（旧）
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# SQLite 配置（新）
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH") or "data/charger.db"

def migrate_data():
    """执行数据迁移"""

    # 连接 Supabase
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 连接 SQLite
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_cur = sqlite_conn.cursor()

    print("开始迁移数据...")

    # 1. 迁移 stations 表
    print("迁移 stations 表...")
    response = supabase.table("stations").select("*").execute()
    for row in response.data:
        sqlite_cur.execute("""
            INSERT OR REPLACE INTO stations
            (hash_id, name, provider, campus_id, campus_name, lat, lon, device_ids, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get("hash_id"),
            row.get("name"),
            row.get("provider"),
            row.get("campus_id"),
            row.get("campus_name"),
            row.get("lat"),
            row.get("lon"),
            str(row.get("device_ids", [])),  # 转换为 JSON 字符串
            row.get("created_at"),
            row.get("updated_at")
        ))
    print(f"已迁移 {len(response.data)} 条 stations 记录")

    # 2. 迁移 latest 表
    print("迁移 latest 表...")
    response = supabase.table("latest").select("*").execute()
    for row in response.data:
        sqlite_cur.execute("""
            INSERT OR REPLACE INTO latest
            (hash_id, snapshot_time, free, used, total, error)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            row.get("hash_id"),
            row.get("snapshot_time"),
            row.get("free"),
            row.get("used"),
            row.get("total"),
            row.get("error")
        ))
    print(f"已迁移 {len(response.data)} 条 latest 记录")

    # 3. 迁移 usage 表（可选，如果数据量大可能需要较长时间）
    print("迁移 usage 表（这可能需要一些时间）...")
    response = supabase.table("usage").select("*").execute()
    for row in response.data:
        sqlite_cur.execute("""
            INSERT INTO usage
            (hash_id, snapshot_time, free, used, total, error)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            row.get("hash_id"),
            row.get("snapshot_time"),
            row.get("free"),
            row.get("used"),
            row.get("total"),
            row.get("error")
        ))
    print(f"已迁移 {len(response.data)} 条 usage 记录")

    # 提交事务
    sqlite_conn.commit()
    sqlite_conn.close()

    print("数据迁移完成！")

if __name__ == "__main__":
    migrate_data()
```

将上述脚本保存为 `migrate_to_sqlite.py`，然后运行：

```bash
# 确保旧的 Supabase 配置仍在 .env 中
uv run python migrate_to_sqlite.py
```

### 第六步：验证迁移结果

1. 检查 SQLite 数据库文件是否存在：

```bash
ls -lh data/charger.db
```

2. 使用 SQLite 命令行工具查看数据：

```bash
sqlite3 data/charger.db "SELECT COUNT(*) FROM stations;"
sqlite3 data/charger.db "SELECT COUNT(*) FROM latest;"
sqlite3 data/charger.db "SELECT COUNT(*) FROM usage;"
```

3. 启动服务器并测试 API：

```bash
./serve.sh
```

访问 `http://localhost:8000/api/status` 验证数据是否正常返回。

### 第七步：清理旧配置

确认迁移成功后，可以从 `.env` 文件中删除旧的 Supabase 配置：

```env
# 可以删除以下配置
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_KEY=your-service-role-key-here
# SUPABASE_HISTORY_ENABLED=true
```

## 注意事项

### 数据格式差异

1. **JSON 字段**：SQLite 中的 `device_ids` 字段存储为 JSON 字符串，而 Supabase 使用 JSONB 类型。迁移时需要进行格式转换。

2. **时间格式**：SQLite 存储时间字符串（ISO 8601 格式），而 Supabase 使用 TIMESTAMPTZ。迁移时保持字符串格式即可。

3. **自增 ID**：SQLite 的 `usage.id` 字段使用 `AUTOINCREMENT`，而 Supabase 使用 `BIGSERIAL`。

### 性能考虑

1. **并发写入**：SQLite 在高并发写入场景下性能有限，但本项目设计为单线程后台写入，无需担心。

2. **数据量**：随着时间推移，`usage` 表会持续增长。建议：
   - 设置 `HISTORY_ENABLED=false` 如果不需要历史数据
   - 定期清理旧数据（参考 [07-sqlite-schema.md](./07-sqlite-schema.md#数据库维护)）

### 备份策略

**Supabase 时代**：

- 云端自动备份
- 可通过 Dashboard 手动备份

**SQLite 时代**：

- 需要手动备份文件
- 建议设置定时任务自动备份

```bash
# 添加到 crontab（每天凌晨 2 点备份）
0 2 * * * cp /path/to/data/charger.db /path/to/backups/charger-$(date +\%Y\%m\%d).db
```

## 回滚方案

如果迁移后遇到问题需要回滚到 Supabase：

1. 恢复 `.env` 中的 Supabase 配置
2. 重新安装 supabase 包：`uv add supabase`
3. 恢复旧版本代码或回滚 commit
4. 重启服务器

## 常见问题

### Q1：迁移后 API 返回 503 错误

**原因**：SQLite 数据库未正确初始化或数据未迁移成功。

**解决**：

1. 检查 `data/charger.db` 文件是否存在
2. 查看服务器日志获取详细错误信息
3. 确认数据库表结构已正确创建

### Q2：历史数据未迁移

**原因**：`migrate_to_sqlite.py` 脚本未运行或执行失败。

**解决**：

1. 检查 Supabase 凭证是否有效
2. 确认网络连接正常
3. 查看脚本输出的错误信息

### Q3：数据迁移后系统运行缓慢

**原因**：`usage` 表数据量过大导致查询变慢。

**解决**：

1. 设置 `HISTORY_ENABLED=false` 停止记录历史数据
2. 定期清理旧历史数据
3. 考虑使用 SQLite 的 `VACUUM` 命令压缩数据库

### Q4：Docker 部署时数据库文件丢失

**原因**：未正确挂载数据卷。

**解决**：
确保 `docker run` 或 `docker-compose.yml` 中包含数据卷挂载：

```yaml
volumes:
  - ./data:/app/data
```

## 迁移检查清单

完成迁移前，请确认以下项目：

- [ ] 已备份 Supabase 数据（如有需要）
- [ ] 已更新 `.env` 配置文件
- [ ] 已重新安装依赖（移除 supabase 包）
- [ ] SQLite 数据库文件已创建
- [ ] 数据库表结构已正确初始化
- [ ] 历史数据已迁移（如需要）
- [ ] API 测试通过
- [ ] 前端页面正常显示数据
- [ ] 已设置数据库备份计划
- [ ] 已清理旧的 Supabase 配置

恭喜！迁移完成后，你的项目将使用本地 SQLite 数据库，无需依赖任何云服务。
