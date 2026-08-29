"""工具注册表"""

from typing import Dict, List, Optional

from core.logging.logger import get_logger

logger = get_logger()


class Tool:
    """工具定义"""

    def __init__(self, name: str, description: str, func, requires_permission: bool = False):
        self.name = name
        self.description = description
        self.func = func
        self.requires_permission = requires_permission

    def run(self, args: dict) -> str:
        """执行工具"""
        if self.requires_permission:
            # MVP：简单审计提示
            logger.warning(f"工具 {self.name} 需要权限，但 MVP 不强制拦截")
        return self.func(args)


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_all(self) -> List[Tool]:
        return list(self._tools.values())

    def list_names(self) -> List[str]:
        return list(self._tools.keys())