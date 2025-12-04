# 扫描尼普顿设备信息
import requests
import json
import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Any, Generator, Tuple, Dict
from tqdm import tqdm
from collections import defaultdict


# --- 核心抓取函数（返回所有详细数据） ---
def get_device_info(address: str) -> Tuple[str, str, int, int, int] | None:
    """
    通过 POST 请求获取指定设备地址 (address) 的详细信息。
    成功获取到有效描述则返回 (devid, devdescript, 可用, 已用, 总数) 元组，否则返回 None。
    """
    try:
        response = requests.post(
            "http://www.szlzxn.cn/wxn/getDeviceInfo",
            data={"areaId": 6, "devaddress": address},
            timeout=5,
        )
        response.raise_for_status()

        data = response.json()
        obj = data.get("obj")

        # 验证是否为有效设备：存在 obj 且 devdescript 不为空
        if obj and obj.get("devdescript"):
            dev_description = obj.get("devdescript", "未知设备").strip()
            # 如果描述是空字符串，也视为无效，避免聚合出现空描述的分组
            if not dev_description:
                return None

            port_status = obj.get("portstatur", "")
            available_count = port_status.count("0")
            used_count = port_status.count("1")
            total_count = len(port_status)

            # 返回结果元组 (devid, devdescript, ...)
            return (address, dev_description, available_count, used_count, total_count)

        return None

    except requests.exceptions.RequestException:
        return None
    except json.JSONDecodeError:
        return None


# --- ID 生成器函数（与之前相同） ---
def generate_ids_by_pattern() -> Generator[str, None, None]:
    """
    根据用户定义的模式生成 8 位设备 ID 字符串。
    """
    prefixes = ["40", "50", "60"]
    mid_parts = ["459", "559", "659", "759", "859", "959"]

    for prefix in prefixes:
        for mid in mid_parts:
            full_prefix = prefix + mid
            for suffix_int in range(1000):
                suffix_str = f"{suffix_int:03d}"
                yield full_prefix + suffix_str


# --- 扫描主逻辑（与之前相同，只是返回值类型不同） ---
def pattern_scan(
    ids_generator: Generator[str, None, None], max_workers: int = 50
) -> List[Tuple[str, str, int, int, int]]:
    """
    接收 ID 生成器，并使用多线程和 tqdm 进行扫描。
    """
    all_ids = list(ids_generator)
    total_ids = len(all_ids)

    if total_ids == 0:
        print("❌ 未生成任何设备 ID。")
        return []

    print(f"✅ 根据模式共生成 {total_ids} 个 ID，开始并发扫描...")

    found_results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_address = {
            executor.submit(get_device_info, address): address for address in all_ids
        }

        with tqdm(total=total_ids, desc="扫描进度") as pbar:
            for future in as_completed(future_to_address):
                pbar.update(1)

                try:
                    result = future.result()
                    if result:
                        found_results.append(result)
                        pbar.set_postfix_str(f"发现: {len(found_results)}")
                except Exception:
                    pass

    print("\n✅ 所有模式匹配 ID 扫描完成。")
    return found_results


# --- 核心聚合逻辑 ---
def aggregate_results(
    results: List[Tuple[str, str, int, int, int]],
) -> List[Dict[str, Any]]:
    """
    按设备描述 (devdescript) 聚合设备 ID，并保留其他信息。

    Args:
        results: 原始扫描结果列表。

    Returns:
        按 devdescript 聚合后的列表。
    """
    aggregated_data = defaultdict(lambda: {"devids": [], "available": 0, "used": 0, "total": 0})

    # 第一次遍历：聚合 ID 和端口信息
    for devid, devdescript, _available, _used, _total in results:
        group = aggregated_data[devdescript]
        group["devids"].append(devid)
        # 这里仅聚合 ID，端口信息我们不进行累加，以第一次出现的为准，但为了简化，我们只输出 ID
        # 如果需要保留端口信息，需要更复杂的逻辑来决定保留哪个设备的端口数据

    # 第二次遍历：格式化最终输出列表
    final_output = []
    for devdescript, data in aggregated_data.items():
        # 将 ID 列表转换为所需的字符串形式 "[id1,id2,id3]"
        devids_str = f"[{','.join(data['devids'])}]"

        final_output.append(
            {
                "devdescript": devdescript,
                "device_ids": devids_str,
            }
        )

    return final_output


# --- CSV 输出函数（针对聚合格式） ---
def write_to_csv(
    aggregated_results: List[Dict[str, Any]],
    output_filename: str = "aggregated_device_results.csv",
):
    """
    将聚合后的结果写入 CSV 文件。
    CSV 头部为: devdescript, device_ids
    """
    if not aggregated_results:
        print("🚫 无有效设备数据，不生成 CSV 文件。")
        return

    # 定义 CSV 表头
    fieldnames = ["devdescript", "device_ids"]

    try:
        with open(output_filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            writer.writeheader()  # 写入表头
            writer.writerows(aggregated_results)  # 写入数据行

        print(f"\n🎉 成功将 {len(aggregated_results)} 组设备信息写入文件: **{output_filename}**")
    except Exception as e:
        print(f"\n❌ 写入 CSV 文件失败: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="根据特定模式扫描设备信息，按描述聚合 ID 并输出 CSV。"
    )
    parser.add_argument("--workers", type=int, default=50, help="并发线程数 (默认: 50)")
    parser.add_argument(
        "--output",
        type=str,
        default="aggregated_device_results.csv",
        help="CSV 输出文件名 (默认: aggregated_device_results.csv)",
    )

    args = parser.parse_args()

    # 1. 生成 ID
    ids_to_scan = generate_ids_by_pattern()

    # 2. 扫描 (获取所有详细数据)
    found_devices_detail = pattern_scan(ids_to_scan, args.workers)

    # 3. 聚合结果 (按 devdescript 分组)
    aggregated_data = aggregate_results(found_devices_detail)

    # 4. 写入 CSV 文件
    write_to_csv(aggregated_data, args.output)
