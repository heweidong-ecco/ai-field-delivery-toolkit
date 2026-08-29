"""长期记忆（基础版）：用户事实存储"""

from typing import Dict, Any, Optional


class LongTermMemory:
    """长期记忆：用户事实，键值对存储"""

    def __init__(self):
        self.facts: Dict[str, Any] = {}

    def set(self, key: str, value: Any):
        """设置或更新事实"""
        self.facts[key] = value

    def get(self, key: str) -> Optional[Any]:
        """获取事实"""
        return self.facts.get(key)

    def delete(self, key: str):
        """删除事实"""
        self.facts.pop(key, None)

    def get_relevant(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """按相关度检索（MVP：简单返回全部，后续可接入向量检索）"""
        # TODO: 后续接入向量检索，根据语义相关度返回事实
        # MVP 简单返回全部（按插入顺序）
        return dict(list(self.facts.items())[:top_k])