"""异常检测与过滤"""

from typing import List, Dict, Any


def filter_anomalies(data: List[Dict[str, Any]], min_length: int = 10, max_length: int = 5000) -> List[Dict[str, Any]]:
    """过滤过短或过长、异常字符过多的记录"""
    result = []
    for item in data:
        content = item.get("content", "")
        length = len(content)
        if length < min_length or length > max_length:
            continue
        # 过滤不可打印/控制字符过多（可能乱码）
        # 注意：不能按"非 ASCII 比例"判断——中文内容本身几乎全为非 ASCII
        unprintable = sum(1 for c in content if ord(c) < 32 and c not in "\n\t")
        if unprintable > length * 0.3:
            continue
        result.append(item)
    return result