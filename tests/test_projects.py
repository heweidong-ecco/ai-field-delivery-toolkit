"""项目作战台 v7.0 测试：warroom 聚合真实 / workflow 按项目过滤 / 诊断 project_id 落盘 / 端点结构

场景：非教学类 —— 制造业设备字段映射 / 某汽车制造厂 项目。
LLM 全部打桩；语义去重（dataprep create）用固定哈希向量替代 chromadb 嵌入（与 test_dataprep 同法）；
RAG 索引档案用手写 archive.json（不触发 ChromaDB）；资产注册表由 conftest 自动隔离。
"""

import hashlib
import io
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from core.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def patch_embed(monkeypatch):
    """固定哈希向量替代 chromadb 默认嵌入（确定性，不联网）"""
    import data_prep.cleaning.semantic_dedup as sd

    def _fake_embed(self, text):
        return [
            float(int(hashlib.md5((text + str(i)).encode("utf-8")).hexdigest(), 16) % 1000) / 1000.0
            for i in range(8)
        ]
    monkeypatch.setattr(sd.SemanticDeduplicator, "_embed_text", _fake_embed)


def _uniq(prefix: str) -> str:
    """唯一客户名，避免测试间 `_ensure_project` 按客户复用导致串项目"""
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


# ---------- 打桩 ----------


def _fake_json_call(system, user):
    """诊断多 Agent 打桩：按角色返回结构化 JSON（与 test_api 同法）"""
    if "生成器" in system:
        return {
            "clarification_questions": [],
            "dimension_scores": {"generation": 4, "reasoning": 3, "uncertainty": 4, "data": 5, "real_time": 2},
            "reasons": {"generation": "G理由1", "reasoning": "G理由2", "uncertainty": "G理由3",
                        "data": "G理由4", "real_time": "G理由5"},
            "summary": "G总结", "draft_notes": "草稿要点",
            "non_tech_feasibility": {
                "business_value": {"item": "价值主张成立", "basis": "需求有明确收益", "signal": "绿", "advice": "优先投入"},
                "organization": {"item": "组织承接需培训", "basis": "未提及决策链", "signal": "黄", "advice": "先做培训"},
                "integration": {"item": "需对接现有系统", "basis": "需求提到集成", "signal": "黄", "advice": "评估映射工作量"},
                "compliance": {"item": "涉及数据隐私", "basis": "合规要求", "signal": "黄", "advice": "启动合规审查"},
                "risk_overview": {"item": "主要风险在数据质量", "basis": "综合判断", "signal": "黄", "advice": "先补数据"},
                "overall_recommendation": {"worth_investing": "值得", "budget_scale": "中",
                                           "main_resistance": "数据质量", "first_steps": "补数据"},
            },
        }
    if "独立评审" in system:
        return {
            "dimension_scores": {"generation": 2, "reasoning": 3, "uncertainty": 3, "data": 4, "real_time": 2},
            "reasons": {"generation": "C理由1", "reasoning": "C理由2", "uncertainty": "C理由3",
                        "data": "C理由4", "real_time": "C理由5"},
            "coverage_gaps": [], "inconsistencies": [], "over_confidence_flags": [],
        }
    if "人工评审复核" in system:
        return {
            "verdicts": {k: {"verdict": "agree", "adjusted_score": None, "reason": "合理"}
                         for k in ("generation", "reasoning", "uncertainty", "data", "real_time")},
            "bias": {"detected": False, "direction": "none", "detail": ""},
            "summary": "R总结",
        }
    raise AssertionError(f"未知角色 system: {system[:20]}")


def _fake_mapping_llm(system, user):
    return {"mappings": [
        {"target": "device_id", "source": "equipment_id", "rule": "direct",
         "expression": "equipment_id", "confidence": "high"},
        {"target": "device_name", "source": "equip_name", "rule": "direct",
         "expression": "equip_name", "confidence": "high"},
    ], "notes": "测试初判"}


def _sensor_csv_bytes() -> bytes:
    lines = ["sensor_id,reading,ts"]
    for i in range(8):
        lines.append(f"S{i:03d},温度 {20 + i} 摄氏度,2026-08-29 0{i % 6}:00:00")
    lines.append(f"S100,{'设备运行日志' * 13},2026-08-29 08:00:00")
    return "\n".join(lines).encode("utf-8")


# ---------- 辅助 ----------


def _finalize_diagnosis(client, monkeypatch, customer="测试客户", requirement="基于知识库的问答系统"):
    """跑完一次诊断并定稿（LLM 打桩），返回 run_id"""
    import diagnosis.agents as agents
    monkeypatch.setattr(agents, "_default_json_call", _fake_json_call)
    s = client.post("/api/v1/diagnosis/start", json={"requirement": requirement}).json()
    client.post("/api/v1/diagnosis/review", json={
        "run_id": s["run_id"], "human_scores": s["generator"]["dimension_scores"], "human_reasons": {}})
    f = client.post("/api/v1/diagnosis/finalize", json={
        "run_id": s["run_id"], "customer_name": customer, "confirmed": True})
    assert f.status_code == 200, f.text
    return s["run_id"]


def _create_mapping_run(client, monkeypatch, project_id, customer):
    """建一个映射 run（LLM 打桩）并挂到项目"""
    import mapping.service as ms
    monkeypatch.setattr(ms, "_default_json_call", _fake_mapping_llm)
    r = client.post("/api/v1/mapping/create", json={
        "name": "制造业设备字段映射",
        "source_fields": [{"name": "equipment_id", "sample": "E001"}, {"name": "equip_name", "sample": "设备1"}],
        "target_fields": [{"name": "device_id", "sample": "E001"}, {"name": "device_name", "sample": "设备1"}],
        "project_id": project_id, "customer": customer,
    })
    assert r.status_code == 200, r.text
    return r.json()["run_id"]


# ---------- 测试 ----------


def test_warroom_aggregation_real(client, monkeypatch, patch_embed, tmp_path):
    """作战台聚合真实：建项目 → 诊断定稿(打桩) → 数据任务 → 映射 → RAG 档案 → warroom 各分区数量正确、URL 可跳"""
    customer = _uniq("某汽车制造厂")
    p = client.post("/api/v1/projects", json={"name": "制造业设备字段映射项目", "customer": customer}).json()
    pid = p["project_id"]

    # 1) 诊断定稿（打桩）→ project_id 落盘 + 自动生成交付物 case + 诊断事件
    run_id = _finalize_diagnosis(client, monkeypatch, customer=customer)

    # 2) 数据作战流任务（显式 project_id；patch_embed 避免联网下载语义去重模型）
    files = {"file": ("sensor.csv", io.BytesIO(_sensor_csv_bytes()), "text/csv")}
    dp = client.post("/api/v1/dataprep/create", files=files,
                     data={"name": "制造业传感器数据", "project_id": pid, "customer": customer}).json()
    dp_run_id = dp["run_id"]

    # 3) 映射 run
    m_run_id = _create_mapping_run(client, monkeypatch, pid, customer)

    # 4) 手写一条 RAG 检索档案（不触发 ChromaDB），kb_run_id 属于本项目数据任务
    import retrieval.service as rs
    rag_dir = tmp_path / "retrieval"
    rag_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(rs, "RETRIEVAL_ROOT", rag_dir)
    (rag_dir / dp_run_id).mkdir(parents=True, exist_ok=True)
    (rag_dir / dp_run_id / "archive.json").write_text(json.dumps({
        "kb_run_id": dp_run_id, "collection": f"kb_{dp_run_id}",
        "chunk_count": 5, "indexed_at": "2026-08-29T00:00:00",
    }), encoding="utf-8")

    # 5) warroom 聚合
    w = client.get(f"/api/v1/projects/{pid}/warroom")
    assert w.status_code == 200
    body = w.json()

    assert body["project"]["project_id"] == pid
    assert body["counts"]["diagnosis"] == 1
    assert body["counts"]["dataprep"] == 1
    assert body["counts"]["mapping"] == 1
    assert body["counts"]["deliverables"] >= 1      # 诊断定稿自动生成交付物 case
    assert body["counts"]["assets"] >= 1            # 诊断方案自动注册资产（客户匹配）
    assert body["counts"]["rag"] == 1
    assert 0 <= body["counts"]["workflow_progress"] <= 100

    # 诊断分区：run 摘要 + URL 可跳
    diag = [d for d in body["diagnosis_runs"] if d["run_id"] == run_id][0]
    assert diag["url"] == f"/api/v1/diagnosis/{run_id}/state"
    assert diag["confirmed"] is True

    # 数据任务分区：摘要 + URL 可跳
    dps = [t for t in body["dataprep_runs"] if t["run_id"] == dp_run_id][0]
    assert dps["url"] == f"/api/v1/dataprep/{dp_run_id}"
    assert dps["progress"] == 3

    # 映射分区：摘要 + URL 可跳
    mps = [r for r in body["mapping_runs"] if r["run_id"] == m_run_id][0]
    assert mps["url"] == f"/api/v1/mapping/{m_run_id}"

    # 交付物分区：HTML 可下载
    case = body["cases"][0]
    assert case["html_url"].startswith("/api/v1/cases/")
    assert client.get(case["html_url"]).status_code == 200

    # RAG 分区
    assert body["indexed_kbs"][0]["kb_run_id"] == dp_run_id

    # 事件时间线含诊断事件（ref==run_id）
    assert any(e["type"] == "diagnosis" and e["ref"] == run_id for e in body["events"])


def test_workflow_project_scoped_filtering(client, monkeypatch):
    """workflow 按项目过滤：两个项目，一个有产物一个没有，各自状态互不污染（真修，非壳）"""
    customer_a = _uniq("客户A")
    customer_b = _uniq("客户B")
    pa = client.post("/api/v1/projects", json={"name": "A项目", "customer": customer_a}).json()
    pb = client.post("/api/v1/projects", json={"name": "B项目", "customer": customer_b}).json()

    # A 跑一次诊断定稿（自动挂到 A 项目）
    _finalize_diagnosis(client, monkeypatch, customer=customer_a)

    wa = client.get(f"/api/v1/workflow/{pa['project_id']}").json()["steps"]
    wb = client.get(f"/api/v1/workflow/{pb['project_id']}").json()["steps"]
    by_a = {s["key"]: s for s in wa}
    by_b = {s["key"]: s for s in wb}

    # A 有诊断 → diagnosis done；B 无任何产物 → diagnosis 未完成
    assert by_a["diagnosis"]["done"] is True
    assert by_b["diagnosis"]["done"] is False
    # A 有诊断交付物 case → deliver done；B 无
    assert by_a["deliver"]["done"] is True
    assert by_b["deliver"]["done"] is False
    # 其它步骤 B 均为未完成
    for key in ("data_prep", "prototype", "deploy"):
        assert by_b[key]["done"] is False

    # 证据里出现「诊断 run×1」（项目级证据，而非全局已确认诊断数）
    assert any("诊断 run×1" in e for e in by_a["diagnosis"]["evidence"])


def test_diagnosis_finalize_persists_project_id(client, monkeypatch):
    """诊断 finalize 落盘 project_id：run 档案 + /diagnosis/runs 列表项 + case meta"""
    customer = _uniq("某客户")
    run_id = _finalize_diagnosis(client, monkeypatch, customer=customer)

    # run 档案带 project_id（只增字段，旧字段不变）
    a = client.get(f"/api/v1/diagnosis/archive/{run_id}").json()
    assert a.get("project_id")
    assert a.get("confirmed") is True

    # /diagnosis/runs 列表项带 project_id
    runs = client.get("/api/v1/diagnosis/runs").json()["runs"]
    r = [x for x in runs if x["run_id"] == run_id][0]
    assert r.get("project_id")

    # 诊断交付物 case meta 带 project_id
    cases = client.get("/api/v1/cases").json()["cases"]
    c = [x for x in cases if x.get("run_id") == run_id and x.get("source_type") == "diagnosis"]
    assert c and c[0].get("project_id")

    # project_id 指向该项目（_ensure_project 按客户复用）
    p = client.get(f"/api/v1/projects/{a['project_id']}").json()
    assert p["customer"] == customer


def test_warroom_endpoint_structure_and_old_endpoints(client, monkeypatch):
    """GET /projects/{pid}/warroom 端点结构；旧 /projects/{pid} 与 /workflow/{project_id} 不破坏"""
    p = client.post("/api/v1/projects", json={"name": "结构测试", "customer": _uniq("客户C")}).json()
    pid = p["project_id"]

    # 旧端点原样返回
    old = client.get(f"/api/v1/projects/{pid}")
    assert old.status_code == 200
    assert old.json()["project_id"] == pid and "events" in old.json()

    # 新端点结构完整
    w = client.get(f"/api/v1/projects/{pid}/warroom")
    assert w.status_code == 200
    body = w.json()
    for k in ("project", "workflow", "counts", "diagnosis_runs", "dataprep_runs",
              "mapping_runs", "cases", "assets", "indexed_kbs", "events"):
        assert k in body
    assert "workflow_progress" in body["counts"]
    assert isinstance(body["diagnosis_runs"], list)
    assert isinstance(body["events"], list)

    # 未知项目 → 404（新旧端点一致）
    assert client.get("/api/v1/projects/nope/warroom").status_code == 404
    assert client.get("/api/v1/projects/nope").status_code == 404

    # 工作流端点（skeleton + 项目级状态）不破坏
    sk = client.get("/api/v1/workflow/skeleton").json()["steps"]
    assert len(sk) == 5
    wf = client.get(f"/api/v1/workflow/{pid}").json()
    assert wf["project_id"] == pid and len(wf["steps"]) == 5


def test_workflow_global_keeps_behavior(monkeypatch):
    """project_id 为空时保持原全局判定（兼容历史调用）"""
    from core.workflow import project_status, skeleton
    assert len(skeleton()) == 5
    st = project_status(None)
    assert len(st) == 5
    for s in st:
        assert {"key", "name", "done", "gate_passed", "evidence"} <= set(s)
