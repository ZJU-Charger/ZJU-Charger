"""
站点基本信息数据结构
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable, List

# 校园 ID 映射，定义在外部，作为常量
CAMPUS_NAME_MAP = {
    1: "玉泉校区",
    2: "紫金港校区",
    # 3: "华家池校区",
    # 4: "之江校区",
    # 5: "西溪校区",
}


# 辅助函数：获取带时区的当前时间戳
def _now_ts() -> str:
    tz_utc_8 = timezone(timedelta(hours=8))
    return datetime.now(tz_utc_8).isoformat()


@dataclass
class StationUsage:
    """站点使用情况统计"""

    free: int = 0  # 可用
    used: int = 0  # 已使用
    total: int = 0  # 总数
    error: int = 0  # 故障


@dataclass
class Station:
    """站点基本信息"""

    # --- 1. 必需参数 (Non-default arguments) 放在最前面 ---
    name: str
    provider: str
    campus_id: int

    # --- 2. 可选参数 (Default arguments) 放在后面 ---
    campus_name: str = ""
    lat: float = 30.0  # 纬度
    lon: float = 120.0  # 经度

    # 使用 default_factory 处理可变类型，确保每个实例有独立的列表
    device_ids: List[str] = field(default_factory=list)
    updated_at: str = field(default_factory=_now_ts)

    # hash_id 和 usage 具有默认值，也放在后面
    # hash_id 可以在 __post_init__ 中计算，这里给个初始空值或使用 init=False
    hash_id: str = field(init=False, default="")  # 标记 init=False 优化，使其不出现在 __init__ 中
    usage: StationUsage = field(default_factory=StationUsage)

    def compute_hash_id(self) -> str:
        """计算站点的唯一哈希 ID"""
        base = f"{self.provider}:{self.name}".strip().lower()
        return hashlib.md5(base.encode("utf-8")).hexdigest()[:8]

    def __post_init__(self):
        """实例创建后执行的逻辑"""
        # 1. 自动计算 hash_id
        # 如果 hash_id 没有使用 init=False，则需要检查是否为默认值
        if not self.hash_id:
            self.hash_id = self.compute_hash_id()

        # 2. 自动填充校区名称
        if not self.campus_name and self.campus_id in CAMPUS_NAME_MAP:
            self.campus_name = CAMPUS_NAME_MAP[self.campus_id]

        # 3. 设备 ID 全部转成字符串，便于比较
        self.device_ids = [str(d) for d in self.device_ids if str(d)]

    @classmethod
    def from_csv_row(cls, row: dict) -> Station:
        """从 CSV 行数据（字典）创建一个 Station 实例"""
        # 1. 处理 device_ids 字段，兼容 JSON 列表或分号分隔字符串
        device_raw = row.get("device_ids", "")
        device_ids: Iterable[str]
        if device_raw:
            try:
                # 尝试解析 JSON
                device_ids = json.loads(device_raw)
            except json.JSONDecodeError:
                # 解析失败，退化为分号分隔
                device_ids = [item.strip() for item in device_raw.split(";") if item.strip()]
        else:
            device_ids = []

        # 2. 获取 campus_id
        campus_id = int(row.get("campus", 0) or 0)  # 确保转换为 int

        # 3. 创建 Station 实例
        return cls(
            name=row.get("name", "未知站点").strip(),
            provider=row.get("provider", "unknown").strip(),
            campus_id=campus_id,
            # campus_name 现在可以省略，因为它会在 __post_init__ 中根据 campus_id 自动填充
            # lat 和 lon 从 CSV 获取值，并安全地转换为 float
            lat=float(row.get("lat", 30.0) or 30.0),
            lon=float(row.get("lon", 120.0) or 120.0),
            device_ids=list(device_ids),
            # updated_at, hash_id, usage 依赖默认值或 __post_init__ 自动处理，无需传入
        )


def load_stations_from_csv(csv_path: Path) -> List[Station]:
    """从 CSV 文件加载所有站点信息"""
    with csv_path.open("r", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        # 直接使用 Station.from_csv_row 创建实例
        stations = [Station.from_csv_row(row) for row in reader]

    # 过滤掉没有 device_ids 的站点
    return [s for s in stations if s.device_ids]


def _data_to_station(data: Dict[str, Any]) -> Station:
    """
    【数据适配器】
    将数据库返回的通用字典数据转换为 Station 对象。
    该转换逻辑存在于 Fetcher 领域层。
    """

    # 1. 处理 usage 字段（如果数据包含 usage 字段，尽管 station_repo 不返回它，但以防万一）
    # 由于 fetch_all_stations_data 只返回 stations 表的元数据，usage 字段通常不包含。
    # 我们可以安全地使用默认的 StationUsage。
    usage = StationUsage(
        free=data.get("free", 0),
        used=data.get("used", 0),
        total=data.get("total", 0),
        error=data.get("error", 0),
    )

    # 2. 构造 Station 实例 (尽量使用 dataclass 的构造函数)
    return Station(
        name=data["name"],  # 假设 DB 确保非空
        provider=data["provider"],
        campus_id=data["campus_id"],
        # 可选参数
        campus_name=data.get("campus_name", ""),
        lat=data.get("lat", 30.0),
        lon=data.get("lon", 120.0),
        # 注意：device_ids 需处理 None 或其他类型
        device_ids=list(data.get("device_ids") or []),
        # 传入 hash_id 和 updated_at 以覆盖默认值/post_init
        hash_id=data.get("hash_id"),
        updated_at=data.get("updated_at"),
        usage=usage,
    )


def load_stations_from_db(provider: str) -> List[Station]:
    """
    从 Supabase 数据库加载指定 provider 的站点列表，并转换为 Station 对象。

    Args:
        provider: 要加载的站点提供商名称。

    Returns:
        加载后的 Station 实例列表。

    Raises:
        任何由 DB 操作或网络引起的异常。
    """
    # **减少 try-catch：** # 直接调用 DB 接口，将潜在的 Supabase/网络错误抛给上层调用者。

    print(f"尝试从数据库加载 provider='{provider}' 的站点数据...")

    # 1. 调用 DB 层接口，获取 List[Dict] (如果失败，异常将抛出)
    station_data_list = fetch_all_stations_data(provider=provider)

    if not station_data_list:
        print(f"数据库中未找到 provider='{provider}' 的站点数据。")
        return []

    # 2. 领域层进行数据转换
    stations = [_data_to_station(data) for data in station_data_list]

    print(f"成功从数据库加载 {len(stations)} 个站点。")
    return stations
