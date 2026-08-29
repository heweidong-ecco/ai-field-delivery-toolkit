"""原型模板真实化测试（v8.0）：三个模板（信息抽取 / 多步推理 / 反思）真调 LLM 驱动。

非教学场景：测试内注入打桩 chat（monkeypatch core.llm.chat），验证——
- agent.run 输出非占位默认值；
- 含模板角色行为（结构化抽取 / 推理分步 / 反思修正）；
- LLMError 时诚实降级（返回错误说明，不装成功）；
- qa_agent 不回归；API llm_mode 诚实为 llm。
"""

import pytest
from fastapi.testclient import TestClient

import core.llm as llm
from core.llm import LLMError
from core.main import create_app

from prototype_assembler.templates.extract_agent import create_extract_agent
from prototype_assembler.templates.reasoning_agent import create_reasoning_agent
from prototype_assembler.templates.reflexion_agent import create_reflexion_agent
from prototype_assembler.templates.qa_agent import create_qa_agent


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


# ---------- 信息抽取（ReAct，真调 LLM） ----------


def test_extract_agent_real_llm(monkeypatch):
    """打桩 chat：抽取模板应产生结构化抽取结果（非占位默认值）"""
    def fake_chat(system, user, **kwargs):
        assert "信息抽取" in system or "抽取" in system
        return "设备E001 | 设备 | 编号=E001, 负责人=张三, 状态=运行中"

    monkeypatch.setattr(llm, "chat", fake_chat)
    result = create_extract_agent().run("设备E001由张三负责维护，状态运行中。")
    assert result != "已完成任务"
    assert "设备E001" in result
    assert "张三" in result
    assert "|" in result  # 结构化输出


def test_extract_agent_llm_error_honest_degradation(monkeypatch):
    """打桩 chat 抛 LLMError：抽取模板应诚实降级（返回错误说明，不装成功）"""
    def fake_chat(system, user, **kwargs):
        raise LLMError("未配置 DEEPSEEK_API_KEY")

    monkeypatch.setattr(llm, "chat", fake_chat)
    result = create_extract_agent().run("设备E001故障。")
    assert "未配置 DEEPSEEK_API_KEY" in result
    assert "信息抽取未能完成" in result
    assert result != "已完成任务"


# ---------- 多步推理（Plan-Execute，真调 LLM） ----------


def test_reasoning_agent_real_llm_plan_execute(monkeypatch):
    """打桩 chat：Plan-Execute 应生成计划 → 逐步执行 → 汇总最终答案（非占位）"""
    calls = []

    def fake_chat(system, user, **kwargs):
        calls.append(system)
        if "规划" in system:
            return "1. 分析输入数据\n2. 计算关键指标\n3. 汇总结论"
        if "执行器" in system:
            return f"步骤执行完成：{user.split('当前步骤：')[1][:20]}"
        if "汇总器" in system:
            return "最终答案：综合各步骤，结论是 X。"
        return "默认回答"

    monkeypatch.setattr(llm, "chat", fake_chat)
    result = create_reasoning_agent().run("客户有3台设备，估算一周工单总量。")
    assert result == "最终答案：综合各步骤，结论是 X。"
    assert result != "任务完成"
    # 推理分步：确实发生了计划生成 + 步骤执行 + 答案汇总
    assert any("规划" in s for s in calls)
    assert any("执行器" in s for s in calls)
    assert any("汇总器" in s for s in calls)
    assert len(calls) >= 5  # 1 次计划 + 3 步执行 + 1 次汇总


def test_reasoning_agent_llm_error_honest_degradation(monkeypatch):
    """打桩 chat 抛 LLMError：多步推理应诚实降级（最终答案如实暴露失败）"""
    def fake_chat(system, user, **kwargs):
        raise LLMError("未配置 DEEPSEEK_API_KEY")

    monkeypatch.setattr(llm, "chat", fake_chat)
    result = create_reasoning_agent().run("客户有3台设备，估算一周工单总量。")
    assert "未配置 DEEPSEEK_API_KEY" in result
    assert "推理未能得出最终答案" in result
    assert result != "任务完成"


# ---------- 反思型 Agent（Reflexion，真调 LLM） ----------


def test_reflexion_agent_real_llm_reflects(monkeypatch):
    """打桩 chat：首次作答过短触发评估失败 → 反思修正 → 最终输出修正后的答案"""
    systems = []

    def fake_chat(system, user, **kwargs):
        systems.append(system)
        if len(systems) == 1:
            return "太短"  # 长度 ≤ 10，触发 _default_evaluator 失败 → 反思
        return "这是一个经过反思修正后的完整答案，长度足够长且包含正确结论。"

    monkeypatch.setattr(llm, "chat", fake_chat)
    result = create_reflexion_agent().run("请写一段超过10个字符的故障说明。")
    # 反思修正：第二次调用携带上一轮评估反馈
    assert len(systems) == 2
    assert "未通过质量评估" in systems[1]
    assert result == "这是一个经过反思修正后的完整答案，长度足够长且包含正确结论。"


def test_reflexion_agent_llm_error_honest_degradation(monkeypatch):
    """打桩 chat 抛 LLMError：反思模板应诚实降级（返回错误说明，不装成功）"""
    def fake_chat(system, user, **kwargs):
        raise LLMError("未配置 DEEPSEEK_API_KEY")

    monkeypatch.setattr(llm, "chat", fake_chat)
    result = create_reflexion_agent().run("请写一段超过10个字符的故障说明。")
    assert "未配置 DEEPSEEK_API_KEY" in result
    assert "反思作答未能完成" in result
    assert result != "执行结果（反思历史：无）"


# ---------- qa_agent 不回归 ----------


def test_qa_agent_no_regression(monkeypatch):
    """打桩 chat：qa_agent 仍真调 LLM（llm_call 注入 + 非占位输出）"""
    def fake_chat(system, user, **kwargs):
        return "根据知识库，E001 表示电源模块异常，请检查电源线并测适配器电压。"

    monkeypatch.setattr(llm, "chat", fake_chat)
    agent = create_qa_agent()
    assert getattr(agent, "llm_call", None) is not None
    result = agent.run("设备出现E001故障如何排查？")
    assert result != "已完成任务"
    assert "E001" in result


# ---------- API：三个真调模板 llm_mode 诚实为 llm；模板元信息 ----------


@pytest.mark.parametrize("template", ["information_extraction", "multi_step_reasoning", "reflexion"])
def test_api_prototype_run_llm_mode_llm(client, monkeypatch, template):
    """/prototype/run 对三个真调模板应返回 llm_mode=llm（非 placeholder）"""
    def fake_chat(system, user, **kwargs):
        if "规划" in system:
            return "1. 分析\n2. 求解\n3. 汇总"
        if "执行器" in system:
            return "步骤结果"
        return "测试回答，长度足够。 "

    monkeypatch.setattr(llm, "chat", fake_chat)
    r = client.post("/api/v1/prototype/run", json={"template": template, "user_input": "测试输入"})
    assert r.status_code == 200
    body = r.json()
    assert body["llm_mode"] == "llm"
    assert isinstance(body["result"], str)
    assert body["result"].strip() != ""


def test_api_prototype_templates_meta(client):
    """/prototype/templates 返回元信息（前端诚实标注用）且旧结构不破坏"""
    r = client.get("/api/v1/prototype/templates")
    assert r.status_code == 200
    body = r.json()
    assert "knowledge_qa" in body["templates"]  # 旧结构 templates 列表保留
    meta = body.get("meta", {})
    for t in body["templates"]:
        assert t in meta
        assert meta[t]["llm"] == "真调 DeepSeek"
    assert meta["knowledge_qa"]["rag_ready"] is True
