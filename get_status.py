# 最小抓取示例
import requests
import argparse


def get_device_info(address: str):
    response = requests.post(
        "http://www.szlzxn.cn/wxn/getDeviceInfo",
        data={"areaId": 6, "devaddress": address},
        timeout=10,
    )
    obj = response.json().get("obj")
    return [
        obj.get("devdescript", "未知设备"),
        "可用",
        obj.get("portstatur", "").count("0"),
        "已用",
        obj.get("portstatur", "").count("1"),
        "总数",
        len(obj.get("portstatur", "")),
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="测试尼普顿 getDeviceInfo API")
    parser.add_argument(
        "--address", type=str, default="50359163", help="设备地址 (默认: 50359163)"
    )
    args = parser.parse_args()
    print(*get_device_info(args.address), sep="\n")
