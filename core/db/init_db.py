"""数据库初始化：创建所有表"""

import asyncio
from sqlalchemy import text

from core.db.models import Base
from core.db.session import get_engine
from core.logging.logger import get_logger

logger = get_logger()


async def init_db():
    """创建所有表并初始化必要的扩展"""
    engine = get_engine()

    async with engine.begin() as conn:
        # 创建扩展
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)

    logger.info("数据库初始化完成，所有表已创建")
    await engine.dispose()


def main():
    asyncio.run(init_db())


if __name__ == "__main__":
    main()