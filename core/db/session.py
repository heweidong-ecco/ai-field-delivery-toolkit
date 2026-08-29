"""异步数据库会话管理"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from core.config.settings import get_settings


def get_database_url() -> str:
    """根据配置构造数据库 URL"""
    settings = get_settings()
    return (
        f"postgresql+asyncpg://{settings.postgres_user}:"
        f"{settings.postgres_password}@{settings.postgres_host}:"
        f"{settings.postgres_port}/{settings.postgres_db}"
    )


# 全局引擎和会话工厂
_engine = None
_session_factory = None


def get_engine():
    """获取全局异步引擎单例"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_database_url(), echo=False, pool_size=5, max_overflow=10)
    return _engine


def get_session_factory() -> async_sessionmaker:
    """获取异步会话工厂"""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncSession:
    """获取一个异步会话（依赖注入用）"""
    async with get_session_factory()() as session:
        yield session


async def close_engine():
    """关闭引擎"""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None