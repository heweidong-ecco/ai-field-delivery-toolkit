"""AI 适用性五维评估清单"""

from typing import Dict, Any, List

from core.logging.logger import get_logger

logger = get_logger()


class AIFeasibilityChecklist:
    """AI 适用性五维评估

    五个维度：
    1. 生成性：任务是否需要生成新内容
    2. 推理复杂度：是否需要多步推理
    3. 不确定性容忍度：对不确定输出的容忍程度
    4. 数据可得性：高质量数据是否可得
    5. 实时性要求：对响应速度的要求

    每个维度得分 1-5 分，总分 5-25 分。
    - 总分 >= 20：强烈推荐使用 AI
    - 总分 15-19：推荐使用 AI，但需谨慎
    - 总分 10-14：AI 适用性一般，建议先传统方案验证
    - 总分 < 10：不推荐使用 AI
    """

    DIMENSIONS = [
        ("generation", "生成性", "任务是否需要生成新内容（文本、代码、图像等）"),
        ("reasoning", "推理复杂度", "任务是否需要多步推理或逻辑分析"),
        ("uncertainty", "不确定性容忍度", "业务对不确定输出的容忍程度（越高分越适合 AI）"),
        ("data", "数据可得性", "是否有足够的高质量数据用于训练或检索"),
        ("real_time", "实时性要求", "对响应速度的要求（越低分越适合 AI）"),
    ]

    def evaluate(self, scores: Dict[str, int]) -> Dict[str, Any]:
        """执行评估

        参数:
            scores: 包含五个维度得分的字典，如 {"generation": 4, ...}

        返回:
            评估结果字典
        """
        # 验证维度完整性
        for dim_key, _, _ in self.DIMENSIONS:
            if dim_key not in scores:
                raise ValueError(f"缺少维度得分: {dim_key}")

        total = sum(scores.values())

        # 判断结论
        if total >= 20:
            conclusion = "强烈推荐使用 AI"
            suggestion = "可进入架构设计阶段"
        elif total >= 15:
            conclusion = "推荐使用 AI，但需谨慎"
            suggestion = "建议先构建小型原型验证"
        elif total >= 10:
            conclusion = "AI 适用性一般"
            suggestion = "建议先使用传统规则或检索方案验证，再考虑 AI"
        else:
            conclusion = "不推荐使用 AI"
            suggestion = "传统方案可能更合适，重新评估需求"

        result = {
            "total_score": total,
            "dimension_scores": scores,
            "conclusion": conclusion,
            "suggestion": suggestion,
            "details": {key: {"name": name, "description": desc} for key, name, desc in self.DIMENSIONS},
        }
        logger.info(f"AI 适用性评估完成，总分={total}，结论={conclusion}")
        return result

    def quick_evaluate(
        self,
        generation: int,
        reasoning: int,
        uncertainty: int,
        data: int,
        real_time: int,
    ) -> Dict[str, Any]:
        """快速评估：直接传入五个维度的得分"""
        scores = {
            "generation": generation,
            "reasoning": reasoning,
            "uncertainty": uncertainty,
            "data": data,
            "real_time": real_time,
        }
        return self.evaluate(scores)