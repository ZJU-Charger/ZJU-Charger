# 钉钉机器人文档

本文档介绍如何配置和使用钉钉机器人功能。

## 功能特性

- 📱 **文本交互**：通过钉钉群聊发送文本命令查询充电桩状态
- 🔍 **全部查询**：查询所有站点的充电桩状态
- 🔐 **签名验证**：支持钉钉签名验证，确保安全性

## 配置步骤

### 1. 创建钉钉机器人

1. 打开钉钉群聊，点击右上角设置
2. 选择「智能群助手」→「添加机器人」
3. 选择「自定义」机器人
4. 设置机器人名称和头像
5. 选择「加签」安全设置（推荐）
6. 复制 Webhook 地址和签名密钥

### 2. 配置环境变量

在 `.env` 文件中添加钉钉机器人配置：

```env
# 钉钉机器人 Webhook 地址
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx

# 钉钉机器人签名密钥（如果启用了加签）
DINGTALK_SECRET=your_secret_here
```

### 3. 配置服务器地址（可选）

如果钉钉机器人和 API 服务器不在同一台机器上，需要配置 API 地址：

```env
# API 服务器地址（可选，默认使用 Config.API_HOST:Config.API_PORT）
API_URL=http://your-api-server.com:8000
```

### 4. 重启服务器

配置完成后，重启服务器使配置生效：

```bash
python run_server.py
```

## 使用方法

### 可用命令

| 命令   | 说明             | 示例         |
| ------ | ---------------- | ------------ |
| `全部` | 查询所有站点状态 | 发送「全部」 |

### 命令格式

在钉钉群聊中直接发送命令文本即可：

```text
全部
```

### 响应格式

机器人会返回 Markdown 格式的消息，包含：

- 更新时间
- 站点列表（按服务商分组）
- 每个站点的状态（可用/总数/已用/故障）

示例响应：

```text
# 全部站点状态

**更新时间**: 2025-01-01 12:00:00

## 尼普顿

### 浙大玉泉园林宿舍
- 可用：5 / 总数：10
- 已用：4 / 故障：1

### 浙大玉泉高分子
- 可用：3 / 总数：8
- 已用：4 / 故障：1
```

## API 端点

### Webhook 端点

```html
POST /ding/webhook
```

### 请求格式

钉钉会自动发送 POST 请求，格式如下：

```json
{
  "msgtype": "text",
  "text": {
    "content": "全部"
  },
  "msgId": "消息 ID"
}
```

### 响应的格式

```json
{
  "errcode": 0,
  "errmsg": "ok"
}
```

## 安全配置

### 签名验证

如果启用了加签，系统会自动验证签名：

1. 钉钉会在请求头中携带 `timestamp` 和 `sign`
2. 系统使用 `DINGTALK_SECRET` 计算签名
3. 验证签名是否匹配

### 签名算法

```python
import hmac
import hashlib
import base64

string_to_sign = f"{timestamp}\n{secret}"
hmac_code = hmac.new(
    secret.encode('utf-8'),
    string_to_sign.encode('utf-8'),
    digestmod=hashlib.sha256
).digest()
sign = base64.b64encode(hmac_code).decode('utf-8')
```

### 禁用签名验证

如果不使用加签，可以不设置 `DINGTALK_SECRET`，系统会跳过签名验证：

```env
# 不设置 DINGTALK_SECRET 即可禁用签名验证
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
# DINGTALK_SECRET=  # 注释掉或删除
```

## 代码结构

```text
ding/
├── bot.py          # 钉钉机器人封装类
├── commands.py     # 命令解析和执行
└── webhook.py      # Webhook 路由处理
```

### bot.py

提供钉钉机器人消息发送功能：

```python
from ding.bot import DingBot

bot = DingBot(webhook, secret)
bot.send_text("文本消息")
bot.send_markdown("标题", "Markdown 内容")
```

### commands.py

解析和执行用户命令：

```python
from ding.commands import parse_command, execute_all_command

# 解析命令
command_type, args = await parse_command("全部")

# 执行命令
result = await execute_all_command()
```

### webhook.py

处理钉钉 Webhook 请求：

- 验证签名
- 解析消息
- 执行命令
- 返回响应

## 扩展命令

### 添加新命令

1. 在 `ding/commands.py` 中添加命令解析：

   ```python
   async def parse_command(text):
       text = text.strip()

       if text == "全部":
           return ("all", None)
       elif text.startswith("查询"):
           # 解析查询参数
           site_name = text[2:].strip()
           return ("query", {"site_name": site_name})
       else:
           return ("unknown", None)
   ```

2. 添加命令执行函数：

   ```python
   async def execute_query_command(site_name):
       """执行查询命令"""
       # 实现查询逻辑
       pass
   ```

3. 在 `ding/webhook.py` 中处理新命令：

   ```python
   if command_type == "all":
       result = await execute_all_command()
   elif command_type == "query":
       result = await execute_query_command(args["site_name"])
   ```

## 故障排查

### 常见问题

1. **机器人无响应**
   - 检查 Webhook 地址是否正确
   - 检查服务器是否正常运行
   - 查看服务器日志

2. **签名验证失败**
   - 检查 `DINGTALK_SECRET` 是否正确
   - 检查服务器时间是否准确（签名包含时间戳）

3. **命令不识别**
   - 检查命令文本是否完全匹配（区分大小写）
   - 查看 `commands.py` 中的命令定义

4. **API 请求失败**
   - 检查 `API_URL` 配置是否正确
   - 检查网络连接
   - 检查 API 服务器是否可访问

### 调试技巧

1. **查看日志**

   ```bash
   # 查看服务器日志
   tail -f logs/server.log

   # 或查看控制台输出
   python run_server.py --log-level DEBUG
   ```

2. **测试 Webhook**

   使用 curl 测试 Webhook：

   ```bash
   curl -X POST http://localhost:8000/ding/webhook \
     -H "Content-Type: application/json" \
     -H "timestamp: 1234567890" \
     -H "sign: your_sign" \
     -d '{
       "msgtype": "text",
       "text": {
         "content": "全部"
       }
     }'
   ```

3. **检查配置**

   ```python
   from server.config import Config

   print(f"Webhook: {Config.DINGTALK_WEBHOOK}")
   print(f"Secret: {Config.DINGTALK_SECRET}")
   ```

## 最佳实践

1. **启用签名验证**：生产环境必须启用签名验证
2. **使用 HTTPS**：确保 Webhook 使用 HTTPS 协议
3. **错误处理**：妥善处理 API 请求失败的情况
4. **日志记录**：记录所有命令和响应，便于排查问题
5. **限流控制**：避免频繁请求导致 API 限流

## 示例

### 完整配置示例

`.env` 文件：

```env
# 钉钉机器人配置
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=abc123
DINGTALK_SECRET=SEC123456

# API 服务器配置
API_HOST=0.0.0.0
API_PORT=8000

# API 地址（如果钉钉机器人和 API 不在同一台机器）
API_URL=http://your-api-server.com:8000
```

### 使用示例

1. 在钉钉群聊中发送「全部」
2. 机器人返回所有站点状态
3. 查看 Markdown 格式的响应消息
