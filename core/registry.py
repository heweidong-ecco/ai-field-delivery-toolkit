"""模块注册中心：管理所有功能模块的生命周期"""

from typing import Dict, List, Optional
from loguru import logger


class ModuleRegistry:
    """模块注册中心

    所有功能模块（诊断器、数据准备器、原型组装器等）在启动时向此注册，
    声明模块名称、依赖、配置项。底座根据注册信息统一管理模块。
    """

    def __init__(self):
        self._modules: Dict[str, dict] = {}

    def register(
        self,
        name: str,
        dependencies: Optional[List[str]] = None,
        config_keys: Optional[List[str]] = None,
    ):
        """注册模块

        参数:
            name: 模块名称，如 "data_prep"
            dependencies: 依赖的其他模块名称列表
            config_keys: 模块特有的配置键列表
        """
        if name in self._modules:
            logger.warning(f"模块 {name} 已注册，跳过重复注册")
            return

        self._modules[name] = {
            "name": name,
            "dependencies": dependencies or [],
            "config_keys": config_keys or [],
            "enabled": True,
        }
        logger.info(f"模块已注册: {name}")

    def unregister(self, name: str):
        """注销模块"""
        if name in self._modules:
            del self._modules[name]
            logger.info(f"模块已注销: {name}")

    def get_module(self, name: str) -> Optional[dict]:
        """获取模块信息"""
        return self._modules.get(name)

    def get_all_modules(self) -> List[dict]:
        """获取全部已注册模块"""
        return list(self._modules.values())

    def is_registered(self, name: str) -> bool:
        """检查模块是否已注册"""
        return name in self._modules


# 全局单例
_registry: Optional[ModuleRegistry] = None


def get_registry() -> ModuleRegistry:
    """获取全局模块注册中心单例"""
    global _registry
    if _registry is None:
        _registry = ModuleRegistry()
    return _registry