"""知识问答 Agent 模板（接 core/llm.py，真实调用 DeepSeek；v5.0 支持 RAG：带 kb_run_id 走检索问答带引用）"""

from prototype_assembler.harness.agent import Agent
from prototype_assembler.loops.react import ReActLoop
from prototype_assembler.memory.short_term import ShortTermMemory
from prototype_assembler.memory.long_term import LongTermMemory
from prototype_assembler.tools.registry import ToolRegistry
from prototype_assembler.tools.builtin import register_builtin_tools
from prototype_assembler.context.builder import ContextBuilder

from core.logging.logger import get_logger

logger = get_logger()


def _qa_llm_call(agent, context: str, user_input: str) -> str:
    """真实 LLM 调用（core/llm.py），返回 finish:<回答> 供 ReAct 解析。

    带 kb_run_id 时：先检索知识库相关分块（ChromaDB 向量检索），拼进上下文再答，
    回答带引用（标注分块编号），并缓存 sources 到 agent.last_sources 供 API 返回。
    """
    from core.llm import chat

    sources = []
    kb_run_id = getattr(agent, "kb_run_id", None)
    if kb_run_id:
        try:
            from retrieval.service import retrieve
            sources = retrieve(kb_run_id, user_input, top_k=getattr(agent, "top_k", 5))
        except Exception as e:
            logger.warning(f"知识库检索失败 kb_run_id={kb_run_id}: {e}")
            sources = []
        agent.last_sources = sources

    if sources:
        ctx_blocks = "\n".join(f"[{i + 1}] {s['chunk']}" for i, s in enumerate(sources))
        system = (
            "你是一个基于知识库的问答助手。根据提供的知识库分块内容回答用户问题。\n"
            "规则：\n"
            "1. 优先使用知识库内容回答；\n"
            "2. 如果知识库内容不足以回答问题，明确回答“我不知道”或“知识库中未找到相关信息”，不要编造；\n"
            "3. 回答末尾标注你所引用的分块编号，格式如 [1][2]；\n"
            "4. 回答简洁准确，只回答用户问题。"
        )
        user = f"知识库分块内容：\n{ctx_blocks}\n\n用户问题：{user_input}"
        answer = chat(system=system, user=user, temperature=0.3)
    else:
        system = getattr(agent.context_builder, "system_prompt", "") or "你是一个知识问答助手。"
        answer = chat(system=system, user=f"{context}\n\n用户问题：{user_input}", temperature=0.3)
    return f"finish: {answer}"


def create_qa_agent(kb_run_id: str = None, top_k: int = 5) -> Agent:
    """创建知识问答 Agent（真调 DeepSeek）。

    kb_run_id 不为空时走 RAG：运行时用检索结果（知识库分块）作为上下文再答，回答带引用，
    并将引用分块缓存在 agent.last_sources。
    """
    loop = ReActLoop()
    memory_short = ShortTermMemory(max_rounds=10)
    memory_long = LongTermMemory()
    tools = ToolRegistry()
    register_builtin_tools(tools)
    context_builder = ContextBuilder(
        system_prompt="你是一个知识问答助手，请根据历史对话和工具返回结果准确回答问题。",
    )
    agent = Agent(
        loop=loop,
        tools=tools.list_all(),
        memory_short=memory_short,
        memory_long=memory_long,
        context_builder=context_builder,
        llm_call=_qa_llm_call,
    )
    agent.kb_run_id = kb_run_id
    agent.top_k = top_k
    agent.last_sources = []
    return agent
