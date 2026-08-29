"""Plan-and-Execute 循环：先生成计划，再逐步执行（v1.2.0 可注入版）"""

from typing import Any

from core.logging.logger import get_logger

from prototype_assembler.loops.base import BaseLoop

logger = get_logger()


class PlanExecuteLoop(BaseLoop):
    """Plan-and-Execute 循环

    流程：
    1. 生成计划：将复杂任务拆解为可执行的步骤列表
    2. 逐步执行：按顺序执行每个步骤，记录中间结果
    3. 生成最终答案：基于执行过程汇总出最终回答

    可注入函数（通过 Agent 实例属性注入）：
    - agent.plan_generator: 自定义计划生成函数，签名 (agent, user_input) -> list[str]
    - agent.step_executor:   自定义步骤执行函数，签名 (agent, context, step) -> str
    - agent.answer_generator: 自定义答案生成函数，签名 (agent, memory) -> str
    """

    name = "plan_execute"

    def run(self, agent: Any, user_input: str, resume: bool = False) -> str:
        """执行 Plan-and-Execute 循环"""
        step_count = agent.state.current_step if resume else 0
        final_answer = ""

        # 1. 生成计划
        plan = self._generate_plan(agent, user_input)
        agent.state.add_step({"step": step_count, "action": "plan", "content": plan})
        step_count += 1

        # 2. 逐步执行计划
        for j, step in enumerate(plan, start=step_count):
            context = agent.context_builder.build(
                agent.memory_short,
                agent.memory_long,
                agent.tools,
            )
            step_result = self._execute_step(agent, context, step)
            agent.state.add_step({"step": j, "action": "execute", "content": step_result})
            agent.memory_short.add("assistant", f"步骤执行: {step_result}")

            if j >= agent.max_iterations:
                break

        # 3. 生成最终答案
        final_answer = self._generate_final_answer(agent, agent.memory_short)
        return final_answer

    def _generate_plan(self, agent: Any, user_input: str) -> list:
        """生成计划

        TODO: 实际项目中替换为真实模型 API 调用。
        可通过 agent.plan_generator 注入自定义计划生成函数。
        """
        if hasattr(agent, "plan_generator") and agent.plan_generator:
            plan = agent.plan_generator(agent, user_input)
            if isinstance(plan, list) and all(isinstance(s, str) for s in plan):
                return plan
            logger.warning("plan_generator 返回格式错误，使用默认计划生成逻辑")

        # 默认占位实现：简单的三步计划
        return [
            f"分析 {user_input[:50]}",
            "执行推理",
            "汇总结果",
        ]

    def _execute_step(self, agent: Any, context: str, step: str) -> str:
        """执行计划中的单个步骤

        TODO: 实际项目中替换为真实模型 API 调用。
        可通过 agent.step_executor 注入自定义步骤执行函数。
        """
        if hasattr(agent, "step_executor") and agent.step_executor:
            result = agent.step_executor(agent, context, step)
            if isinstance(result, str):
                return result
            logger.warning("step_executor 返回格式错误，使用默认步骤执行逻辑")

        # 默认占位实现：返回步骤描述
        return f"执行步骤: {step}"

    def _generate_final_answer(self, agent: Any, memory: Any) -> str:
        """基于执行过程生成最终答案

        TODO: 实际项目中替换为真实模型 API 调用。
        可通过 agent.answer_generator 注入自定义答案生成函数。
        """
        if hasattr(agent, "answer_generator") and agent.answer_generator:
            result = agent.answer_generator(agent, memory)
            if isinstance(result, str):
                return result
            logger.warning("answer_generator 返回格式错误，使用默认答案生成逻辑")

        # 默认占位实现：返回固定完成语
        return "任务完成"