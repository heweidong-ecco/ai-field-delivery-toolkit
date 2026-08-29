"""数据去重（支持完全一致去重和相似度阈值去重）"""

from typing import List, Dict, Any, Optional
import re

from core.logging.logger import get_logger

logger = get_logger()


def _normalize(text: str) -> str:
    """基础归一化：去除所有空白和标点差异"""
    return re.sub(r"[\s\W]+", "", text.lower())


def _similarity(a: str, b: str) -> float:
    """计算两个字符串的相似度（基于归一化后的字符重叠率）"""
    if not a or not b:
        return 0.0
    set_a, set_b = set(a), set(b)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def deduplicate(
    data: List[Dict[str, Any]],
    similarity_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """去重

    参数:
        data: 输入数据列表
        similarity_threshold: 相似度阈值（0-1）
            - None：仅做完全一致去重
            - 0.9：归一化后字符重叠率 >= 0.9 视为重复
            - 0.8：更宽松，允许更多差异

    返回:
        去重后的数据
    """
    seen_exact = set()
    seen_similar: List[str] = []
    result = []

    for item in data:
        content = item.get("content", "")

        # 1. 完全一致去重（基于原始内容，仅完全相同才去重）
        if content in seen_exact:
            continue

        normalized = _normalize(content)

        # 2. 相似度去重（如启用，基于归一化文本）
        if similarity_threshold is not None:
            is_duplicate = False
            for existing in seen_similar:
                if _similarity(normalized, existing) >= similarity_threshold:
                    is_duplicate = True
                    break
            if is_duplicate:
                continue
            seen_similar.append(normalized)

        seen_exact.add(content)
        result.append(item)

    logger.info(
        f"去重完成：原始 {len(data)} 条，去重后 {len(result)} 条，"
        f"模式={'相似度阈值=' + str(similarity_threshold) if similarity_threshold else '完全一致'}"
    )
    return result