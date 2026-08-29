"""原型组装器入口（v1.2.0：增加 Reflexion 模板）"""

from typing import Dict, Any

from core.logging.logger import get_logger

from prototype_assembler.templates.qa_agent import create_qa_agent
from prototype_assembler.templates.extract_agent import create_extract_agent
from prototype_assembler.templates.reasoning_agent import create_reasoning_agent
from prototype_assembler.templates.reflexion_agent import create_reflexion_agent

logger = get_logger()


class PrototypeAssembler:
    """原型组装器（v1.2.0）"""

    TEMPLATE_MAP = {
        "knowledge_qa": create_qa_agent,
        "information_extraction": create_extract_agent,
        "multi_step_reasoning": create_reasoning_agent,
        "reflexion": create_reflexion_agent,
    }

    # v8.0：模板元信息（前端诚实标注用）。四个模板均真调 DeepSeek（core/llm.py）。
    TEMPLATE_META = {
        "knowledge_qa": {
            "label": "知识问答",
            "llm": "真调 DeepSeek",
            "rag_ready": True,
            "detail": "带知识库（kb_run_id）走 RAG 检索问答、回答带引用；不带则普通问答。",
        },
        "information_extraction": {
            "label": "信息抽取",
            "llm": "真调 DeepSeek",
            "rag_ready": False,
            "detail": "从输入文本抽取关键实体和属性，返回结构化抽取结果。",
        },
        "multi_step_reasoning": {
            "label": "多步推理",
            "llm": "真调 DeepSeek",
            "rag_ready": False,
            "detail": "Plan-Execute：先生成计划，再逐步执行，汇总中间结果给出最终答案。",
        },
        "reflexion": {
            "label": "反思型 Agent",
            "llm": "真调 DeepSeek",
            "rag_ready": False,
            "detail": "先作答 → 评估 → 反思修正 → 重试，直至通过评估或达最大反思次数。",
        },
    }

    def create(self, template_name: str, **kwargs) -> Any:
        """创建原型实例（v5.0：支持 kwargs 透传，如 kb_run_id 走 RAG）"""
        if template_name not in self.TEMPLATE_MAP:
            raise ValueError(f"未知模板: {template_name}，可选: {list(self.TEMPLATE_MAP.keys())}")
        logger.info(f"创建原型: {template_name} kwargs={kwargs}")
        return self.TEMPLATE_MAP[template_name](**kwargs)

    def run(self, template_name: str, user_input: str, **kwargs) -> str:
        """创建并运行原型（v5.0：支持 kwargs 透传）"""
        agent = self.create(template_name, **kwargs)
        return agent.run(user_input)