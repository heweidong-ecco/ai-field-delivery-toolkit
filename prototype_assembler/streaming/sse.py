"""SSE 流式输出（集成重连）"""

import asyncio
import json
from typing import AsyncGenerator, Optional

from prototype_assembler.streaming.reconnector import StreamReconnector


async def sse_stream(content_generator, reconnect: bool = True) -> AsyncGenerator[str, None]:
    """将内容生成器包装为 SSE 事件流，支持断线重连

    参数:
        content_generator: 异步生成器，产生内容块字符串
        reconnect: 是否启用自动重连
    """
    if not reconnect:
        async for chunk in content_generator:
            data = json.dumps({"content": chunk}, ensure_ascii=False)
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"
        return

    reconnector = StreamReconnector()

    async def _produce():
        async for chunk in content_generator:
            yield chunk

    result = await reconnector.run_with_reconnect(lambda: _produce())
    if result is None:
        error_data = json.dumps({"error": "流式连接失败，已重试多次"}, ensure_ascii=False)
        yield f"data: {error_data}\n\n"
        yield "data: [DONE]\n\n"
        return

    async for chunk in result:
        data = json.dumps({"content": chunk}, ensure_ascii=False)
        yield f"data: {data}\n\n"
    yield "data: [DONE]\n\n"