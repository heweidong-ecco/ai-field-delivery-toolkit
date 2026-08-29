"""数据准备器测试"""

from data_prep.pipeline import DataPrepPipeline
from data_prep.cleaning.dedup import deduplicate
from data_prep.cleaning.normalization import normalize
from data_prep.cleaning.anomaly import filter_anomalies
from data_prep.cleaning.pii_mask import mask_pii


class TestCleaning:
    """清洗层测试"""

    def test_deduplicate(self, sample_data):
        result = deduplicate(sample_data)
        # 有两条完全重复的
        assert len(result) == len(sample_data) - 1

    def test_normalization(self):
        data = [{"content": "  hello   world  \n\n", "metadata": {}}]
        result = normalize(data)
        assert result[0]["content"] == "hello world"

    def test_filter_anomalies(self):
        data = [
            {"content": "短", "metadata": {}},
            {"content": "这是一条长度正常的测试数据内容，应该被保留下来", "metadata": {}},
        ]
        result = filter_anomalies(data, min_length=5)
        assert len(result) == 1

    def test_mask_pii(self):
        data = [{"content": "手机号13812345678", "metadata": {}}]
        result = mask_pii(data)
        assert "13812345678" not in result[0]["content"]


class TestPipeline:
    """完整管道测试"""

    def test_full_pipeline(self, tmp_path):
        # 创建临时 CSV 文件
        import csv
        csv_path = tmp_path / "test.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["content"])
            writer.writeheader()
            for i in range(20):
                writer.writerow({"content": f"这是第{i}条测试数据，用于验证完整数据准备管道"})

        pipeline = DataPrepPipeline()
        result = pipeline.run(
            source_type="csv",
            source_path=str(csv_path),
            output_dir=str(tmp_path / "output"),
            eval_samples=10,
        )
        assert result["raw_count"] == 20
        assert result["cleaned_count"] > 0
        assert result["eval_set_count"] == 10