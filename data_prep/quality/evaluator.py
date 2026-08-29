"""数据质量评估器"""

from typing import List, Dict, Any
from collections import Counter

from core.security.pii import PIIDetector
from data_prep.quality.report import QualityReport


class DataQualityEvaluator:
    """评估数据质量"""

    def evaluate(self, data: List[Dict[str, Any]]) -> "QualityReport":
        total = len(data)
        if total == 0:
            return QualityReport(total=0, unique=0, duplicate_rate=1.0, pii_types=[], coverage={})

        # 去重统计
        contents = [d["content"] for d in data]
        unique_contents = set(contents)
        unique = len(unique_contents)
        duplicate_rate = (total - unique) / total if total > 0 else 0

        # PII 检测
        pii_found = []
        for d in data[: min(total, 1000)]:  # 抽样 1000 条
            found = PIIDetector.detect(d["content"])
            pii_found.extend(found)
        pii_counter = Counter(pii_found)

        # 覆盖性：基于 metadata 中的可能分类字段（如果有）
        coverage = {}
        # MVP：统计 metadata 中各个 key 的非空比例
        if data and data[0].get("metadata"):
            keys = data[0]["metadata"].keys()
            for key in keys:
                non_empty = sum(1 for d in data if d.get("metadata", {}).get(key))
                coverage[key] = round(non_empty / total, 2)

        return QualityReport(
            total=total,
            unique=unique,
            duplicate_rate=round(duplicate_rate, 4),
            pii_types=dict(pii_counter),
            coverage=coverage,
        )