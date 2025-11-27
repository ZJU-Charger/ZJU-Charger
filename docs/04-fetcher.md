# Fetcher 文档

本文档介绍如何添加新的充电桩服务商、如何更新站点信息，以及如何调整站点数据以符合规范。

[TOC]

## 如何增加新的供应商

### 1. 了解架构

系统采用多服务商架构，所有服务商必须实现 `ProviderBase` 抽象基类：

```shell
fetcher/
├── provider_base.py      # 抽象基类
├── provider_manager.py   # 服务商管理器
└── providers/
    ├── neptune.py        # 尼普顿服务商（示例）
    └── your_provider.py  # 你的新服务商
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
    def provider_id(self) -> str:
        """服务商标识（如 'neptune'）"""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """服务商显示名称（如 '尼普顿'）"""
        pass
    
    @abstractmethod
    async def fetch_stations(self, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """
        从 data/stations.json 中获取站点列表
        
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
            - provider_id: 服务商标识
            - provider_name: 服务商显示名称
            - id: 站点唯一标识（用于聚合和查询）
            - name: 站点名称
            - campus: 校区 ID
            - lat: 纬度
            - lon: 经度
            - free: 可用数量
            - total: 总数
            - used: 已用数量
            - error: 故障数量
        """
        pass
    
    @abstractmethod
    def gen_area_hash(self, *args, **kwargs) -> str:
        """
        生成充电区域的 8 位 hash 值，用于聚合和查询
        
        用于标识一个充电区域，相同区域的不同设备应该返回相同的 hash。
        通常使用 provider_name、site_name 和 devaddress 的组合来生成。
        
        Args:
            provider_name: 服务商显示名称（如 '尼普顿'）
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
    
    logger.info(f"已注册服务商：{your_provider.provider_name} ({your_provider.provider_id})")
```

### 4. 更新站点数据

自行抓取新服务商的站点数据，并添加到 `data/stations.json`：

```json
{
  "updated_at": "2025-01-01T00:00:00+08:00",
  "neptune": [
    {
      "devid": 12345,
      "devaddress": 60359125,
      "areaid": 2143,
      "devdescript": "站点名称",
      "longitude": 120.124954,
      "latitude": 30.269932,
      "simDevaddress": "详细地址（可选）",
      "provider_id": "neptune",
      "provider_name": "尼普顿"
    }
  ],
  "your_provider": [
    {
      "devid": 67890,
      "devaddress": "设备地址",
      "areaid": 2143,
      "devdescript": "站点名称",
      "longitude": 120.12,
      "latitude": 30.27,
      "provider_id": "your_provider",
      "provider_name": "你的服务商"
    }
  ]
}
```

## 如何调整 stations 以符合规范

### 数据格式规范

`data/stations.json` 可以有自己的格式，但是在供应商实现后输出到 `data/latest.json` 时，必须符合以下格式，用于后续的聚合和查询：

```json
{
    "provider_id": "provider_id",
    "provider_name": "provider_name",
    "id": "id",
    "name": "name",
    "campus": 2143,
    "lat": latitude,
    "lon": longitude,
    "free": free,
    "total": total,
    "used": used,
    "error": error
}
```

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
