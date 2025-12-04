"""服务商抽象基类：定义所有充电桩服务商必须实现的接口"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from pathlib import Path

from fetcher.station import Station, load_stations_from_csv

import aiohttp

# 定义一个类型别名，或直接在签名中使用 aiohttp.ClientSession
ClientSession = aiohttp.ClientSession


@dataclass
class ProviderBase(ABC):
    """服务商抽象基类"""

    # 【新增】定义 CSV 文件所在的根目录 (可以根据需要修改)
    # 实际应用中，这可以从配置中加载
    SCRIPT_DIR = Path(__file__).parent
    DATA_DIR = SCRIPT_DIR / "data"

    station_list: List[Station] = field(default_factory=list)

    @property
    @abstractmethod
    def provider(self) -> str:
        """服务商标识（如 'neptune'）"""
        raise NotImplementedError

    def load_station_from_csv(self) -> List[Station]:
        csv_filename = f"{self.provider}_stations.csv"
        csv_path = self.DATA_DIR / csv_filename

        if not csv_path.exists():
            print(f"Warning: Station file not found for provider '{self.provider}' at {csv_path}")
            self.station_list = []
            return []

        # 使用通用的加载函数
        self.station_list = load_stations_from_csv(csv_path)
        return self.station_list

    def load_station_from_db(self) -> List[Station]:
        """
        从 Supabase 数据库加载站点列表
        """
        self.station_list = load_stations_from_db(self.provider)
        return self.station_list

    def load_stations(self) -> List[Station]:
        """
        根据 self.provider 构造 CSV 路径，加载并设置站点列表。
        例如：provider="neptune" -> 尝试加载 "data/neptune_stations.csv"

        Returns:
            加载后的 Station 实例列表
        """
        return self.load_station_from_csv()

    # 其余抽象方法保持不变
    @abstractmethod
    async def fetch_station_list(self, session: ClientSession) -> Optional[List[Dict[str, Any]]]:
        """获取供应商 api 返回的所有站点列表 (原始数据)"""
        raise NotImplementedError

    @abstractmethod
    async def fetch_device_status(
        self, station: Station, device_id: str, session: ClientSession
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        """获取单个设备状态数据。"""
        raise NotImplementedError

    @abstractmethod
    async def fetch_station_status(
        self, station: Station, session: ClientSession
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Exception]]:
        """获取站点状态数据 (包含聚合结果)。"""
        raise NotImplementedError

    @abstractmethod
    async def fetch_status(self, session: ClientSession) -> Optional[List[Dict[str, Any]]]:
        """获取供应商所有 station 的状态数据并转换为统一格式。"""
        raise NotImplementedError
