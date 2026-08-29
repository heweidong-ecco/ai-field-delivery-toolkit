"""FDE 操作台 HTTP API：把各功能模块包装为 REST 端点

契约由 web/ 前端（index.html + app.js）固定，返回原始 JSON（不套 {code,message,data} 包装）。
模块级单例：monitor 收集器、数据飞轮管道（内存/文件持久化，重启清空）。
工作产物统一写入 tmp/web/（已 gitignore）。
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import Optional, List

from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from core.logging.logger import get_logger

logger = get_logger()

# 加载 .env 到 os.environ：pydantic-settings 会把 .env 读进 Settings，但不会导出到 shell，
# 部署前环境检查的 bash 子进程需要真实环境变量
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_ROOT = PROJECT_ROOT / "tmp" / "web"

router = APIRouter(prefix="/api/v1")


# ---------- 模块级单例（遵循仓库 _x / get_x() 模式） ----------

_collector = None
_flywheel = None


def get_collector():
    """监控指标收集器（内存，重启清空）"""
    global _collector
    if _collector is None:
        from monitor.metrics import MetricsCollector
        _collector = MetricsCollector()
    return _collector


def get_flywheel():
    """数据飞轮管道（标注池持久化到 tmp/web/flywheel/annotation_pool.json）"""
    global _flywheel
    if _flywheel is None:
        from data_flywheel.pipeline import DataFlywheelPipeline
        pool_dir = ARTIFACT_ROOT / "flywheel"
        pool_dir.mkdir(parents=True, exist_ok=True)
        _flywheel = DataFlywheelPipeline(storage_path=str(pool_dir / "annotation_pool.json"))
    return _flywheel


# ---------- 自动挂项目档案（诊断/案例 → 项目时间线） ----------


def _ensure_project(customer_name: str) -> str:
    """按客户名自动创建/复用项目，返回 project_id"""
    from projects.archive import create_project, list_projects
    name = f"{customer_name} 项目" if customer_name and customer_name not in ("未填写", "") else "默认项目"
    for p in list_projects():
        if p.get("customer") == customer_name or p.get("name") == name:
            return p["project_id"]
    return create_project(name, customer_name)["project_id"]


def _add_project_event(pid: str, etype: str, title: str, detail: str = "", ref: str = None) -> None:
    from projects.archive import add_event
    try:
        add_event(pid, etype, title, detail, ref)
    except Exception:
        pass


# ---------- 请求模型 ----------


class DiagnosisRequest(BaseModel):
    generation: int = Field(..., ge=1, le=5)
    reasoning: int = Field(..., ge=1, le=5)
    uncertainty: int = Field(..., ge=1, le=5)
    data: int = Field(..., ge=1, le=5)
    real_time: int = Field(..., ge=1, le=5)


class ManualReviewModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    dimension_scores: dict
    reasons: dict = {}
    summary: Optional[str] = None


class DiagnosisReportRequest(BaseModel):
    customer_name: str
    requirement_summary: str
    ai_feasibility: Optional[dict] = None
    feasibility_result: Optional[dict] = None  # 兼容：无人工复核时的旧字段
    manual_review: Optional[ManualReviewModel] = None
    interview_notes: Optional[str] = None
    decision_maker: Optional[str] = None


class DiagnosisAIRequest(BaseModel):
    requirement: str = Field(..., min_length=1)
    prompt_template: Optional[str] = None


class DiagnosisStartRequest(BaseModel):
    requirement: str = Field(..., min_length=1)
    prompt_template: Optional[str] = None
    clarify_answers: Optional[dict] = None


class DiagnosisReviewRequest(BaseModel):
    run_id: str
    human_scores: dict
    human_reasons: dict = {}
    human_summary: Optional[str] = None
    clarify_answers: Optional[dict] = None


class DiagnosisFinalizeRequest(BaseModel):
    run_id: str
    customer_name: str = ""
    requirement_summary: str = ""
    interview_notes: Optional[str] = None
    decision_maker: Optional[str] = None
    confirmed: bool = False


class NextVersionRequest(BaseModel):
    run_id: str
    mode: str = "incremental"


class CaseCreateRequest(BaseModel):
    source_type: str = "diagnosis"
    run_id: str


class ProjectCreateRequest(BaseModel):
    name: str
    customer: str = ""


class ProjectEventRequest(BaseModel):
    type: str = "note"
    title: str
    detail: str = ""
    ref: Optional[str] = None


class FieldModel(BaseModel):
    name: str
    sample: str = ""


class MappingCreateRequest(BaseModel):
    name: str
    source_fields: List[FieldModel]
    target_fields: List[FieldModel]
    project_id: str = ""
    customer: str = ""


class MappingUpdateRequest(BaseModel):
    mappings: list


class MappingValidateRequest(BaseModel):
    max_rows: int = 20


class MappingValidateRowRequest(BaseModel):
    row: dict


class AnnotationCreateRequest(BaseModel):
    name: str
    items: list


class AnnotationFromDataprepRequest(BaseModel):
    dataprep_run_id: str
    sample_size: int = 20
    name: Optional[str] = None


class AnnotationLabelRequest(BaseModel):
    item_id: int
    annotator: str
    label: str


class KBChunkRequest(BaseModel):
    text: str
    chunk_size: int = 500
    overlap: int = 50


class DocPackageRequest(BaseModel):
    run_id: Optional[str] = None
    project_id: Optional[str] = None
    sections: list = ["架构说明", "API 文档", "运维手册", "SOP"]
    confirmed: bool = False  # v10.0：文档包需人工确认（发客户前确认）；true 或项目已有已确认诊断才放行


class CropCaseRequest(BaseModel):
    plan: dict


class HardwareModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cpu: str = "4核"
    memory_gb: int = 16
    gpu: Optional[str] = None
    storage_gb: int = 100


class EnvironmentModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    os: str = "ubuntu-22.04"
    docker: bool = True
    network: str = "internet"
    external_access: bool = True
    network_bandwidth_mbps: int = 100


class DataModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total_records: int = 0
    daily_new: int = 0
    formats: List[str] = []
    quality: str = "medium"


class UserModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total_users: int = 10
    concurrent_peak: int = 5


class ComplianceModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data_residency: str = "on-premise"
    pii_sensitive: bool = True
    compliance_level: str = "standard"


class CropperPlanRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    customer_id: str
    budget: int = 100000
    timeline_weeks: int = 2
    hardware: HardwareModel = HardwareModel()
    environment: EnvironmentModel = EnvironmentModel()
    data: DataModel = DataModel()
    users: UserModel = UserModel()
    compliance: ComplianceModel = ComplianceModel()


class PrototypeRunRequest(BaseModel):
    template: str
    user_input: str
    kb_run_id: Optional[str] = None  # v5.0：带则走 RAG 检索问答（带引用），无则普通问答
    project_id: str = ""            # v10.0：可选，传入则过「数据未达标不进原型」门禁（真阻断）
    force: bool = False             # v10.0：人工勾选「强制继续」时跳过数据门禁（响应诚实记录 gate_override）


class RetrievalIndexRequest(BaseModel):
    kb_run_id: str
    chunks: Optional[List[str]] = None  # 缺省时自动从数据作战流知识库产物读取


class RetrievalQueryRequest(BaseModel):
    kb_run_id: str
    query: str
    top_k: int = 5


class DeployRunRequest(BaseModel):
    mode: str = "docker-compose"
    image_name: str = "toolkit-app"
    app_path: str = "/opt/toolkit"


class MonitorRecordRequest(BaseModel):
    success: bool
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = "unknown"
    hour: Optional[str] = None


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    request_id: str
    user_input: str
    model_output: str
    feedback_type: str = "dislike"
    note: Optional[str] = None


class ExportAssetsRequest(BaseModel):
    project_id: str
    project_summary: Optional[str] = None
    assets: Optional[List[dict]] = None


class AssetAdoptRequest(BaseModel):
    project_id: str = ""
    customer: str = ""
    target_run_id: str = ""


# ---------- ① 需求诊断 ----------


@router.post("/diagnosis/evaluate")
def diagnosis_evaluate(req: DiagnosisRequest):
    from diagnosis.checklist import AIFeasibilityChecklist
    return AIFeasibilityChecklist().quick_evaluate(
        generation=req.generation,
        reasoning=req.reasoning,
        uncertainty=req.uncertainty,
        data=req.data,
        real_time=req.real_time,
    )


@router.post("/diagnosis/report")
def diagnosis_report(req: DiagnosisReportRequest):
    from diagnosis.report import DiagnosisReportGenerator

    feasibility = req.ai_feasibility or req.feasibility_result
    if not feasibility or "total_score" not in feasibility:
        raise HTTPException(status_code=400, detail="缺少 AI 诊断结果（total_score），请先完成评估")

    gen = DiagnosisReportGenerator()

    # 带人工复核：报告含 AI 诊断 + 人工打分 + 对比 + 最终结论 + 建议
    if req.manual_review:
        missing = [k for k in ("generation", "reasoning", "uncertainty", "data", "real_time")
                   if k not in (req.manual_review.dimension_scores or {})]
        if missing:
            raise HTTPException(status_code=400, detail=f"人工打分缺少维度: {missing}")
        return gen.generate_with_review(
            customer_name=req.customer_name,
            requirement_summary=req.requirement_summary,
            ai_feasibility=feasibility,
            manual_scores=req.manual_review.dimension_scores,
            manual_reasons=req.manual_review.reasons,
            manual_summary=req.manual_review.summary,
            interview_notes=req.interview_notes,
            decision_maker=req.decision_maker,
        )

    # 兼容旧版（无人工复核）
    return gen.generate(
        customer_name=req.customer_name,
        requirement_summary=req.requirement_summary,
        feasibility_result=feasibility,
        interview_notes=req.interview_notes,
        decision_maker=req.decision_maker,
    )


@router.get("/diagnosis/default-prompt")
def diagnosis_default_prompt():
    """返回默认中立提示词，供前端编辑区预填"""
    from diagnosis.ai_scorer import DEFAULT_NEUTRAL_PROMPT
    return {"prompt": DEFAULT_NEUTRAL_PROMPT}


@router.post("/diagnosis/ai")
def diagnosis_ai(req: DiagnosisAIRequest):
    """AI 中立视角评估（单次，兼容旧版）：输入客户需求 → 五维打分 + 理由 + 总结"""
    from diagnosis.ai_scorer import ai_evaluate
    try:
        return ai_evaluate(req.requirement, req.prompt_template or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/diagnosis/start")
def diagnosis_start(req: DiagnosisStartRequest):
    """多 Agent 一期：Generator 打分 + Critic 盲审 + 置信度 + 分歧 + 自动带出相关案例与资产"""
    from diagnosis.orchestrator import BudgetExceeded, start_diagnosis
    try:
        result = start_diagnosis(req.requirement, req.prompt_template or None, req.clarify_answers)
        # Q7：自动带出相关历史案例（Agent 记忆）
        from cases.archive import search_cases
        result["related_cases"] = search_cases(query=req.requirement, limit=3)
        # v6.0：新增相关可复用资产（诊断方案/文档包/评测集等），不改变既有字段
        from assets.service import suggest
        result["related_assets"] = suggest(
            query=req.requirement,
            kinds=["diagnosis_plan", "doc_package", "eval_set", "kb_chunks", "cleaning_rules", "mapping_config"],
            top_k=5,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except BudgetExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))


@router.post("/diagnosis/review")
def diagnosis_review(req: DiagnosisReviewRequest):
    """多 Agent 一期：人工打分 + Reviewer 盲审人工 + 分歧"""
    from diagnosis.orchestrator import BudgetExceeded, review_human
    try:
        return review_human(req.run_id, req.human_scores, req.human_reasons, req.human_summary, req.clarify_answers)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BudgetExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))


@router.post("/diagnosis/finalize")
def diagnosis_finalize(req: DiagnosisFinalizeRequest):
    """多 Agent 一期：人工强制确认 → 定稿报告（自动挂项目档案 + 自动生成交付物 HTML/PDF）"""
    from diagnosis.orchestrator import finalize
    try:
        report = finalize(
            req.run_id, req.customer_name, req.requirement_summary,
            req.interview_notes, req.decision_maker, req.confirmed,
        )
        # 自动挂项目档案：按客户创建/复用项目（先算 pid，作为本项目聚合/按项目过滤的归属）
        pid = _ensure_project(report.get("customer_name"))
        report["project_id"] = pid
        # v7.0：把项目归属落盘到诊断 run 档案（只增 project_id 字段，旧档案兼容），
        # 作战台聚合与 workflow 按项目过滤的可靠基础
        try:
            from diagnosis.archive import update_run
            update_run(req.run_id, project_id=pid)
        except Exception as e:
            logger.warning(f"诊断 run 落盘 project_id 失败 run_id={req.run_id}: {e}")
        # 自动生成正式交付物（HTML + 尽力 PDF），保证「打开报告」永远有处可开
        try:
            from cases.service import create_diagnosis_case
            from cases.archive import CASES_ROOT
            case_meta = create_diagnosis_case(req.run_id, project_id=pid)
            report["deliverable"] = {
                "case_id": case_meta["case_id"],
                "html_url": f"/api/v1/cases/{case_meta['case_id']}/render.html",
                "pdf_url": f"/api/v1/cases/{case_meta['case_id']}/export.pdf" if case_meta.get("has_pdf") else None,
                "path": str(CASES_ROOT / case_meta["case_id"] / "deliverable.html"),
            }
            # 交付物信息写入档案，历史诊断恢复时仍可打开正式报告
            from diagnosis.archive import update_run
            update_run(req.run_id, deliverable=report["deliverable"])
            # v6.0：顺手把诊断方案注册为可复用资产（幂等，失败不阻断定稿）
            try:
                from assets.service import register_from_diagnosis
                register_from_diagnosis(req.run_id, case_meta["case_id"], report,
                                        customer_name=report.get("customer_name", ""))
            except Exception as e2:
                logger.warning(f"诊断方案资产注册失败 run_id={req.run_id}: {e2}")
        except Exception as e:
            logger.warning(f"诊断定稿后自动生成交付物失败 run_id={req.run_id}: {e}")
        # 追加「诊断定稿」事件到项目时间线（ref 用 req.run_id：档案里没有 run_id 字段，report 里的 run_id 恒为空）
        _add_project_event(pid, "diagnosis", f"需求诊断定稿 {report.get('version', '')}",
                           detail=f"结论：{(report.get('final_conclusion') or {}).get('conclusion') or ''}",
                           ref=req.run_id)
        return report
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/diagnosis/feedback")
def diagnosis_feedback(
    run_id: str = Form(...),
    file: UploadFile = File(None),
    feedback_text: str = Form(""),
):
    """二期：上传/粘贴客户反馈 → 提炼客户意见条目（返回触达维度）"""
    import tempfile

    from diagnosis import feedback as fb
    from diagnosis.orchestrator import BudgetExceeded, add_client_feedback
    try:
        if file is not None and file.filename:
            suffix = Path(file.filename).suffix.lower()
            tmp = tempfile.NamedTemporaryFile(suffix=suffix or ".txt", delete=False)
            tmp_path = tmp.name
            with open(tmp_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            try:
                text = fb.read_feedback_file(tmp_path)
            finally:
                os.unlink(tmp_path)
            source = file.filename
        elif feedback_text.strip():
            text = feedback_text.strip()
            source = "手动粘贴"
        else:
            raise ValueError("请上传反馈文件或填写反馈文本")
        return add_client_feedback(run_id, text, source=source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BudgetExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))


@router.post("/diagnosis/next-version")
def diagnosis_next_version(req: NextVersionRequest):
    """二期：生成下一版评估草稿（增量/整轮重评），含相对上一版变更清单"""
    from diagnosis.orchestrator import BudgetExceeded, next_version
    try:
        return next_version(req.run_id, req.mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BudgetExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))


@router.get("/diagnosis/runs")
def diagnosis_runs(limit: int = 20):
    """列出最近诊断 run（含人工名字，供「历史/继续」）"""
    from diagnosis.orchestrator import get_archive, list_runs
    runs = []
    for run_id in list_runs(limit):
        try:
            a = get_archive(run_id)
        except FileNotFoundError:
            continue
        runs.append({
            "run_id": run_id,
            "name": a.get("name") or (a.get("requirement") or "")[:18],
            "requirement": (a.get("requirement") or "")[:60],
            "version": (a.get("report") or {}).get("version"),
            "versions": len(a.get("versions", [])),
            "confirmed": a.get("confirmed", False),
            "project_id": a.get("project_id"),  # v7.0：只增字段，作战台按项目聚合
        })
    return {"runs": runs}


class RenameRunRequest(BaseModel):
    name: str


@router.post("/diagnosis/{run_id}/rename")
def diagnosis_rename(run_id: str, req: RenameRunRequest):
    """给历史诊断设人工名字"""
    from diagnosis.orchestrator import rename_run
    try:
        return rename_run(run_id, req.name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/diagnosis/{run_id}/state")
def diagnosis_state(run_id: str):
    """返回可恢复的诊断执行状态（用于「继续历史诊断」）"""
    from diagnosis.orchestrator import get_run_state
    try:
        return get_run_state(run_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/diagnosis/archive/{run_id}")
def diagnosis_archive(run_id: str):
    """二期：返回完整档案（含版本历史），供回溯/审查"""
    from diagnosis.orchestrator import get_archive
    try:
        return get_archive(run_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------- 案例/交付物层（一期核心） ----------


@router.post("/cases/create")
def case_create(req: CaseCreateRequest):
    """把诊断定稿报告打包成可打印交付物案例（HTML + PDF + 结构化存档 + 自动挂项目）"""
    from cases.service import create_diagnosis_case
    try:
        meta = create_diagnosis_case(req.run_id)
        meta["urls"] = {
            "html": f"/api/v1/cases/{meta['case_id']}/render.html",
            "pdf": f"/api/v1/cases/{meta['case_id']}/export.pdf" if meta.get("has_pdf") else None,
        }
        # 自动挂项目档案：挂到该诊断所属项目
        from diagnosis.orchestrator import get_archive
        report = get_archive(req.run_id).get("report") or {}
        pid = _ensure_project(report.get("customer_name"))
        _add_project_event(pid, "case", f"生成交付物 {meta.get('version', '')}",
                           detail=meta.get("title", ""), ref=meta["case_id"])
        meta["project_id"] = pid
        return meta
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/cases")
def case_list(limit: int = 50):
    from cases.archive import list_cases
    return {"cases": list_cases(limit)}


@router.get("/cases/search")
def case_search(q: str = "", tags: str = "", limit: int = 20):
    """三期：跨案例检索（Agent 记忆的基础），下次交付带出相关案例/模板"""
    from cases.archive import search_cases
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    return {"cases": search_cases(q, tag_list, limit)}


@router.get("/cases/{case_id}")
def case_get(case_id: str):
    from cases.archive import load_case
    try:
        meta = load_case(case_id)
        meta["urls"] = {
            "html": f"/api/v1/cases/{case_id}/render.html",
            "pdf": f"/api/v1/cases/{case_id}/export.pdf" if meta.get("has_pdf") else None,
        }
        return meta
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/cases/{case_id}/render.html")
def case_render_html(case_id: str):
    from fastapi.responses import HTMLResponse
    from cases.archive import case_dir
    path = case_dir(case_id) / "deliverable.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="案例 HTML 不存在")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/cases/{case_id}/export.pdf")
def case_export_pdf(case_id: str):
    from fastapi.responses import FileResponse
    from cases.archive import case_dir
    path = case_dir(case_id) / "deliverable.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="案例 PDF 不存在")
    return FileResponse(path, media_type="application/pdf", filename=f"deliverable-{case_id}.pdf")


# ---------- 项目/过程记录（一期） ----------


@router.post("/projects")
def project_create(req: ProjectCreateRequest):
    from projects.archive import create_project
    return create_project(req.name, req.customer)


@router.get("/projects")
def project_list(limit: int = 50):
    from projects.archive import list_projects
    return {"projects": list_projects(limit)}


@router.get("/projects/{pid}")
def project_get(pid: str):
    from projects.archive import get_project
    try:
        return get_project(pid)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/projects/{pid}/events")
def project_add_event(pid: str, req: ProjectEventRequest):
    from projects.archive import add_event
    try:
        return add_event(pid, req.type, req.title, req.detail, req.ref)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/projects/{pid}/warroom")
def project_warroom(pid: str):
    """项目作战台（v7.0）：把项目名下全部产物真实拉齐（诊断/数据作战流/映射/交付物/资产/RAG/工作流/时间线）。

    旧 GET /projects/{pid} 不变（返回原始项目档案），本端点返回聚合视图。
    """
    from projects.warroom import build_warroom
    try:
        return build_warroom(pid)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------- 字段映射工作台（二期 · v4.0 集成工作台） ----------


@router.post("/mapping/create")
def mapping_create(req: MappingCreateRequest):
    """创建映射任务，LLM 初判映射建议；任务挂项目档案（project event）；自动带出相关映射配置资产"""
    from mapping.service import create_mapping
    try:
        result = create_mapping(
            req.name,
            [f.model_dump() for f in req.source_fields],
            [f.model_dump() for f in req.target_fields],
            project_id=req.project_id,
            customer=req.customer,
        )
        # v6.0：按任务名 + 源/目标字段建议相关映射配置（同字段复用 → 一键接入）
        from assets.service import suggest
        field_query = " ".join(
            [req.name]
            + [f.name for f in req.source_fields]
            + [f.name for f in req.target_fields]
        )
        result["related_assets"] = suggest(
            query=field_query, kinds=["mapping_config"],
            customer=req.customer, top_k=5,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/mapping/runs")
def mapping_runs(limit: int = 20):
    """列出最近映射任务（名字/状态/映射数/是否已导入样例/是否已校验/成功率，断点续接入口）"""
    from mapping.service import list_mapping_runs
    return {"runs": list_mapping_runs(limit)}


@router.get("/mapping/{run_id}")
def mapping_get(run_id: str):
    from mapping.service import get_mapping
    try:
        return get_mapping(run_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/mapping/{run_id}/update")
def mapping_update(run_id: str, req: MappingUpdateRequest):
    from mapping.service import update_mapping
    try:
        return update_mapping(run_id, req.mappings)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/mapping/{run_id}/samples")
async def mapping_samples(run_id: str, file: UploadFile = File(...), max_rows: int = Form(200)):
    """导入真实样例数据（CSV，列名=源字段名）→ 存档案 samples（原始行数 + 预览 + 全量行），供试运行"""
    from mapping.service import import_samples
    try:
        content = await file.read()
        return import_samples(run_id, content, filename=Path(file.filename or "sample.csv").name, max_rows=max_rows)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/mapping/{run_id}/validate")
def mapping_validate(run_id: str, req: Optional[MappingValidateRequest] = None):
    """把当前 mappings 对真实样例数据实跑 + LLM 校验，生成逐字段结果与成功率；结果存档案可续接"""
    from mapping.service import validate_mapping
    try:
        max_rows = req.max_rows if req else 20
        return validate_mapping(run_id, max_rows=max_rows)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/mapping/{run_id}/validate-row")
def mapping_validate_row(run_id: str, req: MappingValidateRowRequest):
    """单行试运行：对给定一行源数据执行全部映射，返回每个目标字段的映射值（前端逐行预览）"""
    from mapping.service import validate_row
    try:
        return validate_row(run_id, req.row)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/mapping/{run_id}/export")
def mapping_export(run_id: str):
    from mapping.service import export_mapping
    try:
        return export_mapping(run_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------- ⑪ 可复用资产库（v6.0：项目越多、工具越强） ----------


@router.get("/assets/list")
def assets_list(kind: str = "", limit: int = 50):
    """列出可复用资产（可过滤 kind），按注册时间倒序"""
    from assets.archive import list_assets
    return {"assets": list_assets(kind=kind or None, limit=limit)}


@router.get("/assets/search")
def assets_search(q: str = "", kinds: str = "", tags: str = "", customer: str = "", limit: int = 20):
    """检索可复用资产：关键词 + 资产类型(kinds,逗号分隔) + 标签 + 客户"""
    from assets.archive import search_assets
    kind_list = [k.strip() for k in kinds.split(",") if k.strip()]
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    return {"assets": search_assets(q=q, kinds=kind_list, tags=tag_list, customer=customer, limit=limit)}


@router.get("/assets/suggest")
def assets_suggest(q: str = "", kinds: str = "", customer: str = "", top_k: int = 5):
    """规则评分自动带出相关资产（含 reason）"""
    from assets.service import suggest
    kind_list = [k.strip() for k in kinds.split(",") if k.strip()]
    return {"suggestions": suggest(query=q, kinds=kind_list, customer=customer, top_k=top_k)}


@router.get("/assets/{asset_id}")
def assets_get(asset_id: str):
    """资产详情"""
    from assets.archive import get_asset
    try:
        return get_asset(asset_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/assets/{asset_id}/adopt")
def assets_adopt(asset_id: str, req: Optional[AssetAdoptRequest] = None):
    """一键接入历史资产。

    - mapping_config：用历史源/目标字段 + 映射预填新映射 run（状态 draft，可续做）→ 返回 run_id
    - 数据类资产（eval_set/kb_chunks/cleaning_rules/quality_report/diagnosis_plan）：
      复制 payload 到目标 dataprep run 的 products（target_run_id 给定时），并挂项目 asset_reuse 事件
    """
    from assets.service import adopt_asset
    try:
        r = req or AssetAdoptRequest()
        return adopt_asset(asset_id, project_id=r.project_id, customer=r.customer, target_run_id=r.target_run_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------- 数据标注与评测集管理（二期） ----------


@router.post("/annotation/create")
def annotation_create(req: AnnotationCreateRequest):
    """创建标注任务（双人标注 → 一致性 → 评测集）"""
    from annotation.service import create_annotation_task
    try:
        return create_annotation_task(req.name, req.items)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/annotation/runs")
def annotation_runs(limit: int = 50):
    """列出最近标注任务（run_id / name / 样本数 / 一致性统计），供前端「人工标注工作台」任务列表"""
    from annotation.service import list_tasks
    return {"tasks": list_tasks(limit)}


@router.post("/annotation/from-dataprep")
def annotation_from_dataprep(req: AnnotationFromDataprepRequest):
    """从数据作战流 cleaned_data 产物取前 N 条作为待标注样本，建人工标注任务（样本来源诚实标注）"""
    from annotation.service import create_annotation_task_from_dataprep
    try:
        return create_annotation_task_from_dataprep(req.dataprep_run_id, sample_size=req.sample_size, name=req.name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/annotation/{run_id}")
def annotation_get(run_id: str):
    from annotation.service import get_task
    try:
        return get_task(run_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/annotation/{run_id}/label")
def annotation_label(run_id: str, req: AnnotationLabelRequest):
    from annotation.service import add_label
    try:
        return add_label(run_id, req.item_id, req.annotator, req.label)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/annotation/{run_id}/build-eval")
def annotation_build_eval(run_id: str):
    """从双人一致标注构建评测集"""
    from annotation.service import ANN_ROOT, build_eval_set
    try:
        return build_eval_set(run_id, str(ANN_ROOT / run_id / "eval_set.json"))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------- 知识库构建（三期：分块 + 质检） ----------


@router.post("/kb/chunk")
def kb_chunk(req: KBChunkRequest):
    """长文本分块 + 质检（RAG 知识库最小件）"""
    from kb.service import chunk_text, quality_check
    try:
        chunks = chunk_text(req.text, req.chunk_size, req.overlap)
        return {"chunk_count": len(chunks), "chunks": chunks, "quality": quality_check(chunks)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------- 模块 manifest（自描述 + 分层说明 + 案例链接） ----------


@router.get("/manifests")
def manifest_list():
    from core.manifest import list_manifests
    return {"manifests": list_manifests()}


@router.get("/manifests/{key}")
def manifest_get(key: str):
    from core.manifest import get_manifest
    try:
        return get_manifest(key)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/guide/workflow")
def guide_workflow():
    """连贯工作流：阶段 + 模块 + 产出 + 门禁 + 贯穿模块"""
    from core.guide import workflow_guide
    return workflow_guide()


@router.get("/guide/suggestions")
def guide_suggestions():
    """动态使用建议：基于系统当前状态给出下一步"""
    from core.guide import suggestions
    return {"suggestions": suggestions()}


@router.get("/guide/{key}")
def guide_get(key: str):
    """某模块详细指南（manifest 简要 + guide 步骤/依赖/流向）"""
    from core.manifest import get_manifest
    from core.guide import get_guide
    try:
        return {"manifest": get_manifest(key), "guide": get_guide(key)}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------- 工作流 SOP 骨架 + 门禁（Q21） ----------


@router.get("/workflow/skeleton")
def workflow_skeleton():
    from core.workflow import skeleton
    return {"steps": skeleton()}


@router.get("/workflow/gate")
def workflow_gate(stage: str, project_id: str = ""):
    """v10.0：质量门禁判定（gate_check）——供前端运行前展示「数据达标 / 文档包确认」状态。

    只做判定、不拦截；拦截由各端点自行执行（/prototype/run、/cropper/from-diagnosis、
    /cases/create-doc-package）。project_id 缺省时按全局判定，reason 注明「全局判定」。
    """
    from core.workflow import gate_check
    try:
        return gate_check(stage, project_id.strip() or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workflow/{project_id}")
def workflow_status(project_id: str):
    from core.workflow import project_status
    try:
        return {"project_id": project_id, "steps": project_status(project_id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------- 项目文档包（Q18） ----------


@router.post("/cases/create-crop")
def case_create_crop(req: CropCaseRequest):
    """Q13：裁剪方案 → 可打印交付物案例"""
    from cases.service import create_crop_case
    try:
        meta = create_crop_case(req.plan)
        meta["urls"] = {
            "html": f"/api/v1/cases/{meta['case_id']}/render.html",
            "pdf": f"/api/v1/cases/{meta['case_id']}/export.pdf" if meta.get("has_pdf") else None,
        }
        return meta
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cases/create-doc-package")
def case_create_doc_package(req: DocPackageRequest):
    """Q18：生成项目文档包（架构说明/API 文档/运维手册/SOP），LLM 起草 + 模板

    v10.0：门禁硬化——文档包需人工确认（发客户前确认）。confirmed=true 或该项目已有
    已确认诊断才放行，否则 400；响应附加 gate 结果（诚实记录确认来源）。
    """
    from cases.service import create_doc_package
    from core.workflow import gate_check
    # 解析项目归属：显式 project_id 优先；否则从诊断 run 档案带出（finalize 已落盘 project_id）
    pid = req.project_id or None
    if not pid and req.run_id:
        try:
            from diagnosis.orchestrator import get_archive
            pid = get_archive(req.run_id).get("project_id") or None
        except Exception:
            pid = None
    diag_ok = False
    if pid:
        diag_ok = gate_check("diagnosis", pid).get("allowed", False)
    if not (req.confirmed or diag_ok):
        raise HTTPException(status_code=400, detail="文档包需人工确认")
    meta = create_doc_package(req.run_id, pid, req.sections)
    meta["urls"] = {
        "html": f"/api/v1/cases/{meta['case_id']}/render.html",
        "pdf": f"/api/v1/cases/{meta['case_id']}/export.pdf" if meta.get("has_pdf") else None,
    }
    # v10.0：门禁结果诚实回传（checked=false 表示无项目上下文、仅凭 confirmed=true 放行）
    gate_result = gate_check("deliver", pid) if pid else {"evidence": []}
    meta["gate"] = {
        "checked": bool(pid),
        "allowed": True,
        "reason": "文档包需人工确认",
        "evidence": gate_result.get("evidence", []),
        "confirmation": "request_confirmed" if req.confirmed else ("confirmed_diagnosis" if diag_ok else "none"),
    }
    return meta


# ---------- ② 五步裁剪 ----------


@router.get("/cropper/from-diagnosis/{run_id}")
def cropper_from_diagnosis(run_id: str):
    """三期接线：诊断结论（总分/结论/置信度）→ 裁剪器约束预填，人工可改"""
    from diagnosis.orchestrator import get_archive
    from cropper.constraints import CustomerConstraints
    from cropper.engine import crop_for_customer
    try:
        archive = get_archive(run_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # v10.0：门禁硬化——诊断未定稿确认，禁止据此裁剪发客户（真阻断）
    if not archive.get("confirmed"):
        raise HTTPException(status_code=400, detail="诊断未定稿确认,禁止据此裁剪发客户")

    report = archive.get("report") or {}
    fc = report.get("final_conclusion") or {}
    total = fc.get("total_score") or 0
    conclusion = fc.get("conclusion", "")

    # 由诊断结论推导默认预算（人工可改；不推荐 → 保守裁剪）
    if total < 10:
        budget = 20000
    elif total < 15:
        budget = 50000
    elif total < 20:
        budget = 100000
    else:
        budget = 200000

    constraints = CustomerConstraints(customer_id=report.get("customer_name") or "from-diagnosis", budget=budget)
    plan = crop_for_customer(constraints).to_dict()
    return {
        "diagnosis_context": {
            "run_id": run_id,
            "version": report.get("version", ""),
            "total_score": total,
            "conclusion": conclusion,
            "needs_confirmation": report.get("needs_confirmation", False),
        },
        "prefilled_constraints": {"budget": budget},
        "plan": plan,
    }


@router.post("/cropper/plan")
def cropper_plan(req: CropperPlanRequest):
    from cropper.constraints import (
        ComplianceConstraints, CustomerConstraints, DataConstraints,
        EnvironmentConstraints, HardwareConstraints, UserConstraints,
    )
    from cropper.engine import crop_for_customer

    constraints = CustomerConstraints(
        customer_id=req.customer_id,
        budget=req.budget,
        timeline_weeks=req.timeline_weeks,
        hardware=HardwareConstraints(**req.hardware.model_dump()),
        environment=EnvironmentConstraints(**req.environment.model_dump()),
        data=DataConstraints(**req.data.model_dump()),
        users=UserConstraints(**req.users.model_dump()),
        compliance=ComplianceConstraints(**req.compliance.model_dump()),
    )
    return crop_for_customer(constraints).to_dict()


# ---------- ③ 数据准备（文件上传） ----------


@router.post("/data-prep/run")
def data_prep_run(file: UploadFile = File(...), eval_samples: int = Form(100)):
    filename = Path(file.filename or "").name  # 去掉路径，防目录穿越
    source_type = {".csv": "csv", ".json": "json", ".pdf": "pdf"}.get(Path(filename).suffix.lower())
    if source_type is None:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型（{Path(filename).suffix or '无扩展名'}），支持 csv/json/pdf")

    run_id = uuid.uuid4().hex[:8]
    run_dir = ARTIFACT_ROOT / "data_prep" / run_id
    upload_dir = run_dir / "upload"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / filename
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    out_dir = run_dir / "output"

    from data_prep.pipeline import DataPrepPipeline
    result = DataPrepPipeline().run(
        source_type=source_type,
        source_path=str(upload_path),
        output_dir=str(out_dir),
        eval_samples=eval_samples,
    )

    artifacts = [
        f"/artifacts/data_prep/{run_id}/output/cleaned_data.json",
        f"/artifacts/data_prep/{run_id}/output/eval_set.json",
        f"/artifacts/data_prep/{run_id}/output/quality_report.json",
        f"/artifacts/data_prep/{run_id}/output/cleaning_stats.json",
    ]
    result["run_id"] = run_id
    result["artifacts"] = artifacts
    result["warning"] = "语义去重首次运行需联网下载模型（约 79MB）；内网环境请预置模型到 ~/.cache/chroma/onnx_models/"
    return result


# ---------- ③ 数据准备 · 数据作战流（项目级、可断点续接、产物沉淀复用） ----------


class DataPrepStepRequest(BaseModel):
    """执行某一步（或 run_next 顺序推进下一步）"""
    step: Optional[str] = None       # annotate / eval_set / knowledge_base / clean / quality / import
    run_next: bool = False           # true 时按顺序推进下一步
    num_samples: int = 100           # eval_set 样本数
    sample_size: int = 20            # annotate 抽样数
    chunk_size: int = 500            # kb 分块大小
    overlap: int = 50                # kb 重叠


@router.post("/dataprep/create")
async def dataprep_create(
    name: str = Form(""),
    project_id: str = Form(""),
    customer: str = Form(""),
    file: UploadFile = File(...),
):
    """新建数据作战流任务：上传 csv/json 真实数据 → 自动跑 导入/清洗/质量（前三步），返回可恢复状态"""
    filename = Path(file.filename or "").name
    source_type = {".csv": "csv", ".json": "json"}.get(Path(filename).suffix.lower())
    if source_type is None:
        raise HTTPException(status_code=400,
                            detail=f"不支持的文件类型（{Path(filename).suffix or '无扩展名'}），数据作战流支持 csv/json")
    if Path(filename).suffix.lower() == ".json":
        # 校验 JSON 可解析，避免脏数据进档案
        try:
            import json as _json
            raw = file.file.read()
            _json.loads(raw.decode("utf-8"))
            await file.seek(0)
        except Exception:
            raise HTTPException(status_code=400, detail="JSON 文件解析失败，请上传合法 JSON 数组/对象")

    run_id = uuid.uuid4().hex[:8]
    run_dir = ARTIFACT_ROOT / "dataprep" / run_id
    upload_dir = run_dir / "upload"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / filename
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 项目解析：显式 project_id 优先；否则按客户名自动建/复用（参考 _ensure_project）
    pid = project_id.strip() or None
    if not pid:
        pid = _ensure_project(customer.strip() or "")

    from dataprep.service import start_task
    try:
        result = start_task(name=name, source_path=str(upload_path),
                            project_id=pid, customer=customer, upload_filename=filename)
        # v6.0：自动带出相关数据资产（清洗规则/评测集/知识库分块/质量报告，一键接入指引）
        from assets.service import suggest
        result["related_assets"] = suggest(
            query=f"{name} {filename}",
            kinds=["cleaning_rules", "eval_set", "kb_chunks", "quality_report"],
            customer=customer, top_k=5,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/dataprep/runs")
def dataprep_runs(limit: int = 20):
    """列出最近数据作战流任务（名字/状态/进度/可恢复状态）"""
    from dataprep.service import list_tasks
    return {"runs": list_tasks(limit)}


@router.get("/dataprep/{run_id}")
def dataprep_get(run_id: str):
    """返回数据作战流任务状态 + 各步产物（断点续接入口）"""
    from dataprep.service import get_state
    try:
        return get_state(run_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/dataprep/{run_id}/step")
def dataprep_step(run_id: str, req: DataPrepStepRequest):
    """执行后续某步（annotate/eval_set/knowledge_base/…）或 run_next 顺序推进"""
    from dataprep.service import continue_step
    try:
        kwargs = {}
        if req.step == "annotate":
            kwargs["sample_size"] = req.sample_size
        elif req.step == "eval_set":
            kwargs["num_samples"] = req.num_samples
        elif req.step == "knowledge_base":
            kwargs["chunk_size"] = req.chunk_size
            kwargs["overlap"] = req.overlap
        if req.run_next:
            return continue_step(run_id, step=None, **kwargs)
        return continue_step(run_id, req.step, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/dataprep/{run_id}/rename")
def dataprep_rename(run_id: str, req: RenameRunRequest):
    """给数据作战流任务人工命名"""
    from dataprep.service import rename_task
    try:
        return rename_task(run_id, req.name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/dataprep/{run_id}/deposit")
def dataprep_deposit(run_id: str):
    """沉淀可复用资产（评测集/知识库分块/清洗规则/质量报告 → cases/archive，search_cases 可检索）"""
    from dataprep.service import deposit
    try:
        return deposit(run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------- ④ 原型组装 ----------


@router.get("/prototype/templates")
def prototype_templates():
    from prototype_assembler.assembler import PrototypeAssembler
    asm = PrototypeAssembler()
    return {"templates": list(asm.TEMPLATE_MAP.keys()), "meta": asm.TEMPLATE_META}


@router.post("/prototype/run")
def prototype_run(req: PrototypeRunRequest):
    from prototype_assembler.assembler import PrototypeAssembler
    assembler = PrototypeAssembler()
    if req.template not in assembler.TEMPLATE_MAP:
        raise HTTPException(status_code=400, detail=f"未知模板: {req.template}，可选: {list(assembler.TEMPLATE_MAP.keys())}")

    # v10.0：质量门禁硬化——数据未达标不进原型（真阻断）。传 project_id 才检查；
    # 未通过且未勾选 force → 403（detail 含 gate_reason）；force=true 通过时响应诚实记录 gate_override。
    gate = None
    if req.project_id:
        from core.workflow import gate_check
        gate = gate_check("data_prep", req.project_id)
        if not gate["allowed"] and not req.force:
            raise HTTPException(status_code=403, detail={
                "message": gate["reason"], "gate_reason": gate["reason"], "stage": "data_prep"})

    kwargs = {}
    if req.kb_run_id:
        kwargs["kb_run_id"] = req.kb_run_id
    agent = assembler.create(req.template, **kwargs)
    result = agent.run(req.user_input)
    # v8.0：四个模板均注入真实 LLM 能力。llm_mode 诚实判定：
    # ReAct/Reflexion 看 llm_call；Plan-Execute 看 plan_generator/step_executor/answer_generator。
    llm_mode = (
        "llm"
        if (getattr(agent, "llm_call", None)
            or getattr(agent, "plan_generator", None)
            or getattr(agent, "answer_generator", None))
        else "placeholder"
    )
    resp = {"template": req.template, "result": result, "llm_mode": llm_mode}
    if req.kb_run_id:
        resp["rag"] = True
        resp["sources"] = getattr(agent, "last_sources", []) or []
    # v10.0：门禁结果诚实回传
    if req.project_id:
        resp["gate"] = {"checked": True, "allowed": gate["allowed"], "reason": gate["reason"]}
        if not gate["allowed"] and req.force:
            resp["gate_override"] = True
            resp["gate_reason"] = gate["reason"]
    else:
        resp["gate"] = {"checked": False}
    return resp


# ---------- RAG 检索（v5.0：知识库 → 向量化 → 检索 → 问答带引用） ----------


@router.post("/retrieval/index")
def retrieval_index(req: RetrievalIndexRequest):
    """把知识库分块索引进 ChromaDB（真实向量化）。

    kb_run_id 可为数据作战流 run_id：缺省 chunks 时自动读取其 knowledge_base 步骤的 chunks 产物。
    """
    from retrieval.service import index_knowledge
    try:
        chunks = req.chunks
        if not chunks:
            from dataprep.service import load_kb_chunks
            chunks = load_kb_chunks(req.kb_run_id)
        if not chunks:
            raise HTTPException(status_code=400,
                                detail="未找到可索引的分块：请提供 chunks，或先执行数据作战流 knowledge_base 步骤")
        idx = index_knowledge(req.kb_run_id, chunks)
        idx["kb_run_id"] = req.kb_run_id
        return idx
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"知识库索引失败 kb_run_id={req.kb_run_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrieval/query")
def retrieval_query(req: RetrievalQueryRequest):
    """RAG 问答：检索 top_k 相关分块 → 组装 prompt → 调 LLM → {answer, sources}"""
    from retrieval.service import rag_answer
    try:
        return rag_answer(req.kb_run_id, req.query, top_k=req.top_k)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"RAG 问答失败 kb_run_id={req.kb_run_id}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/retrieval/indexed")
def retrieval_indexed():
    """列出已索引的知识库（供前端 ④ 原型 tab「选择知识库」）"""
    from retrieval.service import list_indexed
    return {"kbs": list_indexed()}


# ---------- ⑤ 部署加固 ----------


@router.post("/deploy/run")
def deploy_run(req: DeployRunRequest):
    if req.mode not in ("docker-compose", "bare-metal"):
        raise HTTPException(status_code=400, detail=f"不支持的部署模式: {req.mode}")

    run_id = uuid.uuid4().hex[:8]
    run_dir = ARTIFACT_ROOT / "deploy" / run_id
    project_dir = run_dir / "project"
    out_dir = run_dir / "output"
    project_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 把部署前检查脚本拷进临时项目目录，让预检真正执行（脚本依赖 .env 中 POSTGRES_* 等变量）
    script_src = PROJECT_ROOT / "deploy_hardener" / "pre_deploy_check.sh"
    if script_src.exists():
        script_dst = project_dir / "deploy_hardener" / "pre_deploy_check.sh"
        script_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(script_src, script_dst)

    from deploy_hardener.pipeline import DeployHardenerPipeline
    result = DeployHardenerPipeline().run(
        project_dir=str(project_dir),
        output_dir=str(out_dir),
        mode=req.mode,
        image_name=req.image_name,
        app_path=req.app_path,
    )

    # 映射产物路径为可下载 URL
    files = [result["degradation_config"]]
    if req.mode == "docker-compose":
        files += [result.get("compose_file"), result.get("dockerfile")]
    else:
        files.append(result.get("systemd_service"))
    artifacts = []
    for p in files:
        if not p:
            continue
        rel = Path(p).resolve().relative_to(ARTIFACT_ROOT.resolve())
        artifacts.append(f"/artifacts/{rel.as_posix()}")
    result["run_id"] = run_id
    result["artifacts"] = artifacts
    return result


# ---------- ⑥ 监控 ----------


@router.post("/monitor/record")
def monitor_record(req: MonitorRecordRequest):
    get_collector().record_request(
        success=req.success,
        latency_ms=req.latency_ms,
        input_tokens=req.input_tokens,
        output_tokens=req.output_tokens,
        model=req.model,
        hour=req.hour,
    )
    return {"recorded": True}


@router.get("/monitor/metrics")
def monitor_metrics():
    """监控指标：手动记录 + 真实 LLM 用量（core/llm.py 计费打点自动喂）"""
    from monitor.alerts import AlertManager
    from monitor.metrics import MetricsCollector
    from core.llm import get_llm_usage

    metrics = get_collector().get_metrics()
    alerts = AlertManager().check_all(metrics)

    # 真实 LLM 用量与成本（来自 core/llm.py 计费打点）
    real = get_llm_usage()
    cost = 0.0
    per_model = {}
    prices = MetricsCollector.MODEL_PRICES
    for m, v in real.get("by_model", {}).items():
        p = prices.get(m, prices["unknown"])
        c = v["input_tokens"] / 1_000_000 * p["input"] + v["output_tokens"] / 1_000_000 * p["output"]
        per_model[m] = round(c, 4)
        cost += c
    real["cost"] = round(cost, 4)
    real["cost_by_model"] = per_model

    return {"metrics": metrics, "alerts": alerts, "real_llm_usage": real}


# ---------- ⑦ 数据飞轮 ----------


@router.post("/flywheel/feedback")
def flywheel_feedback(req: FeedbackRequest):
    return get_flywheel().record_feedback(
        request_id=req.request_id,
        user_input=req.user_input,
        model_output=req.model_output,
        feedback_type=req.feedback_type,
        note=req.note,
    )


@router.get("/flywheel/pool")
def flywheel_pool():
    return {"pool": get_flywheel().feedback_collector.get_pool()}


@router.post("/flywheel/export-assets")
def flywheel_export(req: ExportAssetsRequest):
    run_id = uuid.uuid4().hex[:8]
    out_dir = ARTIFACT_ROOT / "flywheel" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    return get_flywheel().export_assets(
        project_id=req.project_id,
        assets=req.assets,
        output_path=str(out_dir / "project_assets.json"),
        project_summary=req.project_summary,
    )
