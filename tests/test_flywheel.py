"""数据飞轮器测试"""

from data_flywheel.feedback import FeedbackCollector
from data_flywheel.eval_update import EvalSetUpdater
from data_flywheel.asset_export import AssetExporter


class TestFeedbackCollector:
    """反馈收集测试"""

    def test_add_feedback(self):
        collector = FeedbackCollector()
        collector.add_feedback(
            request_id="req-001",
            user_input="问题",
            model_output="回答",
            feedback_type="dislike",
        )
        assert len(collector.get_pool()) == 1

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "pool.json")
        collector = FeedbackCollector()
        collector.add_feedback(request_id="r1", user_input="q", model_output="a")
        collector.save(path)
        collector2 = FeedbackCollector(storage_path=path)
        assert len(collector2.get_pool()) == 1


class TestEvalSetUpdater:
    """评测集更新测试"""

    def test_update(self, tmp_path):
        # 创建空评测集
        import json
        eval_path = str(tmp_path / "eval.json")
        with open(eval_path, "w", encoding="utf-8") as f:
            json.dump([], f)

        pool = [
            {"user_input": "q1", "model_output": "a1", "feedback_type": "dislike"},
            {"user_input": "q2", "model_output": "a2", "feedback_type": "audit_fail"},
        ]
        updater = EvalSetUpdater()
        result = updater.update(pool, eval_path, num_samples=2)
        assert result["added_count"] == 2


class TestAssetExporter:
    """资产导出测试"""

    def test_export(self, tmp_path):
        exporter = AssetExporter()
        path = str(tmp_path / "assets.json")
        result = exporter.export(
            project_id="p1",
            assets=[{"name": "组件1", "type": "component", "path": "/tmp/x"}],
            output_path=path,
        )
        assert result["total_assets"] == 1
        import os
        assert os.path.exists(path)