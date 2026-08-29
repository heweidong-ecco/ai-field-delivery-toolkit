"""需求诊断器测试"""

from diagnosis.checklist import AIFeasibilityChecklist
from diagnosis.report import DiagnosisReportGenerator


class TestChecklist:
    """AI 适用性评估测试"""

    def test_high_score(self):
        checklist = AIFeasibilityChecklist()
        result = checklist.quick_evaluate(5, 5, 5, 5, 5)
        assert result["total_score"] == 25
        assert "强烈推荐" in result["conclusion"]

    def test_low_score(self):
        checklist = AIFeasibilityChecklist()
        result = checklist.quick_evaluate(1, 1, 1, 1, 1)
        assert result["total_score"] == 5
        assert "不推荐" in result["conclusion"]

    def test_missing_dimension(self):
        import pytest
        checklist = AIFeasibilityChecklist()
        with pytest.raises(ValueError):
            checklist.evaluate({"generation": 4})


class TestReport:
    """诊断报告测试"""

    def test_generate_report(self):
        checklist = AIFeasibilityChecklist()
        result = checklist.quick_evaluate(4, 3, 4, 5, 2)
        gen = DiagnosisReportGenerator()
        report = gen.generate(
            customer_name="测试客户",
            requirement_summary="测试需求",
            feasibility_result=result,
        )
        assert report["customer_name"] == "测试客户"
        assert len(report["next_steps"]) > 0