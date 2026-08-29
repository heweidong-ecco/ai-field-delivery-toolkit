"""统一降级管理器"""

from enum import Enum
from typing import Optional, Any


class DegradationLevel(str, Enum):
    """降级等级"""
    NORMAL = "normal"            # 正常运行
    CACHE = "cache"              # 使用缓存
    RULE = "rule"                # 使用规则兜底
    MANUAL = "manual"            # 转人工
    REJECT = "reject"            # 完全拒绝


class DegradationManager:
    """降级管理器

    所有 AI 调用必须通过此管理器执行，当模型不可用时自动降级。
    """

    def __init__(self):
        self.current_level = DegradationLevel.NORMAL

    def execute(self, model_call, cache_get=None, rule_fallback=None, manual_queue=None) -> Any:
        """执行 AI 调用，自动降级

        参数:
            model_call: 模型调用函数
            cache_get: 缓存获取函数
            rule_fallback: 规则兜底函数
            manual_queue: 人工队列推送函数
        """
        # 1. 尝试模型调用
        try:
            result = model_call()
            self.current_level = DegradationLevel.NORMAL
            return result
        except Exception:
            pass

        # 2. 缓存降级
        if cache_get:
            result = cache_get()
            if result is not None:
                self.current_level = DegradationLevel.CACHE
                return result

        # 3. 规则兜底
        if rule_fallback:
            result = rule_fallback()
            if result is not None:
                self.current_level = DegradationLevel.RULE
                return result

        # 4. 转人工
        if manual_queue:
            manual_queue()
            self.current_level = DegradationLevel.MANUAL
            return None

        # 5. 完全拒绝
        self.current_level = DegradationLevel.REJECT
        return None