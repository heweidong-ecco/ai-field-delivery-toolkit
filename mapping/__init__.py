"""字段映射工作台：源字段→目标字段映射表格 + LLM 初判 + 导入真实样例实跑校验 + 人工修正迭代 + 导出适配器 + 断点档案。

v4.0 集成工作台：import_samples / validate_mapping / validate_row / list_mapping_runs。
"""

from mapping.service import (
    create_mapping,
    export_mapping,
    get_mapping,
    import_samples,
    list_mapping_runs,
    update_mapping,
    validate_mapping,
    validate_row,
)

__all__ = [
    "create_mapping",
    "export_mapping",
    "get_mapping",
    "import_samples",
    "list_mapping_runs",
    "update_mapping",
    "validate_mapping",
    "validate_row",
]
