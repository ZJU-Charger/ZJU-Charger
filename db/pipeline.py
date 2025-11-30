"""
业务流程模块
封装数据处理逻辑
"""

# db/pipeline.py

import logging
from typing import Dict, Any, List

# 导入 usage_repo 中实现的批量插入函数
from .usage_repo import batch_insert

logger = logging.getLogger(__name__)


def record_usage_data(data: Dict[str, Any], history_mode_enabled: bool = False) -> bool:
    """
    核心数据管道：根据模式参数，决定是只更新 latest 缓存，还是同时记录 usage 历史。

    Args:
        data: 包含 'stations' (List[Dict]) 和 'updated_at' (str) 的字典。
              'updated_at' 字段是强制性的，作为所有记录的 snapshot_time。
        history_mode_enabled: 是否开启历史记录模式。

    Returns:
        是否成功完成所有必要操作。
    """

    # --- 1. 输入数据完整性检查 ---
    snapshot_time = data.get("updated_at")
    stations_data: List[Dict[str, Any]] = data.get("stations", [])

    if not snapshot_time:
        logger.error("数据记录失败：缺少 'updated_at' 字段，无法确定抓取时间。")
        return False

    if not stations_data:
        logger.warning("无站点数据可记录，流程结束。")
        # 认为空数据处理成功
        return True

    logger.info(
        "开始处理使用情况数据，抓取时间: %s，共 %d 条记录。",
        snapshot_time,
        len(stations_data),
    )

    # --- 2. 写入 latest 缓存表 (必须执行) ---
    # 调用 usage_repo.batch_insert 写入 latest 表
    success_cache = batch_insert(data, sheet_name="latest")

    if not success_cache:
        logger.error("更新 latest 缓存表失败，流程中断。")
        # 如果缓存都失败了，我们通常会返回失败
        return False

    # --- 3. 根据模式决定是否写入 usage 历史表 ---
    success_archive = True  # 默认成功，除非开启了历史模式且失败了

    if history_mode_enabled:
        logger.debug("历史记录模式开启。开始归档 usage 历史数据。")

        # 调用 usage_repo.batch_insert 写入 usage 表
        success_archive = batch_insert(data, sheet_name="usage")

        if not success_archive:
            logger.error("写入 usage 历史表失败。")
    else:
        logger.debug("历史记录模式关闭，跳过 usage 历史表归档。")

    # --- 4. 结果总结 ---
    final_success = success_cache and success_archive

    if final_success:
        mode_desc = "历史模式" if history_mode_enabled else "缓存模式"
        logger.info(f"数据记录和缓存流程全部成功完成 ({mode_desc})。")
    else:
        logger.warning("数据管道执行完毕，但部分操作失败（详见上方日志）。")

    return final_success
