"""语义去重：基于向量相似度检测语义重复"""

from typing import List, Dict, Any, Optional

from core.logging.logger import get_logger

logger = get_logger()


class SemanticDeduplicator:
    """语义去重器

    使用向量相似度判断两条记录是否语义重复。
    MVP 使用 ChromaDB 内置的默认嵌入模型。
    """

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self._embedding_function = None
        self._known_vectors: List[List[float]] = []
        self._known_texts: List[str] = []

    def _get_embedding_function(self):
        """获取嵌入函数（懒加载）"""
        if self._embedding_function is None:
            import chromadb
            from chromadb.utils import embedding_functions
            self._embedding_function = embedding_functions.DefaultEmbeddingFunction()
        return self._embedding_function

    def _embed_text(self, text: str) -> List[float]:
        """将文本转为向量"""
        func = self._get_embedding_function()
        return func([text])[0]

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """计算余弦相似度"""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def deduplicate(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对数据执行语义去重

        参数:
            data: 输入数据列表

        返回:
            去重后的数据列表
        """
        if not data:
            return []

        result: List[Dict[str, Any]] = []
        self._known_vectors = []
        self._known_texts = []

        logger.info(f"开始语义去重，共 {len(data)} 条，阈值 {self.similarity_threshold}")

        for item in data:
            content = item.get("content", "")
            if not content.strip():
                continue

            # 获取当前文本向量
            try:
                vector = self._embed_text(content)
            except Exception as e:
                logger.warning(f"嵌入失败，跳过该条: {e}")
                result.append(item)
                continue

            # 与已知向量比较
            is_duplicate = False
            for known_vector in self._known_vectors:
                sim = self._cosine_similarity(vector, known_vector)
                if sim >= self.similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                self._known_vectors.append(vector)
                self._known_texts.append(content)
                result.append(item)

        logger.info(f"语义去重完成：原始 {len(data)} 条，保留 {len(result)} 条")
        return result


def semantic_deduplicate(
    data: List[Dict[str, Any]],
    similarity_threshold: float = 0.85,
) -> List[Dict[str, Any]]:
    """语义去重快捷函数"""
    deduplicator = SemanticDeduplicator(similarity_threshold=similarity_threshold)
    return deduplicator.deduplicate(data)
