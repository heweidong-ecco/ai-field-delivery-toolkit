"""流式输出自动重连（指数退避）"""

import asyncio
from typing import Optional, Callable, Any

from core.logging.logger import get_logger

logger = get_logger()


class StreamReconnector:
    """流式重连器"""

    def __init__(
        self,
        max_retries: int = 5,
        initial_delay_seconds: float = 1.0,
        max_delay_seconds: float = 30.0,
        backoff_factor: float = 2.0,
    ):
        self.max_retries = max_retries
        self.initial_delay_seconds = initial_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.backoff_factor = backoff_factor

    async def run_with_reconnect(self, stream_func: Callable) -> Optional[Any]:
        """执行流式任务，失败时自动重连

        参数:
            stream_func: 异步流式函数，返回可迭代的结果

        返回:
            成功时返回流式结果，全部重试失败返回 None
        """
        delay = self.initial_delay_seconds
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await stream_func()
                if attempt > 1:
                    logger.info(f"流式重连成功，第 {attempt} 次尝试")
                return result
            except Exception as e:
                logger.warning(f"流式连接失败（第 {attempt} 次）: {e}")
                if attempt >= self.max_retries:
                    logger.error("达到最大重试次数，放弃重连")
                    return None
                logger.info(f"等待 {delay:.1f} 秒后重试...")
                await asyncio.sleep(delay)
                delay = min(delay * self.backoff_factor, self.max_delay_seconds)
        return None