"""Loop 基类"""

from abc import ABC, abstractmethod
from typing import Any


class BaseLoop(ABC):
    """Agent Loop 抽象基类"""

    name: str = "base"

    @abstractmethod
    def run(self, agent: Any, user_input: str, resume: bool = False) -> str:
        """执行循环"""
        pass