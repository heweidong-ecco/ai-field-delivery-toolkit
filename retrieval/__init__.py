"""RAG 检索模块：知识库分块 → 向量化(ChromaDB) → 检索 → 问答(带引用)。

v5.0：打通「数据作战流知识库产物 → 索引 → 检索 → 带引用问答」闭环。
"""

from retrieval.service import (
    get_archive,
    index_knowledge,
    list_indexed,
    rag_answer,
    retrieve,
)

__all__ = [
    "get_archive",
    "index_knowledge",
    "list_indexed",
    "rag_answer",
    "retrieve",
]
