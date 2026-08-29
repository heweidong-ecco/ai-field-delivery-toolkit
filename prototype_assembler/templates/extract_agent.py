"""信息抽取 Agent 模板（接 core/llm.py，真实调用 DeepSeek，返回结构化抽取结果；v8.0 从占位做实）"""

from prototype_assembler.harness.agent import Agent
from prototype_assembler.loops.react import ReActLoop
from prototype_assembler.memory.short_term import ShortTermMemory
from prototype_assembler.memory.long_term import LongTermMemory
from prototype_assembler.tools.registry import ToolRegistry
from prototype_assembler.context.builder import ContextBuilder

from core.llm import LLMError
from core.logging.logger import get_logger

logger = get_logger()


def _extract_llm_call(agent, context: str, user_input: str) -> str:
    """真实 LLM 调用（core/llm.py），返回 finish:<结构化抽取结果> 供 ReAct 解析。

    角色：信息抽取助手，从输入文本中抽取关键实体和属性。
    真实 LLM 失败（LLMError）时诚实降级：返回 finish:<错误说明>，绝不伪装成抽取成功。
    """
    from core.llm import chat

    system = (
        "你是一个信息抽取助手，从输入文本中抽取关键实体和属性。\n"
        "规则：\n"
        "1. 输出为结构化形式，每行一条实体：`实体名 | 类型 | 属性键=属性值`（属性可为空）；\n"
        "2. 只抽取文本中明确出现的信息，不编造、不猜测；\n"
        "3. 若文本无有效实体，如实回答“未抽取到有效实体”。"
    )
    try:
        answer = chat(system=system, user=f"{context}\n\n待抽取文本：{user_input}", temperature=0.2)
    except LLMError as e:
        logger.warning(f"信息抽取 LLM 调用失败，诚实降级: {e}")
        return f"finish: 信息抽取未能完成（LLM 调用失败：{e}）。请检查 DEEPSEEK_API_KEY 配置后重试。"
    except Exception as e:  # 防御性兜底：任何异常都诚实降级，不装成功
        logger.warning(f"信息抽取 LLM 调用异常: {e}")
        return f"finish: 信息抽取未能完成（调用异常：{e}）。"
    return f"finish: {answer}"


def create_extract_agent() -> Agent:
    """创建信息抽取 Agent（真调 DeepSeek，结构化抽取结果）"""
    loop = ReActLoop()
    memory_short = ShortTermMemory(max_rounds=5)
    memory_long = LongTermMemory()
    tools = ToolRegistry()  # 信息抽取通常不需要工具
    context_builder = ContextBuilder(
        system_prompt="你是一个信息抽取助手，请从输入文本中抽取关键实体和属性。",
    )
    return Agent(
        loop=loop,
        tools=tools.list_all(),
        memory_short=memory_short,
        memory_long=memory_long,
        context_builder=context_builder,
        llm_call=_extract_llm_call,
    )
