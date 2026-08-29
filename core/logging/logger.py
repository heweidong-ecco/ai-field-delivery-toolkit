"""统一日志配置"""

import os
import sys
from loguru import logger

from core.config.settings import get_settings


def setup_logger():
    """初始化全局日志"""
    settings = get_settings()

    # 移除默认处理器
    logger.remove()

    # 控制台输出
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan> - <level>{message}</level>",
    )

    # 文件输出
    log_dir = settings.log_dir
    os.makedirs(log_dir, exist_ok=True)
    logger.add(
        os.path.join(log_dir, "toolkit_{time:YYYY-MM-DD}.log"),
        level=settings.log_level,
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} - {message}",
    )

    return logger


# 全局 logger 实例
_logger = None


def get_logger():
    """获取全局 logger"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger