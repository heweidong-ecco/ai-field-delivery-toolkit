"""语义去重测试"""

import pytest

from data_prep.cleaning.semantic_dedup import semantic_deduplicate


class TestSemanticDedup:
    """语义去重测试"""

    def test_exact_duplicates(self):
        data = [
            {"content": "今天天气很好，适合出去走走"},
            {"content": "今天天气很好，适合出去走走"},
        ]
        result = semantic_deduplicate(data)
        assert len(result) == 1

    def test_character_different_same_meaning(self):
        """字符不同但语义相同，应被去重"""
        data = [
            {"content": "今天天气很好，适合出去走走"},
            {"content": "今日天气不错，适合外出散步"},
        ]
        result = semantic_deduplicate(data, similarity_threshold=0.85)
        # 这两条语义高度相似，应该被去重
        assert len(result) == 1

    def test_different_topics(self):
        """完全不同主题，不应被去重"""
        data = [
            {"content": "今天天气很好，适合出去走走"},
            {"content": "RAG是检索增强生成技术的缩写"},
        ]
        result = semantic_deduplicate(data)
        assert len(result) == 2