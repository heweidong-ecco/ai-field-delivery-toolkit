"""Agent 主体：生命周期管理、执行、资源配额"""

import uuid
from typing import Any, Callable, Dict, Optional

from core.logging.logger import get_logger

from prototype_assembler.harness.state import AgentState

logger = get_logger()


class Agent:
    """Agent 实例"""

    def __init__(
        self,
        loop: Any,
        tools: list,
        memory_short,
        memory_long,
        context_builder,
        max_iterations: int = 10,
        max_tokens: int = 2048,
        # v1.2.0 新增：可注入函数
        llm_call=None,              # React 循环用
        plan_generator=None,        # Plan-Execute 循环用
        step_executor=None,         # Plan-Execute 循环用
        answer_generator=None,      # Plan-Execute 循环用
    ):
        self.agent_id = str(uuid.uuid4())[:8]
        self.loop = loop
        self.tools = tools
        self.memory_short = memory_short
        self.memory_long = memory_long
        self.context_builder = context_builder
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.state = AgentState(agent_id=self.agent_id, loop_name=loop.name)
        # 可注入函数
        self.llm_call = llm_call
        self.plan_generator = plan_generator
        self.step_executor = step_executor
        self.answer_generator = answer_generator

        self.state = AgentState(agent_id=self.agent_id, loop_name=loop.name)

    def run(self, user_input: str) -> str:
        """执行 Agent"""
        logger.info(f"Agent {self.agent_id} 开始执行，输入: {user_input[:50]}...")
        # 初始化短期记忆
        self.memory_short.add("user", user_input)
        result = self.loop.run(self, user_input)
        self.state.result = result
        self.state.finished = True
        logger.info(f"Agent {self.agent_id} 执行完成，输出: {str(result)[:50]}...")
        return result

    def resume(self, user_input: str) -> str:
        """从断点恢复执行"""
        if self.state.finished:
            logger.warning("Agent 已执行完成，无法恢复")
            return self.state.result or ""
        logger.info(f"Agent {self.agent_id} 从步骤 {self.state.current_step} 恢复")
        result = self.loop.run(self, user_input, resume=True)
        self.state.result = result
        self.state.finished = True
        return result

    def save_state(self, path: str):
        """保存状态到文件"""
        with open(path, "w", encoding="utf-8") as f:
            import json
            json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2)

    def load_state(self, path: str):
        """从文件加载状态"""
        with open(path, "r", encoding="utf-8") as f:
            import json
            data = json.load(f)
        self.state = AgentState.from_dict(data)
        self.agent_id = self.state.agent_id