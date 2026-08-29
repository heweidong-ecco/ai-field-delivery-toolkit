import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
数据标注与评测集管理示例

运行方式：
    python examples/annotation_example.py

流程：创建标注任务 → 双人打标签 → 一致性 → 构建评测集
"""

from core.logging.logger import get_logger

logger = get_logger()


if __name__ == "__main__":
    logger.info("=== 数据标注与评测集管理示例 ===")

    from annotation.service import add_label, build_eval_set, create_annotation_task, get_task

    samples = [
        "订单超过3天未发货怎么办",
        "如何申请退款",
        "发票信息填写错误如何修改",
    ]
    a = create_annotation_task("客服工单分类", samples)
    run_id = a["run_id"]
    logger.info(f"标注任务已创建 run_id={run_id}，样本 {len(a['items'])} 条")

    # 双人标注（甲/乙），第一条两人一致，第二条分歧
    add_label(run_id, 1, "甲", "物流")
    add_label(run_id, 1, "乙", "物流")
    add_label(run_id, 2, "甲", "退款")
    add_label(run_id, 2, "乙", "物流")
    add_label(run_id, 3, "甲", "发票")

    stats = get_task(run_id)["stats"]
    logger.info(f"一致性统计: 一致 {stats['agreed']} / 分歧 {stats['disagreed']} / 未标 {stats['unlabeled']}")

    result = build_eval_set(run_id)
    logger.info(f"评测集构建: {result['agreed']} 条一致样本进入评测集，{result['disagreements']} 条分歧待复核")
