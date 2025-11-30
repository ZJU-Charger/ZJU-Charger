from fetcher.provider_manager import ProviderManager
import asyncio
import json


def default_serializer(obj):
    # Attempt to get serializable dict for user objects
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        return obj.to_dict()
    elif hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    else:
        return str(obj)


async def main():
    manager = ProviderManager()
    await manager.initialize_providers()
    # 获取格式化后的数据（合并所有服务商，类似 API 返回结构）
    result = await manager.fetch_and_format()
    # 美化输出: 日期时间和站点信息，支持中文内容
    print(json.dumps(result, indent=4, ensure_ascii=False, default=default_serializer))


if __name__ == "__main__":
    asyncio.run(main())
