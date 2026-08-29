"""可复用资产复用闭环 v6.0 测试（非教学场景：制造业 / 零售 / 物流）

覆盖：
- 注册表真实：register/list/get/search（按 kind/tags/customer/关键词）+ (kind,run_id) 幂等去重
- 自动带出真实：suggest 规则评分（关键词命中 + 同客户 + 同类资产 + 时间衰减 + reason）
- 注册挂接真实：mapping export / dataprep deposit 自动注册资产
- API 响应真实：mapping create / dataprep create / diagnosis start 返回 related_assets（不改旧字段）
- 一键接入真实：adopt mapping_config 预填新 run；adopt 数据资产复制 payload + 挂项目 asset_reuse 事件
LLM 全部打桩；ChromaDB 用确定性 fake 嵌入；注册表隔离到临时目录。
"""

import hashlib
import io

import pytest
from fastapi.testclient import TestClient

from core.main import create_app

# ---------- 基础 fixture ----------


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """把资产注册表指向临时文件，隔离各用例的注册数据"""
    import assets.archive as aa
    p = tmp_path / "registry.json"
    monkeypatch.setattr(aa, "REGISTRY_PATH", p)
    return p


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


class _FakeEF:
    """确定性 fake 嵌入函数（接受 list，返回 8 维哈希向量）"""
    name = "fake"

    def __call__(self, input):
        if isinstance(input, str):
            input = [input]
        return [_fake_embed(None, t) for t in input]


@pytest.fixture
def retrieval_iso(monkeypatch, tmp_path):
    """隔离 retrieval 的 ChromaDB 目录 + 索引档案目录 + 默认嵌入函数"""
    import retrieval.service as rs
    fake_ef = _FakeEF()
    monkeypatch.setattr(rs, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(rs, "RETRIEVAL_ROOT", tmp_path / "retrieval")
    monkeypatch.setattr(rs, "_client_instance", None)
    monkeypatch.setattr(rs, "_get_ef", lambda embedding_function=None: fake_ef)
    return fake_ef


# ---------- 打桩：mapping 初判 LLM ----------


def _mapping_fake_llm(create_mappings):
    def fake_llm(system, user):
        if "校验" in system:
            return {"verdict": "pass", "reason": "测试打桩"}
        return {"mappings": create_mappings, "notes": "测试初判"}
    return fake_llm


MAPPING_SOURCE = [
    {"name": "equipment_id", "sample": "E001"}, {"name": "equip_name", "sample": "设备1"},
    {"name": "temp", "sample": "温度 21 摄氏度"}, {"name": "pressure", "sample": "1.1 MPa"},
]
MAPPING_TARGET = [
    {"name": "device_id", "sample": "E001"}, {"name": "device_name", "sample": "设备1"},
    {"name": "temperature", "sample": "温度 21 摄氏度"}, {"name": "pressure_value", "sample": "1.1 MPa"},
]
MAPPING_PREFILL = [
    {"target": "device_id", "source": "equipment_id", "rule": "direct", "expression": "equipment_id", "confidence": "high"},
    {"target": "device_name", "source": "equip_name", "rule": "direct", "expression": "equip_name", "confidence": "high"},
    {"target": "temperature", "source": "temp", "rule": "direct", "expression": "temp", "confidence": "high"},
    {"target": "pressure_value", "source": "pressure", "rule": "direct", "expression": "pressure", "confidence": "high"},
]


# ---------- 1. 注册表：注册/列表/检索/建议（规则评分） ----------


def test_assets_register_list_search_suggest(registry):
    """注册表真实：register/list/get/search + 幂等去重 + suggest 规则评分（非教学场景：制造业/零售）"""
    from assets.archive import get_asset, list_assets, register_asset, search_assets
    from assets.service import suggest

    a1 = register_asset(
        kind="mapping_config", title="字段映射配置 · 制造业设备字段映射",
        summary="设备传感器源→目标字段映射，4 条规则", tags=["字段映射", "制造业"],
        origin={"run_id": "m1", "module": "mapping"}, customer="某汽车制造厂",
        payload_url="/artifacts/mapping/m1/adapter/mapping_config.json", payload_path="/tmp/m1/config.json",
        meta={"source_fields": MAPPING_SOURCE, "target_fields": MAPPING_TARGET, "mapping_count": 4},
    )
    a2 = register_asset(
        kind="eval_set", title="评测集 · 零售库存盘点",
        summary="零售库存清洗后构建的评测集", tags=["数据准备", "评测集", "零售"],
        origin={"run_id": "d1", "module": "dataprep"}, customer="某连锁超市",
        payload_url="/artifacts/cases/c1/asset.json", payload_path="/tmp/d1/eval_set.json",
        meta={"sample_count": 10},
    )

    # 幂等：同一 (kind, run_id) 重复注册返回既有条目（同一 asset_id）
    a1_dup = register_asset(
        kind="mapping_config", title="再注册一次", summary="x", tags=[],
        origin={"run_id": "m1", "module": "mapping"}, customer="某汽车制造厂",
    )
    assert a1_dup["asset_id"] == a1["asset_id"]
    assert len(list_assets()) == 2

    # 按 kind 过滤
    assert [a["asset_id"] for a in list_assets(kind="mapping_config")] == [a1["asset_id"]]
    # 按关键词检索
    assert search_assets(q="设备")[0]["asset_id"] == a1["asset_id"]
    assert search_assets(q="零售")[0]["asset_id"] == a2["asset_id"]
    # 按标签检索（全部命中）
    assert search_assets(tags=["字段映射"])[0]["asset_id"] == a1["asset_id"]
    assert search_assets(tags=["字段映射", "制造业"])[0]["asset_id"] == a1["asset_id"]
    # 按客户检索
    assert search_assets(customer="某连锁超市")[0]["asset_id"] == a2["asset_id"]
    # get_asset
    assert get_asset(a1["asset_id"])["kind"] == "mapping_config"
    # 未知 kind 拒绝
    with pytest.raises(ValueError):
        register_asset(kind="nonsense", title="x", summary="x", tags=[], origin={"run_id": "r"})

    # ---- suggest 规则评分 ----
    sug = suggest(query="设备字段映射", kinds=["mapping_config"], customer="某汽车制造厂", top_k=5)
    assert sug, "应建议出匹配的映射配置资产"
    top = sug[0]
    assert top["asset"]["asset_id"] == a1["asset_id"]
    assert top["score"] > 0
    assert "同客户" in top["reason"]
    # eval_set 不匹配 kinds 过滤 → 不出现在建议里
    assert all(s["asset"]["kind"] == "mapping_config" for s in sug)
    # 无信号的查询 → 空建议
    assert suggest(query="完全无关的主题词xyz", kinds=["mapping_config"], customer="") == []


# ---------- 2. 注册挂接：mapping export ----------


def test_assets_mapping_export_registers(registry, client, monkeypatch):
    """mapping export 成功后自动注册 kind=mapping_config 资产（meta 含源/目标字段 + 映射数）"""
    import mapping.service as ms
    monkeypatch.setattr(ms, "_default_json_call", _mapping_fake_llm(MAPPING_PREFILL))

    r = client.post("/api/v1/mapping/create", json={
        "name": "制造业设备字段映射",
        "source_fields": MAPPING_SOURCE, "target_fields": MAPPING_TARGET,
        "customer": "某汽车制造厂",
    })
    run_id = r.json()["run_id"]

    exp = client.post(f"/api/v1/mapping/{run_id}/export", json={})
    assert exp.status_code == 200
    assert exp.json()["asset"]["kind"] == "mapping_config"
    asset_id = exp.json()["asset"]["asset_id"]

    from assets.archive import get_asset
    asset = get_asset(asset_id)
    assert asset["origin"]["run_id"] == run_id
    assert asset["origin"]["module"] == "mapping"
    assert asset["meta"]["mapping_count"] == 4
    # 总工程师 v6.0 审查修复：mapping 存档必须持久化 customer，否则注册资产的「同客户」信号失效
    assert asset["customer"] == "某汽车制造厂"
    assert asset["meta"]["source_fields"] == MAPPING_SOURCE
    assert asset["payload_url"] == f"/artifacts/mapping/{run_id}/adapter/mapping_config.json"
    # payload 真实可读
    import json as _json
    with open(asset["payload_path"], "r", encoding="utf-8") as f:
        cfg = _json.load(f)
    assert len(cfg["mappings"]) == 4

    # 重复 export 幂等：同 asset_id
    exp2 = client.post(f"/api/v1/mapping/{run_id}/export", json={})
    assert exp2.json()["asset"]["asset_id"] == asset_id


# ---------- 3. 注册挂接：dataprep deposit ----------


def test_assets_dataprep_deposit_registers(client, registry, patch_embed, retrieval_iso):
    """dataprep deposit 自动注册 4 类资产（eval_set/kb_chunks/cleaning_rules/quality_report）"""
    lines = ["sensor_id,reading,ts"]
    for i in range(6):
        lines.append(f"S{i:03d},温度 {20 + i} 摄氏度,2026-08-29 0{i % 6}:00:00")
    files = {"file": ("sensor.csv", io.BytesIO("\n".join(lines).encode("utf-8")), "text/csv")}
    r = client.post("/api/v1/dataprep/create", files=files, data={"name": "制造业传感器", "customer": "某汽车制造厂"})
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    # 推进到 评测集 + 知识库
    assert client.post(f"/api/v1/dataprep/{run_id}/step", json={"step": "eval_set"}).status_code == 200
    assert client.post(f"/api/v1/dataprep/{run_id}/step", json={"step": "knowledge_base"}).status_code == 200

    dep = client.post(f"/api/v1/dataprep/{run_id}/deposit")
    assert dep.status_code == 200
    assert dep.json()["count"] >= 4

    from assets.archive import list_assets
    assets = list_assets()
    kinds = {a["kind"] for a in assets}
    assert {"eval_set", "kb_chunks", "cleaning_rules", "quality_report"} <= kinds
    assert all(a["origin"]["run_id"] == run_id for a in assets)
    assert all(a["payload_url"].startswith("/artifacts/cases/") for a in assets)


# ---------- 4. 自动带出：三个创建入口返回 related_assets ----------


def test_assets_related_on_mapping_create(client, registry, monkeypatch):
    """mapping create 响应新增 related_assets（旧字段不破坏），能带出同字段映射配置"""
    import mapping.service as ms
    monkeypatch.setattr(ms, "_default_json_call", _mapping_fake_llm(MAPPING_PREFILL))

    # 先注册一条历史映射配置资产（制造业设备字段映射）
    from assets.archive import register_asset
    register_asset(
        kind="mapping_config", title="字段映射配置 · 制造业设备字段映射",
        summary="equipment_id equip_name temp pressure 映射", tags=["字段映射"],
        origin={"run_id": "old1", "module": "mapping"}, customer="某汽车制造厂",
        payload_url="/artifacts/mapping/old1/adapter/mapping_config.json", payload_path="",
        meta={"source_fields": MAPPING_SOURCE, "target_fields": MAPPING_TARGET, "mapping_count": 4},
    )

    r = client.post("/api/v1/mapping/create", json={
        "name": "制造业设备字段映射",
        "source_fields": MAPPING_SOURCE, "target_fields": MAPPING_TARGET,
        "customer": "某汽车制造厂",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"]
    assert "related_assets" in body
    rel = body["related_assets"]
    assert isinstance(rel, list)
    # 同字段映射配置被建议带出
    assert any(s["asset"]["kind"] == "mapping_config" for s in rel)


def test_assets_related_on_dataprep_create(client, registry, patch_embed):
    """dataprep create 响应新增 related_assets，能带出同客户清洗规则/评测集资产"""
    from assets.archive import register_asset
    register_asset(
        kind="cleaning_rules", title="清洗规则说明 · 零售库存",
        summary="字符去重/语义去重/归一化/脱敏", tags=["数据准备", "清洗规则"],
        origin={"run_id": "d9", "module": "dataprep"}, customer="某连锁超市",
        payload_url="/artifacts/cases/c9/asset.json", payload_path="",
    )

    lines = ["sku,name,qty"]
    lines += [f"SKU-{i:04d},库存商品{i},{i * 10}" for i in range(8)]
    files = {"file": ("inventory.csv", io.BytesIO("\n".join(lines).encode("utf-8")), "text/csv")}
    r = client.post("/api/v1/dataprep/create", files=files,
                    data={"name": "零售库存盘点数据", "customer": "某连锁超市"})
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"]
    assert "related_assets" in body
    rel = body["related_assets"]
    # 同客户清洗规则资产应被带出（同客户 + 同类资产信号）
    assert any(s["asset"]["kind"] == "cleaning_rules" for s in rel)
    assert all("reason" in s and "score" in s for s in rel)


def test_assets_related_on_diagnosis_start(client, registry, monkeypatch):
    """diagnosis start 保留 related_cases 并新增 related_assets（不改旧字段/旧行为）"""
    import diagnosis.agents as agents

    def fake_diag_llm(system, user):
        if "Critic" in system or "盲审" in system:
            return {"dimension_scores": {k: 2 for k in agents.DIMENSIONS},
                    "reasons": {k: "critic" for k in agents.DIMENSIONS}, "summary": "critic"}
        return {"dimension_scores": {k: 4 for k in agents.DIMENSIONS},
                "reasons": {k: "gen" for k in agents.DIMENSIONS}, "summary": "gen",
                "clarification_questions": []}

    monkeypatch.setattr(agents, "_default_json_call", fake_diag_llm)

    from assets.archive import register_asset
    register_asset(
        kind="diagnosis_plan", title="基于知识库的问答系统 诊断方案",
        summary="五维评估结论", tags=["诊断方案"], customer="某客户",
        origin={"run_id": "dg1", "module": "diagnosis"},
        payload_url="/api/v1/cases/c1/render.html", payload_path="",
        meta={"version": "v1", "total_score": 18},
    )

    r = client.post("/api/v1/diagnosis/start", json={"requirement": "基于知识库的问答系统"})
    assert r.status_code == 200
    body = r.json()
    # 旧契约不破坏：related_cases 保留 + 核心字段不变
    assert "related_cases" in body and isinstance(body["related_cases"], list)
    assert "generator" in body and "critic" in body and "confidence" in body
    # 新字段：related_assets
    assert "related_assets" in body
    assert any(s["asset"]["kind"] == "diagnosis_plan" for s in body["related_assets"])


# ---------- 5. 一键接入：mapping_config 预填新 run ----------


def test_assets_adopt_mapping_config_creates_prefilled_run(client, registry, monkeypatch):
    """adopt mapping_config：读历史映射 → 预填新 mapping run（draft，可续做）+ 挂 asset_reuse 事件"""
    import mapping.service as ms
    from mapping.service import create_mapping, export_mapping, get_mapping

    monkeypatch.setattr(ms, "_default_json_call", _mapping_fake_llm(MAPPING_PREFILL))

    # 先造一条历史映射并导出（导出即注册资产）
    old = create_mapping("历史设备字段映射", MAPPING_SOURCE, MAPPING_TARGET,
                         prefill_mappings=MAPPING_PREFILL, customer="某汽车制造厂")
    old_id = old["run_id"]
    exp = export_mapping(old_id)
    asset_id = exp["asset"]["asset_id"]

    # 一键接入：新客户/新项目
    r = client.post(f"/api/v1/assets/{asset_id}/adopt", json={"customer": "某新客户"})
    assert r.status_code == 200
    body = r.json()
    new_run_id = body["run_id"]
    assert body["prefilled_from_asset"] == asset_id
    assert len(body["mappings"]) == 4

    # 新 run 真实预填历史映射，状态 draft，可继续导入样例/校验
    # 注：mapping_config.json（adapter 契约）只含 target/source/rule/expression，不含 confidence
    new_run = get_mapping(new_run_id)
    assert new_run["status"] == "draft"
    expected = [{"target": m["target"], "source": m["source"], "rule": m["rule"], "expression": m["expression"]}
                for m in MAPPING_PREFILL]
    assert new_run["mappings"] == expected
    assert new_run["project_id"]  # 按客户自动建项目

    # 项目事件 asset_reuse 已挂
    from projects.archive import get_project
    proj = get_project(new_run["project_id"])
    evs = [e for e in proj["events"] if e["type"] == "asset_reuse"]
    assert any(e["ref"] == new_run_id for e in evs)


# ---------- 6. 一键接入：数据资产复制 + 项目事件 ----------


def test_assets_adopt_data_asset_writes_to_run(client, registry, patch_embed):
    """adopt eval_set：给 target_run_id → payload 写入该 run 的 products（可继续用）+ 挂项目事件"""
    import json as _json
    import tempfile
    from pathlib import Path

    from assets.archive import register_asset
    from dataprep.archive import load_run, products_dir
    from dataprep.service import start_task

    # 造一条 eval_set 资产（payload 落临时文件）
    tmpdir = Path(tempfile.mkdtemp())
    payload_path = tmpdir / "eval_set.json"
    _json.dump({"eval_set": [{"instruction": "x", "output": "y"}]}, open(payload_path, "w", encoding="utf-8"))
    asset = register_asset(
        kind="eval_set", title="评测集 · 零售库存", summary="可复用评测集", tags=["评测集"],
        origin={"run_id": "ds1", "module": "dataprep"}, customer="某连锁超市",
        payload_url="/artifacts/cases/ds1/asset.json", payload_path=str(payload_path),
        meta={"sample_count": 1},
    )

    # 目标 dataprep run（真实创建）
    import csv as _csv
    path = tmpdir / "inventory.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["sku", "name", "qty"])
        for i in range(5):
            w.writerow([f"SKU-{i:04d}", f"库存商品{i}", i * 10])
    st = start_task(name="新零售盘点", source_path=str(path), customer="某新零售客户")
    target_run = st["run_id"]

    # 一键接入（带 target_run_id + customer）
    r = client.post(f"/api/v1/assets/{asset['asset_id']}/adopt",
                    json={"customer": "某新零售客户", "target_run_id": target_run})
    assert r.status_code == 200
    body = r.json()
    assert body["adopted"] is True
    assert body["kind"] == "eval_set"
    assert body["target_run_id"] == target_run
    assert body["written_path"]

    # payload 真实写入目标 run 的 products
    run = load_run(target_run)
    filename = run["products"].get("reused_eval_set")
    assert filename and (products_dir(target_run) / filename).exists()
    with open(products_dir(target_run) / filename, "r", encoding="utf-8") as f:
        assert _json.load(f)["eval_set"][0]["instruction"] == "x"

    # 项目 asset_reuse 事件可见
    from projects.archive import get_project
    proj = get_project(body["project_id"])
    evs = [e for e in proj["events"] if e["type"] == "asset_reuse"]
    assert any(e["ref"] == target_run for e in evs)


def test_assets_adopt_data_asset_without_run_registers_ref(client, registry):
    """adopt 数据资产未给 target_run_id → 仅登记为项目资产引用（asset_reuse 事件，不造假数据）"""
    import tempfile
    from pathlib import Path

    from assets.archive import register_asset

    tmpdir = Path(tempfile.mkdtemp())
    payload_path = tmpdir / "cleaning.json"
    payload_path.write_text("{}", encoding="utf-8")
    asset = register_asset(
        kind="cleaning_rules", title="清洗规则 · 物流订单", summary="清洗方案", tags=["清洗规则"],
        origin={"run_id": "l1", "module": "dataprep"}, customer="某物流公司",
        payload_url="/artifacts/cases/l1/asset.json", payload_path=str(payload_path),
    )

    r = client.post(f"/api/v1/assets/{asset['asset_id']}/adopt", json={"customer": "某新物流客户"})
    assert r.status_code == 200
    body = r.json()
    assert body["written_path"] is None  # 未给 target_run_id → 不复制 payload
    assert "项目资产引用" in body["note"]

    from projects.archive import get_project
    proj = get_project(body["project_id"])
    assert any(e["type"] == "asset_reuse" for e in proj["events"])


# ---------- 7. 通用检索端点 ----------


def test_assets_api_list_search_get(client, registry):
    """GET /assets/list + /assets/search + /assets/{id} 可用"""
    from assets.archive import register_asset
    a = register_asset(
        kind="kb_chunks", title="知识库分块 · 设备运维手册", summary="可复用分块", tags=["知识库分块"],
        origin={"run_id": "kb1", "module": "dataprep"}, customer="某设备厂",
        payload_url="/artifacts/cases/kb1/asset.json", payload_path="",
    )

    lst = client.get("/api/v1/assets/list").json()["assets"]
    assert any(x["asset_id"] == a["asset_id"] for x in lst)
    lst_kind = client.get("/api/v1/assets/list?kind=kb_chunks").json()["assets"]
    assert all(x["kind"] == "kb_chunks" for x in lst_kind)

    sr = client.get("/api/v1/assets/search?q=运维手册").json()["assets"]
    assert any(x["asset_id"] == a["asset_id"] for x in sr)
    sr2 = client.get("/api/v1/assets/search?kinds=kb_chunks&customer=某设备厂").json()["assets"]
    assert any(x["asset_id"] == a["asset_id"] for x in sr2)

    got = client.get(f"/api/v1/assets/{a['asset_id']}").json()
    assert got["kind"] == "kb_chunks"

    # 未知资产 → 404
    assert client.get("/api/v1/assets/nope").status_code == 404
