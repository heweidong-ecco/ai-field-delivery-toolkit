import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
数据飞轮器 MVP 使用示例

运行方式：
    python examples/data_flywheel_example.py
"""

from data_flywheel.pipeline import DataFlywheelPipeline
from core.logging.logger import get_logger

logger = get_logger()


if __name__ == "__main__":
    logger.info("=== 数据飞轮器示例 ===")

    pipeline = DataFlywheelPipeline(storage_path="annotation_pool.json")

    # 1. 记录反馈
    pipeline.record_feedback(
        request_id="req-001",
        user_input="什么是RAG？",
        model_output="RAG是检索增强生成。",
        feedback_type="dislike",
        note="回答过于简单，缺少细节",
    )
    pipeline.record_feedback(
        request_id="req-002",
        user_input="如何部署？",
        model_output="使用Docker。",
        feedback_type="audit_fail",
        note="人工审核不通过：缺少具体步骤",
    )

    # 保存标注池
    pipeline.feedback_collector.save("annotation_pool.json")
    logger.info(f"标注池共 {len(pipeline.feedback_collector.get_pool())} 条")

    # 2. 更新评测集（需要已存在评测集文件 eval_set.json）
    # 实际使用中 eval_set.json 来自数据准备器
    # 这里模拟：先创建一个简单的评测集文件
    import json
    with open("eval_set.json", "w", encoding="utf-8") as f:
        json.dump([], f)

    update_result = pipeline.update_eval_set(
        eval_set_path="eval_set.json",
        num_samples=2,
        output_path="eval_set_updated.json",
    )
    logger.info(f"评测集更新：新增 {update_result['added_count']} 条，总数 {update_result['total_count']} 条")

    # 3. 导出项目资产
    assets = [
        {"type": "component", "name": "PII脱敏组件", "path": "core/security/pii.py", "description": "通用PII检测与脱敏"},
        {"type": "template", "name": "知识问答Agent模板", "path": "prototype_assembler/templates/qa_agent.py", "description": "RAG问答场景模板"},
    ]
    asset_result = pipeline.export_assets(
        project_id="project-001",
        assets=assets,
        output_path="project_assets.json",
        project_summary="研发知识库问答项目",
    )
    logger.info(f"资产导出完成，共 {asset_result['total_assets']} 项")