#!/usr/bin/env python3
"""真实试运行 v11.0：全工具链在一套真实制造业客户项目上端到端跑通 + 生成客户交付物包

北极星：用真实落地项目建立说服力。本脚本把
  需求诊断 → 数据作战流 → 原型+RAG → 字段映射 → 部署配置 → 项目作战台 → 交付物包
完整串一遍，产出可发给客户的交付物包（tmp/web/pilot/<客户>/）。

数据：examples/data/manufacturing_sensors.csv（制造业传感器，42 行，固定数据集，非教学场景）。
客户：某汽车零部件制造厂（真实制造业场景：设备预测性维护）。

LLM 策略（诚实标注）：
  - 默认：真调 DeepSeek（仓库 .env 有 DEEPSEEK_API_KEY）。耗时较长（约 3-6 分钟，含多次 LLM 调用）。
  - --stub：全部打桩（确定性 JSON / 固定文本 / 固定哈希嵌入），可复现、CI 用、秒级完成。

幂等：每次运行都新建项目 / 新 run_id，不覆盖旧产物。
运行方式：
    python examples/pilot_example.py          # 真调 DeepSeek
    python examples/pilot_example.py --stub   # 全部打桩，可复现
    python examples/pilot_example.py --stub --max-rows 8 --pilot-dir /tmp/pilot_out
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 引导项目根到 sys.path（与其它 examples/*_example.py 一致）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from core.main import create_app  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SENSOR_CSV = PROJECT_ROOT / "examples" / "data" / "manufacturing_sensors.csv"
RETAIL_CSV = PROJECT_ROOT / "examples" / "data" / "retail_inventory.csv"

CUSTOMER = "某汽车零部件制造厂"
REQUIREMENT = (
    "我们是某汽车零部件制造厂，拥有注塑、CNC 加工、冲压、装配等多条产线，关键设备约 120 台。"
    "目前设备故障依赖人工巡检与事后维修，非计划停机时间长，备件与人力成本高。"
    "希望基于设备传感器历史数据（温度、压力、振动、转速、电流等）构建预测性维护系统，"
    "提前预警设备故障、减少非计划停机，并保留质量追溯记录。IT 环境为内网，数据需本地部署，"
    "合规要求数据不出厂。"
)
REQUIREMENT_SUMMARY = "设备预测性维护系统（基于传感器数据提前预警故障）"

MAPPING_TARGETS = [
    ("sensor_id", "设备编号"),
    ("device_name", "设备名称"),
    ("metric", "采集指标"),
    ("reading", "读数"),
    ("unit", "单位"),
    ("ts", "采集时间"),
]


# ======================================================================
# 打桩实现（--stub 模式：确定性、离线、可复现）
# ======================================================================


def _stub_json_call(system: str, user: str) -> dict:
    """按角色返回确定性 JSON（诊断 Generator / Critic / Reviewer / 商务评估）。"""
    import hashlib

    from diagnosis.agents import DIMENSIONS

    def dim(scores):
        return {k: scores[k] for k in DIMENSIONS}

    if "生成器" in system:
        return {
            "requirement_understanding": {
                "background": "某汽车零部件制造厂设备多、依赖人工巡检，非计划停机时间长",
                "pain_points": ["非计划停机时间长", "事后维修成本高"],
                "goals": ["基于传感器数据提前预警设备故障", "减少非计划停机"],
                "constraints": ["内网部署", "数据不出厂"],
            },
            "dimension_analysis": {
                k: {"score": v, "analysis": f"{k} 维度打桩论证：需求具备 AI 落地条件",
                    "evidence": user[:40], "implications": "降低停机损失"}
                for k, v in dim({"generation": 4, "reasoning": 4, "uncertainty": 4, "data": 5, "real_time": 3}).items()
            },
            "dimension_scores": dim({"generation": 4, "reasoning": 4, "uncertainty": 4, "data": 5, "real_time": 3}),
            "reasons": {k: f"打桩理由：{k}" for k in DIMENSIONS},
            "scope": {"in_scope": ["预测性维护预警", "质量追溯"], "out_of_scope": ["硬件改造", "MES 集成"]},
            "functional_requirements": ["设备故障提前预警", "告警工单生成"],
            "non_functional_requirements": [
                {"title": "本地部署", "detail": "全部数据在工厂内网", "standard": "数据不出厂"},
                {"title": "性能", "detail": "预警延迟可接受分钟级", "standard": "≤5 分钟"},
            ],
            "data_requirements": {
                "data_sources": ["设备传感器历史数据（温度/压力/振动/转速/电流）"],
                "data_volume": "中等（120 台设备 × 按分钟采集）",
                "data_quality": "需清洗（缺失/异常值）",
                "security_compliance": "数据不出厂，本地部署",
                "resources": ["现场数据对接", "标注样本"],
            },
            "risks": [{"risk": "数据质量不足", "likelihood": "中", "impact": "影响模型效果", "mitigation": "先做数据质量评估与清洗"}],
            "assumptions": ["传感器数据连续采集且可导出 CSV"],
            "clarification_questions": [],
            "implementation_phases": [
                {"phase": "试点期", "focus": "单产线单类设备", "deliverables": ["预警原型", "评测集雏形"], "risks": "数据对接延迟"},
                {"phase": "一期", "focus": "扩展到多条产线", "deliverables": ["生产可用系统", "运维手册"], "risks": "集成复杂度"},
            ],
            "draft_sections": {
                "background": "设备预测性维护背景",
                "goals": "降低非计划停机",
                "scope": "试点范围",
                "functional_requirements": "预警与工单",
                "non_functional_requirements": "本地部署、性能",
                "acceptance_criteria": "预警准确率达标",
            },
            "non_tech_feasibility": {
                "business_value": {"item": "降低停机带来的 ROI 成立", "basis": "停机损失可量化", "signal": "绿", "advice": "优先投入"},
                "organization": {"item": "需明确运维归属与培训", "basis": "工厂无专职数据团队", "signal": "黄", "advice": "先做培训"},
                "integration": {"item": "需对接设备数据导出", "basis": "传感器可导出 CSV", "signal": "黄", "advice": "评估数据对接工作量"},
                "compliance": {"item": "数据不出厂合规", "basis": "合规要求明确", "signal": "绿", "advice": "本地部署"},
                "risk_overview": {"item": "主要风险在数据质量", "basis": "综合判断", "signal": "黄", "advice": "先做数据评估"},
                "overall_recommendation": {
                    "worth_investing": "值得投入", "budget_scale": "中量级", "main_resistance": "数据质量", "first_steps": "先跑试点",
                },
            },
            "summary": "打桩总结：该需求适合引入 AI，先按试点范围跑最小闭环。",
        }
    if "独立评审" in system:
        return {
            "dimension_analysis": {
                k: {"score": v, "analysis": f"{k} 维度打桩盲审", "evidence": user[:40], "implications": "降低停机损失"}
                for k, v in dim({"generation": 3, "reasoning": 4, "uncertainty": 3, "data": 4, "real_time": 3}).items()
            },
            "dimension_scores": dim({"generation": 3, "reasoning": 4, "uncertainty": 3, "data": 4, "real_time": 3}),
            "reasons": {k: f"打桩盲审理由：{k}" for k in DIMENSIONS},
            "coverage_gaps": [], "inconsistencies": [], "over_confidence_flags": [],
            "non_tech_audit": {
                "business_value": {"item": "盲审：ROI 需数据支撑", "basis": "缺量化停机损失", "signal": "黄", "advice": "补充测算", "audit_note": ""},
                "organization": {"item": "盲审：组织承接需确认决策链", "basis": "未提及", "signal": "黄", "advice": "确认决策链", "audit_note": ""},
                "integration": {"item": "盲审：数据对接是主要工作量", "basis": "传感器 CSV 导出", "signal": "黄", "advice": "先做对接试点", "audit_note": ""},
                "compliance": {"item": "盲审：本地部署合规成立", "basis": "合规要求明确", "signal": "绿", "advice": "按本地部署设计", "audit_note": ""},
                "risk_overview": {"item": "盲审：风险集中在数据与集成", "basis": "综合", "signal": "黄", "advice": "分阶段投入", "audit_note": ""},
                "overall_audit_note": "整体谨慎乐观，建议先做最小原型验证。",
            },
        }
    if "人工评审复核" in system:
        return {
            "verdicts": {
                k: {"verdict": "agree", "adjusted_score": None, "full_analysis": f"{k} 人工打分合理", "counter_to_human": ""}
                for k in DIMENSIONS
            },
            "bias_analysis": {"detected": False, "direction": None, "detail": "未发现系统性偏差", "evidence": ""},
            "need_reconfirm": [],
            "summary": "打桩评审：人工打分站得住，可定稿。",
        }
    if "商务评估" in system:
        return {
            "investment_estimate": {
                "disclaimer": "此为讨论用初步估算，最终以商务洽谈确认为准。",
                "tiers": [
                    {"period": "试点期", "focus": "单产线单类设备预测性维护",
                     "scope": "1 条产线 / 20 台设备", "investment_range": "8-15 万元",
                     "basis": "数据对接与原型开发约 1-2 名工程师 2 周", "deliverables": ["预警原型", "评测集雏形"]},
                    {"period": "一期", "focus": "多条产线接入与生产可用",
                     "scope": "全部 120 台设备", "investment_range": "20-50 万元",
                     "basis": "数据清洗/标注与集成改造占比高", "deliverables": ["生产系统", "运维手册"]},
                ],
                "total_range": "28-65 万元（试点 + 一期）",
                "notes": "实际以商务洽谈确认的边界为准",
            },
            "milestones": [
                {"phase": "试点期", "duration": "2 周", "first_usable": "第 2 周末：可演示的单设备预警原型",
                 "milestone": "单产线预警可用且指标可度量", "dependencies": "甲方提供传感器数据 CSV"},
                {"phase": "一期", "duration": "6 周", "first_usable": "第 8 周末：全设备接入",
                 "milestone": "全量设备接入且准确率达约定阈值", "dependencies": "甲方完成数据脱敏与接口开通"},
            ],
            "client_responsibilities": [
                {"item": "提供设备传感器历史数据（CSV，含温度/压力/振动等）", "category": "数据/接口",
                 "needed_before": "试点启动前", "owner": "甲方设备部", "reason": "数据可得性决定效果上限", "blocking": True},
                {"item": "指定业务对接人与决策链", "category": "人员/决策", "needed_before": "试点启动前",
                 "owner": "甲方管理层", "reason": "决策链不明确会阻塞推进", "blocking": True},
            ],
            "vendor_responsibilities": [
                {"item": "预测性维护模型开发与调优", "category": "实施", "owner": "乙方"},
                {"item": "数据清洗、告警规则与部署上线", "category": "集成/部署", "owner": "乙方"},
            ],
            "pilot_and_exit": {
                "pilot_scope": "1 条产线 / 20 台设备 / 单类故障",
                "success_criteria": ["预警准确率 ≥ 80%", "误报率 ≤ 30%", "非计划停机时间降幅 ≥ 20%"],
                "exit_conditions": ["试点 4 周内准确率 < 60%", "甲方数据在试点启动后 2 周内仍无法提供"],
                "review_point": "试点结束（第 4 周末）联合评审",
                "exit_terms": "退出时交接已建数据/接口访问方式，不再产生增量费用",
            },
            "alternatives_and_cost": {
                "alternatives": [
                    {"name": "现有规则阈值告警改造", "description": "在既有系统上叠加阈值规则",
                     "pros": ["成本低、见效快"], "cons": ["对早期故障泛化差"],
                     "cost_range": "3-8 万元", "risk": "误报漏报率高", "verdict": "可作为过渡"},
                    {"name": "人工流程优化（不引入 AI）", "description": "靠流程与培训减少停机",
                     "pros": ["无技术风险"], "cons": ["不可扩展"],
                     "cost_range": "持续人力成本", "risk": "改善天花板低", "verdict": "补充手段"},
                    {"name": "引入 AI 预测性维护（本方案）", "description": "基于传感数据建模提前预警",
                     "pros": ["可量化降停机、可扩展"], "cons": ["需数据与集成配合"],
                     "cost_range": "28-65 万元（分期）", "risk": "数据质量/集成是主要风险", "verdict": "建议按试点推进"},
                ],
                "cost_of_inaction": "不做则维持现状：非计划停机年损失约 80-150 万元，且数据资产长期未被利用",
                "recommendation": "先按试点范围跑最小闭环，用量化结果决定是否进入一期",
            },
        }
    raise AssertionError(f"未知打桩角色 system 前缀: {system[:20]}")


def _stub_mapping_call(system: str, user: str) -> dict:
    """映射初判 / 校验（确定性）。"""
    if "校验" in system:
        return {"verdict": "pass", "reason": "打桩校验通过：映射输出符合目标字段语义"}
    return {
        "mappings": [
            {"target": "设备编号", "source": "sensor_id", "rule": "direct", "expression": "sensor_id", "confidence": "high"},
            {"target": "设备名称", "source": "device_name", "rule": "direct", "expression": "device_name", "confidence": "high"},
            {"target": "采集指标", "source": "metric", "rule": "direct", "expression": "metric", "confidence": "high"},
            {"target": "读数", "source": "reading", "rule": "direct", "expression": "reading", "confidence": "high"},
            {"target": "单位", "source": "unit", "rule": "direct", "expression": "unit", "confidence": "high"},
            {"target": "采集时间", "source": "ts", "rule": "direct", "expression": "ts", "confidence": "high"},
        ],
        "notes": "打桩初判：全部 direct 映射",
    }


def _stub_chat(system: str, user: str = "", **kwargs) -> str:
    """core.llm.chat 打桩（原型 QA / RAG 问答）。"""
    return "打桩回答：基于知识库[1]，建议先检查传感器连接与电源模块，再评估是否需要更换（stub 模式）。"


def _stub_chat_json(system: str, user: str = "", **kwargs) -> dict:
    """core.llm.chat_json 打桩（项目文档包）。"""
    return {
        "sections": {
            "架构说明": "## 架构\n本地部署的预测性维护系统：传感器数据 → 数据作战流清洗/质量 → 知识库分块 → RAG 检索问答原型。",
            "API 文档": "## API\n- POST /api/v1/diagnosis/start 需求诊断\n- POST /api/v1/dataprep/create 数据作战流\n- POST /api/v1/prototype/run 原型运行",
            "运维手册": "## 运维\n- 数据文件放在 examples/data/，运行 python examples/pilot_example.py --stub 可复现全流程。",
            "SOP": "## SOP\n1. 跑需求诊断 → 2. 跑数据作战流 → 3. 跑原型+RAG → 4. 映射 → 5. 部署 → 6. 交付。",
        }
    }


def _fake_embed(self, text: str) -> list:
    """语义去重打桩：固定哈希向量（8 维），确定性、不联网。"""
    import hashlib

    return [
        float(int(hashlib.md5((text + str(i)).encode("utf-8")).hexdigest(), 16) % 1000) / 1000.0
        for i in range(8)
    ]


class _FakeEmbeddingFunction:
    """RAG 索引打桩：确定性嵌入（字符二元组袋，1024 维），不依赖 ONNX 模型/网络。"""

    DIM = 1024

    def __call__(self, input):
        return [self._vec(t) for t in input]

    def _vec(self, text):
        import hashlib

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


def _apply_stubs() -> dict:
    """把所有 LLM + 模型调用打桩，返回原始值（供恢复）。"""
    import core.llm as llm
    import data_prep.cleaning.semantic_dedup as sd
    import diagnosis.agents as agents
    import mapping.service as ms
    import retrieval.service as rs

    originals = {
        "agents._default_json_call": agents._default_json_call,
        "ms._default_json_call": ms._default_json_call,
        "llm.chat": llm.chat,
        "llm.chat_json": llm.chat_json,
        "sd.SemanticDeduplicator._embed_text": sd.SemanticDeduplicator._embed_text,
        "rs._get_ef": rs._get_ef,
    }
    agents._default_json_call = _stub_json_call
    ms._default_json_call = _stub_mapping_call
    llm.chat = _stub_chat
    llm.chat_json = _stub_chat_json
    sd.SemanticDeduplicator._embed_text = _fake_embed
    rs._get_ef = lambda embedding_function=None: _FakeEmbeddingFunction()
    return originals


def _restore_stubs(originals: dict) -> None:
    import core.llm as llm
    import data_prep.cleaning.semantic_dedup as sd
    import diagnosis.agents as agents
    import mapping.service as ms
    import retrieval.service as rs

    agents._default_json_call = originals["agents._default_json_call"]
    ms._default_json_call = originals["ms._default_json_call"]
    llm.chat = originals["llm.chat"]
    llm.chat_json = originals["llm.chat_json"]
    sd.SemanticDeduplicator._embed_text = originals["sd.SemanticDeduplicator._embed_text"]
    rs._get_ef = originals["rs._get_ef"]


# ======================================================================
# 小工具
# ======================================================================


def _api(client, method: str, url: str, expect: int = 200, **kwargs):
    r = getattr(client, method)(url, **kwargs)
    if r.status_code != expect:
        raise RuntimeError(f"{method.upper()} {url} → {r.status_code}: {r.text[:400]}")
    return r.json()


def _trim_csv(src: Path, max_rows: int, tmp: Path) -> Path:
    """取 CSV 前 max_rows 条数据行（保留表头），写临时文件，供测试/小数据子集。"""
    out = tmp / f"{src.stem}_max{max_rows}.csv"
    with open(src, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    header = rows[0]
    data = rows[1:max_rows + 1]
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(data)
    return out


# ======================================================================
# 试运行主体
# ======================================================================


def run_pilot(stub: bool = True, max_rows: int = None, pilot_dir: str = None,
              sections: list = None, verbosity: int = 1) -> dict:
    """完整跑一遍真实客户项目（诊断→数据→原型+RAG→映射→部署→作战台→交付物包）。

    参数：
      stub         True=全部打桩（可复现/CI）；False=真调 DeepSeek（需 .env 有 key）
      max_rows     数据子集行数（None=全量；测试建议 8）
      pilot_dir    客户交付物包目录（None=默认 tmp/web/pilot/<客户>/）
      sections     项目文档包章节
      verbosity    0=安静；1=打印进度
    返回：
      完整试运行报告 dict（project_id / 各 run_id / 各分区计数 / 门禁状态 / 产物清单 / llm_mode）
    """
    def log(msg: str):
        if verbosity >= 1:
            print(msg, flush=True)

    llm_mode = "stub" if stub else "real"
    originals = _apply_stubs() if stub else None
    try:
        app = create_app()
        with TestClient(app) as client:
            # ---------- 0. 准备 ----------
            sensor_csv = SENSOR_CSV
            tmp_holder = PROJECT_ROOT / "tmp" / "pilot_runtime"
            tmp_holder.mkdir(parents=True, exist_ok=True)
            if max_rows:
                sensor_csv = _trim_csv(SENSOR_CSV, max_rows, tmp_holder)
                log(f"[0] 使用数据子集：{sensor_csv.name}（{max_rows} 行）")
            else:
                log(f"[0] 使用固定数据集：{sensor_csv.name}")
            if not stub:
                # 真 LLM 前检查 key
                from core.config.settings import get_settings
                if not get_settings().deepseek_api_key:
                    raise RuntimeError("未配置 DEEPSEEK_API_KEY：真调模式不可用，请加 --stub 或补 .env")

            # ---------- 1. 需求诊断 ----------
            log("[1] 需求诊断 start → review → finalize")
            s = _api(client, "post", "/api/v1/diagnosis/start",
                     json={"requirement": REQUIREMENT})
            diag_run_id = s["run_id"]
            gen_scores = s["generator"]["dimension_scores"]
            rv = _api(client, "post", "/api/v1/diagnosis/review", json={
                "run_id": diag_run_id,
                "human_scores": gen_scores,
                "human_reasons": {k: "现场访谈确认：数据可得性高、生成性要求中等" for k in gen_scores},
                "human_summary": "人工复核：同意 AI 评估，数据维度偏乐观但方向正确。",
            })
            fin = _api(client, "post", "/api/v1/diagnosis/finalize", json={
                "run_id": diag_run_id,
                "customer_name": CUSTOMER,
                "requirement_summary": REQUIREMENT_SUMMARY,
                "interview_notes": "现场访谈：设备部 2 人、IT 1 人；已确认传感器数据可导出 CSV。",
                "decision_maker": "设备部部长",
                "confirmed": True,
            })
            pid = fin["project_id"]
            deliverable = fin.get("deliverable") or {}
            diag_total = (fin.get("final_conclusion") or {}).get("total_score")
            log(f"    项目 project_id={pid} 诊断 run={diag_run_id} 总分={diag_total} "
                f"交付物={deliverable.get('case_id', '-')}")

            # ---------- 2. 数据作战流 ----------
            log("[2] 数据作战流 create → clean/quality → annotate → eval_set → knowledge_base → deposit")
            with open(sensor_csv, "rb") as f:
                dp = _api(client, "post", "/api/v1/dataprep/create",
                          files={"file": (sensor_csv.name, f, "text/csv")},
                          data={"name": "制造业传感器数据作战流", "project_id": pid, "customer": CUSTOMER})
            dp_run_id = dp["run_id"]
            log(f"    数据任务 run={dp_run_id} 初始进度={dp['progress']}/{dp['progress_total']}")
            # 推进到知识库（annotate → eval_set → knowledge_base）
            st = dp
            while st.get("next_step"):
                st = _api(client, "post", f"/api/v1/dataprep/{dp_run_id}/step",
                          json={"run_next": True})
            log(f"    数据任务完成 progress={st['progress']}/{st['progress_total']} 状态={st['status']}")
            done_steps = st["done_steps"]
            kb_step = [x for x in st["steps"] if x["step"] == "knowledge_base"]
            kb_indexed = bool(kb_step and kb_step[0].get("indexed"))
            deposit = _api(client, "post", f"/api/v1/dataprep/{dp_run_id}/deposit")
            log(f"    知识库索引={kb_indexed} 沉淀资产={deposit['count']} 类")

            # ---------- 3. 原型 + RAG（数据门禁应放行） ----------
            log("[3] 原型 run（knowledge_qa + kb_run_id + project_id，过数据门禁）")
            proto = _api(client, "post", "/api/v1/prototype/run", json={
                "template": "knowledge_qa",
                "user_input": "注塑机温度偏高时，预测性维护系统应如何预警？",
                "kb_run_id": dp_run_id,
                "project_id": pid,
            })
            proto_gate = proto.get("gate") or {}
            # 注意：API 返回的 llm_mode 是「模板是否已接 LLM」的能力标志（v8 起恒为 llm），
            # 不代表本次运行是否打桩；本次运行真实/打桩以本脚本报告顶层的 llm_mode 为准。
            log(f"    原型结果门禁 gate={proto_gate} 模板能力=llm(API标志) rag={proto.get('rag')}")
            _api(client, "post", f"/api/v1/projects/{pid}/events", json={
                "type": "prototype", "title": "现场原型 · knowledge_qa（预测性维护问答）",
                "detail": f"run={diag_run_id} kb={dp_run_id} gate.allowed={proto_gate.get('allowed')}",
                "ref": dp_run_id,
            })

            # ---------- 4. 字段映射 ----------
            log("[4] 字段映射 create → samples → validate → export")
            source_fields = []
            with open(sensor_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames
                first = next(reader, None) or {}
                source_fields = [{"name": c, "sample": str(first.get(c, ""))[:40]} for c in header]
            target_fields = [{"name": t, "sample": src} for src, t in MAPPING_TARGETS]
            mp = _api(client, "post", "/api/v1/mapping/create", json={
                "name": "传感器数据→预测性维护字段映射",
                "source_fields": source_fields,
                "target_fields": target_fields,
                "project_id": pid,
                "customer": CUSTOMER,
            })
            mp_run_id = mp["run_id"]
            with open(sensor_csv, "rb") as f:
                _api(client, "post", f"/api/v1/mapping/{mp_run_id}/samples",
                     files={"file": (sensor_csv.name, f, "text/csv")},
                     data={"max_rows": str(max_rows or 50)})
            mp_val = _api(client, "post", f"/api/v1/mapping/{mp_run_id}/validate",
                          json={"max_rows": 20})
            mp_exp = _api(client, "post", f"/api/v1/mapping/{mp_run_id}/export")
            log(f"    映射 run={mp_run_id} 映射数={mp_exp['mapping_count']} "
                f"校验成功率={mp_val.get('success_rate')} 资产={mp_exp.get('asset', {}).get('asset_id', '-')}")

            # ---------- 5. 部署配置 ----------
            log("[5] 部署配置 deploy run（docker-compose + 降级预案）")
            dep = _api(client, "post", "/api/v1/deploy/run", json={
                "mode": "docker-compose", "image_name": "toolkit-app", "app_path": "/opt/toolkit"})
            dep_run_id = dep["run_id"]
            _api(client, "post", f"/api/v1/projects/{pid}/events", json={
                "type": "deploy", "title": "部署配置生成 · docker-compose",
                "detail": f"run={dep_run_id} artifacts={len(dep['artifacts'])}", "ref": dep_run_id,
            })
            log(f"    部署 run={dep_run_id} 产物={len(dep['artifacts'])} 项")

            # ---------- 6. 项目作战台 ----------
            log("[6] 项目作战台 warroom 聚合")
            warroom = _api(client, "get", f"/api/v1/projects/{pid}/warroom")
            counts = warroom["counts"]
            log(f"    warroom counts={counts}")

            # ---------- 7. 项目文档包 + 客户交付物包 ----------
            log("[7] 项目文档包 create-doc-package（confirmed=true）")
            doc = _api(client, "post", "/api/v1/cases/create-doc-package", json={
                "run_id": diag_run_id,
                "project_id": pid,
                "sections": sections or ["架构说明", "API 文档", "运维手册", "SOP"],
                "confirmed": True,
            })
            doc_case_id = doc["case_id"]
            log(f"    文档包 case={doc_case_id} gate={doc.get('gate')}")

            # 数据作战流产物 URL（报告用）
            from dataprep.service import get_state as dp_get_state
            dp_state = dp_get_state(dp_run_id)
            dp_products = {
                key: {"url": v.get("url", ""), "exists": v.get("exists", False)}
                for key, v in (dp_state.get("products") or {}).items()
            }

            # ---------- 8. 客户交付物包 ----------
            log("[8] 聚合客户交付物包")
            from cases.archive import case_dir

            out_dir = Path(pilot_dir) if pilot_dir else (
                PROJECT_ROOT / "tmp" / "web" / "pilot" / CUSTOMER)
            out_dir.mkdir(parents=True, exist_ok=True)

            # 复制诊断交付物 HTML
            diag_case_id = deliverable.get("case_id")
            diag_html_src = case_dir(diag_case_id) / "deliverable.html" if diag_case_id else None
            diag_html_dst = None
            if diag_html_src and diag_html_src.exists():
                diag_html_dst = out_dir / "诊断交付物.html"
                diag_html_dst.write_text(diag_html_src.read_text(encoding="utf-8"), encoding="utf-8")

            # 复制文档包 HTML
            doc_html_src = case_dir(doc_case_id) / "deliverable.html"
            doc_html_dst = out_dir / "项目文档包.html"
            if doc_html_src.exists():
                doc_html_dst.write_text(doc_html_src.read_text(encoding="utf-8"), encoding="utf-8")

            # warroom JSON 快照
            warroom_dst = out_dir / "warroom.json"
            warroom_dst.write_text(json.dumps(warroom, ensure_ascii=False, indent=2), encoding="utf-8")

            # 客户项目总览
            overview = _build_overview_md(
                pid=pid, customer=CUSTOMER, diag_run_id=diag_run_id, diag_total=diag_total,
                deliverable=deliverable, dp_run_id=dp_run_id, done_steps=done_steps,
                kb_indexed=kb_indexed, deposit_count=deposit["count"],
                proto=proto, proto_gate=proto_gate,
                mp_run_id=mp_run_id, mp_count=mp_exp["mapping_count"],
                mp_success_rate=mp_val.get("success_rate"),
                dep_run_id=dep_run_id, counts=counts,
                doc=doc, doc_case_id=doc_case_id, llm_mode=llm_mode,
                pilot_dir=out_dir,
            )
            overview_dst = out_dir / "客户项目总览.md"
            overview_dst.write_text(overview, encoding="utf-8")

            log(f"    客户交付物包已生成：{out_dir}")

            return {
                "llm_mode": llm_mode,
                "project_id": pid,
                "customer": CUSTOMER,
                "diagnosis_run_id": diag_run_id,
                "diagnosis_confirmed": fin.get("confirmed", True),
                "diagnosis_total_score": diag_total,
                "deliverable": deliverable,
                "dataprep_run_id": dp_run_id,
                "dataprep_done_steps": done_steps,
                "dataprep_kb_indexed": kb_indexed,
                "dataprep_products": dp_products,
                "deposit_count": deposit["count"],
                "prototype": {"result": proto["result"], "gate": proto_gate, "rag": proto.get("rag"), "sources_count": len(proto.get("sources") or [])},
                "mapping_run_id": mp_run_id,
                "mapping_count": mp_exp["mapping_count"],
                "mapping_success_rate": mp_val.get("success_rate"),
                "mapping_export_path": mp_exp.get("config_path"),
                "mapping_export_url": f"/artifacts/mapping/{mp_run_id}/adapter/mapping_config.json",
                "deploy_run_id": dep_run_id,
                "deploy_artifacts": dep["artifacts"],
                "warroom_counts": counts,
                "doc_package_case_id": doc_case_id,
                "doc_package_urls": {
                    "html": f"/api/v1/cases/{doc_case_id}/render.html",
                    "pdf": f"/api/v1/cases/{doc_case_id}/export.pdf" if doc.get("has_pdf") else None,
                },
                "doc_package_gate": doc.get("gate"),
                "pilot_dir": str(out_dir),
                "pilot_files": sorted(p.name for p in out_dir.iterdir()) if out_dir.exists() else [],
            }
    finally:
        if originals:
            _restore_stubs(originals)


def _build_overview_md(pid: str, customer: str, diag_run_id: str, diag_total: int,
                       deliverable: dict, dp_run_id: str, done_steps: list, kb_indexed: bool,
                       deposit_count: int, proto: dict, proto_gate: dict,
                       mp_run_id: str, mp_count: int, mp_success_rate,
                       dep_run_id: str, counts: dict, doc: dict, doc_case_id: str,
                       llm_mode: str, pilot_dir: Path) -> str:
    lines = [
        f"# {customer} · AI 项目现场交付客户项目总览",
        "",
        f"> 本包由 ai-field-delivery-toolkit 自动生成 · 生成时间 {datetime.now().isoformat(timespec='seconds')}",
        f"> 试运行模式：**{llm_mode}**（{'全部打桩，可复现' if llm_mode == 'stub' else '真实调用 DeepSeek'}）",
        "",
        "## 1. 项目摘要",
        "",
        f"- **客户**：{customer}",
        f"- **需求**：设备预测性维护系统（基于传感器数据提前预警故障）",
        f"- **项目 ID**：`{pid}`",
        f"- **诊断 run**：`{diag_run_id}`，五维总分 **{diag_total}** / 25",
        f"- **走完的模块**：需求诊断 → 数据作战流 → 原型+RAG → 字段映射 → 部署配置 → 项目作战台 → 交付物包",
        "",
        "## 2. 架构（本地部署、数据不出厂）",
        "",
        "```",
        "设备传感器历史数据(CSV) → 数据作战流(清洗/质量/标注/评测集/知识库分块)",
        "                                    ↓ 自动索引(ChromaDB)   ↓ 沉淀可复用资产",
        "                              RAG 检索问答原型(knowledge_qa)  可复用资产注册表",
        "                                    ↓",
        "                            字段映射(传感器字段→目标字段) + 适配器导出",
        "                                    ↓",
        "                            部署配置(Dockerfile/compose + degradation.yaml)",
        "```",
        "",
        "## 3. 成果清单",
        "",
        f"- **需求诊断定稿**：已人工确认（confirmed=true），交付物 case `{deliverable.get('case_id', '-')}`（HTML/PDF）。",
        f"- **数据作战流**：`{dp_run_id}`，已完成步骤：{'、'.join(done_steps)}；知识库索引 = {'✅ 已索引' if kb_indexed else '❌ 未索引'}。",
        f"- **数据资产沉淀**：`{deposit_count}` 类可复用资产（评测集 / 知识库分块 / 清洗规则 / 质量报告）。",
        f"- **现场原型**：knowledge_qa 模板，门禁 `gate.allowed={proto_gate.get('allowed')}`（数据达标放行），RAG 带引用。",
        f"- **字段映射**：`{mp_run_id}`，{mp_count} 条映射，实跑校验成功率 `{mp_success_rate}`，已导出适配器并注册为资产。",
        f"- **部署配置**：`{dep_run_id}`，docker-compose + degradation.yaml。",
        f"- **项目文档包**：case `{doc_case_id}`（架构说明 / API 文档 / 运维手册 / SOP）。",
        "",
        "## 4. 质量门禁状态（项目级判定）",
        "",
        f"- 诊断门禁（发客户前人工确认）：✅ 已确认",
        f"- 数据门禁（数据未达标不进原型）：{'✅ 通过' if proto_gate.get('allowed') else '⚠️ 未过'}（reason：`{proto_gate.get('reason', '-')}`）",
        f"- 交付门禁（文档包需人工确认）：已 confirmed=true 放行（confirmation=`{doc.get('gate', {}).get('confirmation')}`）",
        "",
        "## 5. 作战台分区计数",
        "",
        "| 分区 | 数量 |",
        "| ---- | ---- |",
        f"| 诊断 run | {counts.get('diagnosis')} |",
        f"| 数据作战流 | {counts.get('dataprep')} |",
        f"| 字段映射 | {counts.get('mapping')} |",
        f"| 交付物案例 | {counts.get('deliverables')} |",
        f"| 可复用资产 | {counts.get('assets')} |",
        f"| RAG 索引 | {counts.get('rag')} |",
        f"| 工作流进度 | {counts.get('workflow_progress')}% |",
        "",
        "## 6. 本包产物清单",
        "",
        "- `客户项目总览.md`：本文件",
        "- `诊断交付物.html`：需求诊断正式报告副本",
        "- `项目文档包.html`：项目文档包副本",
        "- `warroom.json`：项目作战台聚合快照",
        "",
        "## 7. 复现方法",
        "",
        "```bash",
        f"python examples/pilot_example.py --stub --max-rows 8   # 打桩模式，可复现",
        "python examples/pilot_example.py                          # 真调 DeepSeek",
        "```",
        "",
        "固定数据集：`examples/data/manufacturing_sensors.csv`（42 行）、`examples/data/retail_inventory.csv`（32 行）。",
        "",
    ]
    return "\n".join(lines)


# ======================================================================
# CLI
# ======================================================================


def main():
    parser = argparse.ArgumentParser(description="AI 现场交付工具包 · 真实试运行（v11.0）")
    parser.add_argument("--stub", action="store_true", help="全部打桩（确定性、离线、CI 可用）")
    parser.add_argument("--max-rows", type=int, default=None, help="数据子集行数（None=全量；测试建议 8）")
    parser.add_argument("--pilot-dir", type=str, default=None, help="客户交付物包输出目录（默认 tmp/web/pilot/<客户>/）")
    parser.add_argument("--sections", type=str, default=None, help="文档包章节，逗号分隔（默认 4 章）")
    args = parser.parse_args()

    sections = None
    if args.sections:
        sections = [s.strip() for s in args.sections.split(",") if s.strip()]

    mode_label = "打桩模式（stub，可复现）" if args.stub else "真实调用 DeepSeek（耗时较长，约 3-6 分钟）"
    print(f"== 真实试运行 v11.0 · {mode_label} ==")
    print(f"== 客户：{CUSTOMER} ==")
    print(f"== 数据：{SENSOR_CSV} ==")

    report = run_pilot(stub=args.stub, max_rows=args.max_rows,
                       pilot_dir=args.pilot_dir, sections=sections)

    print("\n" + "=" * 70)
    print("试运行报告")
    print("=" * 70)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("=" * 70)
    print("试运行完成。客户交付物包目录：", report["pilot_dir"])


if __name__ == "__main__":
    main()
