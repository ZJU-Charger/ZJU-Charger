# Server 端部署

本文档介绍如何部署 ZJU Charger 的后端服务器。

## 系统要求

- Python 3.8+
- pip 包管理器
- 网络连接（用于访问充电桩服务商 API）

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 配置环境变量

创建 `.env` 文件：

```shell
# 钉钉机器人配置（可选）
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
DINGTALK_SECRET=your_secret_here

# API 服务器配置
API_HOST=0.0.0.0
API_PORT=2333

# 数据抓取配置
FETCH_INTERVAL=60
BACKEND_FETCH_INTERVAL=300

# 限流配置
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=60/hour
RATE_LIMIT_STATUS=3/minute
```

### 3. 启动服务器

```bash
python run_server.py
```

也可以增加一些启动参数

```bash
# 基本启动
python run_server.py

# 指定主机和端口
python run_server.py --host 0.0.0.0 --port 8000

# 启用自动重载（开发模式）
python run_server.py --reload

# 保存日志到文件
python run_server.py --log-file logs/server.log

# 设置日志级别
python run_server.py --log-level DEBUG
```

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

启动 Caddy：

```shell
sudo caddy run --config /etc/caddy/Caddyfile
```

配置 Caddyfile：

```shell
https://charger.philfan.cn {
    reverse_proxy http://127.0.0.1:8000
}
```

配置 SSL：

```shell
sudo caddy cert issue --domain charger.philfan.cn
```

```shell
caddy run --config ./Caddyfile.json
```

```shell
caddy start --config ./Caddyfile.json
```

```shell
sudo systemctl start caddy
```

caddy 的默认配置文件在 `/etc/caddy/Caddyfile` 下。

### 方式二：使用 Docker（待实现）

TODO: Docker 部署方案

### 方式三：使用 Nginx 反向代理

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

       # Web 前端
       location /web/ {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }

       # 静态文件（可选）
       location /data/ {
           proxy_pass http://127.0.0.1:8000;
       }
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

- `DINGTALK_WEBHOOK`: 钉钉机器人 webhook 地址
- `DINGTALK_SECRET`: 钉钉机器人签名密钥
- `FETCH_INTERVAL`: 前端自动刷新间隔（秒，默认：60）
- `BACKEND_FETCH_INTERVAL`: 后端定时抓取间隔（秒，默认：300）
- `RATE_LIMIT_ENABLED`: 是否启用接口限流（默认：true）
- `RATE_LIMIT_DEFAULT`: 默认限流规则（默认："60/hour"，即每小时 60 次）
- `RATE_LIMIT_STATUS`: `/api/status` 端点限流规则（默认："3/minute"，即每分钟 3 次）

### 服务商配置

服务商配置通过环境变量或 `secret.json` 文件设置：

```env
# 格式：PROVIDER_<PROVIDER_ID>_<CONFIG_KEY>=<value>
PROVIDER_NEPTUNE_API_URL=https://api.example.com
```

## 限流功能

### 功能说明

系统集成了 `slowapi` 进行接口限流，防止 API 被恶意调用或过度请求。限流基于客户端 IP 地址进行统计。

### 限流规则

- **默认规则** (`RATE_LIMIT_DEFAULT`): `60/hour` - 适用于大部分 API 端点（`/api`, `/api/config`, `/api/providers`, `/ding/webhook`）
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
   python run_server.py --port 8001
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

## 备份和恢复

### 备份

```bash
# 备份数据目录
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
