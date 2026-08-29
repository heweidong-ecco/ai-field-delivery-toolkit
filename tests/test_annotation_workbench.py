"""人工双人标注工作台测试（v9.0）：from-dataprep 建任务 / 双人标注一致性 / 分歧检出与改判 / list_tasks / API 全链路

场景：非教学类真实数据 —— 制造业传感器 CSV（进数据作战流清洗后作为标注样本源）。
隔离：annotation ANN_ROOT 与 dataprep ARCHIVE_ROOT 均指向 tmp（不污染真实档案）。
语义去重用固定哈希向量替代 chromadb 嵌入（与 test_dataprep.py 同法，不联网）。
"""

import csv
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
    """隔离标注与数据作战流档案目录，避免测试污染真实 tmp/web/"""
    import annotation.service as ann
    import dataprep.archive as dpa

    ann_root = tmp_path / "web" / "annotation"
    ann_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ann, "ANN_ROOT", ann_root)

    dp_root = tmp_path / "web" / "dataprep"
    dp_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dpa, "ARCHIVE_ROOT", dp_root)
    return ann_root, dp_root


@pytest.fixture
def client(isolated_roots):
    with TestClient(create_app()) as c:
        yield c


def _sensor_csv_path(tmp_path) -> str:
    """制造业传感器 CSV：10 条温度 + 2 条设备日志（长度 100-120 → 双人规则分歧带）+ 1 条压力 PII"""
    path = tmp_path / "sensor.csv"
    lines = ["sensor_id,reading,ts"]
    for i in range(10):
        lines.append(f"S{i:03d},温度 {20 + i} 摄氏度,2026-08-29 0{i % 6}:00:00")
    lines.append(f"S100,{'设备运行日志' * 13},2026-08-29 08:00:00")
    lines.append(f"S101,{'巡检排查异常日志' * 11},2026-08-29 09:00:00")
    lines.append("S999,压力 5.2 MPa 联系 13812345678,2026-08-29 10:00:00")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines))
    return str(path)


def _make_dataprep_run(tmp_path):
    """跑一个真实数据作战流任务（自动前三步），返回 run_id 与 cleaned_data 产物路径"""
    from dataprep.service import get_state, start_task

    path = _sensor_csv_path(tmp_path)
    st = start_task(name="制造业传感器预测性维护", source_path=path, customer="某汽车制造厂")
    run_id = st["run_id"]
    assert st["products"]["cleaned_data"]["exists"] is True
    return run_id, st


# ---------- 服务层 ----------


def test_from_dataprep_creates_task_from_real_cleaned_data(tmp_path, patch_embed, isolated_roots):
    """from_dataprep 建任务：样本来自真实 cleaned_data 产物（非空），source 诚实标注"""
    import json

    import annotation.service as ann

    dp_run, st = _make_dataprep_run(tmp_path)
    cleaned_path = st["products"]["cleaned_data"]["path"]
    with open(cleaned_path, "r", encoding="utf-8") as f:
        cleaned = json.load(f)
    assert cleaned, "cleaned_data 产物应为非空"

    task = ann.create_annotation_task_from_dataprep(dp_run, sample_size=3)
    assert task["run_id"]
    assert task["name"] == "数据作战流-人工标注-制造业传感器预测性维护"
    assert len(task["items"]) == 3
    # 样本内容与前 N 条 cleaned_data 的 content 一致（真实样本源）
    assert task["items"][0]["content"] == cleaned[0]["content"]
    assert task["items"][1]["content"] == cleaned[1]["content"]
    # 来源诚实标注
    assert task["source"]["type"] == "dataprep"
    assert task["source"]["dataprep_run_id"] == dp_run
    assert task["source"]["sample_size"] == 3


def test_from_dataprep_errors(tmp_path, patch_embed, isolated_roots):
    """from_dataprep 对不存在 run / 无 cleaned_data 产物诚实报错"""
    import annotation.service as ann

    # 不存在的 run
    with pytest.raises(FileNotFoundError):
        ann.create_annotation_task_from_dataprep("no_such_run", sample_size=3)


def test_dual_annotator_consistency_stats(isolated_roots):
    """双人标注 A/B → get_task 一致性 stats 正确（一致/分歧/未标）且每样本一致性明细可见"""
    import annotation.service as ann

    t = ann.create_annotation_task("测试", ["样本A", "样本B", "样本C"])
    run = t["run_id"]
    ann.add_label(run, 1, "A", "x")
    ann.add_label(run, 1, "B", "x")
    ann.add_label(run, 2, "A", "x")
    ann.add_label(run, 2, "B", "y")

    g = ann.get_task(run)
    assert g["stats"] == {"agreed": 1, "disagreed": 1, "unlabeled": 1, "total": 3}
    by_id = {it["id"]: it["consistency"] for it in g["items"]}
    assert by_id == {1: "agreed", 2: "disagreed", 3: "unlabeled"}


def test_disagreement_after_relabel_build_eval(isolated_roots):
    """分歧样本检出 → 改标签后一致 → build_eval 只含一致样本、分歧被列出/清空"""
    import annotation.service as ann

    t = ann.create_annotation_task("测试", ["样本A", "样本B"])
    run = t["run_id"]
    ann.add_label(run, 1, "A", "x")
    ann.add_label(run, 1, "B", "x")
    ann.add_label(run, 2, "A", "x")
    ann.add_label(run, 2, "B", "y")

    # 分歧检出
    g = ann.get_task(run)
    assert g["stats"]["disagreed"] == 1
    ev = ann.build_eval_set(run)
    assert ev["agreed"] == 1 and ev["disagreements"] == 1
    assert ev["disagreement_items"][0]["id"] == 2
    assert set(ev["disagreement_items"][0]["labels"].values()) == {"x", "y"}
    # 一致样本进评测集（不含未标/分歧）
    assert [e["instruction"] for e in ev["eval_set"]] == ["样本A"]

    # 改 B 的标签 → 一致
    ann.add_label(run, 2, "B", "x")
    g2 = ann.get_task(run)
    assert g2["stats"] == {"agreed": 2, "disagreed": 0, "unlabeled": 0, "total": 2}
    ev2 = ann.build_eval_set(run)
    assert ev2["agreed"] == 2 and ev2["disagreements"] == 0
    assert {e["instruction"] for e in ev2["eval_set"]} == {"样本A", "样本B"}


def test_list_tasks(isolated_roots):
    """list_tasks：按 mtime 倒序返回 run_id/name/样本数/stats"""
    import annotation.service as ann

    t1 = ann.create_annotation_task("任务一", ["a", "b"])
    ann.add_label(t1["run_id"], 1, "A", "x")
    ann.add_label(t1["run_id"], 1, "B", "x")
    t2 = ann.create_annotation_task("任务二", ["c"])  # 最后创建 → archive.json mtime 最新

    tasks = ann.list_tasks(limit=10)
    by_run = {x["run_id"]: x for x in tasks}
    assert t1["run_id"] in by_run and t2["run_id"] in by_run
    t1_entry = by_run[t1["run_id"]]
    assert t1_entry["name"] == "任务一"
    assert t1_entry["total"] == 2
    assert t1_entry["stats"]["agreed"] == 1 and t1_entry["stats"]["unlabeled"] == 1
    assert by_run[t2["run_id"]]["total"] == 1
    # 倒序：最后写入的任务在前
    assert tasks[0]["run_id"] == t2["run_id"]


# ---------- API 层（全链路） ----------


def test_api_annotation_workbench_full_chain(tmp_path, patch_embed, client, isolated_roots):
    """API 全链路：from-dataprep 建任务 → label 双人 → get 一致性 → build-eval → runs 列表"""
    dp_run, _ = _make_dataprep_run(tmp_path)

    # from-dataprep 建任务
    r = client.post("/api/v1/annotation/from-dataprep",
                    json={"dataprep_run_id": dp_run, "sample_size": 4})
    assert r.status_code == 200
    body = r.json()
    ann_run = body["run_id"]
    assert body["source"]["type"] == "dataprep"
    assert len(body["items"]) == 4

    # get：默认全未标，且每样本有 consistency 明细
    g = client.get(f"/api/v1/annotation/{ann_run}").json()
    assert g["stats"] == {"agreed": 0, "disagreed": 0, "unlabeled": 4, "total": 4}
    assert all(it["consistency"] == "unlabeled" for it in g["items"])

    # 双人打标：item1 一致，item2 分歧
    item1, item2 = g["items"][0]["id"], g["items"][1]["id"]
    client.post(f"/api/v1/annotation/{ann_run}/label", json={"item_id": item1, "annotator": "A", "label": "温度记录"})
    client.post(f"/api/v1/annotation/{ann_run}/label", json={"item_id": item1, "annotator": "B", "label": "温度记录"})
    client.post(f"/api/v1/annotation/{ann_run}/label", json={"item_id": item2, "annotator": "A", "label": "温度记录"})
    client.post(f"/api/v1/annotation/{ann_run}/label", json={"item_id": item2, "annotator": "B", "label": "压力记录"})

    g2 = client.get(f"/api/v1/annotation/{ann_run}").json()
    assert g2["stats"] == {"agreed": 1, "disagreed": 1, "unlabeled": 2, "total": 4}
    by_id = {it["id"]: it["consistency"] for it in g2["items"]}
    assert by_id[item1] == "agreed" and by_id[item2] == "disagreed"

    # build-eval：分歧被列出，一致样本进评测集
    ev = client.post(f"/api/v1/annotation/{ann_run}/build-eval", json={}).json()
    assert ev["agreed"] == 1 and ev["disagreements"] == 1
    assert ev["disagreement_items"][0]["id"] == item2

    # 改判 item2 B 标签 → 一致，再 build-eval 只含一致
    client.post(f"/api/v1/annotation/{ann_run}/label", json={"item_id": item2, "annotator": "B", "label": "温度记录"})
    g3 = client.get(f"/api/v1/annotation/{ann_run}").json()
    assert g3["stats"] == {"agreed": 2, "disagreed": 0, "unlabeled": 2, "total": 4}
    ev2 = client.post(f"/api/v1/annotation/{ann_run}/build-eval", json={}).json()
    assert ev2["agreed"] == 2 and ev2["disagreements"] == 0

    # 评测集产物真实落盘（output_path 指向隔离目录；真实环境该路径经 /artifacts 可下载）
    assert ev2.get("output_path")
    from pathlib import Path
    assert Path(ev2["output_path"]).exists()
    import json as _json
    with open(ev2["output_path"], "r", encoding="utf-8") as f:
        saved = _json.load(f)
    assert saved["agreed"] == 2 and saved["disagreements"] == 0

    # runs 列表包含该任务
    runs = client.get("/api/v1/annotation/runs").json()["tasks"]
    assert any(x["run_id"] == ann_run and x["total"] == 4 and x["stats"]["agreed"] == 2 for x in runs)


def test_api_manual_create_and_old_endpoints_ok(client, isolated_roots):
    """旧 annotation 端点不破坏：create / label / get / build-eval 全通"""
    a = client.post("/api/v1/annotation/create", json={"name": "测试", "items": ["样本A", "样本B"]}).json()
    run = a["run_id"]
    client.post(f"/api/v1/annotation/{run}/label", json={"item_id": 1, "annotator": "甲", "label": "x"})
    client.post(f"/api/v1/annotation/{run}/label", json={"item_id": 1, "annotator": "乙", "label": "x"})
    client.post(f"/api/v1/annotation/{run}/label", json={"item_id": 2, "annotator": "甲", "label": "x"})
    client.post(f"/api/v1/annotation/{run}/label", json={"item_id": 2, "annotator": "乙", "label": "y"})
    g = client.get(f"/api/v1/annotation/{run}").json()
    assert g["stats"]["agreed"] == 1 and g["stats"]["disagreed"] == 1
    # 非 A/B 标注员也给出合理 consistency（仅一人/分歧）
    by_id = {it["id"]: it["consistency"] for it in g["items"]}
    assert by_id[1] == "agreed" and by_id[2] == "disagreed"
    ev = client.post(f"/api/v1/annotation/{run}/build-eval", json={}).json()
    assert ev["agreed"] == 1 and ev["disagreements"] == 1
