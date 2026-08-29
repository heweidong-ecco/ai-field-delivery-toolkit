"""PII 脱敏"""

from typing import List, Dict, Any
from core.security.pii import PIIDetector


def mask_pii(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """对每条记录的 content 进行 PII 脱敏"""
    for item in data:
        item["content"] = PIIDetector.mask(item["content"])
        # 同时对 metadata 中的字符串字段脱敏
        if item.get("metadata"):
            for key, value in item["metadata"].items():
                if isinstance(value, str):
                    item["metadata"][key] = PIIDetector.mask(value)
    return data