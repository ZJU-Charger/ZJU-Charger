# Server 端部署

本文档介绍如何部署 ZJU Charger 的后端服务器。

## 系统要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 包管理器（建议使用 `curl -LsSf https://astral.sh/uv/install.sh | sh` 或 Homebrew 安装）
- 网络连接（用于访问充电桩服务商 API 及 PyPI）

## 快速启动

### 1. 安装依赖

```bash
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple  # 可选：使用清华镜像
uv sync --frozen
```

### 2. 配置环境变量

创建 `.env` 文件：

```shell
# 钉钉机器人配置（可选，暂未启用）
# DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
# DINGTALK_SECRET=your_secret_here

# API 服务器配置
API_HOST=0.0.0.0
API_PORT=8000

# 数据抓取配置
BACKEND_FETCH_INTERVAL=300

# 限流配置
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=60/hour
RATE_LIMIT_STATUS=3/minute

# SQLite 数据库配��（可选）
# 留空则使用默认路径：项目根目录/data/charger.db
# SQLITE_DB_PATH=/path/to/your/database.db

# 历史记录模式配置（可选）
# 是否启用历史 usage 表记录，关闭后只维护 latest 缓存表
# HISTORY_ENABLED=true
```

### 3. 启动服务器

#### 方式一：使用启动脚本（推荐）

```bash
./serve.sh
```

`serve.sh` 会自动执行以下检查和初始化步骤：

1. ✅ 检查 `uv` 包管理器是否已安装
2. 📦 同步项目依赖（遵循 `uv.lock`）
3. 🔍 检查 SQLite3 支持是否正常
4. 🗄️ 初始化数据库（自动创建 `data/charger.db` 和相关表结构）
5. 🚀 启动 API 服务器

如果任何步骤失败，脚本会显示错误信息并退出。

#### 方式二：使用 Python 模块

```bash
uv run python -m server.run_server
```

这种方式同样会执行 SQLite3 检查和数据库初始化。

也可以增加一些启动参数：

```bash
# 指定主机和端口
uv run python -m server.run_server --host 0.0.0.0 --port 8000

# 启用自动重载（开发模式）
uv run python -m server.run_server --reload

# 跳过数据库检查（适用于数据库已在外部初始化的情况）
uv run python -m server.run_server --skip-db-check

# 保存日志到文件
uv run python -m server.run_server --log-file logs/server.log

# 设置日志级别
uv run python run_server.py --log-level DEBUG
```

无论选择哪种启动方式，`server.run_server` 都会先初始化 FastAPI 应用，然后在独立线程中启动 `BackgroundFetcher`。该任务会周期性调用 ProviderManager 抓取数据、写入 SQLite `stations/latest` 表，API 本身只负责读库，不再直接访问服务商 API。

## 生产环境部署

### 方式一：使用 Caddy

```shell title="Caddy 安装"
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

确认安装成功

```shell
caddy version
```

```shell
sudo systemctl start caddy
sudo systemctl status caddy
```

配置 Caddyfile，默认在`/etc/caddy/Caddyfile`下

```shell
your_domain {
    reverse_proxy http://127.0.0.1:8000
    tls your_email@your_domain.com # 可选，用于申请 HTTPS 证书
}
```

启动 Caddy：

```shell
caddy start --config ./Caddyfile.json
```

### 方式二：使用 Docker

Docker 镜像已经内置在项目根目录下的 `Dockerfile` 中，适合希望快速启动且不想在宿主机安装 Python 环境的场景。

#### 方案 A：单容器运行 API

1. **构建镜像**

   ```bash
   docker build -t zju-charger:latest .
   ```

2. **准备环境变量**

   复制一份 `.env`（或命名为 `.env.production`），填入前文所述的环境变量。例如：

   ```shell
   cp .env .env.production  # 如无现成配置，可根据文档手动创建
   ```

3. **启动容器**

   ```bash
   docker run -d \
     --name zju-charger \
     -p 8000:8000 \
     -v $(pwd)/data:/app/data \
     --env-file .env.production \
     zju-charger:latest
   ```

   - `-p 8000:8000` 将容器内的 API (`API_PORT`) 暴露到宿主机。
   - `-v $(pwd)/data:/app/data` 将宿主机的 `data` 目录挂载到容器内，确保持久化数据存储。
   - `--env-file` 会把你配置的钉钉/SQLite/API 等变量注入容器。
   - 需要自定义端口时，可以同时修改 `.env.production` 中的 `API_PORT` 以及映射端口。

4. **查看日志 / 管理容器**

   ```bash
   docker logs -f zju-charger          # 查看运行日志
   docker stop zju-charger             # 停止
   docker start zju-charger            # 重启
   docker rm -f zju-charger            # 删除容器
   ```

如需让宿主机挂载日志目录，可在 `docker run` 时加入 `-v /host/path:/app/logs` 等参数。

#### 方案 B：`docker-compose` 运行 API + 宿主机 Caddy 反向代理

1. **准备配置文件**
   - 将 `.env` 或 `.env.production` 配置好后供 `app` 服务读取。
   - `docker-compose.yml` 默认会将容器 `8000` 端口映射到宿主机 `8000`，如需修改可调整 `ports`。

2. **启动服务**

   ```bash
   docker compose up -d
   ```

   `app` 服务会使用根目录的 `Dockerfile` 构建 FastAPI 应用并监听 8000 端口。

3. **配置 Caddy（在宿主机或单独容器中运行）**

   使用仓库根目录的 `Caddyfile` 作为模板，核心规则示例：

   ```caddy
   :80 {
       encode gzip zstd


       handle {
           reverse_proxy 127.0.0.1:8000
       }
   }
   ```

   - 将 `:80` 改为你的域名（如 `charger.example.com`）即可让 Caddy 自动申请 HTTPS 证书。
   - 若 Caddy 运行在其它主机或容器里，请把 `reverse_proxy` 指向宿主机暴露出来的 `app` 端口。

4. **管理命令**

   ```bash
   docker compose logs -f app    # 查看 FastAPI 日志
   docker compose down           # 停止并删除容器
   docker compose restart app    # 重启 FastAPI
   ```

5. **常见问题**
   - **Docker Daemon 未启动**

     如果执行 `docker compose up` 报错：

     ```text
     unable to get image 'zju-charger:latest': Cannot connect to the Docker daemon at unix:///Users/philfan/.docker/run/docker.sock. Is the docker daemon running?
     ```

     说明宿主机上的 Docker 服务尚未启动或当前用户没有访问 `docker.sock` 的权限。请先启动 Docker Desktop（或 `sudo systemctl start docker` 等命令），确保 Docker Engine 运行，再次执行 `docker compose up -d`。若问题依旧，请检查该 socket 的权限或将用户加入 `docker` 用户组。

### 方式三：使用 Nginx 反向代理（不推荐）

1. 安装 Nginx：

   ```shell
   sudo apt-get install nginx
   sudo yum install nginx
   ```

2. 配置 Nginx `/etc/nginx/sites-available/zju-charger`：

   ```shell
   server {
       listen 80;
       server_name your-domain.com;

       # API 代理
       location /api/ {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       # Web 前端请通过 CDN/Pages 等静态托管
   }
   ```

3. 启用配置：

   ```bash
   sudo ln -s /etc/nginx/sites-available/zju-charger /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

4. 配置 SSL（可选，使用 Let's Encrypt）：

   ```bash
   sudo apt-get install certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```

## 环境变量配置

### 必需配置

- `API_HOST`: 服务器监听地址（默认：0.0.0.0）
- `API_PORT`: 服务器端口（默认：8000）

### 可选配置

- `DINGTALK_WEBHOOK`: 钉钉机器人 webhook 地址（功能暂未启用）
- `DINGTALK_SECRET`: 钉钉机器人签名密钥（功能暂未启用）
- `BACKEND_FETCH_INTERVAL`: 后端定时抓取间隔（秒，默认：300）
- `RATE_LIMIT_ENABLED`: 是否启用接口限流（默认：true）
- `RATE_LIMIT_DEFAULT`: 默认限流规则（默认："60/hour"，即每小时 60 次）
- `RATE_LIMIT_STATUS`: `/api/status` 端点限流规则（默认："3/minute"，即每分钟 3 次）
- `SQLITE_DB_PATH`: SQLite 数据库文件路径（留空则使用默认路径：`data/charger.db`）
- `HISTORY_ENABLED`: 是否写入历史 `usage` 表（默认 `true`；设为 `false` 时只维护 `latest` 快照）

### 后台抓取任务

系统启动后会自动启动后台定时抓取任务，定期从服务商 API 抓取数据并更新缓存。

**功能说明**：

- 启动时立即执行一次抓取，初始化缓存
- 之后按 `BACKEND_FETCH_INTERVAL` 间隔定时抓取
- 抓取的数据会写入 SQLite `latest` 表（字段与 `usage` 表一致，保存每个站点的最新一条记录）
- 根据 `HISTORY_ENABLED` 配置决定是否同步写入历史 `usage` 表，便于趋势分析

**夜间暂停时段**：

- 系统在 **0:10-5:50** 时段会暂停后台抓取任务
- 这是为了避免在充电桩使用率极低的时间段进行不必要的抓取
- 在暂停时段内，API 仍可正常访问（使用缓存数据）

**数据流程**：

1. **启动阶段**：系统初始化 SQLite 数据库，创建必要的表结构（`stations`, `latest`, `usage`）
2. 后台任务定时抓取 → 调用 `db/pipeline.record_usage_data()` 写入 SQLite `latest` 表，并在 `HISTORY_ENABLED=true` 时追加 `usage` 历史 → 同步更新 `stations` 表基础信息
3. API 请求优先通过 `db/usage_repo.load_latest()` 和 `db/station_repo.fetch_station_metadata()` 组装 JSON，缓存不可用时再实时抓取

### `/api/status` 查询方式

`/api/status` 提供三种访问模式，便于不同客户端定位站点：

1. **Hash ID 查询**：`GET /api/status?hash_id=<hash_id>`，其中 `<hash_id>` 必须是 8 位十六进制字符串（例如 `3e262917`）。
2. **Provider + Devid**：`GET /api/status?provider=<provider>&devid=<devid>`，当只知道设备号时可定位站点（必须同时提供 `provider`）。
3. **按服务商过滤**：`GET /api/status?provider=<provider>`，返回该服务商下的全部站点。

所有模式都会返回统一的站点结构（包含 `devids` 列表），并在命中缓存时享受低延迟响应。

### 服务商配置

服务商配置通过环境变量或 `secret.json` 文件设置：

```env
# 格式：PROVIDER_<PROVIDER_ID>_<CONFIG_KEY>=<value>
PROVIDER_NEPTUNE_API_URL=https://api.example.com
```

## 限流功能

### 功能说明

系统集成了 `slowapi` 进行接口限流，防止 API 被恶意调用或过度请求。限流基���客户端 IP 地址进行统计。

### 限流规则

- **默认规则** (`RATE_LIMIT_DEFAULT`): `60/hour` - 适用于大部分 API 端点（`/api`, `/api/providers`, `/ding/webhook`）
- **`/api/status` 端点** (`RATE_LIMIT_STATUS`): `3/minute` - 更严格限制，允许前端 60 秒刷新 + 容错（手动刷新等）

限流规则格式：`"数量/时间单位"`，支持的时间单位：

- `second` - 秒
- `minute` - 分钟
- `hour` - 小时
- `day` - 天

示例：

- `30/minute` - 每分钟 30 次
- `100/hour` - 每小时 100 次
- `1000/day` - 每天 1000 次

### 存储后端

系统默认使用**内存存储**（memory），适用于单实例部署：

- **内存占用**：每个 IP 的限流计数器约占用 100-200 字节
- **适用场景**：单实例部署、IP 数量有限（<1000 个不同 IP）
- **估算**：1000 个不同 IP ≈ 100-200 KB，10000 个 ≈ 1-2 MB
- **优点**：无需额外服务，配置简单，性能好
- **缺点**：多实例无法共享限流状态，重启后限流计数丢失

如需使用 **Redis 存储**（适用于多实例部署），可在代码中修改配置：

1. 安装 Redis：

   ```bash
   # Ubuntu/Debian
   sudo apt-get install redis-server

   # macOS
   brew install redis
   ```

2. 修改 `server/api.py` 中的 limiter 初始化代码：

   ```python
   # 将内存存储改为 Redis 存储
   limiter = Limiter(key_func=get_remote_address, storage_uri="redis://localhost:6379/0")
   ```

### 前端处理

当请求超过限流阈值时，服务器会返回 HTTP 429 状态码。前端会自动检测并显示友好的弹窗提醒，提示用户请求过于频繁，请稍后再试。

### 配置示例

```env
# 启用限流
RATE_LIMIT_ENABLED=true

# 默认限流规则（每小时60次）
RATE_LIMIT_DEFAULT=60/hour

# /api/status 端点限流规则（每分钟3次）
RATE_LIMIT_STATUS=3/minute
```

## 日志配置

### 日志文件位置

- 默认：控制台输出
- 使用 `--log-file` 参数：指定日志文件路径

### 日志级别

- `DEBUG`: 详细调试信息
- `INFO`: 一般信息（默认）
- `WARNING`: 警告信息
- `ERROR`: 错误信息

## 故障排查

### 常见问题

1. **端口被占用**

   ```bash
   # 检查端口占用
   lsof -i :8000
   # 或
   netstat -tulpn | grep 8000

   # 修改端口
   python -m server.run_server --port 8001
   ```

2. **端口开放问题**

```shell
sudo iptables -L -n | grep 80
sudo iptables -L -n | grep 443
```

```shell
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables-save
```

## 安全建议

1. **使用 HTTPS**：生产环境必须使用 HTTPS
2. **防火墙配置**：只开放必要的端口
3. **定期更新**：定期更新依赖包和系统
4. **备份数据**：定期备份 `data/` 目录
5. **接口限流**：系统已集成接口限流功能，可根据实际情况调整限流规则
6. **限制访问**：使用 Nginx 限制访问频率（可选，系统已内置限流）

## SQLite 数据库配置

### 数据库功能说明

系统使用本地 SQLite 数据库存储充电桩数据，无需额外配置云服务。

### 数据库结构

系统包含三张表：

- **`stations`** 表：存储站点基础信息（名称、坐标、服务商等）
- **`latest`** 表：存储每个站点的最新使用情况快照
- **`usage`** 表：存储使用情况历史快照（根据 `HISTORY_ENABLED` 配置决定是否记录）

### 数据库文件位置

- 默认路径：`data/charger.db`（相对于项目根目录）
- 可通过 `SQLITE_DB_PATH` 环境变量自定义路径

### 数据库初始化

系统首次启动时会自动：

1. 创建 `data` 目录（如果不存在）
2. 创建数据库文件（如果不存在）
3. 执行 `db/schema.sql` 初始化表结构

### 数据记录

配置 SQLite 后，系统会在每次后台抓取时自动：

- 更新站点基础信息（`stations` 表）
- 更新使用情况快照（`latest` 表）
- 根据 `HISTORY_ENABLED` 配置决定是否写入历史 `usage` 表

### 注意事项

- **数据量**：每次抓取都会插入 `usage` 表记录，表会快速增长。如不需要历史数据，可设置 `HISTORY_ENABLED=false`
- **备份**：建议定期备份 `data/charger.db` 文件
- **并发**：SQLite 在高并发写入场景下可能有限制，但本项目设计为单线程后台写入，无需担心

## 备份和恢复

### 备份

```bash
# 备份数据目录（包含 SQLite 数据库）
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# 备份配置
tar -czf config-backup-$(date +%Y%m%d).tar.gz .env secret.json
```

### 恢复

```bash
# 恢复数据
tar -xzf backup-20250101.tar.gz

# 恢复配置
tar -xzf config-backup-20250101.tar.gz
```

### SQLite 数据库备份

```bash
# 使用 SQLite 命令备份数据库
sqlite3 data/charger.db ".backup data/charger-backup-$(date +%Y%m%d).db"

# 或直接复制文件（需确保数据库未被写入）
cp data/charger.db data/charger-backup-$(date +%Y%m%d).db
```
