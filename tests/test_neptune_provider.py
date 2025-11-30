from fetcher.providers.neptune import NeptuneProvider
from pathlib import Path
import asyncio


async def main():
    # 1. 监测是否可以正确加载数据
    neptune = NeptuneProvider()
    await neptune.load_stations()
    print(neptune.station_list)


if __name__ == "__main__":
    asyncio.run(main())
