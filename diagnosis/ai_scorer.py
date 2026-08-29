"""AI 中立视角可行性评估

把客户需求文本交给 LLM 打分（五个维度 + 理由 + 总结），通过 DegradationManager
统一降级：模型不可用时回退到规则关键词评估，保证离线可用。
默认提示词严格要求中立客观，且可在前端自定义。
"""

from typing import Callable, Dict, Any, Optional

from core.config.settings import get_settings
from core.logging.logger import get_logger

logger = get_logger()

# 默认提示词：严格要求中立客观；{requirement} 为需求占位符
DEFAULT_NEUTRAL_PROMPT = """你是 AI 项目可行性评估专家，必须保持完全中立、客观的立场。

硬性要求：
1. 严格中立：不迎合客户需求中的任何倾向性表述，不预设"适合/不适合 AI"的结论，基于事实客观评估。
2. 对任何客户一视同仁，不得因表述积极或消极而偏颇。
3. 只依据提供的需求文本评估，不臆造未提供的信息，不确定处如实说明。

评估维度（各 1-5 分）：
- generation 生成性：任务是否需要生成新内容（文本/代码/图像等）。越高分越需要 AI。
- reasoning 推理复杂度：是否需要多步推理/逻辑分析。越高分越需要 AI。
- uncertainty 不确定性容忍度：业务对不确定输出的容忍程度。越高分越适合 AI。
- data 数据可得性：是否有足够高质量数据用于训练或检索。越高分越适合 AI。
- real_time 实时性要求：对响应速度的要求，越低分越适合 AI（1=极高实时要求，5=无实时要求）。

对每个维度给出具体打分理由；最后给出总体结论与总结。

客户需求：
{requirement}

只输出 JSON（不要输出任何其他文字），格式：
{"dimension_scores": {"generation": 1-5, "reasoning": 1-5, "uncertainty": 1-5, "data": 1-5, "real_time": 1-5}, "reasons": {"generation": "理由", "reasoning": "理由", "uncertainty": "理由", "data": "理由", "real_time": "理由"}, "summary": "总体总结（150字内）"}
"""

_DIMENSIONS = ("generation", "reasoning", "uncertainty", "data", "real_time")


def build_prompt(requirement: str, prompt_template: Optional[str] = None) -> str:
    """组装提示词：用需求替换 {requirement} 占位符（不校验自定义模板格式，容忍用户编辑）"""
    template = (prompt_template or DEFAULT_NEUTRAL_PROMPT)
    return template.replace("{requirement}", requirement)


def _default_llm_call(prompt: str) -> str:
    """默认 LLM 调用：DeepSeek（OpenAI 兼容接口）。未配置 key 或调用失败时抛异常走降级。"""
    from openai import OpenAI

    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")
    client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    resp = client.chat.completions.create(
        model=settings.default_model,
        messages=[
            {"role": "system", "content": "你只输出 JSON，不要输出任何其他内容。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    content = resp.choices[0].message.content or ""
    if not content.strip():
        raise RuntimeError("LLM 返回为空")
    return content


def _parse_llm_result(text: str) -> Dict[str, Any]:
    """解析 LLM 返回的 JSON（容忍 ```json 代码块包裹或前后缀文字）"""
    import json
    import re

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("LLM 输出中未找到 JSON")
    data = json.loads(m.group(0))
    raw_scores = data["dimension_scores"]
    scores = {}
    for k in _DIMENSIONS:
        v = int(raw_scores[k])
        if not 1 <= v <= 5:
            raise ValueError(f"维度 {k} 得分越界: {v}")
        scores[k] = v
    return {
        "dimension_scores": scores,
        "reasons": data.get("reasons", {}),
        "summary": data.get("summary", ""),
    }


# ---------- 规则兜底（模型不可用时） ----------

_RULE_UP = {
    "generation": (["生成", "创作", "撰写", "代码", "摘要", "总结", "文案", "报告", "内容"], "需求涉及内容生成类任务"),
    "reasoning": (["推理", "分析", "多步", "规划", "决策", "诊断", "复杂", "根因"], "需求涉及多步推理/分析"),
    "uncertainty": (["开放", "主观", "创意", "探索", "发散"], "需求容忍开放性/主观输出"),
    "data": (["知识库", "文档", "数据", "语料", "标注", "历史记录"], "存在可用的数据/文档基础"),
}
_RULE_DOWN = {
    "uncertainty": (["精确", "准确率", "标准", "合规", "零误差"], "需求强调精确/合规，容错低"),
    "real_time": (["实时", "毫秒", "秒级", "响应", "并发"], "需求有实时响应要求"),
}


def _rule_based_parsed(requirement: str) -> Dict[str, Any]:
    """关键词规则打分（兜底），产出与 LLM 解析一致的结构"""
    text = requirement
    scores, reasons = {}, {}
    for k in _DIMENSIONS:
        score = 3
        up_kw, up_reason = _RULE_UP.get(k, ([], ""))
        down_kw, down_reason = _RULE_DOWN.get(k, ([], ""))
        hit_up = [w for w in up_kw if w in text]
        hit_down = [w for w in down_kw if w in text]
        if hit_up:
            score += 1
        if hit_down:
            score -= 1
        scores[k] = max(1, min(5, score))
        parts = []
        if hit_up:
            parts.append("命中「" + "、".join(hit_up[:3]) + "」" + up_reason)
        if hit_down:
            parts.append("命中「" + "、".join(hit_down[:3]) + "」" + down_reason)
        reasons[k] = ("规则兜底：" + "；".join(parts)) if parts else "规则兜底：无明显信号，取基准分 3"
    summary = "未接入或模型调用失败，已用规则关键词评估兜底。建议配置 DEEPSEEK_API_KEY 后重新评估，以获得 AI 中立打分。"
    return {"dimension_scores": scores, "reasons": reasons, "summary": summary}


def ai_evaluate(
    requirement: str,
    prompt_template: Optional[str] = None,
    llm_call: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    """AI 中立视角评估入口

    参数:
        requirement: 客户需求描述
        prompt_template: 自定义提示词（含 {requirement} 占位符），None 用默认中立提示词
        llm_call: 可注入的 LLM 调用函数（测试/定制用），None 走默认 DeepSeek

    返回:
        与 AIFeasibilityChecklist.evaluate 兼容的字典，额外含 reasons / summary / llm_mode / prompt_used
    """
    requirement = requirement.strip()
    if not requirement:
        raise ValueError("客户需求描述不能为空")
    prompt = build_prompt(requirement, prompt_template)

    from core.degradation.manager import DegradationManager

    dm = DegradationManager()
    parsed = dm.execute(
        model_call=lambda: {**(_parse_llm_result((llm_call or _default_llm_call)(prompt))), "_llm": True},
        rule_fallback=lambda: {**_rule_based_parsed(requirement), "_llm": False},
    )
    if parsed is None:
        parsed = {**_rule_based_parsed(requirement), "_llm": False}
    llm_mode = "llm" if parsed.pop("_llm", False) else "rule-fallback"
    if llm_mode == "rule-fallback":
        logger.warning("AI 评估降级为规则兜底")

    from diagnosis.checklist import AIFeasibilityChecklist

    base = AIFeasibilityChecklist().evaluate(parsed["dimension_scores"])
    base["reasons"] = parsed["reasons"]
    base["summary"] = parsed["summary"]
    base["llm_mode"] = llm_mode
    base["requirement"] = requirement
    base["prompt_used"] = prompt
    return base
