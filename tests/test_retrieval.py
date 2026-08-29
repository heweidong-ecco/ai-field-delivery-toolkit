"""RAG 检索链路测试（v5.0）：知识库分块 → 索引(ChromaDB) → 检索 → 问答(带引用) → 数据作战流衔接

场景：非教学类真实数据 —— 设备运维手册 / 故障处理指南。
- ChromaDB 向量检索用确定性 fake 嵌入（字符二元组袋），保证测试不依赖模型/网络（与 test_dataprep 同法）；
  真实嵌入链路（本机已缓存 MiniLM）单独冒烟验证。
- RAG 问答 LLM 全部打桩，不真实调用。
"""

import hashlib

import pytest
from fastapi.testclient import TestClient

from chromadb.api.types import EmbeddingFunction

from core.main import create_app

OPS_MANUAL = """设备故障处理指南
1. 故障代码 E001（电源模块异常）
当设备显示屏出现 E001 时，说明电源模块异常。请首先检查电源线是否插紧，然后测量电源适配器输出电压是否在 24V 范围内。若电压异常，请更换电源适配器。更换后重新启动设备，观察是否恢复正常。
2. 故障代码 E002（传感器连接中断）
当设备出现 E002 报警时，说明传感器连接中断。请检查传感器接头是否松动，重新插拔传感器连接线。若仍报警，请检查线缆是否破损，必要时更换线缆。
3. 故障代码 E003（温度过高保护）
当设备内部温度超过 85 摄氏度时触发保护，显示屏出现 E003。请检查散热风扇是否正常运转，清理进风口灰尘，确保设备放置在通风良好的位置。
4. 日常维护与保养
每运行 500 小时更换一次空气滤芯；每季度检查一次电池健康度；长期不用时断开电源并加盖防尘罩。
"""


# ---------- 确定性 fake 嵌入（字符二元组袋，1024 维；相关文本共享 n-gram → 高相似度） ----------


class FakeEmbeddingFunction(EmbeddingFunction):
    DIM = 1024

    def __call__(self, input):
        return [self._vec(t) for t in input]

    def _vec(self, text):
        vec = [0.0] * self.DIM
        s = str(text)
        grams = [s[i:i + 2] for i in range(len(s) - 1)] or [s]
        for g in grams:
            idx = int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16) % self.DIM
            vec[idx] += 1.0
        norm = sum(v * v for v in vec) ** 0.5
        if norm == 0:
            return vec
        return [v / norm for v in vec]


@pytest.fixture
def fake_ef():
    return FakeEmbeddingFunction()


@pytest.fixture
def retrieval_tmp(monkeypatch, tmp_path, fake_ef):
    """隔离 retrieval 的 ChromaDB 目录 + 索引档案目录 + 默认嵌入函数，返回 fake_ef"""
    import retrieval.service as rs
    monkeypatch.setattr(rs, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(rs, "RETRIEVAL_ROOT", tmp_path / "retrieval")
    monkeypatch.setattr(rs, "_client_instance", None)
    monkeypatch.setattr(rs, "_get_ef", lambda embedding_function=None: fake_ef)
    return fake_ef


def _sensor_csv_bytes() -> bytes:
    """制造业传感器 CSV（复用 test_dataprep 场景：含温度/压力/设备日志，PII，重复）"""
    lines = ["sensor_id,reading,ts"]
    for i in range(8):
        lines.append(f"S{i:03d},温度 {20 + i} 摄氏度,2026-08-29 0{i % 6}:00:00")
    lines.append("S100,设备运行日志" * 13 + ",2026-08-29 08:00:00")
    lines.append("S999,压力 5.2 MPa 联系 13812345678,2026-08-29 10:00:00")
    lines.append("S001,温度 20 摄氏度,2026-08-29 00:00:00")  # 完全重复
    return "\n".join(lines).encode("utf-8")


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


# ---------- 1. 全链路：分块 → 索引 → 检索 → RAG 问答（带引用） ----------


def test_retrieval_manufacturing_manual_full_chain(retrieval_tmp, tmp_path):
    from kb.service import chunk_text
    import retrieval.service as rs

    kb_run_id = "ops_manual_001"
    chunks = chunk_text(OPS_MANUAL, chunk_size=150, overlap=20)
    assert len(chunks) >= 3

    # 分块 → 索引（真实 ChromaDB 写入 + 档案）
    idx = rs.index_knowledge(kb_run_id, chunks)
    assert idx["collection"] == f"kb_{kb_run_id}"
    assert idx["chunk_count"] == len(chunks)
    archive = rs.get_archive(kb_run_id)
    assert archive and archive["collection"] == f"kb_{kb_run_id}"
    assert archive["chunk_count"] == len(chunks)
    assert archive["indexed_at"]
    assert any(k["kb_run_id"] == kb_run_id for k in rs.list_indexed())

    # 检索：query 命中相关分块（E001 故障）
    hits = rs.retrieve(kb_run_id, "设备出现E001故障如何排查？", top_k=3)
    assert hits, "检索应返回分块"
    assert hits[0]["score"] >= 0, "score 为相似度（应存在）"
    assert all(h["chunk"] and h["source"] for h in hits)
    assert any("E001" in h["chunk"] for h in hits), "检索结果应包含 E001 相关分块"
    # 传感器 query 命中 E002 分块
    hits2 = rs.retrieve(kb_run_id, "传感器连接中断怎么办？", top_k=3)
    assert any("E002" in h["chunk"] for h in hits2)

    # RAG 问答（LLM 打桩，返回含引用）
    def stub_llm(system, user):
        assert "知识库" in system
        assert "E001" in user or "知识库分块" in user
        return "根据知识库[1]，E001 表示电源模块异常，请先检查电源线，再测适配器输出电压。"

    rag = rs.rag_answer(kb_run_id, "设备出现E001故障如何排查？", llm_call=stub_llm, top_k=3)
    assert rag["answer"]
    assert "E001" in rag["answer"]
    assert len(rag["sources"]) >= 1
    for s in rag["sources"]:
        assert "chunk" in s and len(s["chunk"]) <= 100   # chunk 前 100 字
        assert "score" in s


# ---------- 2. RAG 问答：sources 截断 + 无相关知识诚实回答 ----------


def test_retrieval_rag_answer_sources_and_honest_unknown(retrieval_tmp, tmp_path):
    from kb.service import chunk_text
    import retrieval.service as rs

    kb_run_id = "ops_manual_002"
    chunks = chunk_text(OPS_MANUAL, chunk_size=150, overlap=20)
    rs.index_knowledge(kb_run_id, chunks)

    # sources 中 chunk 截断到前 100 字
    def stub_llm(system, user):
        return "知识库中未找到与问题直接相关的内容，无法确定答案。"

    rag = rs.rag_answer(kb_run_id, "这台设备支持蓝牙连接吗？", llm_call=stub_llm, top_k=3)
    assert "未找到" in rag["answer"] or "无法确定" in rag["answer"]   # 诚实不知道，由 LLM 判断
    assert len(rag["sources"]) >= 1
    assert all(len(s["chunk"]) <= 100 for s in rag["sources"])


# ---------- 3. 未索引时检索报错 ----------


def test_retrieval_retrieve_unindexed_raises(retrieval_tmp, tmp_path):
    import retrieval.service as rs
    with pytest.raises(FileNotFoundError):
        rs.retrieve("never_indexed", "任何问题", top_k=3)


# ---------- 4. 数据作战流 kb 产物 → 索引 → RAG 就绪（闭环） ----------


def test_retrieval_dataprep_kb_product_indexable(retrieval_tmp, monkeypatch, tmp_path):
    """数据作战流：传感器 CSV → 清洗/质量 → knowledge_base 步骤自动索引 → 检索可用"""
    import io

    import data_prep.cleaning.semantic_dedup as sd

    # 语义去重：固定哈希向量（8 维），不依赖真实模型（与 test_dataprep 同法）
    def _fake_embed(self, text):
        return [
            float(int(hashlib.md5((text + str(i)).encode("utf-8")).hexdigest(), 16) % 1000) / 1000.0
            for i in range(8)
        ]
    monkeypatch.setattr(sd.SemanticDeduplicator, "_embed_text", _fake_embed)

    from dataprep.service import continue_step, start_task

    path = tmp_path / "sensor.csv"
    path.write_bytes(_sensor_csv_bytes())
    st = start_task(name="制造业传感器数据", source_path=str(path), customer="某汽车制造厂")
    run_id = st["run_id"]
    assert st["progress"] == 3

    # 顺序推进到知识库
    continue_step(run_id, step=None)   # annotate
    continue_step(run_id, step=None)   # eval_set
    kb = continue_step(run_id, step=None)  # knowledge_base
    assert kb["status"] == "completed"
    kb_step = [s for s in kb["steps"] if s["step"] == "knowledge_base"][0]
    assert kb_step["indexed"] is True, "knowledge_base 步骤应自动索引"
    assert kb_step["collection"] == f"kb_{run_id}"
    assert kb["products"]["chunks"]["exists"] is True

    # 数据作战流产物 → 检索 → RAG 就绪
    import retrieval.service as rs
    hits = rs.retrieve(run_id, "温度传感器数据", top_k=3)
    assert hits, "数据作战流知识库产物应可被检索"
    assert any("温度" in h["chunk"] for h in hits)


# ---------- 5. API：索引 / 查询 / 已索引列表 ----------


def test_retrieval_api_index_query(client, retrieval_tmp):
    import retrieval.service as rs
    from kb.service import chunk_text

    kb_run_id = "api_ops_001"
    chunks = chunk_text(OPS_MANUAL, chunk_size=150, overlap=20)

    # POST /retrieval/index
    r = client.post("/api/v1/retrieval/index", json={"kb_run_id": kb_run_id, "chunks": chunks})
    assert r.status_code == 200
    body = r.json()
    assert body["collection"] == f"kb_{kb_run_id}"
    assert body["chunk_count"] == len(chunks)

    # GET /retrieval/indexed
    listed = client.get("/api/v1/retrieval/indexed").json()["kbs"]
    assert any(k["kb_run_id"] == kb_run_id for k in listed)

    # POST /retrieval/query（LLM 打桩）
    rs._default_llm_call = lambda system, user: "根据知识库[1]，E001 表示电源模块异常，请检查电源线。"
    q = client.post("/api/v1/retrieval/query", json={"kb_run_id": kb_run_id, "query": "E001怎么排查？", "top_k": 3})
    assert q.status_code == 200
    qbody = q.json()
    assert "E001" in qbody["answer"]
    assert len(qbody["sources"]) >= 1
    assert all(len(s["chunk"]) <= 100 for s in qbody["sources"])


# ---------- 6. 原型 QA 带 kb_run_id 走 RAG（带引用返回） ----------


def test_prototype_run_with_kb_rag(client, retrieval_tmp, monkeypatch):
    """POST /prototype/run 带 kb_run_id：检索知识库做上下文 → 回答 + 引用分块"""
    from kb.service import chunk_text
    import retrieval.service as rs
    import core.llm as llm
    import prototype_assembler.templates.qa_agent as qa

    kb_run_id = "proto_ops_001"
    chunks = chunk_text(OPS_MANUAL, chunk_size=150, overlap=20)
    rs.index_knowledge(kb_run_id, chunks)

    # LLM 打桩：返回含引用的回答（不真实调用 DeepSeek）
    def fake_chat(system, user, **kwargs):
        assert "知识库分块" in user or "知识库" in system
        return "根据知识库[1]，E001 表示电源模块异常，请检查电源线并测适配器电压。"

    monkeypatch.setattr(llm, "chat", fake_chat)

    r = client.post("/api/v1/prototype/run", json={
        "template": "knowledge_qa", "user_input": "设备出现E001故障如何排查？", "kb_run_id": kb_run_id,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["rag"] is True
    assert "E001" in body["result"]
    assert body["sources"], "RAG 问答应返回引用分块"
    assert all("chunk" in s and "score" in s for s in body["sources"])
