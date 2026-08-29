"""FDE 操作台 HTTP API 测试（core/api.py + core/main.py 静态托管）"""

import io
import hashlib

import pytest
from fastapi.testclient import TestClient

from core.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    names = [m["name"] for m in body["modules"]]
    assert "data_prep" in names
    assert "cropper" in names


def test_frontend_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "FDE 操作台" in r.text


def test_diagnosis_evaluate(client):
    r = client.post("/api/v1/diagnosis/evaluate", json={
        "generation": 4, "reasoning": 3, "uncertainty": 4, "data": 5, "real_time": 2,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["total_score"] == 18
    assert "conclusion" in body and "suggestion" in body


def test_diagnosis_report(client):
    ev = client.post("/api/v1/diagnosis/evaluate", json={
        "generation": 4, "reasoning": 3, "uncertainty": 4, "data": 5, "real_time": 2,
    }).json()
    r = client.post("/api/v1/diagnosis/report", json={
        "customer_name": "测试客户",
        "requirement_summary": "内部文档智能问答",
        "feasibility_result": ev,
        "interview_notes": "访谈 3 人",
        "decision_maker": "负责人",
    })
    assert r.status_code == 200
    assert r.json()["customer_name"] == "测试客户"
    assert "next_steps" in r.json()


def test_diagnosis_default_prompt(client):
    r = client.get("/api/v1/diagnosis/default-prompt")
    assert r.status_code == 200
    assert "中立" in r.json()["prompt"]
    assert "{requirement}" in r.json()["prompt"]


def test_diagnosis_ai_with_llm(client, monkeypatch):
    """注入假 LLM：验证 AI 打分 + 理由 + 总结 + llm_mode"""
    import json
    import diagnosis.ai_scorer as scorer

    canned = json.dumps({
        "dimension_scores": {"generation": 4, "reasoning": 3, "uncertainty": 4, "data": 5, "real_time": 2},
        "reasons": {"generation": "理由1", "reasoning": "理由2", "uncertainty": "理由3", "data": "理由4", "real_time": "理由5"},
        "summary": "测试总结",
    }, ensure_ascii=False)
    monkeypatch.setattr(scorer, "_default_llm_call", lambda prompt: canned)

    r = client.post("/api/v1/diagnosis/ai", json={"requirement": "客户需要基于知识库的问答系统"})
    assert r.status_code == 200
    body = r.json()
    assert body["llm_mode"] == "llm"
    assert body["total_score"] == 18
    assert body["summary"] == "测试总结"
    assert body["reasons"]["generation"] == "理由1"
    assert body["prompt_used"]


def test_diagnosis_ai_fallback_on_failure(client, monkeypatch):
    """模型调用抛异常时，应降级为规则兜底且不报错"""
    import diagnosis.ai_scorer as scorer

    def boom(prompt):
        raise RuntimeError("模型不可用")
    monkeypatch.setattr(scorer, "_default_llm_call", boom)

    r = client.post("/api/v1/diagnosis/ai", json={"requirement": "实时客服系统，要求毫秒级响应"})
    assert r.status_code == 200
    body = r.json()
    assert body["llm_mode"] == "rule-fallback"
    assert 1 <= body["dimension_scores"]["real_time"] <= 5
    assert "兜底" in body["summary"]


def test_diagnosis_ai_empty_requirement(client):
    r = client.post("/api/v1/diagnosis/ai", json={"requirement": "   "})
    assert r.status_code == 400


def test_diagnosis_report_with_manual_review(client, monkeypatch):
    """生成诊断报告：AI 诊断 + 人工复核打分 + 对比 + 建议"""
    import json
    import diagnosis.ai_scorer as scorer

    canned = json.dumps({
        "dimension_scores": {"generation": 4, "reasoning": 3, "uncertainty": 4, "data": 5, "real_time": 2},
        "reasons": {"generation": "AI理由1", "reasoning": "AI理由2", "uncertainty": "AI理由3", "data": "AI理由4", "real_time": "AI理由5"},
        "summary": "AI总结",
    }, ensure_ascii=False)
    monkeypatch.setattr(scorer, "_default_llm_call", lambda prompt: canned)

    ai = client.post("/api/v1/diagnosis/ai", json={"requirement": "基于知识库的问答系统"}).json()
    assert ai["total_score"] == 18  # AI：4+3+4+5+2

    r = client.post("/api/v1/diagnosis/report", json={
        "customer_name": "测试客户",
        "requirement_summary": "智能问答",
        "ai_feasibility": ai,
        "manual_review": {
            "dimension_scores": {"generation": 2, "reasoning": 3, "uncertainty": 4, "data": 5, "real_time": 2},
            "reasons": {"generation": "人工理由：生成需求低"},
            "summary": "人工复核意见：同意 AI 结论但生成性应下调",
        },
        "decision_maker": "负责人",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["report_version"] == "2.0"
    assert body["ai_diagnosis"]["total_score"] == 18
    assert body["manual_review"]["dimension_scores"]["generation"] == 2
    assert body["score_comparison"]
    # 生成性 delta = 2-4 = -2，应触发差异提示；最终总分 = 2+3+4+5+2 = 16
    assert any("差异较大" in rec for rec in body["recommendations"])
    assert body["final_conclusion"]["total_score"] == 16


def _fake_json_call(system, user):
    """按角色返回固定的结构化 JSON（用于多 Agent 流程测试）；带客户反馈上下文时模拟回应调整"""
    if "客户反馈解析" in system:
        return {
            "items": [{"item": "客户反馈数据质量不足，应下调数据可得性", "dimension": "data", "intent": "lower"}],
            "summary": "客户认为数据质量不达标",
        }
    if "生成器" in system:
        if "客户反馈意见" in user:
            return {
                "clarification_questions": [],
                "dimension_scores": {"generation": 4, "reasoning": 3, "uncertainty": 4, "data": 3, "real_time": 2},
                "reasons": {"generation": "G理由1", "reasoning": "G理由2", "uncertainty": "G理由3",
                            "data": "回应客户反馈：数据质量存疑，下调", "real_time": "G理由5"},
                "summary": "G总结-v2", "draft_notes": "草稿要点",
                "non_tech_feasibility": {
                    "business_value": {"item": "价值主张成立", "basis": "需求有明确收益", "signal": "绿", "advice": "优先投入"},
                    "organization": {"item": "组织承接需培训", "basis": "未提及决策链", "signal": "黄", "advice": "先做培训"},
                    "integration": {"item": "需对接现有系统", "basis": "需求提到集成", "signal": "黄", "advice": "评估映射工作量"},
                    "compliance": {"item": "涉及数据隐私", "basis": "合规要求", "signal": "黄", "advice": "启动合规审查"},
                    "risk_overview": {"item": "主要风险在数据质量", "basis": "客户反馈", "signal": "黄", "advice": "先补数据"},
                    "overall_recommendation": {"worth_investing": "值得", "budget_scale": "中", "main_resistance": "数据质量", "first_steps": "补数据"},
                },
            }
        return {
            "clarification_questions": ["数据量大概多大？", "用户并发多少？"],
            "dimension_scores": {"generation": 4, "reasoning": 3, "uncertainty": 4, "data": 5, "real_time": 2},
            "reasons": {"generation": "G理由1", "reasoning": "G理由2", "uncertainty": "G理由3", "data": "G理由4", "real_time": "G理由5"},
            "summary": "G总结", "draft_notes": "草稿要点",
            "non_tech_feasibility": {
                "business_value": {"item": "商业价值成立，投入产出清晰", "basis": "需求有明确收益场景", "signal": "绿", "advice": "优先投入"},
                "organization": {"item": "组织承接有一定阻力，需明确决策链与培训", "basis": "未提及决策链", "signal": "黄", "advice": "先做用户培训与决策链确认"},
                "integration": {"item": "需对接现有系统，字段映射工作量大", "basis": "需求提到集成", "signal": "黄", "advice": "评估适配器工作量"},
                "compliance": {"item": "涉及数据隐私，需合规审查", "basis": "合规要求", "signal": "黄", "advice": "启动合规评估"},
                "risk_overview": {"item": "主要风险在集成与数据质量", "basis": "综合判断", "signal": "黄", "advice": "先做集成试点"},
                "overall_recommendation": {"worth_investing": "值得", "budget_scale": "建议小步投入", "main_resistance": "集成复杂度", "first_steps": "先跑最小原型"},
            },
        }
    if "独立评审" in system:
        if "客户反馈意见" in user:
            return {
                "dimension_scores": {"generation": 2, "reasoning": 3, "uncertainty": 3, "data": 3, "real_time": 2},
                "reasons": {"generation": "C理由1", "reasoning": "C理由2", "uncertainty": "C理由3",
                            "data": "同意客户下调数据可得性", "real_time": "C理由5"},
                "coverage_gaps": [], "inconsistencies": [], "over_confidence_flags": [],
                "non_tech_audit": {
                    "business_value": {"item": "价值主张需数据支撑", "basis": "缺量化指标", "signal": "黄", "advice": "补充测算", "audit_note": "与 Generator 信号分歧"},
                    "organization": {"item": "组织阻力真实存在", "basis": "", "signal": "红", "advice": "评估决策链", "audit_note": ""},
                    "integration": {"item": "集成风险高", "basis": "", "signal": "红", "advice": "先做接口摸底", "audit_note": ""},
                    "compliance": {"item": "合规审查必要", "basis": "", "signal": "黄", "advice": "", "audit_note": ""},
                    "risk_overview": {"item": "风险集中在前三项目", "basis": "", "signal": "红", "advice": "分阶段投入", "audit_note": ""},
                    "overall_audit_note": "整体偏谨慎，建议先做最小原型验证。",
                },
            }
        return {
            "dimension_scores": {"generation": 2, "reasoning": 3, "uncertainty": 3, "data": 4, "real_time": 2},
            "reasons": {"generation": "C理由1", "reasoning": "C理由2", "uncertainty": "C理由3", "data": "C理由4", "real_time": "C理由5"},
            "coverage_gaps": ["未覆盖网络带宽约束"], "inconsistencies": [], "over_confidence_flags": ["生成性可能过高"],
            "non_tech_audit": {
                "business_value": {"item": "商业价值需更扎实测算", "basis": "缺 ROI 数据", "signal": "黄", "advice": "补充测算", "audit_note": "与 Generator 信号分歧"},
                "organization": {"item": "组织承接阻力存在", "basis": "决策链不明确", "signal": "红", "advice": "先确认决策链", "audit_note": "比 Generator 更悲观"},
                "integration": {"item": "集成复杂度高", "basis": "多系统对接", "signal": "红", "advice": "先做接口摸底", "audit_note": ""},
                "compliance": {"item": "合规与数据驻留需审查", "basis": "数据隐私", "signal": "黄", "advice": "启动合规评估", "audit_note": ""},
                "risk_overview": {"item": "风险集中在组织与集成", "basis": "综合", "signal": "红", "advice": "分阶段投入", "audit_note": ""},
                "overall_audit_note": "整体偏谨慎，建议先做最小原型验证后再扩大投入。",
            },
        }
    if "人工评审复核" in system:
        return {
            "verdicts": {
                "generation": {"verdict": "correct", "adjusted_score": 3, "reason": "人工偏高"},
                "reasoning": {"verdict": "agree", "adjusted_score": None, "reason": "合理"},
                "uncertainty": {"verdict": "agree", "adjusted_score": None, "reason": "合理"},
                "data": {"verdict": "agree", "adjusted_score": None, "reason": "合理"},
                "real_time": {"verdict": "agree", "adjusted_score": None, "reason": "合理"},
            },
            "bias": {"detected": True, "direction": "high", "detail": "人工分数略高于需求依据"},
            "summary": "R总结",
        }
    if "商务评估" in system:
        return {
            "investment_estimate": {
                "disclaimer": "此为讨论用初步估算，最终以商务洽谈确认为准。",
                "tiers": [
                    {"period": "试点期", "focus": "最小闭环原型：基于知识库做单场景问答",
                     "scope": "单科目/单数据源", "investment_range": "5-12 万元",
                     "basis": "数据接入与原型开发约需 1-2 名工程师 2 周，集成以只读对接为主",
                     "deliverables": ["可演示问答原型", "评测集雏形"]},
                    {"period": "一期", "focus": "核心场景功能完善与全量数据接入",
                     "scope": "全部知识库数据 + 2 个核心场景", "investment_range": "15-35 万元",
                     "basis": "数据清洗/标注与集成改造占比约 60-70%（诊断集成维度为黄/红）",
                     "deliverables": ["生产可用系统", "标注数据集", "验收报告"]},
                    {"period": "二期", "focus": "扩展到全部场景与组织推广",
                     "scope": "全量场景 + 多部门", "investment_range": "30-80 万元",
                     "basis": "组织培训与多系统集成工作量上升",
                     "deliverables": ["全量上线", "培训与运维手册"]},
                ],
                "total_range": "50-130 万元（分三期）",
                "notes": "实际金额以商务洽谈确认的边界（范围/数据/工期）为准",
            },
            "milestones": [
                {"phase": "试点期", "duration": "2 周", "first_usable": "第 2 周末：可演示的问答原型",
                 "milestone": "单场景可用且指标可度量", "dependencies": "甲方提供数据访问账号与样例"},
                {"phase": "一期", "duration": "6 周", "first_usable": "第 8 周末：核心场景生产可用",
                 "milestone": "全量数据接入且准确率达约定阈值", "dependencies": "甲方完成数据脱敏与接口开通"},
                {"phase": "二期", "duration": "8 周", "first_usable": "第 16 周末：全量场景上线",
                 "milestone": "组织推广与培训完成", "dependencies": "甲方确认各业务部门参与"},
            ],
            "client_responsibilities": [
                {"item": "提供知识库文档与问答样例数据", "category": "数据/接口", "needed_before": "试点启动前",
                 "owner": "甲方知识管理负责人", "reason": "数据可得性决定效果上限（诊断 data 维度）", "blocking": True},
                {"item": "提供系统集成对接清单（接口/字段/权限账号）", "category": "数据/接口",
                 "needed_before": "一期启动前", "owner": "甲方 IT 部门", "reason": "集成复杂度高，需摸底",
                 "blocking": True},
                {"item": "指定业务对接人并确认决策链", "category": "人员/决策", "needed_before": "试点启动前",
                 "owner": "甲方管理层", "reason": "决策链不明确会阻塞推进", "blocking": True},
            ],
            "vendor_responsibilities": [
                {"item": "模型选型、提示词与 RAG 检索调优", "category": "实施", "owner": "乙方"},
                {"item": "系统集成开发、数据清洗与部署上线", "category": "集成/部署", "owner": "乙方"},
                {"item": "用户培训与验收期运维支持", "category": "培训/运维", "owner": "乙方"},
            ],
            "pilot_and_exit": {
                "pilot_scope": "单科目知识库问答（100 篇文档）",
                "success_criteria": ["问答准确率（召回命中率）≥ 80%", "误报/答非所问率 ≤ 20%",
                                     "试点期间用户周活使用 ≥ 30 人"],
                "exit_conditions": ["试点 4 周内准确率 < 60%", "甲方数据在试点启动后 2 周内仍无法提供",
                                    "单次试点投入超出预算 50%"],
                "review_point": "试点结束（第 4 周末）联合评审",
                "exit_terms": "退出时交接已建数据/接口访问方式，不再产生增量费用",
            },
            "alternatives_and_cost": {
                "alternatives": [
                    {"name": "现有系统规则检索改造", "description": "在既有搜索/知识系统上加规则匹配",
                     "pros": ["成本低、周期短"], "cons": ["对自然语言问题泛化差"],
                     "cost_range": "3-10 万元", "risk": "命中率低，用户仍需人工检索",
                     "verdict": "可作为过渡，不建议单独投入"},
                    {"name": "人工流程优化（不引入 AI）", "description": "靠人工整理 FAQ 与培训",
                     "pros": ["无技术风险"], "cons": ["不可扩展、依赖个人"],
                     "cost_range": "持续人力成本", "risk": "改善天花板低", "verdict": "补充手段"},
                    {"name": "引入 AI 问答（本方案）", "description": "基于知识库 RAG 的智能问答",
                     "pros": ["可量化提升问答效率、可扩展"], "cons": ["需数据与集成配合"],
                     "cost_range": "50-130 万元（分期）", "risk": "数据质量/集成是主要风险",
                     "verdict": "建议按试点-分期推进"},
                ],
                "cost_of_inaction": "不做则维持现状：问答依赖人工检索与传帮带，知识利用效率低，预计每年人工成本损失约 30-60 万元",
                "recommendation": "先按试点范围跑最小闭环，用量化结果决定是否进入一期",
            },
        }
    raise AssertionError(f"未知角色 system: {system[:20]}")


def test_diagnosis_agents_flow(client, monkeypatch):
    """多 Agent 一期：start（Generator+Critic 盲审）→ review（Reviewer 评人工）→ finalize"""
    import diagnosis.agents as agents
    monkeypatch.setattr(agents, "_default_json_call", _fake_json_call)

    # 1) start
    s = client.post("/api/v1/diagnosis/start", json={"requirement": "基于知识库的问答系统"})
    assert s.status_code == 200
    sbody = s.json()
    run_id = sbody["run_id"]
    assert sbody["generator"]["dimension_scores"]["generation"] == 4
    assert sbody["critic"]["dimension_scores"]["generation"] == 2
    # 生成性 gen=4 vs crit=2 → 分歧
    assert any(d["dimension"] == "generation" and d["source"] == "generator_vs_critic" for d in sbody["divergences"])
    assert sbody["confidence"]["needs_confirm"]

    # 2) review（人工用 Generator 分数）
    rv = client.post("/api/v1/diagnosis/review", json={
        "run_id": run_id,
        "human_scores": {"generation": 4, "reasoning": 3, "uncertainty": 4, "data": 5, "real_time": 2},
        "human_reasons": {"generation": "人工理由"},
        "human_summary": "人工意见",
    })
    assert rv.status_code == 200
    rvbody = rv.json()
    assert rvbody["reviewer"]["verdicts"]["generation"]["verdict"] == "correct"
    assert rvbody["reviewer"]["bias"]["detected"] is True
    # Reviewer 修正 vs 人工：generation 4→3
    assert any(d["source"] == "reviewer_vs_human" and d["dimension"] == "generation" for d in rvbody["divergences"])

    # 3) finalize 未确认 → 400
    f_bad = client.post("/api/v1/diagnosis/finalize", json={"run_id": run_id, "confirmed": False})
    assert f_bad.status_code == 400

    # 4) finalize 确认 → 报告 v3.0
    f = client.post("/api/v1/diagnosis/finalize", json={
        "run_id": run_id, "customer_name": "测试客户", "requirement_summary": "问答系统",
        "confirmed": True,
    })
    assert f.status_code == 200
    report = f.json()
    assert report["report_version"] == "3.1"
    assert report["generator"]["dimension_scores"]
    assert report["critic"]["coverage_gaps"]
    assert report["human_review"]["scores"]
    assert report["reviewer"]["verdicts"]
    assert report["confidence"]["overall"] is not None
    assert report["divergences"]
    assert report["final_conclusion"]["conclusion"]


def test_diagnosis_version_loop(client, monkeypatch):
    """二期版本循环：v1 定稿 → 客户反馈 → 增量重评 → v2 定稿 + 档案检索"""
    import diagnosis.agents as agents
    monkeypatch.setattr(agents, "_default_json_call", _fake_json_call)

    # v1
    s = client.post("/api/v1/diagnosis/start", json={"requirement": "基于知识库的问答系统"}).json()
    run_id = s["run_id"]
    client.post("/api/v1/diagnosis/review", json={
        "run_id": run_id, "human_scores": s["generator"]["dimension_scores"], "human_reasons": {}})
    v1 = client.post("/api/v1/diagnosis/finalize", json={
        "run_id": run_id, "customer_name": "客户A", "confirmed": True}).json()
    assert v1["version"] == "v1"
    assert v1["previous_version"] is None
    assert v1["changelog"] == []

    # 客户反馈（data 维度）
    fb = client.post("/api/v1/diagnosis/feedback",
                     data={"run_id": run_id, "feedback_text": "客户反馈数据质量不足"})
    assert fb.status_code == 200
    fbbody = fb.json()
    assert "data" in fbbody["touched_dimensions"]

    # 增量重评：只动 data（5→3），generation 沿用 v1
    nv = client.post("/api/v1/diagnosis/next-version", json={"run_id": run_id, "mode": "incremental"})
    assert nv.status_code == 200
    nvbody = nv.json()
    assert nvbody["version"] == "v2"
    assert nvbody["generator"]["dimension_scores"]["data"] == 3
    assert nvbody["generator"]["dimension_scores"]["generation"] == 4
    assert any(c["dimension"] == "data" for c in nvbody["changelog"])

    # v2 review + finalize
    client.post("/api/v1/diagnosis/review", json={
        "run_id": run_id, "human_scores": nvbody["generator"]["dimension_scores"], "human_reasons": {}})
    v2 = client.post("/api/v1/diagnosis/finalize", json={
        "run_id": run_id, "customer_name": "客户A", "confirmed": True}).json()
    assert v2["version"] == "v2"
    assert v2["previous_version"] == "v1"
    assert any(c["dimension"] == "data" for c in v2["changelog"])
    assert v2["client_feedback"] and v2["client_feedback"][0]["items"]

    # 档案检索
    runs = client.get("/api/v1/diagnosis/runs").json()["runs"]
    assert any(x["run_id"] == run_id and x["versions"] == 2 for x in runs)
    arch = client.get(f"/api/v1/diagnosis/archive/{run_id}").json()
    assert len(arch["versions"]) == 2
    assert arch["versions"][-1]["version"] == "v2"


def _finalize_diagnosis(client, monkeypatch, requirement="基于知识库的问答系统"):
    """辅助：跑完一次诊断并定稿，返回 run_id"""
    import diagnosis.agents as agents
    monkeypatch.setattr(agents, "_default_json_call", _fake_json_call)
    s = client.post("/api/v1/diagnosis/start", json={"requirement": requirement}).json()
    client.post("/api/v1/diagnosis/review", json={
        "run_id": s["run_id"], "human_scores": s["generator"]["dimension_scores"], "human_reasons": {}})
    client.post("/api/v1/diagnosis/finalize", json={"run_id": s["run_id"], "customer_name": "测试客户", "confirmed": True})
    return s["run_id"]


def test_cases_deliverable(client, monkeypatch):
    """一期：诊断定稿 → 可打印交付物案例"""
    run_id = _finalize_diagnosis(client, monkeypatch)
    r = client.post("/api/v1/cases/create", json={"source_type": "diagnosis", "run_id": run_id})
    assert r.status_code == 200
    body = r.json()
    assert body["urls"]["html"]
    html = client.get(body["urls"]["html"])
    assert html.status_code == 200 and "需求诊断报告" in html.text
    if body.get("has_pdf"):
        assert client.get(body["urls"]["pdf"]).status_code == 200


def test_diagnosis_report_v21_sections(client, monkeypatch):
    """v2.1：报告含「整体可行性评估」章节 + 每维「对抗评审过程」内联块 + 非技术对抗（非 JSON）"""
    run_id = _finalize_diagnosis(client, monkeypatch)
    r = client.post("/api/v1/cases/create", json={"source_type": "diagnosis", "run_id": run_id})
    assert r.status_code == 200
    html = client.get(r.json()["urls"]["html"]).text

    # 1) 整体可行性评估章节
    assert "7. 整体可行性评估" in html
    assert "7.1 技术可行性：五维得分概览" in html
    assert "7.2 非技术可行性（各维 Generator 立场 vs Critic 盲审）" in html
    assert "7.3 综合建议" in html

    # 2) 每维对抗评审过程内联块（非 JSON：出现 Generator 立场/Critic 独立盲审/采纳结论）
    for dim_name in ("生成性", "推理复杂度", "不确定性容忍度", "数据可得性", "实时性要求"):
        assert f"对抗评审过程 · {dim_name}" in html
    assert "Generator 立场" in html
    assert "Critic 独立盲审立场" in html
    assert "采纳结论" in html

    # 3) 非技术各维：Generator 立场 vs Critic 盲审 + 红黄绿信号
    for cat in ("商业价值与 ROI", "组织承接与变革阻力", "系统集成复杂度", "合规与安全", "风险全景"):
        assert cat in html
    assert "值不值得投" in html and "主要阻力" in html and "先做什么" in html
    # 信号徽章存在（红黄绿之一）
    assert any(s in html for s in (">红<", ">黄<", ">绿<"))
    # 非技术对抗分歧可见
    assert "分歧：" in html

    # 4) 附录 A 完整原文保留（含非技术可行性 JSON 原文）
    assert "non_tech_feasibility" in html and "non_tech_audit" in html


def test_diagnosis_report_v22_business_proposal(client, monkeypatch):
    """v2.2：报告含「商务提案（供洽谈讨论）」章节，五块齐全，洽谈口径标注，附录顺延 15/16"""
    run_id = _finalize_diagnosis(client, monkeypatch)
    r = client.post("/api/v1/cases/create", json={"source_type": "diagnosis", "run_id": run_id})
    assert r.status_code == 200
    html = client.get(r.json()["urls"]["html"]).text

    # 1) 章节存在且五块齐全
    assert "14. 商务提案（供洽谈讨论）" in html
    for sub in ("14.1 投入估算与分期", "14.2 时间里程碑", "14.3 责任清单（摊开边界）",
                "14.4 试点范围与退出机制", "14.5 替代方案与不做的代价"):
        assert sub in html

    # 2) 洽谈确认口径标注
    assert "此为讨论用初步估算，最终以商务洽谈确认为准" in html
    assert "供贵方决策与洽谈讨论" in html

    # 3) 实质内容：投入区间 + 依据、里程碑时间、责任条目、可量化成功标准、替代方案对比、机会成本
    assert "万元" in html and "投入依据" in html
    assert "第 2 周末" in html  # 时间里程碑给出「第一个能用的东西」具体时点
    assert "阻塞开工" in html
    assert "甲方责任" in html and "乙方责任" in html
    assert "%" in html  # 成功标准可量化（带数字）
    assert "机会成本" in html and "替代方案" in html

    # 4) 附录顺延为 15/16 章，既有多章节结构不破坏
    assert "15. 附录 A · 完整对抗评审过程" in html
    assert "16. 附录 B · 多轮客户反馈与版本演进" in html
    assert "7. 整体可行性评估" in html
    assert "对抗评审过程 · 生成性" in html
    assert "non_tech_feasibility" in html


def test_mapping_flow(client, monkeypatch):
    """二期：字段映射工作台 LLM 初判 + 导出适配器"""
    import mapping.service as ms
    monkeypatch.setattr(ms, "_default_json_call", lambda s, u: {
        "mappings": [{"target": "name", "source": "customer_name", "rule": "direct",
                      "expression": "customer_name", "confidence": "high"}],
        "notes": "测试映射",
    })
    r = client.post("/api/v1/mapping/create", json={
        "name": "测试映射",
        "source_fields": [{"name": "customer_name", "sample": "张三"}],
        "target_fields": [{"name": "name", "sample": "张三"}],
    })
    assert r.status_code == 200
    assert r.json()["mappings"][0]["source"] == "customer_name"
    exp = client.post(f"/api/v1/mapping/{r.json()['run_id']}/export", json={})
    assert exp.status_code == 200
    assert "def transform" in exp.json()["adapter_code"]


def test_annotation_consistency(client):
    """二期：双人标注 → 一致性 → 评测集"""
    a = client.post("/api/v1/annotation/create", json={"name": "测试", "items": ["样本A", "样本B"]}).json()
    run = a["run_id"]
    client.post(f"/api/v1/annotation/{run}/label", json={"item_id": 1, "annotator": "甲", "label": "x"})
    client.post(f"/api/v1/annotation/{run}/label", json={"item_id": 1, "annotator": "乙", "label": "x"})
    client.post(f"/api/v1/annotation/{run}/label", json={"item_id": 2, "annotator": "甲", "label": "x"})
    client.post(f"/api/v1/annotation/{run}/label", json={"item_id": 2, "annotator": "乙", "label": "y"})
    ev = client.post(f"/api/v1/annotation/{run}/build-eval", json={}).json()
    assert ev["agreed"] == 1 and ev["disagreements"] == 1


def test_kb_chunk(client):
    """三期：知识库分块 + 质检"""
    r = client.post("/api/v1/kb/chunk", json={"text": "这是一段文档。" * 50, "chunk_size": 100, "overlap": 30})
    assert r.status_code == 200
    assert r.json()["chunk_count"] > 1
    assert r.json()["quality"]["total"] == r.json()["chunk_count"]


def test_cropper_from_diagnosis(client, monkeypatch):
    """三期接线：诊断结论 → 裁剪器预填"""
    run_id = _finalize_diagnosis(client, monkeypatch)
    r = client.get(f"/api/v1/cropper/from-diagnosis/{run_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["diagnosis_context"]["run_id"] == run_id
    assert body["plan"]["enabled_modules"]


def test_diagnosis_rename_and_state(client, monkeypatch):
    """历史诊断：人工命名 + 可恢复执行状态（继续）"""
    run_id = _finalize_diagnosis(client, monkeypatch)
    r = client.post(f"/api/v1/diagnosis/{run_id}/rename", json={"name": "AI助教需求诊断"})
    assert r.status_code == 200
    assert r.json()["name"] == "AI助教需求诊断"

    runs = client.get("/api/v1/diagnosis/runs").json()["runs"]
    me = [x for x in runs if x["run_id"] == run_id][0]
    assert me["name"] == "AI助教需求诊断"

    st = client.get(f"/api/v1/diagnosis/{run_id}/state").json()
    assert st["run_id"] == run_id
    assert st["generator"]["dimension_scores"]
    assert st["confirmed"] is True
    assert st["version"] == "v1"


def test_confidence_and_budget():
    from diagnosis.archive import BUDGET_MAX_CALLS, compute_confidence, consume_call, create_run, new_run_id

    c = compute_confidence(
        {"generation": 4, "reasoning": 3, "uncertainty": 4, "data": 5, "real_time": 2},
        {"generation": 2, "reasoning": 3, "uncertainty": 4, "data": 5, "real_time": 2},
    )
    assert c["per_dimension"]["generation"] == 0.5
    assert "generation" in c["needs_confirm"]
    assert c["level"] in ("high", "medium", "low")

    run_id = new_run_id()
    create_run(run_id, {"requirement": "x"})
    for _ in range(BUDGET_MAX_CALLS):
        assert consume_call(run_id) > 0
    assert consume_call(run_id) == -1  # 超预算


def test_cropper_plan(client):
    r = client.post("/api/v1/cropper/plan", json={
        "customer_id": "c1",
        "budget": 100000,
        "timeline_weeks": 2,
        "hardware": {"gpu": None},
        "environment": {"docker": True, "network": "intranet-isolated", "external_access": False},
        "data": {"total_records": 10000, "quality": "medium"},
        "users": {"total_users": 50},
        "compliance": {},
    })
    assert r.status_code == 200
    body = r.json()
    assert "enabled_modules" in body and "deleted_modules" in body
    assert "data_prep" in body["enabled_modules"]


def test_prototype_templates_and_run(client, monkeypatch):
    import prototype_assembler.templates.qa_agent as qa
    monkeypatch.setattr(qa, "_qa_llm_call", lambda agent, ctx, u: "finish: 测试回答")

    t = client.get("/api/v1/prototype/templates")
    assert t.status_code == 200
    assert "knowledge_qa" in t.json()["templates"]

    r = client.post("/api/v1/prototype/run", json={"template": "knowledge_qa", "user_input": "什么是RAG？"})
    assert r.status_code == 200
    body = r.json()
    assert body["llm_mode"] == "llm"
    assert body["result"] == "测试回答"


def test_monitor_record_and_metrics(client):
    r = client.post("/api/v1/monitor/record", json={
        "success": True, "latency_ms": 100, "input_tokens": 50, "output_tokens": 30, "model": "deepseek-chat",
    })
    assert r.status_code == 200

    m = client.get("/api/v1/monitor/metrics")
    assert m.status_code == 200
    body = m.json()
    assert "metrics" in body and "alerts" in body
    assert body["metrics"]["total_requests"] >= 1


def test_flywheel_feedback_pool_export(client):
    f = client.post("/api/v1/flywheel/feedback", json={
        "request_id": "r1", "user_input": "问题", "model_output": "回答", "feedback_type": "dislike",
    })
    assert f.status_code == 200

    p = client.get("/api/v1/flywheel/pool")
    assert p.status_code == 200
    assert any(x["request_id"] == "r1" for x in p.json()["pool"])

    e = client.post("/api/v1/flywheel/export-assets", json={"project_id": "p1", "project_summary": "测试项目"})
    assert e.status_code == 200
    assert e.json()["total_assets"] > 0


def test_data_prep_run_with_upload(client, monkeypatch):
    # 用固定哈希向量替代 chromadb 嵌入，保证测试不依赖模型/网络
    def fake_embed(self, text):
        return [
            float(int(hashlib.md5((text + str(i)).encode("utf-8")).hexdigest(), 16) % 1000) / 1000.0
            for i in range(8)
        ]

    import data_prep.cleaning.semantic_dedup as sd
    monkeypatch.setattr(sd.SemanticDeduplicator, "_embed_text", fake_embed)

    csv_content = "content\n" + "".join(
        f"这是第{i}条用于测试的语义各异的数据内容\n" for i in range(20)
    )
    files = {"file": ("sample.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    r = client.post("/api/v1/data-prep/run", files=files, data={"eval_samples": "5"})
    assert r.status_code == 200
    body = r.json()
    assert body["raw_count"] == 20
    assert body["cleaned_count"] > 0
    assert body["eval_set_count"] == 5
    assert len(body["artifacts"]) == 4


def test_deploy_run(client):
    r = client.post("/api/v1/deploy/run", json={"mode": "docker-compose", "image_name": "toolkit-app"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "docker-compose"
    assert body["artifacts"]
    # 不应在仓库根目录写入 Dockerfile
    from pathlib import Path
    assert not (Path(__file__).resolve().parent.parent / "Dockerfile").exists()


def test_data_prep_unsupported_type(client):
    files = {"file": ("sample.txt", io.BytesIO(b"hello"), "text/plain")}
    r = client.post("/api/v1/data-prep/run", files=files, data={"eval_samples": "5"})
    assert r.status_code == 400
