"""数据作战流测试（v3.0）：真实数据导入→清洗→质量→标注→评测集→知识库→断点续接→资产沉淀可检索

场景：非教学类真实数据 —— 制造业传感器 CSV / 零售库存 CSV。
语义去重用固定哈希向量替代 chromadb 嵌入，保证测试不依赖模型/网络（与 test_api.py 同法）。
"""

import hashlib
import io

import pytest
from fastapi.testclient import TestClient

from core.main import create_app

SENSOR_CSV_COLUMNS = ["sensor_id", "reading", "ts"]


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
def client():
    with TestClient(create_app()) as c:
        yield c


def _sensor_csv_bytes() -> bytes:
    """制造业传感器 CSV：10 条温度 + 2 条通用日志（整行 content 长度 100-120 → 双人分歧）
    + 1 条含 PII 的压力记录 + 1 条完全重复（字符级去重删除）"""
    lines = ["sensor_id,reading,ts"]
    for i in range(10):
        lines.append(f"S{i:03d},温度 {20 + i} 摄氏度,2026-08-29 0{i % 6}:00:00")
    # 整行 content = "S100 设备运行日志×13 2026-08-29 08:00:00"，长度 103（A 判"正常"/B 判"长文本" → 分歧）
    lines.append(f"S100,{'设备运行日志' * 13},2026-08-29 08:00:00")
    # 整行 content 长度 113，同样落入分歧带
    lines.append(f"S101,{'巡检排查异常日志' * 11},2026-08-29 09:00:00")
    # 含 PII 的压力记录（脱敏验证）
    lines.append("S999,压力 5.2 MPa 联系 13812345678,2026-08-29 10:00:00")
    # 完全重复（字符级去重应删除）
    lines.append("S001,温度 20 摄氏度,2026-08-29 00:00:00")
    return "\n".join(lines).encode("utf-8")


def _inventory_csv_path(tmp_path) -> str:
    """零售库存 CSV：写入临时文件，返回路径"""
    import csv
    path = tmp_path / "retail_inventory.csv"
    rows = []
    for i in range(15):
        rows.append({"sku": f"SKU-{i:04d}", "name": f"库存商品 商品编号{i}", "qty": i * 10,
                     "warehouse": f"仓库{chr(65 + i % 4)}"})
    for i in range(3):
        rows.append({"sku": "SKU-0000", "name": "库存商品 商品编号0", "qty": 0, "warehouse": "仓库A"})
    rows.append({"sku": "SKU-9999", "name": "订单记录 编号9999", "qty": 5, "warehouse": "仓库B"})
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sku", "name", "qty", "warehouse"])
        w.writeheader()
        w.writerows(rows)
    return str(path)


def test_dataprep_full_flow_api(client, patch_embed):
    """全链路：上传制造业传感器 CSV → 前三步自动 → 标注 → 评测集 → 知识库 → 断点续接 → 沉淀资产可检索 → 项目事件可见"""
    files = {"file": ("sensor_data.csv", io.BytesIO(_sensor_csv_bytes()), "text/csv")}
    r = client.post("/api/v1/dataprep/create", files=files,
                    data={"name": "制造业传感器预测性维护", "customer": "某汽车制造厂"})
    assert r.status_code == 200
    st = r.json()
    run_id = st["run_id"]
    assert st["status"] == "running"
    assert st["progress"] == 3 and st["progress_total"] == 6
    assert st["done_steps"] == ["import", "clean", "quality"]
    # 真实产物落盘
    for key in ("raw_data", "cleaned_data", "quality_report"):
        assert st["products"][key]["exists"] is True
    assert st["project_id"]  # 按客户自动建/复用项目
    assert st["source"] == "sensor_data.csv"

    # ---- 断点续接：先 get_state（模拟刷新），确认不丢 ----
    resumed = client.get(f"/api/v1/dataprep/{run_id}").json()
    assert resumed["progress"] == 3 and resumed["done_steps"] == ["import", "clean", "quality"]
    assert resumed["status"] == "running"

    # ---- 标注（双人一致性，应出现分歧） ----
    ann = client.post(f"/api/v1/dataprep/{run_id}/step", json={"step": "annotate", "sample_size": 30})
    assert ann.status_code == 200
    ann_body = ann.json()
    assert "annotate" in ann_body["done_steps"]
    ann_step = [s for s in ann_body["steps"] if s["step"] == "annotate"][0]
    assert ann_step["agreed"] + ann_step["disagreed"] == ann_step["total"]
    assert ann_step["disagreed"] >= 1  # 设备日志长度分歧

    # ---- 评测集 ----
    ev = client.post(f"/api/v1/dataprep/{run_id}/step", json={"step": "eval_set", "num_samples": 100})
    assert ev.status_code == 200
    assert "eval_set" in ev.json()["done_steps"]
    assert ev.json()["products"]["eval_set"]["exists"] is True

    # ---- 知识库 ----
    kb = client.post(f"/api/v1/dataprep/{run_id}/step", json={"step": "knowledge_base"})
    assert kb.status_code == 200
    assert kb.json()["status"] == "completed"
    assert kb.json()["progress"] == 6
    assert kb.json()["products"]["chunks"]["exists"] is True

    # ---- 断点续接：全部完成后 get_state 仍可恢复 ----
    final = client.get(f"/api/v1/dataprep/{run_id}").json()
    assert final["status"] == "completed"
    assert len(final["done_steps"]) == 6
    assert final["next_step"] is None

    # ---- 产物可下载（/artifacts 复用） ----
    dl = client.get(final["products"]["eval_set"]["url"])
    assert dl.status_code == 200
    assert len(dl.content) > 0

    # ---- 资产沉淀 + 可检索 ----
    dep = client.post(f"/api/v1/dataprep/{run_id}/deposit")
    assert dep.status_code == 200
    assert dep.json()["count"] >= 4
    asset_types = {a["asset_type"] for a in dep.json()["deposited"]}
    assert {"eval_set", "kb_chunks", "cleaning_rules", "quality_report"} <= asset_types

    q = client.get("/api/v1/cases/search?q=评测集")
    assert q.status_code == 200
    hits = [c for c in q.json()["cases"] if c.get("run_id") == run_id and c.get("asset_type") == "eval_set"]
    assert len(hits) >= 1
    assert hits[0]["payload_url"]  # asset.json 可下载
    pa = client.get(hits[0]["payload_url"])
    assert pa.status_code == 200

    # ---- 任务挂项目档案（project event 可见） ----
    proj = client.get(f"/api/v1/projects/{st['project_id']}").json()
    dpevents = [e for e in proj["events"] if e["type"] in ("dataprep", "dataprep_asset")]
    assert len(dpevents) >= 2
    assert any(e["ref"] == run_id for e in dpevents)

    # ---- 任务列表含该任务 ----
    runs = client.get("/api/v1/dataprep/runs").json()["runs"]
    assert any(x["run_id"] == run_id and x["status"] == "completed" and x["progress"] == 6 for x in runs)


def test_dataprep_retail_inventory_service_resume(tmp_path, patch_embed):
    """零售库存 CSV：服务级 start_task → get_state 续接 → run_next 顺序推进 → 资产检索（不同标签）"""
    from dataprep.service import continue_step, deposit, get_state, start_task

    path = _inventory_csv_path(tmp_path)
    st = start_task(name="零售库存盘点数据", source_path=path, customer="某连锁超市")
    run_id = st["run_id"]
    assert st["progress"] == 3
    assert st["source"].endswith("retail_inventory.csv")

    # 断点续接：get_state 后继续（模拟刷新/重连不丢）
    resumed = get_state(run_id)
    assert resumed["progress"] == 3
    assert resumed["next_step"] == "annotate"

    # run_next 顺序推进 3 步到完成
    s1 = continue_step(run_id, step=None)
    assert "annotate" in s1["done_steps"]
    s2 = continue_step(run_id, step=None)
    assert "eval_set" in s2["done_steps"]
    s3 = continue_step(run_id, step=None)
    assert s3["status"] == "completed" and s3["progress"] == 6

    # 已完成的步骤再 continue 不应重跑/报错
    s4 = continue_step(run_id, "knowledge_base")
    assert s4["status"] == "completed"

    # 资产沉淀 + 按标签检索（知识库分块 / 清洗规则）
    dep = deposit(run_id)
    assert dep["count"] >= 4

    from cases.archive import search_cases
    kb_hits = [c for c in search_cases(tags=["知识库分块"]) if c.get("run_id") == run_id]
    assert kb_hits, "知识库分块资产应可被 search_cases 按标签检索到"
    cr_hits = [c for c in search_cases(tags=["清洗规则"]) if c.get("run_id") == run_id]
    assert cr_hits, "清洗规则说明资产应可被 search_cases 按标签检索到"


def test_dataprep_rejects_non_csv_json(client):
    """数据作战流仅接受 csv/json（旧 data-prep/run 的 pdf 不支持）"""
    files = {"file": ("data.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}
    r = client.post("/api/v1/dataprep/create", files=files, data={"name": "x"})
    assert r.status_code == 400


def test_dataprep_json_upload(client, patch_embed):
    """JSON 数组真实数据也可导入"""
    import json as _json
    records = [{"sensor_id": f"J{i:03d}", "reading": f"温度 {20 + i} 摄氏度"} for i in range(8)]
    payload = _json.dumps(records, ensure_ascii=False).encode("utf-8")
    files = {"file": ("sensor_data.json", io.BytesIO(payload), "application/json")}
    r = client.post("/api/v1/dataprep/create", files=files, data={"name": "JSON 传感器数据"})
    assert r.status_code == 200
    st = r.json()
    assert st["progress"] == 3
    assert st["source"].endswith(".json")
    assert st["products"]["raw_data"]["exists"] is True
