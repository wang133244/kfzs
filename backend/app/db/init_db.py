# 数据库初始化脚本入口：执行 python -m app.db.init_db 即可建表并写入种子数据
import asyncio

from app.seed import init_db


# 同步入口：将异步初始化流程包装为 asyncio.run 调用
def main() -> None:
    asyncio.run(init_db())


if __name__ == "__main__":
    main()
