"""短期记忆"""

from collections import deque
from typing import List, Tuple


class ShortTermMemory:
    """短期记忆：会话上下文，保留最近 N 轮"""

    def __init__(self, max_rounds: int = 10):
        self.max_rounds = max_rounds
        self.messages: deque = deque(maxlen=max_rounds * 2)  # 用户 + 助手

    def add(self, role: str, content: str):
        """添加一条消息"""
        self.messages.append({"role": role, "content": content})

    def get_all(self) -> List[dict]:
        """获取所有消息"""
        return list(self.messages)

    def get_last_n(self, n: int) -> List[dict]:
        """获取最近 n 条消息"""
        return list(self.messages)[-n:]

    def clear(self):
        """清空记忆"""
        self.messages.clear()