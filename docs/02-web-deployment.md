# Web 前端实现

本文档聚焦 Web 前端的代码组织与运行机制，帮助你快速理解如何在不依赖框架的情况下构建地图页面、消费后端 API，并提供流畅的交互体验。

## 技术栈概览

- **基础**：原生 HTML + ES6 模块化脚本，TailwindCSS CDN 负责样式；无需打包工具即可直接部署。
- **地图**：Leaflet 1.9.4，配合 `leaflet.ChineseTmsProviders` 切换国内常用底图，`leaflet-easyprint` 输出地图截图。
- **坐标系**：`leaflet-coord-transform.js` 内置 BD09/GCJ02/WGS84 之间的互转工具，确保数据与底图一致。
- **数据交互**：浏览器通过 `fetch` 调用 `/api/status`、`/api/providers`、`/api/config`，并使用 `/api/stations` 补全地图/站点定义信息。
- **状态与存储**：`localStorage` 记录关注列表与主题偏好，`Set` 结构在前端完成去重和快速查询。

## 目录与模块职责

```text
web/
├── index.html               # 页面骨架、Tailwind/Leaflet/CDN 注入及脚本加载顺序
├── js/
│   ├── config.js            # 常量、校区/地图配置、localStorage key
│   ├── map.js               # Leaflet 初始化、坐标转换、图层与标记渲染
│   ├── data.js              # 数据获取、合并、过滤、watchlist 管理
│   ├── ui.js                # 主题/夜间提示/交互入口，绑定事件与定时刷新
│   ├── leaflet-coord-transform.js
│   └── leaflet.ChineseTmsProviders.js
├── data/                    # 启动或迁移时的原始站点缓存（由服务器同步至数据库）
└── 40x/50x.html             # 兜底静态页面
```

加载顺序在 `index.html` 最后：`config` → `map` → `data` → `ui`。这样 `map.js` 能依赖配置常量，`data.js` 在渲染时调用 `renderMap`，而最终的事件绑定与刷新循环在 `ui.js` 完成。

## 数据流与 API

1. **配置拉取**：`loadConfig()` 调用 `/api/config`，读取 `fetch_interval`，用于后续的自动刷新周期；失败时采用默认 60 秒。
2. **服务商清单**：`loadProviders()` 访问 `/api/providers`，更新右上角下拉框，顺便缓存 `availableProviders` 供图层命名。
3. **站点状态**：`fetchStatus()` 直接调用 `/api/status`（可追加 `?provider=`）。后台服务会从 Supabase `latest` 表读取缓存（`latest` 与 `usage` 表字段一致，API 层负责组装 JSON）；前端无需感知具体存储位置。同时请求 `/api/stations`，将尚未抓取到实时数据的桩位补齐并打上 `isFetched: false` 标记。
4. **关注列表状态**：`fetchWatchlistStatus()` 读取本地 watchlist，按服务商拼接 `/api/status?provider=x&devid=...` 批量查询，必要时再全量拉取 `/api/status` 过滤出基于名称的收藏。
5. **限流提示**：任意接口返回 429 时触发 `showRateLimitAlert()`，以浮层提醒用户不要频繁刷新。

## 全局状态与本地存储

`data.js` 维护若干顶级变量：

- `currentCampus`、`currentProvider` 控制地图与列表过滤。
- `availableProviders` 驱动图层命名以及下拉选项。
- `watchlistDevids` 与 `watchlistDevdescripts` 两个 `Set`，分别存储 (devid+provider) 与 devdescript，用于收藏判定与快速排序。
- `fetchInterval`：来自配置接口，供 `setInterval` 使用。

观测点：

- `WATCHLIST_STORAGE_KEY = 'zju_charger_watchlist'` 保存 `{devids, devdescripts, updated_at}`，在页面初始化和刷新定时器里都会重新读取，确保多标签页同步。
- `THEME_STORAGE_KEY = 'zju_charger_theme'` 由 `ui.js` 控制，切换暗色模式后立即写入。

## 地图渲染流程（`map.js`）

1. **初始化**：`initMap()` 根据当前校区（默认玉泉，取 `CAMPUS_CONFIG[2143]`）确定中心点，调用 `convertCoord()` 将 BD09 数据转到地图所需坐标，再创建 Leaflet 实例。
2. **底图与坐标系联动**：`MAP_LAYERS_CONFIG` 为 OSM/高德/腾讯预定义底图及其坐标系。`updateLayerControl()` 将这些底图，以及后续生成的“服务商图层组”一起放进 `L.control.layers`。当用户切换底图时触发 `baselayerchange`，同步更新 `MAP_CONFIG.useMap` 和 `MAP_CONFIG.webCoordSystem`，随后强制重新绘制所有桩位标记以保证坐标转换正确。
3. **标记绘制**：`renderMap()` 先将所有旧的服务商图层移除，再把站点按 `provider` 分组。每个分组对应一个 `L.layerGroup`，并使用 `L.divIcon` 自定义图标颜色/形状：默认绿色表示有空闲，橙色/红色分别表示紧张和无空闲，灰色则表示 `isFetched=false` 的“未抓取”桩位。`providerShapes` 允许为不同服务商定义圆/三角/方形等差异化外观。
4. **交互能力**：
   - `layerControl` 允许快速显示/隐藏某个服务商的桩。
   - `manualPrint()` 基于 `L.easyPrint` 导出当前视口，结合 `#download-map-btn` 提供“下载地图”功能。
   - `showCurrentLocation()` 在 HTTPS/localhost 环境下请求浏览器定位，使用 WGS84→GCJ02/BD09 转换后在地图上加蓝色圆点。
   - 校区切换或首次加载时可触发 `map.fitBounds(...)` 自动调整视野；定时刷新则保持用户当前视角。

## 列表与 UI（`data.js` + `ui.js`）

- **渲染逻辑**：`renderList()` 将实时数据与 `/api/stations` 提供的定义做并集后，再按校区、服务商过滤。排序优先级是“是否关注 → 是否实时数据 → 可用数”。每一项都包含彩色进度条（绿色=空闲、灰色=占用、红色=故障），并展示校区/服务商徽章。
- **收藏**：点击星形图标会调用 `toggleWatchlist()`。函数优先使用 devid+provider 组合保证唯一性，如果接口数据缺失则退化为站点名称。
- **夜间提示**：`isNightTime()` 判断 00:10–05:50 区间，`updateNightMessage()` 控制提示条显隐。
- **主题切换**：`initTheme()` 在加载时读取本地主题，`toggleTheme()` 切换 `document.documentElement` 的 `dark` class，SVG 图标跟随变化。
- **校区与服务商筛选**：`setupCampusSelector()`、`setupProviderSelector()` 对按钮和下拉框绑定事件。校区切换会允许地图自动缩放；服务商筛选尝试重新获取数据（确保能请求到仅包含指定 provider 的列表）。
- **时间戳**：`updateTime()` 将接口返回的 `updated_at` 格式化为“YYYY/MM/DD HH:MM:SS”，绑定在 Header 中。

## 自动刷新与提示机制

- `ui.js` 的 `DOMContentLoaded` 回调完成所有初始化后，会：
  1. `await loadConfig()` / `loadProviders()` / `fetchStatus()`。
  2. `setInterval` 以 `fetchInterval` 调用 `fetchStatus()`，并同步刷新 watchlist 以捕获其它标签页的变化。
  3. 另外一个 `setInterval` 每分钟刷新夜间提示状态。
- 每次手动点击“刷新”按钮会立即执行 `fetchStatus()`。
- 429 或网络异常会在列表区域显示错误卡片，并提示排障步骤。

## 位置识别与校区自动切换

- `detectNearestCampus()` 在 HTTPS 或 localhost 场景下尝试读取浏览器地理位置，与 `CAMPUS_CONFIG` 中的坐标逐一计算距离（Haversine）。
- 找到最近校区后：
  1. 若与当前校区不同则调用 `switchToCampus()`，从而触发地图的 `fitBounds` 和列表重渲染；
  2. `showLocationNotification()` 弹出右上角提醒，包含校区名与距离，5 秒后自动消失。

## 扩展指引

- **新增校区**：在 `CAMPUS_CONFIG` 中添加 `{id: {name, center}}` 即可，记得在 `index.html` 的按钮区添加对应 DOM。
- **接入新的地图底图**：向 `MAP_LAYERS_CONFIG` 增加条目，并提供 `coordSystem` 与 `layers` 映射；`baselayerchange` 会自动同步坐标系。
- **自定义服务商样式**：扩展 `providerShapes` 和 `providerShapesForBadge`，或在 `createMarkerIcon()` 内添加更多样式分支。
- **更复杂的排序/标签**：`renderList()` 已集中所有列表项模板，可在该函数里增加额外信息（如电压、运营时间）或替换排序规则。

通过以上模块化拆分，前端保持“直接丢到任意静态托管即可运行”的简单部署体验，同时仍具备可维护的结构与充分的扩展空间。
