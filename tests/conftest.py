"""pytest 公共配置和 fixture"""

import os
import sys
import pytest

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _isolate_assets_registry(tmp_path, monkeypatch):
    """每个用例把可复用资产注册表指向临时文件，避免测试（如 mapping export 自动注册）污染真实 registry（v6.0）"""
    import assets.archive as aa
    p = tmp_path / "registry.json"
    monkeypatch.setattr(aa, "REGISTRY_PATH", p)
    return p


@pytest.fixture
def sample_data():
    """提供测试用样本数据"""
    return [
        {"content": "这是一条正常的测试数据，长度适中，用于测试数据清洗流程", "metadata": {"source": "test"}},
        {"content": "这是一条正常的测试数据，长度适中，用于测试数据清洗流程", "metadata": {"source": "test"}},
        {"content": "短数据", "metadata": {"source": "test"}},
        {"content": "我的手机号是13812345678，邮箱是test@example.com，这是一条包含PII的数据", "metadata": {"source": "test"}},
        {"content": "这是一条包含敏感信息的数据，身份证号110101199001011234需要被脱敏", "metadata": {"source": "test"}},
        {"content": "这是一条正常的测试数据，内容涉及RAG检索增强生成技术", "metadata": {"source": "test"}},
        {"content": "这是一条正常的测试数据，内容涉及Agent工具调用", "metadata": {"source": "test"}},
        {"content": "这是一条正常的测试数据，内容涉及多步推理", "metadata": {"source": "test"}},
        {"content": "这是一条正常的测试数据，内容涉及结构化输出", "metadata": {"source": "test"}},
        {"content": "这是一条正常的测试数据，内容涉及流式输出", "metadata": {"source": "test"}},
    ]