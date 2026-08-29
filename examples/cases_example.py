import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
案例/交付物层示例

运行方式：
    python examples/cases_example.py

流程：诊断定稿 → 打包成可打印交付物（HTML + PDF）→ 结构化案例存档
说明：需要已配置 DEEPSEEK_API_KEY（诊断会调真实模型）；若已有定稿的诊断会用最近一次。
"""

from core.logging.logger import get_logger

logger = get_logger()


def _find_or_run_diagnosis():
    """优先用已有定稿诊断，否则跑一次诊断"""
    from diagnosis.orchestrator import finalize, get_archive, list_runs, review_human, start_diagnosis

    for run_id in list_runs(5):
        try:
            archive = get_archive(run_id)
        except Exception:
            continue
        if archive.get("confirmed") and archive.get("report"):
            logger.info(f"复用已定稿诊断 run_id={run_id}")
            return run_id

    logger.info("无已定稿诊断，现场跑一次…")
    s = start_diagnosis("制造企业需要基于设备传感器数据的故障预测系统，数据实时、准确率高")
    review_human(s["run_id"], s["generator"]["dimension_scores"], human_reasons={})
    finalize(s["run_id"], customer_name="示例客户", requirement_summary="设备故障预测", confirmed=True)
    return s["run_id"]


if __name__ == "__main__":
    logger.info("=== 案例/交付物层示例 ===")
    run_id = _find_or_run_diagnosis()

    from cases.service import create_diagnosis_case
    meta = create_diagnosis_case(run_id)
    logger.info(f"案例已生成: {meta['case_id']}")
    logger.info(f"标题: {meta['title']} | 结论: {meta['conclusion']}")
    logger.info(f"HTML: /api/v1/cases/{meta['case_id']}/render.html")
    if meta.get("has_pdf"):
        logger.info(f"PDF:  /api/v1/cases/{meta['case_id']}/export.pdf")
    else:
        logger.warning("PDF 不可用（本机无 Chrome），HTML 可直接打印成 PDF")

    # 检索
    from cases.archive import search_cases
    hits = search_cases(query="故障预测", limit=5)
    logger.info(f"案例检索「故障预测」命中 {len(hits)} 条")
