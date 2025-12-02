# Web 前端实现

本文档聚焦 Next.js 版本 Web 前端的代码组织与运行机制，帮助你快速理解如何使用 App Router + shadcn/ui + ECharts 构建地图页面、消费后端 API，并提供流畅的交互体验。

## 技术栈概览

- **基础**：Next.js 16（App Router）+ TypeScript + pnpm 构建 SPA，Tailwind CSS + shadcn/ui（Supabase 主题）负责样式与交互组件。
- **地图**：Apache ECharts 5 + `echarts-extension-amap`，统一使用高德地图底图，具备 geolocation 与截图能力。
- **状态管理**：React Hooks + 定制 `useStations/useWatchlist/useRealtimeLocation` 等 hooks，将数据获取、轮询、主题、关注、定位 watch 等逻辑拆分成可复用模块。
- **数据交互**：仍通过 `/api/status`、`/api/providers`、`/api/config`、`/api/stations` 获取实时/元数据，服务端实现保持不变。
- **部署模式**：前端可运行在 Node（`pnpm start`）、Vercel、Caddy 等环境，FastAPI 仅提供 API；通过 `NEXT_PUBLIC_API_BASE` 指定 API 根地址即可支持跨域请求。
- **存储**：`localStorage` 保留主题、关注列表、定位偏好；`NEXT_PUBLIC_AMAP_KEY` 在 `.env.local` 中配置后由 Next.js 注入。

## 目录与模块职责

```text
frontend/
├── package.json            # pnpm scripts（dev/build/lint/format）
├── tailwind.config.ts      # Tailwind + shadcn 配置
├── postcss.config.mjs
├── tsconfig.json           # TypeScript & path alias 配置（@ -> src）
└── src/
    ├── app/               # Next App Router：layout/page/not-found/503/504
    ├── components/        # HeaderBar、MapView、StationList、SummaryGrid、ErrorPage 等
    ├── hooks/             # useStations/useProviders/useThemeMode/useWatchlist/useRealtimeLocation
    ├── lib/               # 校区/常量/Storage key、API 客户端、时间&坐标、AMap loader
    └── types/             # API/站点类型声明
```

生产阶段执行 `pnpm build && pnpm start` 即可预览 `.next` 输出，或交由 Vercel/Caddy/Nginx 托管。

## 数据流与 API

1. **配置拉取**：`useConfig()` 在挂载后调用 `/api/config`，将 `fetch_interval`（秒）写入状态并驱动 `useAutoRefresh()`，失败时自动回退到 60 秒。
2. **服务商清单**：`useProviders()` 请求 `/api/providers`，结果传入 Header 组件以渲染筛选下拉框。
3. **站点状态**：`useStations()` 并行请求 `/api/status`（支持 `?provider=` 筛选）与 `/api/stations`，通过 `mergeStations()` 合并实时数据与元数据，保证未抓取站点也能显示在地图/列表，并标记 `isFetched=false`。
4. **关注列表**：`useWatchlist()` 负责从 `localStorage` 解析/持久化 `{devids, devdescripts}`，并暴露 `isWatched()` 与 `toggleWatch()` 给列表组件使用。
5. **限流提示**：当 API 返回 429 时抛出 `RateLimitError`，`useStations()` 捕获后设置 `rateLimited=true`，由 `RateLimitToast` 组件展示提示。

## 全局状态与本地存储

- React 组件树以 `App` 为根，通过 `useState` 持有 `campusId`、`providerId` 等筛选条件。
- `useStations()`（数据）、`useProviders()`（选项）、`useConfig()`（刷新频率）等 hooks 将 API 结果注入组件。
- `useWatchlist()`+`localStorage` 保存 `{devids, devdescripts, updated_at}`，支持多标签同步；`useTheme()` 负责 `THEME_STORAGE_KEY`。

## 地图渲染流程（`MapView`）

1. **AMap 加载**：组件初始化时调用 `loadAmap(NEXT_PUBLIC_AMAP_KEY)` 动态注入高德 JS SDK，随后 `echarts.init()` 创建实例。
2. **ECharts 配置**：`amap` 选项指定视图模式、中心、缩放与暗色样式；`series` 使用 `scatter` + `coordinateSystem: 'amap'` 渲染标记，颜色按照站点可用性（绿=空闲、橙=紧张、红=故障）。
3. **坐标转换**：`normalizeStation()` 将 BD09 坐标转换为 GCJ02，确保与高德底图一致；缺失坐标的站点会被过滤，不影响列表展示。
4. **交互能力**：
   - Tooltip 展示站点名称、校区、服务商、实时数量，并附带“高德/系统地图”导航链接。
   - 双击任意站点标记会弹出导航卡片，可一键打开高德或系统地图；右下角按钮切换实时定位（浏览器 `watchPosition` → GCJ02 → `setCenter`），并允许一键停止。
   - 校区切换会更新 AMap `center/zoom`，地图与列表保持同步。

## 列表与 UI（React 组件）

- **StationList**：从 `useStations()` 返回的 `campusStations` 中渲染卡片，排序策略保持“关注优先 → 实时数据 → 空闲数量”。卡片使用 shadcn Button/Card 组合构成，右上角为独立关注按钮，支持键盘访问，进度条、校区/服务商标签和“未抓取”提示与旧版一致。
- **Watchlist**：`useWatchlist()` 注入 `isWatched/toggleWatch`，按钮样式改为星形字符（★）并实时同步 `localStorage`。
- **NightNotice**：独立组件，通过 `isNightTime()` 决定是否展示夜间提示，不再依赖 DOM 操作。
- **HeaderBar**：封装校区按钮、服务商下拉、更新时间、手动刷新与主题切换按钮。
- **SummaryGrid**：新增校区摘要组件，显示每个校区的空闲数量与站点总数。

## 自动刷新与提示机制

- `useConfig()` 读取 `fetch_interval`，`useAutoRefresh()` 依据该值调用 `useStations().refresh()`。
- Header 中的“刷新”按钮直接触发 `refresh()`，并在 UI 上立刻进入 loading 状态。
- `RateLimitToast` 根据 `rateLimited` 状态展示限流提示；其余错误在列表卡片中提示排查步骤。

## 位置识别与校区自动切换

- `MapView` 的“实时定位”按钮调用 `useRealtimeLocation()`（内部封装了 `navigator.geolocation.watchPosition`），并通过 `wgs84ToGcj02()` 校正后持续更新用户标记，可随时停止或在权限被拒绝时提示。
- 校区切换由 React 状态驱动，`MapView` 和 `StationList` 同时响应，无需手动触发 `fitBounds`。

## 扩展指引

- **新增校区**：在 `src/config/campuses.ts` 中追加配置，并更新 `CAMPUS_LIST`；按钮会自动从配置渲染。
- **调整地图样式**：`MapView` 中的 `getStationColor()`、`symbolSize` 决定标记风格，可根据数据类型扩展多个 series。
- **附加筛选项**：在 `HeaderBar` 添加新的控件，并将状态下传给 `useStations()` 的参数即可。
- **排序/标签**：修改 `StationList` 内的排序函数或卡片标签；React 组件结构使其更易维护。

Next.js + shadcn 仍保持组件化拆分，部署方式（Node/Vercel/自托管）灵活，新需求可以在各自文件中实现，避免脚本互相耦合。

## 部署提示

- 环境变量：
  - 本地 `frontend/.env.local`

    ```ini
    NEXT_PUBLIC_AMAP_KEY=dev-gaode-key
    NEXT_PUBLIC_API_BASE=http://localhost:8000
    NEXT_PUBLIC_REFRESH_INTERVAL=60
    ```

  - 生产（`.env.production` 或部署平台）

    ```ini
    NEXT_PUBLIC_AMAP_KEY=prod-gaode-key
    NEXT_PUBLIC_API_BASE=https://charger.philfan.cn
    NEXT_PUBLIC_REFRESH_INTERVAL=120
    ```

  - 若前后端同域部署，可省略 `NEXT_PUBLIC_API_BASE`，客户端会直接请求 `/api/*`；设置 `NEXT_PUBLIC_REFRESH_INTERVAL` 可覆盖后端 `/api/config` 中的 `fetch_interval`。
- `pnpm dev` 用于本地调试；`pnpm build && pnpm start` 可验证生产输出，随后按需部署（Vercel、自建 Node/Caddy 等）。

### Vercel 部署

1. 将前端代码推送到 GitHub/GitLab（如果使用子模块，请在 Vercel 项目设置里开启 `Git Submodules`）。
2. Vercel 仪表盘中新建项目 → 关联仓库，框架选择 **Next.js**。
3. Build Command 使用 `pnpm build`，Output 设置为默认 `.next` 即可。
4. 在 **Environment Variables** 中添加 `NEXT_PUBLIC_AMAP_KEY`、`NEXT_PUBLIC_API_BASE`（如需）、`NEXT_PUBLIC_REFRESH_INTERVAL`。
5. 保存后 Vercel 会自动构建并生成 preview/production 域名；如果 API 与前端不同源，记得在 FastAPI 端开启 CORS。

### Cloudflare Pages 部署

Cloudflare Pages 可以使用 Next.js 的“适配器”模式，也可以简单地导出静态包（如果不需要 SSR）。推荐步骤：

1. 运行 `pnpm next export` 生成 `out/`（需先设置 `output: "export"` 或单独添加 `next.config.ts` 中的 `exportTrailingSlash` 等设置；纯静态地图场景通常足够）。
2. 在 Cloudflare Pages 控制台创建项目，选择 Git 仓库，**Build command** 设为 `pnpm next build && pnpm next export`，**Build output directory** 填 `out`。
3. 或者若需要 SSR，可使用 `@cloudflare/next-on-pages` 适配器。安装依赖后在 `package.json` 添加：

   ```json
   {
     "scripts": {
       "cf:build": "next-on-pages"
     }
   }
   ```

   然后在 Pages 中把 Build command 改为 `pnpm run cf:build`，output 目录使用 `.vercel/output/static`。
4. 同样在 Pages 项目设置里添加 `NEXT_PUBLIC_AMAP_KEY`、`NEXT_PUBLIC_API_BASE`、`NEXT_PUBLIC_REFRESH_INTERVAL` 环境变量。
5. Cloudflare 默认开启缓存，如需最新数据可在 Workers/Pages Rules 中为 `/api/*` 路径禁用缓存。
