"""字段映射工作台 v4.0 集成工作流测试（非教学场景）

场景：制造业设备字段映射 / 物流订单字段映射。
流程：创建映射（LLM 初判打桩）→ 导入真实样例 CSV → validate 实跑校验（LLM 打桩）→
     修正失败映射 → 重跑（成功率变化可见）→ 导出适配器。
校验 LLM 调用全部打桩（不真实调用）；真实链路用 DeepSeek 冒烟在服务层单独验证。
"""

import io

import pytest
from fastapi.testclient import TestClient

from core.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


# ---------- 打桩：创建初判 + 校验判定（按 system 是否含「校验」区分） ----------


def _make_fake_llm(create_mappings):
    def fake_llm(system, user):
        if "校验" in system:  # 映射校验 LLM（打桩）
            # 真实打桩：有执行失败痕迹 → fail；否则 pass
            if "不存在" in user or "需人工实现" in user or "执行异常" in user:
                return {"verdict": "fail", "reason": "映射输出异常/源缺失"}
            return {"verdict": "pass", "reason": "样例映射合理"}
        return {"mappings": create_mappings, "notes": "测试初判"}  # 创建 LLM（打桩）
    return fake_llm


CREATE_MANUFACTURING = [
    # device_id 故意用错源字段「id」（样例 CSV 里是 equipment_id）→ 实跑应 fail，供修正重跑验证
    {"target": "device_id", "source": "id", "rule": "direct", "expression": "id", "confidence": "medium"},
    {"target": "device_name", "source": "equip_name", "rule": "direct", "expression": "equip_name", "confidence": "high"},
    {"target": "temperature", "source": "temp", "rule": "direct", "expression": "temp", "confidence": "high"},
    {"target": "pressure_value", "source": "pressure", "rule": "direct", "expression": "pressure", "confidence": "high"},
    {"target": "status_note", "source": None, "rule": "concat", "expression": "equip_name + status_code", "confidence": "medium"},
]

CREATE_LOGISTICS = [
    {"target": "order_id", "source": "order_no", "rule": "direct", "expression": "order_no", "confidence": "high"},
    {"target": "recipient_name", "source": "receiver_name", "rule": "direct", "expression": "receiver_name", "confidence": "high"},
    {"target": "phone", "source": "receiver_phone", "rule": "direct", "expression": "receiver_phone", "confidence": "high"},
    {"target": "full_address", "source": None, "rule": "concat", "expression": "province + city + district + address_detail", "confidence": "high"},
]


def _manufacturing_csv() -> bytes:
    lines = ["equipment_id,equip_name,temp,pressure,status_code"]
    for i in range(8):
        lines.append(f"E{i:03d},设备{i},温度 {20 + i} 摄氏度,压力 {1.0 + i * 0.1:.1f} MPa,R{i % 3}")
    return "\n".join(lines).encode("utf-8")


def _logistics_csv() -> bytes:
    import csv as _csv
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["order_no", "receiver_name", "receiver_phone", "province", "city", "district", "address_detail"])
    for i in range(5):
        w.writerow([f"SO{i:06d}", f"收货人{i}", f"1380000{i:04d}", "广东省", "深圳市", "南山区", f"科技园路{i}号"])
    return buf.getvalue().encode("utf-8")


def test_mapping_integration_manufacturing_api(client, monkeypatch):
    """制造业设备字段映射：创建→导入真实样例→validate（含失败）→修正→重跑（成功率上升）→导出→项目事件→断点续接"""
    import mapping.service as ms
    monkeypatch.setattr(ms, "_default_json_call", _make_fake_llm(CREATE_MANUFACTURING))

    # 创建（带客户 → 自动建项目）
    r = client.post("/api/v1/mapping/create", json={
        "name": "制造业设备字段映射",
        "source_fields": [
            {"name": "equipment_id", "sample": "E001"}, {"name": "equip_name", "sample": "设备1"},
            {"name": "temp", "sample": "温度 21 摄氏度"}, {"name": "pressure", "sample": "1.1 MPa"},
            {"name": "status_code", "sample": "R0"},
        ],
        "target_fields": [
            {"name": "device_id", "sample": "E001"}, {"name": "device_name", "sample": "设备1"},
            {"name": "temperature", "sample": "温度 21 摄氏度"},
            {"name": "pressure_value", "sample": "1.1 MPa"}, {"name": "status_note", "sample": "设备1 R0"},
        ],
        "customer": "某汽车制造厂",
    })
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    assert r.json()["project_id"]

    # 导入真实样例 CSV
    files = {"file": ("equip.csv", io.BytesIO(_manufacturing_csv()), "text/csv")}
    s = client.post(f"/api/v1/mapping/{run_id}/samples", files=files)
    assert s.status_code == 200
    assert s.json()["row_count"] == 8
    assert "equipment_id" in s.json()["columns"]

    # validate 实跑：device_id 源字段「id」不存在 → fail，成功率 < 100%
    v1 = client.post(f"/api/v1/mapping/{run_id}/validate", json={"max_rows": 8})
    assert v1.status_code == 200
    body1 = v1.json()
    assert body1["total_rows"] == 8 and body1["mapped_rows"] == 8
    assert body1["counts"]["fail"] >= 1 and body1["success_rate"] < 1.0
    assert body1["no_fail_rate"] < 1.0
    dev = [f for f in body1["per_field"] if f["target"] == "device_id"][0]
    assert dev["verdict"] == "fail"
    assert "不存在" in dev["reason"]
    assert dev["fail"] == 8  # 该字段全部行执行失败

    # 断点续接：get_mapping 带 samples + validation
    gm = client.get(f"/api/v1/mapping/{run_id}").json()
    assert gm["samples"]["original_row_count"] == 8
    assert gm["validation"]["success_rate"] == body1["success_rate"]

    # 修正失败映射：device_id 源字段改为 equipment_id
    fixed = list(gm["mappings"])
    for m in fixed:
        if m["target"] == "device_id":
            m["source"] = "equipment_id"
            m["expression"] = "equipment_id"
    upd = client.post(f"/api/v1/mapping/{run_id}/update", json={"mappings": fixed})
    assert upd.status_code == 200

    # 重跑：成功率变化可见（→ 100% 无失败率）
    v2 = client.post(f"/api/v1/mapping/{run_id}/validate", json={"max_rows": 8})
    assert v2.status_code == 200
    body2 = v2.json()
    assert body2["success_rate"] == 1.0 and body2["counts"]["fail"] == 0
    assert body2["no_fail_rate"] == 1.0
    assert body2["no_fail_rate"] > body1["no_fail_rate"]
    assert body2["success_rate"] >= body1["success_rate"]

    # 导出：adapter 语义与校验一致（device_id → row.get('equipment_id')）
    exp = client.post(f"/api/v1/mapping/{run_id}/export", json={})
    assert exp.status_code == 200
    assert "row.get('equipment_id')" in exp.json()["adapter_code"]

    # 任务挂项目档案：mapping 事件可见（创建/校验/调整）
    proj = client.get(f"/api/v1/projects/{gm['project_id']}").json()
    mev = [e for e in proj["events"] if e["type"] == "mapping"]
    assert len(mev) >= 1
    assert any(e["ref"] == run_id for e in mev)

    # 任务列表（断点续接入口）：显示成功率
    runs = client.get("/api/v1/mapping/runs").json()["runs"]
    assert any(x["run_id"] == run_id and x["success_rate"] == 1.0 and x["has_samples"] for x in runs)


def test_mapping_integration_logistics_service(monkeypatch):
    """物流订单字段映射：服务级 create→import→validate（全 pass）→validate_row→导出→项目事件"""
    import mapping.service as ms
    monkeypatch.setattr(ms, "_default_json_call", _make_fake_llm(CREATE_LOGISTICS))
    from mapping.service import create_mapping, export_mapping, import_samples, validate_mapping, validate_row

    m = create_mapping(
        "物流订单字段映射",
        [{"name": "order_no", "sample": "SO000001"}, {"name": "receiver_name", "sample": "收货人1"},
         {"name": "receiver_phone", "sample": "13800000001"}, {"name": "province", "sample": "广东省"},
         {"name": "city", "sample": "深圳市"}, {"name": "district", "sample": "南山区"},
         {"name": "address_detail", "sample": "科技园路1号"}],
        [{"name": "order_id", "sample": "SO000001"}, {"name": "recipient_name", "sample": "收货人1"},
         {"name": "phone", "sample": "13800000001"}, {"name": "full_address", "sample": "广东省深圳市南山区科技园路1号"}],
        customer="某物流公司",
    )
    run_id = m["run_id"]
    assert m["project_id"]

    imp = import_samples(run_id, _logistics_csv(), filename="orders.csv")
    assert imp["row_count"] == 5
    assert imp["columns"] == ["order_no", "receiver_name", "receiver_phone", "province", "city", "district", "address_detail"]

    v = validate_mapping(run_id, max_rows=5)
    assert v["success_rate"] == 1.0
    assert v["no_fail_rate"] == 1.0
    assert v["counts"] == {"pass": 4, "warn": 0, "fail": 0}
    assert len(v["per_field"]) == 4
    fa = [f for f in v["per_field"] if f["target"] == "full_address"][0]
    assert fa["verdict"] == "pass"
    # concat 真实拼接结果
    assert str(fa["examples"][0]["output"]).startswith("广东省深圳市南山区科技园路0号")

    # 单行试运行
    row = {"order_no": "SO999999", "receiver_name": "王五", "receiver_phone": "13900000000",
           "province": "广东省", "city": "广州市", "district": "天河区", "address_detail": "体育西路1号"}
    vr = validate_row(run_id, row)
    fa2 = [f for f in vr["per_field"] if f["target"] == "full_address"][0]
    assert fa2["ok"] is True
    assert fa2["value"] == "广东省广州市天河区体育西路1号"

    exp = export_mapping(run_id)
    assert "def transform" in exp["adapter_code"]

    # 项目事件
    from projects.archive import get_project
    proj = get_project(m["project_id"])
    assert any(e["type"] == "mapping" and e["ref"] == run_id for e in proj["events"])


def test_mapping_validate_requires_samples(client, monkeypatch):
    """未导入样例就 validate → 400（诚实校验，先有真实数据）"""
    import mapping.service as ms
    monkeypatch.setattr(ms, "_default_json_call", _make_fake_llm(
        [{"target": "a", "source": "x", "rule": "direct", "expression": "x", "confidence": "high"}]))
    r = client.post("/api/v1/mapping/create", json={
        "name": "无样例任务", "source_fields": [{"name": "x", "sample": "1"}],
        "target_fields": [{"name": "a", "sample": "1"}],
    })
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    v = client.post(f"/api/v1/mapping/{run_id}/validate", json={})
    assert v.status_code == 400


def test_mapping_lookup_rule_fails_honestly(client, monkeypatch):
    """lookup/other 规则无法自动实跑 → 校验判 fail 并提示需人工实现（不糊弄）"""
    import mapping.service as ms
    monkeypatch.setattr(ms, "_default_json_call", _make_fake_llm(
        [{"target": "b", "source": "code", "rule": "lookup", "expression": "code表", "confidence": "low"}]))
    r = client.post("/api/v1/mapping/create", json={
        "name": "查表规则", "source_fields": [{"name": "code", "sample": "A1"}],
        "target_fields": [{"name": "b", "sample": "状态"}],
    })
    run_id = r.json()["run_id"]
    files = {"file": ("code.csv", io.BytesIO("code,note\nA1,x\nB2,y\n".encode("utf-8")), "text/csv")}
    client.post(f"/api/v1/mapping/{run_id}/samples", files=files)
    v = client.post(f"/api/v1/mapping/{run_id}/validate", json={"max_rows": 2})
    assert v.status_code == 200
    b = [f for f in v.json()["per_field"] if f["target"] == "b"][0]
    assert b["verdict"] == "fail"
    assert "需人工实现" in b["reason"]
