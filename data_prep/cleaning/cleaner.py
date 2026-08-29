"""清洗流水线（v1.2.0：增加语义去重选项）"""

from typing import List, Dict, Any, Tuple, Optional

from core.logging.logger import get_logger

from data_prep.cleaning.dedup import deduplicate
from data_prep.cleaning.semantic_dedup import semantic_deduplicate
from data_prep.cleaning.normalization import normalize
from data_prep.cleaning.anomaly import filter_anomalies
from data_prep.cleaning.pii_mask import mask_pii

logger = get_logger()


class DataCleaner:
    """数据清洗器（v1.2.0）"""

    def clean(
        self,
        data: List[Dict[str, Any]],
        dedup_similarity: Optional[float] = None,
        semantic_dedup: bool = False,
        semantic_threshold: float = 0.85,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """执行全流程清洗

        参数:
            data: 原始数据
            dedup_similarity: 字符级相似度去重阈值（None 为完全一致去重）
            semantic_dedup: 是否启用语义去重
            semantic_threshold: 语义去重相似度阈值
        """
        stats = {
            "原始条数": len(data),
            "字符去重后条数": 0,
            "语义去重后条数": 0,
            "去重删除": 0,
            "归一化后条数": 0,
            "异常过滤后条数": 0,
            "异常删除": 0,
            "脱敏后条数": 0,
        }

        # 1. 字符级去重
        data = deduplicate(data, similarity_threshold=dedup_similarity)
        stats["字符去重后条数"] = len(data)

        # 2. 语义去重（可选）
        if semantic_dedup:
            data = semantic_deduplicate(data, similarity_threshold=semantic_threshold)
            stats["语义去重后条数"] = len(data)
        else:
            stats["语义去重后条数"] = len(data)

        stats["去重删除"] = stats["原始条数"] - stats["语义去重后条数"]

        # 3. 归一化
        data = normalize(data)
        stats["归一化后条数"] = len(data)

        # 4. 异常过滤
        before = len(data)
        data = filter_anomalies(data)
        stats["异常过滤后条数"] = len(data)
        stats["异常删除"] = before - len(data)

        # 5. PII 脱敏
        data = mask_pii(data)
        stats["脱敏后条数"] = len(data)

        logger.info(f"清洗完成：{stats}")
        return data, stats