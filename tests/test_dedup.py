"""去重策略测试"""

from data_prep.cleaning.dedup import deduplicate


class TestDedup:
    """去重测试"""

    def test_exact_dedup(self):
        data = [
            {"content": "完全相同的内容"},
            {"content": "完全相同的内容"},
            {"content": "不同的内容"},
        ]
        result = deduplicate(data)
        assert len(result) == 2

    def test_similar_dedup(self):
        """相似度阈值去重"""
        data = [
            {"content": "今天天气很好，适合出去走走"},
            {"content": "今天天气很好 适合出去走走"},  # 仅空格差异
            {"content": "今天天气很好适合出去走走"},     # 无空格
            {"content": "完全不同的主题"},
        ]
        # 阈值 0.9，归一化后三条相似度极高，应去重为 2 条
        result = deduplicate(data, similarity_threshold=0.9)
        assert len(result) == 2

    def test_no_similar_dedup_without_threshold(self):
        """不启用相似度去重时，仅完全一致去重"""
        data = [
            {"content": "今天天气很好，适合出去走走"},
            {"content": "今天天气很好 适合出去走走"},
            {"content": "今天天气很好适合出去走走"},
        ]
        result = deduplicate(data)
        assert len(result) == 3  # 仅完全一致才去重