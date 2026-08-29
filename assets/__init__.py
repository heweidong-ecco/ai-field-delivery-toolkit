"""可复用资产注册表：项目越多、工具越强。

v6.0 资产复用闭环：dataprep 沉淀 / mapping 导出 / 诊断定稿的产物统一注册进资产库，
新任务启动时按规则评分自动带出相关资产（suggest），一键接入历史资产（adopt）。
"""

from assets.archive import get_asset, list_assets, register_asset, search_assets
from assets.service import adopt_asset, register_from_dataprep, register_from_diagnosis, register_from_mapping, suggest

__all__ = [
    "adopt_asset",
    "get_asset",
    "list_assets",
    "register_asset",
    "register_from_dataprep",
    "register_from_diagnosis",
    "register_from_mapping",
    "search_assets",
    "suggest",
]
