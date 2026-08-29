"""提示词注入拦截"""

import re


class InjectionDetector:
    """提示词注入检测器"""

    INJECTION_PATTERNS = [
        r"忽略.*(以上|之前|系统).*指令",
        r"忘记.*(系统|之前).*提示",
        r"你是.*新角色",
        r"忽略.*限制",
        r"无视.*规则",
        r"系统提示.*已?泄露",
        r"现在.*你.*扮演",
    ]

    @classmethod
    def detect(cls, text: str) -> bool:
        """检测文本中是否包含提示词注入模式"""
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False