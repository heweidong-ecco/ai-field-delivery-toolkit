"""多步推理 Agent 模板（接 core/llm.py，真实调用 DeepSeek；Plan-Execute 逐步求解；v8.0 从占位做实）"""

import re

from prototype_assembler.harness.agent import Agent
from prototype_assembler.loops.plan_execute import PlanExecuteLoop
from prototype_assembler.memory.short_term import ShortTermMemory
from prototype_assembler.memory.long_term import LongTermMemory
from prototype_assembler.tools.registry import ToolRegistry
from prototype_assembler.tools.builtin import register_builtin_tools
from prototype_assembler.context.builder import ContextBuilder

from core.llm import LLMError
from core.logging.logger import get_logger

logger = get_logger()


def _parse_plan(text: str) -> list:
    """把 LLM 返回的编号步骤解析为字符串列表（容忍 `1.`/`1、`/`1)` 等编号前缀）"""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\s*\d+[.、)）:：]?\s*(.*)$", line)
        if m and m.group(1).strip():
            lines.append(m.group(1).strip())
        else:
            lines.append(line)
    return lines or [text.strip()]


def _reasoning_plan_generator(agent, user_input: str) -> list:
    """真实 LLM 生成执行计划（返回步骤字符串列表）。

    失败（LLMError）时诚实降级为「单步直答」：退化为一步直接回答整个问题，
    由 step_executor 用真实 LLM 作答；若后续步骤也失败，最终答案会如实暴露。
    """
    from core.llm import chat

    system = (
        "你是一个推理规划助手。请把用户的复杂问题拆解为 3-6 个可执行的分析步骤。\n"
        "规则：\n"
        "1. 每行一个步骤，形如 `1. 步骤内容`；\n"
        "2. 步骤要具体、可执行、按推理先后顺序；\n"
        "3. 只输出步骤列表，不要额外解释。"
    )
    try:
        plan_text = chat(system=system, user=f"问题：{user_input}", temperature=0.2)
    except LLMError as e:
        logger.warning(f"计划生成 LLM 调用失败，退化为单步直答: {e}")
        return [f"直接回答以下问题：{user_input}"]
    except Exception as e:  # 防御性兜底
        logger.warning(f"计划生成 LLM 调用异常: {e}")
        return [f"直接回答以下问题：{user_input}"]
    return _parse_plan(plan_text)


def _reasoning_step_executor(agent, context: str, step: str) -> str:
    """真实 LLM 执行单个推理步骤。

    失败（LLMError）时诚实降级：返回明确的失败说明，供汇总阶段如实呈现。
    """
    from core.llm import chat

    system = (
        "你是一个多步推理执行器。当前正在执行复杂问题的一个推理步骤，请只完成这一步并输出结果。\n"
        "规则：\n"
        "1. 只针对当前步骤作答，不要规划后续步骤；\n"
        "2. 结果简洁、聚焦，作为后续步骤的输入；\n"
        "3. 如遇信息不足，写明“信息不足：<缺什么>”。"
    )
    try:
        return chat(system=system, user=f"{context}\n\n当前步骤：{step}", temperature=0.2)
    except LLMError as e:
        logger.warning(f"步骤执行 LLM 调用失败，诚实降级: {e}")
        return f"[步骤执行失败：LLM 调用失败（{e}）]"
    except Exception as e:
        logger.warning(f"步骤执行 LLM 调用异常: {e}")
        return f"[步骤执行失败：调用异常（{e}）]"


def _reasoning_answer_generator(agent, memory) -> str:
    """真实 LLM 汇总各步骤中间结果生成最终答案。

    失败（LLMError）时诚实降级：如实说明未能得出最终答案，不装成功。
    """
    from core.llm import chat

    steps = [m["content"] for m in memory.get_all() if m["role"] == "assistant"]
    step_text = "\n".join(f"- {s}" for s in steps) if steps else "（无步骤结果）"
    system = (
        "你是一个多步推理汇总器。请基于各步骤的中间结果，给出问题的最终答案。\n"
        "规则：\n"
        "1. 综合所有步骤结果，形成连贯、准确的最终回答；\n"
        "2. 明确指出结论及其依据；\n"
        "3. 若中间结果不完整，如实说明，不要编造。"
    )
    try:
        return chat(system=system, user=f"各步骤中间结果：\n{step_text}", temperature=0.2)
    except LLMError as e:
        logger.warning(f"答案汇总 LLM 调用失败，诚实降级: {e}")
        return f"推理未能得出最终答案（LLM 调用失败：{e}）。"
    except Exception as e:
        logger.warning(f"答案汇总 LLM 调用异常: {e}")
        return f"推理未能得出最终答案（调用异常：{e}）。"


def create_reasoning_agent() -> Agent:
    """创建多步推理 Agent（真调 DeepSeek，Plan-Execute 逐步求解）"""
    loop = PlanExecuteLoop()
    memory_short = ShortTermMemory(max_rounds=15)
    memory_long = LongTermMemory()
    tools = ToolRegistry()
    register_builtin_tools(tools)
    context_builder = ContextBuilder(
        system_prompt="你是一个推理助手，请将复杂问题拆解为步骤并逐步解决。",
    )
    return Agent(
        loop=loop,
        tools=tools.list_all(),
        memory_short=memory_short,
        memory_long=memory_long,
        context_builder=context_builder,
        plan_generator=_reasoning_plan_generator,
        step_executor=_reasoning_step_executor,
        answer_generator=_reasoning_answer_generator,
    )
