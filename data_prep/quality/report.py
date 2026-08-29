"""质量报告数据结构"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class QualityReport:
    total: int
    unique: int
    duplicate_rate: float
    pii_types: Dict[str, int]
    coverage: Dict[str, float]

    @property
    def summary(self) -> str:
        return (
            f"总数={self.total}, 唯一={self.unique}, "
            f"重复率={self.duplicate_rate:.2%}, PII类型={list(self.pii_types.keys())}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "unique": self.unique,
            "duplicate_rate": self.duplicate_rate,
            "pii_types": self.pii_types,
            "coverage": self.coverage,
        }