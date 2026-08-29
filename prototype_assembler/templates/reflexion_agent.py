"""Reflexion Agent 模板（接 core/llm.py，真实调用 DeepSeek；先作答 → 评估 → 反思修正 → 重试；v8.0 从占位做实）"""

from prototype_assembler.harness.agent import Agent
from prototype_assembler.loops.reflexion import ReflexionLoop
from prototype_assembler.memory.short_term import ShortTermMemory
from prototype_assembler.memory.long_term import LongTermMemory
from prototype_assembler.tools.registry import ToolRegistry
from prototype_assembler.context.builder import ContextBuilder

from core.llm import LLMError
from core.logging.logger import get_logger

logger = get_logger()


def _default_evaluator(result: str):
    """默认评估器：检查结果是否包含有效内容"""
    if len(result) > 10:
        return True, ""
    return False, "结果太短，可能不完整"


def _reflexion_llm_call(agent, context: str, user_input: str) -> str:
    """真实 LLM 调用（core/llm.py），先作答再自评修正。

    反思历史（ReflexionLoop 写入 agent._reflection_history）存在时，把上一轮评估反馈
    拼进 system prompt，让模型针对反馈修正，体现「反思 → 修正」。
    失败（LLMError）时诚实降级：返回 finish:<错误说明>，绝不伪装成功。
    """
    from core.llm import chat

    reflection_history = getattr(agent, "_reflection_history", None) or []
    try:
        if reflection_history:
            feedback = "\n".join(reflection_history)
            system = (
                "你是一个带有自我反思能力的助手。你上一次的作答未通过质量评估，反馈如下：\n"
                f"{feedback}\n"
                "请针对反馈修正你的回答，确保这次给出完整、正确的最终答案。"
            )
        else:
            system = (
                "你是一个带有自我反思能力的助手。请先完整作答，再简要自检一遍，"
                "如有遗漏或错误，修正后给出最终答案。"
            )
        answer = chat(system=system, user=f"{context}\n\n任务：{user_input}", temperature=0.2)
    except LLMError as e:
        logger.warning(f"反思作答 LLM 调用失败，诚实降级: {e}")
        return f"finish: 反思作答未能完成（LLM 调用失败：{e}）。请检查 DEEPSEEK_API_KEY 配置后重试。"
    except Exception as e:  # 防御性兜底
        logger.warning(f"反思作答 LLM 调用异常: {e}")
        return f"finish: 反思作答未能完成（调用异常：{e}）。"
    return f"finish: {answer}"


def create_reflexion_agent() -> Agent:
    """创建 Reflexion Agent（真调 DeepSeek，先作答再反思修正）"""
    loop = ReflexionLoop(max_reflections=3, evaluator=_default_evaluator)
    memory_short = ShortTermMemory(max_rounds=10)
    memory_long = LongTermMemory()
    tools = ToolRegistry()
    context_builder = ContextBuilder(
        system_prompt="你是一个带有自我反思能力的助手，请确保输出质量。",
    )
    return Agent(
        loop=loop,
        tools=tools.list_all(),
        memory_short=memory_short,
        memory_long=memory_long,
        context_builder=context_builder,
        llm_call=_reflexion_llm_call,
    )
