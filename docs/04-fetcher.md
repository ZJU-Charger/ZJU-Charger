# Fetcher 文档

本文档介绍如何添加新的充电桩服务商、如何更新站点信息，以及如何调整站点数据以符合规范。

[TOC]

## 如何增加新的供应商

### 1. 了解架构

系统采用多服务商架构，所有服务商必须实现 `ProviderBase` 抽象基类：

```shell
fetcher/
├── provider_manager.py       # 服务商管理器
├── providers/
│   ├── provider_base.py      # 抽象基类
│   ├── neptune.py            # 尼普顿服务商（示例）
│   └── your_provider.py      # 你的新服务商
└── station.py                # Station 数据类（供 fetcher/server 复用）
```

### 2. 创建服务商类

在 `fetcher/providers/` 目录下创建新文件，例如 `your_provider.py`：

完成下面接口的实现：

```python
"""服务商抽象基类：定义所有充电桩服务商必须实现的接口"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class ProviderBase(ABC):
    """充电桩服务商抽象基类

    所有服务商适配器必须继承此类并实现抽象方法
    """

    @property
    @abstractmethod
    def provider(self) -> str:
        """服务商标识（如 'neptune'）"""
        pass
```

## Station 数据结构

`fetcher/station.py` 定义了 `Station` 数据类，集中管理站点的静态信息：

- `name` / `provider`：站点名称与服务商唯一标识；
- `campus_id` / `campus_name`：校区 ID 与可选名称；
- `lat` / `lon`：坐标；
- `device_ids`：该站点包含的所有设备号（字符串列表）；
- `hash_id`：由 `compute_hash_id(provider, name)` 自动生成；
- `updated_at`：写入数据库时使用的时间戳。

所有 CSV 行会转换为 `Station` 实例，后台启动或 fetcher 运行时均复用该数据类，从而保证 hash 算法和字段含义只实现一次。

    ```python
    @abstractmethod
    async def fetch_stations(self, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """
        从 data/stations.csv 中获取站点列表

        Returns:
            站点列表，如果失败返回 None
        """
        pass

    @abstractmethod
    async def fetch_status(self, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """获取站点状态数据

        Returns:
            统一格式的站点列表，如果失败返回 None
            每个站点必须包含以下字段：
            - provider: 服务商标识
            - hash_id/id: 站点唯一标识（`md5(provider:name)`）
            - name/campus_id/campus_name/lat/lon/device_ids
            - free/total/used/error
        """
        pass

    @abstractmethod
    def gen_area_hash(self, *args, **kwargs) -> str:
        """
        生成充电区域的 8 位 hash 值，用于聚合和查询

        用于标识一个充电区域，相同区域的不同设备应该返回相同的 hash。
        通常使用 provider（服务商标识）+ site_name 的组合来生成。

        Args:
            provider_name: 服务商标识（如 'neptune'）
            site_name: 站点名称（devdescript）
            devaddress: 设备地址

        Returns:
            8 位 hash 字符串，用于标识充电区域
        """
        pass
    ```

### 3. 注册服务商

在 `fetcher/provider_manager.py` 中注册新服务商：

```python
from .providers.your_provider import YourProvider

def _register_providers(self):
    """注册所有可用服务商"""
    # 注册尼普顿服务商
    neptune = NeptuneProvider()
    self.providers.append(neptune)

    # 注册你的新服务商
    your_provider = YourProvider()
    self.providers.append(your_provider)

    logger.info(f"已注册服务商：{your_provider.provider}")
```

### 4. 更新站点数据

自行抓取新服务商的站点数据，并追加到 `data/stations.csv`。CSV 头部如下：

```text
name,provider,campus,lat,lon,device_ids
玉泉科工楼东侧，neptune,2143,30.266195,120.130415,[10574]
玉泉教七北侧，neptune,2143,30.270660,120.126950,"[10223,10222,9501]"
```

字段含义：

- `name`：站点名称；
- `provider`：服务商唯一标识（与 `.env`、前端筛选一致）；
- `campus`：校区 ID（`2143`=玉泉，`1774`=紫金港，或自定义 ID）；
- `lat`/`lon`：站点地理坐标；
- `device_ids`：该站点包含的全部设备/桩号，JSON 数组格式。

`fetcher/station.py` 中的 `Station` 数据类会读取 CSV，自动生成 `hash_id`（`md5(provider:name)`）并在缺失时补齐 `campus_name`、`updated_at`。

## 如何调整 stations 以符合规范

### 数据格式规范

`data/stations.csv` 定义了全部静态信息，启动 FastAPI 时会自动同步到 Supabase `stations` 表。运行时流程：

1. **基础信息** → CSV → `Station` 数据类 → `stations` 表（字段：`hash_id/name/provider/campus_id/campus_name/lat/lon/device_ids/updated_at`）。
2. **使用情况** → 抓取后写入 `latest`（保留最新一条）与 `usage`（历史快照，若 `SUPABASE_HISTORY_ENABLED=true`）。

CSV 每行会被转换为如下结构（仅示意）：

```json
{
  "hash_id": "29e30f45",
  "name": "玉泉教三",
  "provider": "neptune",
  "campus_id": 2143,
  "campus_name": "玉泉校区",
  "lat": 30.2699,
  "lon": 120.1249,
  "device_ids": ["50359163", "50359164"]
}
```

> 说明：启动时的同步逻辑只会补齐 `hash_id` 和 `updated_at`，不会覆盖 CSV，也完全不再使用旧版 `stations.json`。

`latest/usage` 行的结构示例：

```json
{
  "hash_id": "29e30f45",
  "snapshot_time": "2025-11-29T10:00:00+08:00",
  "free": 4,
  "used": 6,
  "total": 10,
  "error": 0
}
```

因此，fetcher 的职责就是把抓取到的实时数据拆分为：

- 站点静态信息 → `stations` 表（upsert）
- 最新快照 → `latest` 表（upsert，每个 `hash_id` 仅一行）
- 历史快照 → `usage` 表（insert）

API 层会从 `latest` + `stations` 表组装 `/api/status` 所需的 JSON，前端无需关心数据库细节。若 `.env` 中将 `SUPABASE_HISTORY_ENABLED=false`，则 fetcher 仍需更新 `latest` 与 `stations`（尤其是 `devids`），但可以跳过历史 `usage` 表的插入。

### 校区 ID 规范

- `2143`: 玉泉校区
- `1774`: 紫金港校区
- 其他值：其他校区（可根据实际情况定义）

## 测试

启动服务器并测试：

```bash
python run_server.py
```

访问 `http://localhost:8000/api/status?provider=your_provider` 查看新服务商的数据。
