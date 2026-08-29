"""裁剪方案输出数据结构"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class CropPlan:
    """裁剪方案"""
    customer_id: str
    enabled_modules: List[str]
    deleted_modules: List[str]
    simplifications: Dict[str, Any]
    automations: List[str]
    timeline_suggestion: Dict[str, Any]
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "plan_version": self.version,
            "enabled_modules": self.enabled_modules,
            "deleted_modules": self.deleted_modules,
            "simplifications": self.simplifications,
            "automations": self.automations,
            "timeline_suggestion": self.timeline_suggestion,
        }

    def save(self, path: str):
        """保存方案到 JSON 文件"""
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)