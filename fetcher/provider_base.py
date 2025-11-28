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
            - campus: 校区ID
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
        生成充电区域的 8位 hash 值，用于聚合和查询

        用于标识一个充电区域，相同区域的不同设备应该返回相同的 hash。
        通常使用 provider_name、site_name 和 devaddress 的组合来生成。

        Args:
            provider_name: 服务商显示名称（如 '尼普顿'）
            site_name: 站点名称（devdescript）
            devaddress: 设备地址

        Returns:
            8位hash 字符串，用于标识充电区域
        """
        pass
