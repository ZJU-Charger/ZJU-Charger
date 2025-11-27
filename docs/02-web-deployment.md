# Web 介绍与部署

本文档介绍前端 Web 页面的功能和使用方法，以及如何部署前端页面。

## 功能特性

- 🗺️ **地图可视化**：使用 Leaflet 地图库展示充电桩位置
- 🔍 **服务商筛选**：支持按服务商筛选站点（下拉框）
- 🏫 **校区筛选**：支持按校区筛选站点（玉泉、紫金港等）
- ❤️ **关注列表**：支持添加/移除关注站点，数据存储在浏览器 localStorage
- 🔄 **自动刷新**：支持自动刷新站点状态（默认 60 秒）
- 🗺️ **多种地图**：支持高德地图、OpenStreetMap 等多种地图源

## 文件结构

```shell
web/
├── index.html                    # 主页面
├── script.js                     # 前端逻辑
├── leaflet-coord-transform.js    # 坐标转换工具
└── leaflet.ChineseTmsProviders.js # 中国地图提供商插件
```

## 主要功能说明

### 1. 地图展示

- 使用 Leaflet 地图库展示充电桩位置
- 支持多种地图源切换（高德地图、OpenStreetMap 等）
- 自动处理坐标转换（BD09、GCJ02、WGS84）

### 2. 站点列表

- 显示所有充电站点的状态信息
- 支持按服务商筛选
- 支持按校区筛选
- 显示站点名称、位置、可用数量等信息

### 3. 关注列表

- 点击站点列表中的心形图标添加/移除关注
- 关注列表数据存储在浏览器 localStorage 中
- 支持快速查询关注站点的状态

### 4. 自动刷新

- 默认每 60 秒自动刷新一次站点状态
- 可通过环境变量 `FETCH_INTERVAL` 配置刷新间隔

## 部署方式

### 方式一：与后端一起部署（推荐）

前端文件位于 `web/` 目录，FastAPI 会自动提供静态文件服务：

```python
# server/api.py 中已配置
app.mount("/web", StaticFiles(directory=str(web_dir), html=True), name="web")
```

启动服务器后，访问 `http://localhost:8000/web/` 即可。

### 方式二：独立静态部署

#### GitHub Pages

1. 将 `web/` 目录内容推送到 GitHub 仓库
2. 在仓库设置中启用 GitHub Pages
3. 选择 `web` 目录作为源目录
4. 访问 `https://your-username.github.io/repo-name/`

**注意**：独立部署时，需要修改 `script.js` 中的 API 地址：

```javascript
// 修改 API_BASE_URL
const API_BASE_URL = 'https://your-api-server.com';
```

#### Nginx 部署

1. 将 `web/` 目录内容复制到 Nginx 网站根目录：

    ```bash
    cp -r web/* /var/www/html/
    ```

2. 配置 Nginx（可选，如果需要代理 API）：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    root /var/www/html;
    index index.html;
    
    # 代理 API 请求
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # 静态文件
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

#### 其他静态托管服务

- **Vercel**：将 `web/` 目录推送到 GitHub，在 Vercel 中导入项目
- **Netlify**：将 `web/` 目录推送到 GitHub，在 Netlify 中导入项目
- **Cloudflare Pages**：将 `web/` 目录推送到 GitHub，在 Cloudflare Pages 中导入项目

## 配置说明

### API 地址配置

前端通过 `script.js` 中的 `API_BASE_URL` 配置 API 地址：

```javascript
// 默认使用相对路径（与后端一起部署时）
const API_BASE_URL = '';

// 或使用绝对路径（独立部署时）
const API_BASE_URL = 'https://your-api-server.com';
```

### 刷新间隔配置

刷新间隔由后端环境变量 `FETCH_INTERVAL` 控制，前端会自动读取：

```env
FETCH_INTERVAL=60  # 秒
```

## 浏览器兼容性

- Chrome/Edge（推荐）
- Firefox
- Safari
- 移动端浏览器（iOS Safari、Chrome Mobile）

## 常见问题

### Q: 地图不显示？

A: 检查网络连接，确保可以访问地图服务（高德地图、OpenStreetMap 等）。

### Q: API 请求失败？

A: 检查 API 地址配置是否正确，确保后端服务正常运行。

### Q: 关注列表丢失？

A: 关注列表存储在浏览器 localStorage 中，清除浏览器数据会导致列表丢失。

### Q: 如何修改地图样式？

A: 修改 `script.js` 中的地图初始化代码，可以切换地图源或自定义样式。

## 开发说明

### 本地开发

1. 启动后端服务器：

    ```bash
    python run_server.py --reload
    ```

2. 访问 `http://localhost:8000/web/`

3. 修改 `web/script.js` 或 `web/index.html` 后刷新页面即可看到效果

### 调试技巧

- 打开浏览器开发者工具（F12）查看控制台日志
- 检查 Network 标签页查看 API 请求
- 检查 Application 标签页查看 localStorage 数据
