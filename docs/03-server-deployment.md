# Server 端部署

本文档介绍如何部署 ZJU Charger 的后端服务器。

## 系统要求

- Python 3.8+
- pip 包管理器
- 网络连接（用于访问充电桩服务商 API）

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```shell
# 钉钉机器人配置（可选）
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
DINGTALK_SECRET=your_secret_here

# API 服务器配置
API_HOST=0.0.0.0
API_PORT=8000

# 数据抓取配置
FETCH_INTERVAL=60
BACKEND_FETCH_INTERVAL=300
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

### 方式一：使用 systemd（Linux）

1. 创建 systemd 服务文件 `/etc/systemd/system/zju-charger.service`：

    ```ini
    [Unit]
    Description=ZJU Charger API Server
    After=network.target

    [Service]
    Type=simple
    User=your-user
    WorkingDirectory=/path/to/Charge-in-ZJU
    Environment="PATH=/path/to/venv/bin"
    ExecStart=/path/to/venv/bin/python run_server.py --host 0.0.0.0 --port 8000 --log-file /var/log/zju-charger/server.log
    Restart=always
    RestartSec=10

    [Install]
    WantedBy=multi-user.target
    ```

2. 启动服务：

    ```shell
    sudo systemctl daemon-reload
    sudo systemctl enable zju-charger
    sudo systemctl start zju-charger
    ```

3. 查看状态：

    ```shell
    sudo systemctl status zju-charger
    ```

4. 查看日志：

    ```shell
    sudo journalctl -u zju-charger -f
    ```

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

### 服务商配置

服务商配置通过环境变量或 `secret.json` 文件设置：

```env
# 格式：PROVIDER_<PROVIDER_ID>_<CONFIG_KEY>=<value>
PROVIDER_NEPTUNE_API_URL=https://api.example.com
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

2. **权限问题**

    ```bash
    # 确保有写入权限
    chmod -R 755 /path/to/Charge-in-ZJU/data
    ```

3. **依赖问题**

    ```bash
    # 重新安装依赖
    pip install -r requirements.txt --upgrade
    ```

4. **日志查看**

    ```bash
    # 查看实时日志
    tail -f /var/log/zju-charger/server.log
    ```

## 安全建议

1. **使用 HTTPS**：生产环境必须使用 HTTPS
2. **防火墙配置**：只开放必要的端口
3. **定期更新**：定期更新依赖包和系统
4. **备份数据**：定期备份 `data/` 目录
5. **限制访问**：使用 Nginx 限制访问频率

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
