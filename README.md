# <img src="assets/logo_white.png" alt="logo" width="30"> 𝐙𝐉𝐔 𝐂𝐡𝐚𝐫𝐠𝐞𝐫 | 便捷高效的充电桩查询助手

![Star Badge](https://img.shields.io/github/stars/Phil-Fan/ZJU-Charger?style=social) ![License Badge](https://img.shields.io/github/license/Phil-Fan/ZJU-Charger) ![Contributors Badge](https://img.shields.io/github/contributors/Phil-Fan/ZJU-Charger) ![Issues Badge](https://img.shields.io/github/issues/Phil-Fan/ZJU-Charger) ![Pull Requests Badge](https://img.shields.io/github/issues-pr/Phil-Fan/ZJU-Charger) ![Last Commit Badge](https://img.shields.io/github/last-commit/Phil-Fan/ZJU-Charger) ![Code Size Badge](https://img.shields.io/github/languages/code-size/Phil-Fan/ZJU-Charger)

[![Markdown Quality Check](https://github.com/Phil-Fan/ZJU-Charger/actions/workflows/markdown-check.yml/badge.svg)](https://github.com/Phil-Fan/ZJU-Charger/actions/workflows/markdown-check.yml) [![Python (Ruff Action)](https://github.com/Phil-Fan/ZJU-Charger/actions/workflows/python-check.yml/badge.svg)](https://github.com/Phil-Fan/ZJU-Charger/actions/workflows/python-check.yml) [![pages-build-deployment](https://github.com/Phil-Fan/ZJU-Charger/actions/workflows/pages/pages-build-deployment/badge.svg)](https://github.com/Phil-Fan/ZJU-Charger/actions/workflows/pages/pages-build-deployment)

![logo](assets/logo.gif)

你是否也曾骑着没电的小龟，慢吞吞地骑到充电桩，却发现一个空余的桩位都没有？😫
你是否也曾被充电桩服务商离谱的 UI 界面与复杂的查询接口所困扰？😠

ZJU Charger 基于 FastAPI 开发，瞄准**校内充电桩不好找、供应商入口不一、使用状态查询不便**三大痛点，为你提供一个简洁、易用、扩展性强的充电桩查询方案。

目前支持网站在线分校区、分服务商查询（普查）、iOS 快捷指令查询特定站点状态（精准查）、钉钉 Webhook 机器人等功能。

访问 [https://charger.philfan.cn/](https://charger.philfan.cn/) 查看效果。

> **免责声明**：本项目仅用于学习交流，不得用于商业盈利与非法用途。使用本项目所造成的任何后果，由使用者自行承担，作者不承担任何责任。请遵守相关法律法规。

## News

- 2025.12.11 - 网站累计访问用户突破 3000 人，感谢所有用户的使用与支持！
- 2025.12.07 - 修复 [CVE-2025-55182](https://www.cve.org/CVERecord?id=CVE-2025-55182)；支持紫金创业园站点；支持望月社区站点
- 2025.12.05 - 支持堕落街服务商，校准并支持西溪校区站点；最新介绍推文详见 [ZJU Charger:便捷高效的充电桩查询助手](https://mp.weixin.qq.com/s/fh2EriLV7aPlDiwghRCwzw)
- 2025.12.02 - 重构前端 UI 并支持尼普顿智慧生活公众号查询
- 2025.11.30 - GitHub 达到 50 Star，感谢支持！[校内公众号宣传贴](https://mp.weixin.qq.com/s/8tX1yHx_uvv64XQashPpTA)
- 2025.12.01 - 支持 iOS 快捷指令，增加华家池校区 [CC98 宣传贴](https://www.cc98.org/topic/6359446)（十大）
- 2025.11.29 - 完成后端页面开发，网站上线 [CC98 宣传贴](https://www.cc98.org/topic/6357576)（十大第一）
- 2025.11.28 - 发现脚本，制作可视化 [CC98 宣传贴](https://www.cc98.org/topic/6357005)

## 功能特性

### 前端功能

Next.js 框架开发：App Router + TypeScript + shadcn/ui, 开源在 [Phil-Fan/zju-charger-frontend](https://github.com/Phil-Fan/zju-charger-frontend) 这个仓库。

- [x] 校区切换：点击校区卡片切换校区，不同校区信息一键查询。
  ![campus_01](assets/campus_01.png)
  ![campus_02](assets/campus_02.png)
  ![campus_03](assets/campus_03.png)
- [x] 站点排序：开启定位后，实时显示站点距离，可按照距离优先或者空闲数量优先对站点进行排序。
  ![sort](assets/sort.png)
- [x] 站点导航：长按或双击地图站点可选择导航，一键跳转到高德/系统地图 APP，找到充电桩不再困难。
  ![navigate](assets/navigate.png)
- [x] 站点关注：常去某站点？点击星标关注站点，显示并保存在列表最上方。通过 localStorage 实现。
  ![watchlist](assets/watchlist.png)
- [x] 明暗切换：点击右上角按钮切换颜色模式，明暗样式任你选择。
  ![light](assets/web_light.png)
  ![dark](assets/web_dark.png)
- [x] 前端定时自动刷新。
- [x] 夜间提示。
- [x] 绿/橙/红三色编码空闲、紧张、故障状态。
- [x] 英文界面支持。

### 后端功能

- [x] FastAPI 统一 API 接口，使用 slowapi 实现接口限流功能
- [x] 多服务商架构支持，可同时异步抓取多个服务商的充电桩数据（目前支持了尼普顿服务商）
- [x] `BackgroundFetcher` 后台定时抓取任务，自动写入 Supabase 缓存
- [x] Supabase 数据库支持，记录历史使用情况数据（可选）

### 快捷指令

[ZJU Charger.shortcut](https://www.icloud.com/shortcuts/1545aeee457046dbacba42ef0ab6285d)

支持快速查询关注的几个站点的状态，并可以添加到主屏幕，方便随时查看。
操作步骤详见 [Script 快捷指令文档](./docs/06-script-shortcuts.md#使用方法)。

![shortcut](assets/shortcut_result.jpg)

### 钉钉 Webhook 机器人

![dingbot](assets/dingbot.png)

## 文档

详细的文档请查看 [docs](./docs/) 目录：

- [快速开始](./docs/01-quick-start.md) - 快速上手指南
- [Web 介绍与部署](./docs/02-web-deployment.md) - 前端功能说明和部署指南
- [Server 端部署](./docs/03-server-deployment.md) - 后端服务器部署指南
- [Fetcher 文档](./docs/04-fetcher.md) - 如何添加新服务商、更新站点信息
- [钉钉机器人文档](./docs/05-dingbot.md) - 钉钉机器人配置和使用
- [Script 快捷指令文档](./docs/06-script-shortcuts.md) - iOS 快捷指令使用指南
- [Supabase 数据库架构](./docs/07-supabase-schema.md) - Supabase 数据库表结构和使用说明
- [API 参考](./docs/08-api.md) - 后端 REST API 描述与示例
- [Logfire Dashboard 指南](./docs/09-logfire-dashboard.md) - 如何启用/自定义 Logfire 监控看板

### 系统架构

在开发层面，目标实现高内聚、低耦合、易于扩展。

```mermaid
flowchart TD

    A["iOS 快捷指令<br/>1. 关注点快速查询"]

    B["Next.js Web App<br/>App Router"]

    C["FastAPI API 服务<br/>(*只读 Supabase*)"]

    D["钉钉机器人<br/>全部"]

    H["Background Fetcher<br/>ProviderManager"]

    F1["NeptuneProvider<br/>尼普顿服务商"]
    F2["其他服务商<br/>可扩展..."]

    G["Supabase 数据库"]

    %% 连接关系
    A --> |查询| C

    B <--> |AJAX| C

    D --> |webhook| C

    C --> |读取数据| G
    H --> |写入缓存| G
    H --> |调度| F1
    H --> |调度| F2
```

所有查询来源（Web、钉钉、脚本）只调用 FastAPI，从 Supabase 读取最近一次抓取的 `latest` 数据；后台抓取线程（`BackgroundFetcher`）在独立线程中运行 ProviderManager，异步刷新数据库缓存。前后端因此做到完全解耦，API 不再直连服务商。

### 项目结构

```text
project/
├── fetcher/
│   ├── provider_manager.py   # 服务商管理器
│   ├── providers/
│   │   ├── provider_base.py  # 服务商抽象基类
│   │   └── neptune.py        # 尼普顿服务商实现
│   └── station.py            # 共享 Station 模型（CSV 解析 + hash 生成）
├── db/
│   ├── client.py             # Supabase 客户端初始化
│   ├── station_repo.py       # stations 表 CRUD
│   ├── usage_repo.py         # latest/usage 表读写
│   ├── pipeline.py           # record_usage_data 数据管道
│   └── __init__.py           # 统一暴露 initialize/get/batch 接口
├── server/
│   ├── api.py                # FastAPI 主服务（直接调用 db/ 仓库）
│   ├── config.py             # 环境变量配置（支持服务商配置）
│   ├── run_server.py         # 服务器启动脚本
│   └── logging_config.py     # 日志配置
├── ding/
│   ├── bot.py                # 钉钉机器人封装
│   ├── webhook.py            # 钉钉 webhook 路由
│   └── commands.py           # 命令解析和执行
├── frontend/                 # Next.js + shadcn 前端
│   ├── package.json          # pnpm scripts、依赖、biome 配置
│   ├── src/app/              # Next App Router 页面、layout、错误页
│   ├── src/components/       # shadcn ui + 业务组件（Header/Map/List 等）
│   └── src/lib|hooks|types   # 校区配置、API 客户端、状态 hooks、坐标工具
├── script/                   # iOS 快捷指令
│   ├── README.md             # 快捷指令使用说明
│   └── *.shortcut            # 快捷指令文件
├── serve.sh                  # 快速启动脚本（基于 uv 同步依赖并调用 server.run_server）
├── pyproject.toml            # Python 依赖声明 + uv/Ruff 配置
└── uv.lock                   # uv 生成的锁定文件
```

## 许可证

使用 GPLv3 许可证，见 [LICENSE](./LICENSE) 文件

## 贡献

欢迎提交 Issue 和 Pull Request！

请查看：

- [行为准则](./CODE_OF_CONDUCT.md)
- [贡献指南](./CONTRIBUTING.md)
- [Issue 模板](./.github/ISSUE_TEMPLATE/)
- [Pull Request 模板](./.github/pull_request_template.md)

![star history](https://api.star-history.com/svg?repos=Phil-Fan/ZJU-Charger&type=Date)

## 致谢

### 后端

- 感谢 [cyc-987/Charge-in-ZJU: 浙大充电桩查询](https://github.com/cyc-987/Charge-in-ZJU) 的原作者 [@cyc-987](https://github.com/cyc-987)，为项目提供灵感；感谢 [紫金港充电桩地图 - CC98 论坛](https://www.cc98.org/topic/6348814) 中分享的 ZJG 充电地图；感谢 [浙江大学 E 校园电子地图平台](https://map.zju.edu.cn/index?locale=en_US) 中的部分充电桩点位信息。
- 使用 [经纬度查询定位 ｜ 坐标拾取](https://www.mapchaxun.cn/Regeo) 调整抓取到的错误站点坐标。
- 使用 [fastapi](https://fastapi.tiangolo.com/) 实现 API 服务；使用 [slowapi](https://github.com/sunhailin-dev/slowapi) 实现接口限流功能。
- 使用 [supabase](https://supabase.com/) 实现数据库功能。
- 使用 [Caddy](https://caddyserver.com/) 实现 HTTPS 证书与反向代理服务。
- 使用 [Logfire](https://pydantic.dev/logfire) 实现日志收集与分析。

### 前端

- 使用 [Next.js](https://nextjs.org/) 实现前端框架。
- 使用 [高德地图 Web JS SDK](https://console.amap.com/dev/index) 实现地图渲染。
- 使用 [Apache ECharts](https://echarts.apache.org/) + [echarts-extension-amap](https://github.com/plainheart/echarts-extension-amap) 完成地图渲染。
- 使用 [Apple URL Scheme - Map Links](https://developer.apple.com/library/archive/featuredarticles/iPhoneURLScheme_Reference/MapLinks/MapLinks.html) 与 [高德地图手机版 API - 路径规划](https://lbs.amap.com/api/amap-mobile/guide/android/navigation) 实现地图跳转。
- 使用 [shadcn/ui](https://ui.shadcn.com/) 实现组件库，使用 [tweakcn](https://tweakcn.com/editor/theme) 生成 Supabase 主题。
- 使用 [Biome](https://biomejs.dev/) 实现代码检查与格式化。
- 感谢 [wandergis/coordtransform](https://github.com/wandergis/coordtransform) 实现坐标转换（WGS84 ↔ GCJ02 ↔ BD09）。

### 其他

- 特别鸣谢 [@qychen2001](https://github.com/qychen2001) 对项目的大力支持！
- 使用 [vuejs/vitepress](https://github.com/vuejs/vitepress) 主题生成项目文档。
- 使用 [huacnlee/autocorrect](https://github.com/huacnlee/autocorrect/), [DavidAnson/markdownlint-cli2-action](https://github.com/DavidAnson/markdownlint-cli2-action) 与 [gaurav-nelson/github-action-markdown-link-check](https://github.com/gaurav-nelson/github-action-markdown-link-check) 对 Markdown 文档进行自动化检查。
- 使用 [uv](https://docs.astral.sh/uv/) 管理 Python 依赖，并以 [Ruff](https://docs.astral.sh/ruff/)&[astral-sh/ruff-action](https://github.com/astral-sh/ruff-action) 完成格式化。
- 使用 [jitter.video](https://jitter.video/templates) 实现 GIF 动画。
- 使用 [Star History](https://star-history.com/) 实现 star 历史统计。
- 使用 [Google analytics](https://analytics.google.com/) 和 [Clarity](https://clarity.microsoft.com/) 实现网站访问统计与用户理解。
- 使用 [Aliyun ECS](https://www.aliyun.com/product/ecs) 实现服务器部署，也使用了 [Vercel](https://vercel.com/) 与 [Cloudflare Pages](https://pages.cloudflare.com/) 实现静态网站部署。
- 感谢 [Elliottt001](https://github.com/Elliottt001)、[Kolle](https://www.cc98.org/user/id/584395)、[且寄白鹿_](https://www.cc98.org/user/id/648756)、[HansWang](https://www.cc98.org/user/id/650562)、[jeno_ccc](https://www.cc98.org/user/id/781655)、[粉红头鲨鱼](https://www.cc98.org/user/id/730812)、[Momentymmt](https://www.cc98.org/user/id/762758)、小王子、红豆糕糕糕、木子霏、云兮归处、青雨、Geoay、小彦子穿花衣、帆、Yyoloooo 等用户对于站点坐标校准的帮助！
- 感谢 SQTP 团队「校园充电桩使用现状可视化分析与优化设计」对于紫金港校区站点位置的校准帮助！
- 感谢[浙江大学学生法律援助中心](https://mp.weixin.qq.com/s/KccCwU2P7ECra-TuvO-aYA)！
- 感谢各位用户对于项目功能的建议与反馈！

感谢所有贡献者！

![GitHub contributors](https://contrib.rocks/image?repo=Phil-Fan/ZJU-Charger)
