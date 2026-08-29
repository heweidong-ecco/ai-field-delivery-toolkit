import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
需求诊断器使用示例

运行方式：
    python examples/diagnosis_example.py
"""

from diagnosis.checklist import AIFeasibilityChecklist
from diagnosis.report import DiagnosisReportGenerator
from core.logging.logger import get_logger

logger = get_logger()


if __name__ == "__main__":
    logger.info("=== 需求诊断器示例 ===")

    # 五维评估
    checklist = AIFeasibilityChecklist()
    result = checklist.quick_evaluate(
        generation=4,
        reasoning=3,
        uncertainty=4,
        data=5,
        real_time=2,
    )
    logger.info(f"评估总分: {result['total_score']}")
    logger.info(f"评估结论: {result['conclusion']}")

    # 生成诊断报告
    report_gen = DiagnosisReportGenerator()
    report = report_gen.generate(
        customer_name="研发团队",
        requirement_summary="基于内部文档的智能问答",
        feasibility_result=result,
        interview_notes="访谈 5 人，确认主要痛点是文档查找慢",
        decision_maker="研发负责人",
    )
    logger.info(f"下一步建议: {report['next_steps']}")
    report_gen.save_report(report, "diagnosis_report.json")