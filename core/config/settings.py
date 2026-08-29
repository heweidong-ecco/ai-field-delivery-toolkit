"""统一配置入口，所有模块通过此入口读取配置"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """全局配置"""

    # 数据库
    postgres_user: str = "toolkit"
    postgres_password: str = "toolkit_dev"
    postgres_db: str = "toolkit"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # 模型 API
    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    default_model: str = "deepseek-chat"

    # 日志
    log_level: str = "INFO"
    log_dir: str = "./logs"

    # 服务端口
    api_port: int = 8100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局单例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取全局配置单例"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings