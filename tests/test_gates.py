"""门禁硬化测试（v10.0）：质量门禁从「展示」变「真阻断」

非教学场景：制造业传感器 CSV（数据作战流真实清洗+质量评估）。
隔离：diagnosis / dataprep / cases / projects 档案根目录全部指向 tmp（不污染真实 tmp/web/）。
语义去重打桩固定哈希向量（不联网）；LLM 全部打桩（原型 qa_agent / 文档包 core.llm.chat）。
旧接口不破坏：旧调用（不传 project_id / 不传 confirmed）行为不变。
"""

import hashlib

import pytest
from fastapi.testclient import TestClient

from core.main import create_app


def _fake_embed(self, text):
    """固定哈希向量替代 chromadb 默认嵌入（确定性，不联网）"""
    return [
        float(int(hashlib.md5((text + str(i)).encode("utf-8")).hexdigest(), 16) % 1000) / 1000.0
        for i in range(8)
    ]


@pytest.fixture
def patch_embed(monkeypatch):
    import data_prep.cleaning.semantic_dedup as sd
    monkeypatch.setattr(sd.SemanticDeduplicator, "_embed_text", _fake_embed)


@pytest.fixture
def isolated_roots(tmp_path, monkeypatch):
    """隔离全部档案根目录，避免测试污染真实 tmp/web/"""
    import diagnosis.archive as da
    import dataprep.archive as dpa
    import cases.archive as ca
    import projects.archive as pa

    da_root = tmp_path / "web" / "diagnosis"; da_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(da, "ARCHIVE_ROOT", da_root)

    dp_root = tmp_path / "web" / "dataprep"; dp_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dpa, "ARCHIVE_ROOT", dp_root)

    cs_root = tmp_path / "web" / "cases"; cs_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ca, "CASES_ROOT", cs_root)

    pj_root = tmp_path / "web" / "projects"; pj_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pa, "PROJECTS_ROOT", pj_root)
    return da_root, dp_root, cs_root, pj_root


@pytest.fixture
def client(isolated_roots):
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def no_pdf(monkeypatch):
    """禁用 PDF 生成（避免测试触发 Chrome），回退 HTML 即可"""
    import cases.render as cr
    monkeypatch.setattr(cr, "render_html_to_pdf", lambda html, path: False)


def _sensor_csv_path(tmp_path) -> str:
    """制造业传感器 CSV：8 条温度 + 1 条含 PII 的压力记录"""
    path = tmp_path / "sensor.csv"
    lines = ["sensor_id,reading,ts"]
    for i in range(8):
        lines.append(f"S{i:03d},温度 {20 + i} 摄氏度,2026-08-29 0{i % 6}:00:00")
    lines.append("S100,压力 5.2 MPa 联系 13812345678,2026-08-29 10:00:00")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines))
    return str(path)


def _make_dataprep_run(tmp_path, project_id=None):
    """跑一个真实数据作战流任务（自动前三步 → quality_report 产物存在），返回 run_id"""
    from dataprep.service import start_task
    path = _sensor_csv_path(tmp_path)
    st = start_task(name="制造业传感器预测性维护", source_path=path,
                    project_id=project_id, customer="某汽车制造厂")
    assert st["products"]["quality_report"]["exists"] is True
    return st["run_id"], st


def _make_confirmed_diagnosis(pid=None):
    """直接建一个已定稿确认的诊断档案（不依赖 LLM），返回 run_id"""
    from diagnosis.archive import create_run, new_run_id, update_run
    rid = new_run_id()
    create_run(rid, {"requirement": "基于知识库的问答系统"})
    update_run(rid, confirmed=True, project_id=pid, report={
        "version": "v1",
        "customer_name": "某客户",
        "requirement": "基于知识库的问答系统",
        "final_conclusion": {"total_score": 18, "conclusion": "推荐试点"},
    })
    return rid


# ---------- A. 门禁判定 gate_check（服务层） ----------


def test_gate_check_project_mode(isolated_roots, patch_embed, tmp_path):
    """gate_check 基于真实档案判定（非写死）：无数据/无确认诊断 → 未过；有产物 → 通过"""
    from core.workflow import gate_check
    from projects.archive import create_project

    pid = create_project("测试项目", "某客户")["project_id"]

    # 无数据任务 → data_prep 未过，reason 诚实
    g = gate_check("data_prep", pid)
    assert g["allowed"] is False
    assert "数据未达标" in g["reason"]

    # 无已确认诊断 → diagnosis 未过
    g2 = gate_check("diagnosis", pid)
    assert g2["allowed"] is False
    assert "人工确认" in g2["reason"]

    # 建好数据任务（quality_report 产物在）→ data_prep 通过
    _make_dataprep_run(tmp_path, project_id=pid)
    g3 = gate_check("data_prep", pid)
    assert g3["allowed"] is True
    assert any("质量报告产物" in e for e in g3["evidence"])

    # 建已确认诊断 + 文档包 → diagnosis 与 deliver 通过
    _make_confirmed_diagnosis(pid)
    from cases.archive import new_case_id, save_case
    cid = new_case_id()
    save_case(cid, {"case_id": cid, "source_type": "doc_package",
                    "project_id": pid, "title": "文档包", "summary": "", "tags": []})
    g4 = gate_check("diagnosis", pid)
    assert g4["allowed"] is True
    g5 = gate_check("deliver", pid)
    assert g5["allowed"] is True
    assert "文档包需人工确认" == g5["reason"]

    # 未知阶段诚实报错
    with pytest.raises(ValueError):
        gate_check("no_such_stage", pid)


def test_gate_check_global_mode(isolated_roots, patch_embed, tmp_path):
    """全局判定：全局有 quality_report 产物 → data_prep 允许，reason 注明「全局判定」"""
    from core.workflow import gate_check
    _make_dataprep_run(tmp_path)  # project_id=None
    g = gate_check("data_prep", None)
    assert g["allowed"] is True
    assert "全局判定" in g["reason"]


def test_project_status_gate_alignment(isolated_roots, patch_embed, tmp_path):
    """project_status 的 gate_passed 对齐 gate_check，且附 gate_reason（只增字段）"""
    from core.workflow import project_status
    from projects.archive import create_project

    pid = create_project("测试项目", "某客户")["project_id"]
    _make_confirmed_diagnosis(pid)
    from cases.archive import new_case_id, save_case
    cid = new_case_id()
    save_case(cid, {"case_id": cid, "source_type": "doc_package",
                    "project_id": pid, "title": "文档包", "summary": "", "tags": []})

    st = {s["key"]: s for s in project_status(pid)}
    # 结构完整（旧字段 + 新增 gate_reason）
    for s in st.values():
        assert {"key", "name", "done", "gate_passed", "gate_reason", "evidence"} <= set(s)
    # deliver 门禁通过（有已确认诊断 + 文档包）
    assert st["deliver"]["gate_passed"] is True
    assert st["deliver"]["gate_reason"] == "文档包需人工确认"
    # data_prep 无数据任务 → 未过
    assert st["data_prep"]["gate_passed"] is False
    assert "数据未达标" in st["data_prep"]["gate_reason"]


# ---------- B1. /prototype/run 数据门禁真阻断 ----------


def test_prototype_run_blocked_no_data(client, isolated_roots, monkeypatch):
    """无达标数据的项目跑原型 → 403 + gate_reason"""
    import prototype_assembler.templates.qa_agent as qa
    monkeypatch.setattr(qa, "_qa_llm_call", lambda agent, ctx, u: "finish: 测试回答")
    from projects.archive import create_project
    pid = create_project("测试项目", "某客户")["project_id"]

    r = client.post("/api/v1/prototype/run", json={
        "template": "knowledge_qa", "user_input": "什么是RAG？", "project_id": pid})
    assert r.status_code == 403
    body = r.json()
    assert body["detail"]["gate_reason"] and "数据未达标" in body["detail"]["gate_reason"]
    assert body["detail"]["stage"] == "data_prep"


def test_prototype_run_allowed_with_quality_report(tmp_path, client, isolated_roots, patch_embed, monkeypatch):
    """有 dataprep run（quality_report 产物在）的项目 → 200 + gate.checked true + allowed true"""
    import prototype_assembler.templates.qa_agent as qa
    monkeypatch.setattr(qa, "_qa_llm_call", lambda agent, ctx, u: "finish: 测试回答")
    from projects.archive import create_project
    pid = create_project("测试项目", "某客户")["project_id"]
    _make_dataprep_run(tmp_path, project_id=pid)

    r = client.post("/api/v1/prototype/run", json={
        "template": "knowledge_qa", "user_input": "什么是RAG？", "project_id": pid})
    assert r.status_code == 200
    body = r.json()
    assert body["result"] == "测试回答"
    assert body["gate"] == {"checked": True, "allowed": True, "reason": "数据未达标不进原型（缺少质量评估）"}
    assert "gate_override" not in body


def test_prototype_run_force_override(client, isolated_roots, monkeypatch):
    """force=true → 200 + gate_override true + gate_reason 诚实记录"""
    import prototype_assembler.templates.qa_agent as qa
    monkeypatch.setattr(qa, "_qa_llm_call", lambda agent, ctx, u: "finish: 测试回答")
    from projects.archive import create_project
    pid = create_project("测试项目", "某客户")["project_id"]

    r = client.post("/api/v1/prototype/run", json={
        "template": "knowledge_qa", "user_input": "什么是RAG？", "project_id": pid, "force": True})
    assert r.status_code == 200
    body = r.json()
    assert body["gate_override"] is True
    assert "数据未达标" in body["gate_reason"]
    assert body["gate"] == {"checked": True, "allowed": False, "reason": "数据未达标不进原型（缺少质量评估）"}


def test_prototype_run_without_project_not_blocked(client, isolated_roots, monkeypatch):
    """未传 project_id → 不拦 + gate.checked false（旧调用行为不变）"""
    import prototype_assembler.templates.qa_agent as qa
    monkeypatch.setattr(qa, "_qa_llm_call", lambda agent, ctx, u: "finish: 测试回答")

    r = client.post("/api/v1/prototype/run", json={
        "template": "knowledge_qa", "user_input": "什么是RAG？"})
    assert r.status_code == 200
    assert r.json()["gate"] == {"checked": False}
    assert "gate_override" not in r.json()


# ---------- B2. /cropper/from-diagnosis 确认门禁真阻断 ----------


def test_cropper_from_diagnosis_blocked_unconfirmed(client, isolated_roots):
    """未确认诊断 → /cropper/from-diagnosis 400（禁止据此裁剪发客户）"""
    from diagnosis.archive import create_run, new_run_id
    rid = new_run_id()
    create_run(rid, {"requirement": "基于知识库的问答系统"})

    r = client.get(f"/api/v1/cropper/from-diagnosis/{rid}")
    assert r.status_code == 400
    assert "诊断未定稿确认" in r.json()["detail"]


def test_cropper_from_diagnosis_allowed_confirmed(client, isolated_roots):
    """已确认诊断 → /cropper/from-diagnosis 200"""
    rid = _make_confirmed_diagnosis()
    r = client.get(f"/api/v1/cropper/from-diagnosis/{rid}")
    assert r.status_code == 200
    assert r.json()["diagnosis_context"]["run_id"] == rid
    assert r.json()["plan"]["enabled_modules"]


# ---------- B3. /cases/create-doc-package 文档包确认门禁真阻断 ----------


def test_doc_package_blocked_without_confirmation(client, isolated_roots, no_pdf):
    """文档包无确认（项目无已确认诊断）→ 400"""
    from projects.archive import create_project
    pid = create_project("测试项目", "某客户")["project_id"]

    r = client.post("/api/v1/cases/create-doc-package", json={
        "run_id": None, "project_id": pid, "sections": ["架构说明"]})
    assert r.status_code == 400
    assert "文档包需人工确认" in r.json()["detail"]


def test_doc_package_allowed_with_confirmed(client, isolated_roots, monkeypatch, no_pdf):
    """文档包 confirmed=true → 200，响应附 gate 结果（confirmation=request_confirmed）"""
    import core.llm as llm
    monkeypatch.setattr(llm, "chat", lambda system, user, **kw:
                        '{"sections": {"架构说明": "## 架构\\n内容"}}')
    from projects.archive import create_project
    pid = create_project("测试项目", "某客户")["project_id"]

    r = client.post("/api/v1/cases/create-doc-package", json={
        "run_id": None, "project_id": pid, "sections": ["架构说明"], "confirmed": True})
    assert r.status_code == 200
    body = r.json()
    assert body["gate"]["checked"] is True
    assert body["gate"]["allowed"] is True
    assert body["gate"]["confirmation"] == "request_confirmed"


def test_doc_package_allowed_with_confirmed_diagnosis(client, isolated_roots, monkeypatch, no_pdf):
    """项目已有已确认诊断 → 文档包无需再确认 → 200，confirmation=confirmed_diagnosis"""
    import core.llm as llm
    monkeypatch.setattr(llm, "chat", lambda system, user, **kw:
                        '{"sections": {"架构说明": "## 架构\\n内容"}}')
    from projects.archive import create_project
    pid = create_project("测试项目", "某客户")["project_id"]
    _make_confirmed_diagnosis(pid)

    r = client.post("/api/v1/cases/create-doc-package", json={
        "run_id": None, "project_id": pid, "sections": ["架构说明"]})
    assert r.status_code == 200
    body = r.json()
    assert body["gate"]["confirmation"] == "confirmed_diagnosis"
    # 生成的文档包应带 project_id（供后续 deliver 门禁判定）
    assert body["project_id"] == pid


def test_doc_package_allowed_with_confirmed_diagnosis_via_run(client, isolated_roots, monkeypatch, no_pdf):
    """只传 run_id（其档案带 project_id）→ 门禁按该项目判定，无需再确认 → 200"""
    import core.llm as llm
    monkeypatch.setattr(llm, "chat", lambda system, user, **kw:
                        '{"sections": {"架构说明": "## 架构\\n内容"}}')
    from projects.archive import create_project
    pid = create_project("测试项目", "某客户")["project_id"]
    rid = _make_confirmed_diagnosis(pid)

    r = client.post("/api/v1/cases/create-doc-package", json={
        "run_id": rid, "project_id": None, "sections": ["架构说明"]})
    assert r.status_code == 200
    assert r.json()["gate"]["confirmation"] == "confirmed_diagnosis"


# ---------- B4. /diagnosis/finalize 强制 confirmed 回归 ----------


def test_finalize_requires_confirmed(client, isolated_roots):
    """/diagnosis/finalize 未 confirmed → 400（回归：既有强制不破坏）"""
    from diagnosis.archive import create_run, new_run_id
    rid = new_run_id()
    create_run(rid, {"requirement": "x"})
    r = client.post("/api/v1/diagnosis/finalize", json={"run_id": rid, "confirmed": False})
    assert r.status_code == 400
    assert "人工确认" in r.json()["detail"]


# ---------- 前端门禁状态端点 /workflow/gate ----------


def test_workflow_gate_endpoint(client, isolated_roots):
    """GET /workflow/gate 返回 gate_check 结果；未知阶段 400"""
    from projects.archive import create_project
    pid = create_project("测试项目", "某客户")["project_id"]

    r = client.get(f"/api/v1/workflow/gate?stage=data_prep&project_id={pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["allowed"] is False and "数据未达标" in body["reason"]

    r2 = client.get("/api/v1/workflow/gate?stage=no_such_stage")
    assert r2.status_code == 400
