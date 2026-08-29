"""真实试运行 v11.0 测试：pilot 脚本（打桩模式）全流程跑通，产出客户交付物包

北极星：全工具链在一套真实制造业客户项目上端到端跑通，交付物可发客户。
- 数据：examples/data/manufacturing_sensors.csv（固定数据集，非教学场景；测试用 max_rows=8 子集提速）
- LLM 全打桩（确定性 JSON / 固定文本）；语义去重与 RAG 嵌入固定哈希（不联网/不依赖 ONNX）
- 隔离：diagnosis / dataprep / cases / projects / mapping / retrieval 档案根目录全部指向 tmp
- 旧接口不破坏：全部走真实 API（TestClient），与既有 161 用例并行无冲突
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def isolated_roots(tmp_path, monkeypatch):
    """隔离全部档案根目录，避免测试污染真实 tmp/web/"""
    import cases.archive as ca
    import dataprep.archive as dpa
    import diagnosis.archive as da
    import mapping.service as ms
    import projects.archive as pa
    import retrieval.service as rs

    da_root = tmp_path / "web" / "diagnosis"; da_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(da, "ARCHIVE_ROOT", da_root)

    dp_root = tmp_path / "web" / "dataprep"; dp_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dpa, "ARCHIVE_ROOT", dp_root)

    cs_root = tmp_path / "web" / "cases"; cs_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ca, "CASES_ROOT", cs_root)

    pj_root = tmp_path / "web" / "projects"; pj_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pa, "PROJECTS_ROOT", pj_root)

    mp_root = tmp_path / "web" / "mapping"; mp_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ms, "MAPPING_ROOT", mp_root)

    # retrieval：隔离 ChromaDB 目录 + 索引档案目录 + 重置单例
    monkeypatch.setattr(rs, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(rs, "RETRIEVAL_ROOT", tmp_path / "retrieval")
    monkeypatch.setattr(rs, "_client_instance", None)
    return da_root, dp_root, cs_root, pj_root


@pytest.fixture
def no_pdf(monkeypatch):
    """禁用 PDF 生成（避免测试触发 Chrome），回退 HTML 即可"""
    import cases.render as cr
    monkeypatch.setattr(cr, "render_html_to_pdf", lambda html, path: False)


@pytest.fixture
def pilot_out(tmp_path):
    return tmp_path / "pilot_out"


def test_fixed_datasets_committed():
    """固定数据集提交仓库且非教学场景（真实制造业/零售列结构、行数达标）"""
    sensor = PROJECT_ROOT / "examples" / "data" / "manufacturing_sensors.csv"
    retail = PROJECT_ROOT / "examples" / "data" / "retail_inventory.csv"
    assert sensor.exists(), "固定数据集 manufacturing_sensors.csv 应提交到 examples/data/"
    assert retail.exists(), "固定数据集 retail_inventory.csv 应提交到 examples/data/"

    import csv
    with open(sensor, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 40, f"制造业传感器数据集应 ≥40 行，实际 {len(rows)}"
    assert {"sensor_id", "device_name", "reading", "unit", "ts", "status"} <= set(rows[0])
    # 非教学场景：设备名/指标应贴近真实制造业
    joined = " ".join(rows[0].values())
    assert any(k in joined for k in ("注塑", "CNC", "冲压", "空压", "装配"))

    with open(retail, encoding="utf-8") as f:
        rows2 = list(csv.DictReader(f))
    assert len(rows2) >= 30, f"零售库存数据集应 ≥30 行，实际 {len(rows2)}"
    assert {"sku", "name", "category", "stock_qty", "cost_price", "supplier"} <= set(rows2[0])


def test_pilot_stub_full_flow(isolated_roots, no_pdf, pilot_out):
    """pilot（--stub 等价：run_pilot(stub=True, max_rows=8)）完整跑通并产出客户交付物包"""
    from examples.pilot_example import run_pilot

    report = run_pilot(stub=True, max_rows=8, pilot_dir=str(pilot_out))

    # 1. 项目存在 + 诊断定稿
    assert report["project_id"]
    assert report["diagnosis_confirmed"] is True
    assert report["diagnosis_total_score"] and report["diagnosis_total_score"] > 0
    assert report["deliverable"].get("case_id")

    from diagnosis.orchestrator import get_archive
    arch = get_archive(report["diagnosis_run_id"])
    assert arch.get("confirmed") is True
    assert arch.get("project_id") == report["project_id"]

    # 2. 数据作战流全部步骤完成 + 评测集/知识库产物落盘
    from dataprep.service import get_state
    dp = get_state(report["dataprep_run_id"])
    assert set(report["dataprep_done_steps"]) == {
        "import", "clean", "quality", "annotate", "eval_set", "knowledge_base"}
    assert dp["products"]["eval_set"]["exists"] is True
    assert dp["products"]["chunks"]["exists"] is True
    assert dp["products"]["quality_report"]["exists"] is True
    assert report["dataprep_kb_indexed"] is True
    assert report["deposit_count"] >= 4

    # 3. 原型可跑（qa 模板 + RAG），数据门禁放行
    proto = report["prototype"]
    assert proto["result"]
    assert proto["gate"]["checked"] is True
    assert proto["gate"]["allowed"] is True
    assert proto["rag"] is True

    # 4. 字段映射导出
    assert report["mapping_count"] >= 5
    assert report["mapping_success_rate"] and report["mapping_success_rate"] > 0
    assert Path(report["mapping_export_path"]).exists()

    # 5. 部署配置
    assert report["deploy_run_id"]
    assert len(report["deploy_artifacts"]) >= 3

    # 6. warroom 分区计数 > 0
    counts = report["warroom_counts"]
    for key in ("diagnosis", "dataprep", "mapping", "deliverables", "assets", "rag"):
        assert counts.get(key, 0) > 0, f"warroom 分区 {key} 应为正数，实际 {counts.get(key)}"
    assert counts["workflow_progress"] == 100

    # 7. 项目文档包存在（confirmed=true 放行）
    assert report["doc_package_case_id"]
    assert report["doc_package_gate"]["allowed"] is True
    from cases.archive import case_dir
    assert (case_dir(report["doc_package_case_id"]) / "deliverable.html").exists()

    # 8. 客户交付物包目录生成
    pdir = Path(report["pilot_dir"])
    assert pdir.is_dir()
    for name in ("客户项目总览.md", "warroom.json", "诊断交付物.html", "项目文档包.html"):
        assert (pdir / name).exists(), f"客户交付物包应包含 {name}"
    assert "本包由 ai-field-delivery-toolkit 自动生成" in (pdir / "客户项目总览.md").read_text(encoding="utf-8")

    # warroom JSON 快照可解析且分区数一致
    snap = json.loads((pdir / "warroom.json").read_text(encoding="utf-8"))
    assert snap["project"]["project_id"] == report["project_id"]
