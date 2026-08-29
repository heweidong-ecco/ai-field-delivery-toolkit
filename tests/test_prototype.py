"""原型组装器测试（v1.2.0：增加 Reflexion 测试）"""

from prototype_assembler.assembler import PrototypeAssembler


class TestPrototypeAssemblerV2:
    """原型组装器测试（v1.2.0）"""

    def setup_method(self):
        self.assembler = PrototypeAssembler()

    def test_available_templates(self):
        templates = list(self.assembler.TEMPLATE_MAP.keys())
        assert "knowledge_qa" in templates
        assert "information_extraction" in templates
        assert "multi_step_reasoning" in templates

    def test_create_agent(self):
        agent = self.assembler.create("knowledge_qa")
        assert agent is not None
        assert agent.agent_id is not None

    def test_run_agent(self):
        result = self.assembler.run("knowledge_qa", "什么是RAG？")
        assert isinstance(result, str)

    def test_unknown_template(self):
        import pytest
        with pytest.raises(ValueError):
            self.assembler.create("unknown_template")

    def test_reflexion_template_available(self):
        from prototype_assembler.assembler import PrototypeAssembler
        assembler = PrototypeAssembler()
        templates = list(assembler.TEMPLATE_MAP.keys())
        assert "reflexion" in templates

    def test_reflexion_agent_runs(self):
        from prototype_assembler.assembler import PrototypeAssembler
        assembler = PrototypeAssembler()
        result = assembler.run("reflexion", "写一个超过10个字符的回答")
        assert isinstance(result, str)

class TestAgentState:
    """Agent 状态测试"""

    def test_state_save_load(self, tmp_path):
        from prototype_assembler.harness.state import AgentState
        state = AgentState(agent_id="test", loop_name="react")
        state.add_step({"step": 1, "action": "finish", "content": "完成"})
        state.finished = True
        state.result = "结果"

        path = tmp_path / "state.json"
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f)

        with open(path, "r", encoding="utf-8") as f:
            loaded = AgentState.from_dict(json.load(f))

        assert loaded.agent_id == "test"
        assert loaded.finished is True
        assert len(loaded.steps) == 1


class TestMemory:
    """记忆系统测试"""

    def test_short_term_memory(self):
        from prototype_assembler.memory.short_term import ShortTermMemory
        mem = ShortTermMemory(max_rounds=2)
        mem.add("user", "你好")
        mem.add("assistant", "你好")
        mem.add("user", "再见")
        mem.add("assistant", "再见")
        mem.add("user", "第三条")
        # max_rounds=2 即最多保留 4 条消息
        assert len(mem.get_all()) == 4

    def test_long_term_memory(self):
        from prototype_assembler.memory.long_term import LongTermMemory
        mem = LongTermMemory()
        mem.set("location", "北京")
        assert mem.get("location") == "北京"
        mem.delete("location")
        assert mem.get("location") is None