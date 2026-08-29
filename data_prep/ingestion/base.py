"""数据接入基类"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class DataIngestor(ABC):
    """数据接入抽象基类"""

    @abstractmethod
    def ingest(self, source: str) -> Dict[str, Any]:
        """执行数据接入

        返回:
            {"data": [{"content": "...", "metadata": {...}}, ...]}
        """
        pass