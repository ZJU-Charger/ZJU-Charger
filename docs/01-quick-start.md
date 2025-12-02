# 快速开始

本文档讲解用户侧如何使用 ZJU Charger 项目。

## Web 页面

### 访问方式

1. **在线访问**：部署后的 Next.js 前端（`https://charger.philfan.cn/`）。
2. **本地开发**：进入 `frontend/` 目录运行 Next.js，即可通过 `http://localhost:3000` 预览；后端只需暴露 `/api/*` 接口（本地 FastAPI 或远端 API 均可，通过 `NEXT_PUBLIC_API_BASE` 指定）。

### 本地开发步骤

```bash
cd frontend
pnpm install
cp .env.local.example .env.local  # 若示例文件不存在，可直接创建 .env.local
echo "NEXT_PUBLIC_AMAP_KEY=你的高德JSKey" >> .env.local
pnpm dev                          # 启动 Next.js 开发服务器
```

构建与部署：

```bash
pnpm build        # 生成 .next 输出
pnpm start        # 以 Node 方式预览生产包
# 或结合你使用的托管环境（Vercel、Caddy、Docker 等）
```

Next.js App Router 版本同样通过 `.env*` 注入配置：

- 本地开发 => `frontend/.env.local`

  ```ini
  NEXT_PUBLIC_AMAP_KEY=dev-gaode-key
  NEXT_PUBLIC_API_BASE=http://localhost:8000
  ```

  缺少 `NEXT_PUBLIC_API_BASE` 时会默认使用相对路径 `/api/*`，方便你用 Caddy 或 Next 代理后端。
- 远程部署 => `.env.production` 或部署平台环境变量

  ```ini
  NEXT_PUBLIC_AMAP_KEY=prod-gaode-key
  NEXT_PUBLIC_API_BASE=https://charger.philfan.cn
  ```

  构建 (`pnpm build`) 阶段 Next.js 会把这些值打包进浏览器脚本。

> 只需记住：凡是要给浏览器用的变量必须带 `NEXT_PUBLIC_` 前缀；如果某个环境无须跨域访问，可不设置 `NEXT_PUBLIC_API_BASE`。

### 主要功能

- **Next.js + shadcn/ui**：使用 App Router、TypeScript 与 shadcn Supabase 主题构建 UI，所有组件位于 `frontend/src/components`。
- **AMap + Apache ECharts**：依旧通过 `echarts-extension-amap` 渲染高德底图，标记颜色与旧版保持一致。
- **站点列表与关注**：校区、服务商筛选、关注状态、主题偏好全部通过 hooks 与 `localStorage` 管理，多标签页实时同步。
- **自动刷新**：读取 `/api/config` 的 `fetch_interval` 自动轮询（默认 60 秒），可手动点击 Header 的“刷新”按钮。
- **实时定位与夜间提醒**：定位按钮现在使用 `watchPosition` 持续追踪并绘制用户位置（可手动停止），夜间提示依旧在 00:10–05:50 之间显示，顶部也保留校区空闲摘要。

### 使用技巧

- 点击地图标记可查看站点详情；右下角按钮可定位当前位置或导出 PNG 截图。
- 关注列表存储在浏览器 `localStorage` 中，清除数据会导致关注记录丢失。
- 若未设置 `VITE_AMAP_KEY`，地图区域会提示错误，请到高德开放平台申请 Web JS Key。

## iOS 快捷指令

### 安装方式

1. 下载快捷指令文件（`.shortcut` 格式）
2. 在 iOS 设备上打开快捷指令 App
3. 导入下载的快捷指令文件

### 使用方法

1. 在快捷指令 App 中运行对应的快捷指令
2. 或通过 Siri 语音命令运行（如果已配置）
3. 快捷指令会自动查询关注站点的状态并显示结果

### 功能说明

- **关注点快速查询**：快速查询已关注的充电桩站点状态
- **自定义 API 地址**：可以在快捷指令中配置 API 服务器地址

详细使用说明请参考 [Script 快捷指令文档](./06-script-shortcuts.md)。

## 钉钉机器人

### 配置方式

1. 在钉钉群聊中添加自定义机器人
2. 获取 Webhook 地址和签名密钥
3. 在服务器环境变量中配置：

   ```env
   DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
   DINGTALK_SECRET=your_secret_here
   ```

### DingBot 使用方法

在钉钉群聊中发送命令：

- `/全部` - 查询所有站点状态
- `/关注` - 查询关注站点状态（需要先配置关注列表）
- `/帮助` - 显示帮助信息

详细配置说明请参考 [钉钉机器人文档](./05-dingbot.md)。

## API 接口

### 基础接口

- `GET /api/status` - 查询所有站点状态
  - 参数：`?provider=neptune` - 筛选特定服务商
  - 参数：`?id=xxx` - 查询指定站点
- `GET /api/providers` - 获取可用服务商列表
- `GET /api/config` - 获取前端配置信息

### 使用示例

```bash
# 查询所有站点
curl http://localhost:8000/api/status

# 查询特定服务商的站点
curl http://localhost:8000/api/status?provider=neptune

# 查询指定站点
curl http://localhost:8000/api/status?id=29e30f45
```

## 常见问题

### Q: Web 页面无法访问？

A: 检查后端服务器是否正常运行，确认端口是否正确。

### Q: 快捷指令查询失败？

A: 检查 API 服务器地址配置是否正确，确保网络连接正常。

### Q: 钉钉机器人无响应？

A: 检查环境变量配置是否正确，确认服务器已启动并正常运行。

### Q: 数据不更新？

A: 系统会自动定时抓取数据，如果长时间不更新，请检查服务器日志。
