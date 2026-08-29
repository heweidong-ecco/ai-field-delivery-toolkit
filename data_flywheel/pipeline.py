"""数据飞轮统一入口"""

from typing import Optional, List, Dict, Any

from core.logging.logger import get_logger

from data_flywheel.feedback import FeedbackCollector
from data_flywheel.eval_update import EvalSetUpdater
from data_flywheel.asset_export import AssetExporter

logger = get_logger()


class DataFlywheelPipeline:
    """数据飞轮管道：反馈收集 → 评测集更新 → 资产导出"""

    def __init__(self, storage_path: Optional[str] = None):
        self.feedback_collector = FeedbackCollector(storage_path=storage_path)
        self.eval_updater = EvalSetUpdater()
        self.asset_exporter = AssetExporter()

    def record_feedback(
        self,
        request_id: str,
        user_input: str,
        model_output: str,
        feedback_type: str = "dislike",
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """记录一条反馈"""
        return self.feedback_collector.add_feedback(
            request_id=request_id,
            user_input=user_input,
            model_output=model_output,
            feedback_type=feedback_type,
            note=note,
        )

    def update_eval_set(
        self,
        eval_set_path: str,
        num_samples: int = 20,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """从标注池更新评测集"""
        pool = self.feedback_collector.get_pool()
        return self.eval_updater.update(
            annotation_pool=pool,
            eval_set_path=eval_set_path,
            num_samples=num_samples,
            output_path=output_path,
        )

    def export_assets(
        self,
        project_id: str,
        assets: Optional[List[Dict[str, Any]]] = None,
        output_path: str = "assets.json",
        project_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """导出项目可复用资产"""
        if assets is None:
            assets = self.asset_exporter.generate_default_assets(project_id)
        return self.asset_exporter.export(
            project_id=project_id,
            assets=assets,
            output_path=output_path,
            project_summary=project_summary,
        )