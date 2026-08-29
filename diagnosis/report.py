"""诊断报告生成器"""

from datetime import datetime
from typing import Dict, Any, Optional

from core.logging.logger import get_logger

logger = get_logger()


class DiagnosisReportGenerator:
    """诊断报告生成器：根据评估结果和访谈记录生成诊断报告"""

    def generate(
        self,
        customer_name: str,
        requirement_summary: str,
        feasibility_result: Dict[str, Any],
        interview_notes: Optional[str] = None,
        decision_maker: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成诊断报告

        参数:
            customer_name: 客户名称
            requirement_summary: 需求摘要
            feasibility_result: AI 适用性评估结果（来自 AIFeasibilityChecklist.evaluate）
            interview_notes: 访谈记录（可选）
            decision_maker: 验收人（可选）

        返回:
            诊断报告字典，可直接保存为 JSON 或渲染为 Markdown
        """
        report = {
            "report_version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "customer_name": customer_name,
            "requirement_summary": requirement_summary,
            "feasibility": feasibility_result,
            "interview_notes": interview_notes or "",
            "decision_maker": decision_maker or "未确认",
            "next_steps": self._generate_next_steps(feasibility_result),
        }
        logger.info(f"诊断报告已生成: {customer_name}")
        return report

    def _generate_next_steps(self, feasibility_result: Dict[str, Any]) -> list:
        """根据评估结果生成下一步建议"""
        total = feasibility_result.get("total_score", 0)
        steps = []
        if total >= 20:
            steps = [
                "进入数据准备阶段",
                "确认数据来源和数据量",
                "确定评测集构建方案",
            ]
        elif total >= 15:
            steps = [
                "先构建小型原型验证核心假设",
                "准备小规模真实数据用于测试",
            ]
        elif total >= 10:
            steps = [
                "先用传统规则/检索方案验证",
                "收集用户反馈后再评估是否引入 AI",
            ]
        else:
            steps = [
                "重新评估需求",
                "考虑传统解决方案",
            ]
        if feasibility_result.get("decision_maker") != "已确认":
            steps.append("⚠️ 确认最终验收人")
        return steps

    def generate_with_review(
        self,
        customer_name: str,
        requirement_summary: str,
        ai_feasibility: Dict[str, Any],
        manual_scores: Dict[str, int],
        manual_reasons: Optional[Dict[str, str]] = None,
        manual_summary: Optional[str] = None,
        interview_notes: Optional[str] = None,
        decision_maker: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成含人工复核的诊断报告

        ai_feasibility: AI 中立评估结果（含 dimension_scores / reasons / summary / llm_mode）
        manual_scores: 人工复核后的五维打分
        manual_reasons: 人工复核各维度理由
        manual_summary: 人工复核总结/意见

        报告包含：AI 诊断、人工复核、打分对比、最终结论（以人工打分为准）、建议。
        """
        from diagnosis.checklist import AIFeasibilityChecklist

        manual_reasons = manual_reasons or {}
        manual_summary = manual_summary or ""
        # 人工打分校验与钳位
        manual_scores = {k: max(1, min(5, int(v))) for k, v in manual_scores.items()}

        ai = AIFeasibilityChecklist().evaluate(ai_feasibility.get("dimension_scores", {}))
        manual = AIFeasibilityChecklist().evaluate(manual_scores)

        # 各维度 AI vs 人工 对比
        comparison = []
        for key, name, _ in AIFeasibilityChecklist.DIMENSIONS:
            ai_v = ai_feasibility.get("dimension_scores", {}).get(key)
            m_v = manual_scores.get(key)
            comparison.append({
                "dimension": key,
                "name": name,
                "ai_score": ai_v,
                "manual_score": m_v,
                "delta": (m_v - ai_v) if (ai_v is not None and m_v is not None) else None,
            })

        recommendations = self._generate_next_steps({"total_score": manual["total_score"]})
        if ai["conclusion"] != manual["conclusion"]:
            recommendations.insert(
                0, f"AI 初步结论为「{ai['conclusion']}」，人工复核后调整为「{manual['conclusion']}」，请以最终结论为准。"
            )
        for c in comparison:
            if c["delta"] is not None and abs(c["delta"]) >= 2:
                recommendations.append(
                    f"维度「{c['name']}」AI 与人工差异较大（AI {c['ai_score']} 分 vs 人工 {c['manual_score']} 分），建议复核依据。"
                )
        if manual_scores.get("uncertainty", 3) <= 2 and ai_feasibility.get("llm_mode") == "llm":
            recommendations.append("人工对不确定性容忍度打分偏低：若业务容错要求高，建议补充人工审核机制或降低对 AI 完全自动化的依赖。")

        report = {
            "report_version": "2.0",
            "generated_at": datetime.now().isoformat(),
            "customer_name": customer_name,
            "requirement_summary": requirement_summary,
            "interview_notes": interview_notes or "",
            "decision_maker": decision_maker or "未确认",
            "ai_diagnosis": {
                "total_score": ai_feasibility.get("total_score", ai["total_score"]),
                "conclusion": ai_feasibility.get("conclusion", ai["conclusion"]),
                "suggestion": ai_feasibility.get("suggestion", ""),
                "llm_mode": ai_feasibility.get("llm_mode", ""),
                "dimension_scores": ai_feasibility.get("dimension_scores", {}),
                "reasons": ai_feasibility.get("reasons", {}),
                "summary": ai_feasibility.get("summary", ""),
            },
            "manual_review": {
                "total_score": manual["total_score"],
                "conclusion": manual["conclusion"],
                "suggestion": manual["suggestion"],
                "dimension_scores": manual_scores,
                "reasons": manual_reasons,
                "summary": manual_summary,
            },
            "score_comparison": comparison,
            "final_conclusion": {
                "total_score": manual["total_score"],
                "conclusion": manual["conclusion"],
                "suggestion": manual["suggestion"],
            },
            "recommendations": recommendations,
        }
        logger.info(f"诊断报告（含人工复核）已生成: {customer_name}")
        return report

    def save_report(self, report: Dict[str, Any], output_path: str):
        """保存诊断报告为 JSON 文件"""
        import json
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"诊断报告已保存: {output_path}")
        return output_path