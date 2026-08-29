"""项目作战台聚合（v7.0）：把项目名下的全部产物真实拉齐到一个视图

北极星：「以项目为中心」——打开一个项目，诊断 / 数据作战流 / 映射 / 交付物 / 资产 /
RAG 索引 / 工作流进度 / 过程时间线都在一个作战台上。本模块不造假、不做壳，
所有分区都从各模块的真实档案（tmp/web/<模块>/）跨模块拉取并按项目过滤。
"""

from core.logging.logger import get_logger

logger = get_logger()

# 每类产物在作战台展示的条数上限（控制返回体量，不返回巨量数据）
_SECTION_LIMIT = 20
# 过滤用扫描条数（聚合需在全局档案里找到本项目产物，故扫全量但只返回摘要）
_SCAN_LIMIT = 500


def build_warroom(project_id: str) -> dict:
    """构建某项目的作战台聚合视图。

    返回：
        project          项目档案（get_project 原样）
        workflow         项目级工作流状态（按本项目判定，见 core.workflow.project_status）
        diagnosis_runs   诊断 run（run 档案 project_id==pid / 项目 diagnosis 事件 ref==run_id / 客户匹配，并集）
        dataprep_runs    数据作战流任务（project_id==pid）
        mapping_runs     映射任务（project_id==pid）
        cases            交付物案例（project_id==pid 或客户匹配）
        assets           可复用资产（project_id==pid 或客户==项目客户）
        indexed_kbs      RAG 索引（kb_run_id 属于本项目数据作战流 run）
        events           完整时间线
        counts           各分区数量 + 工作流进度百分比
    """
    from projects.archive import get_project

    project = get_project(project_id)  # FileNotFoundError 向上抛，由 API 层转 404
    customer = project.get("customer") or ""
    events = project.get("events") or []
    diag_refs = {e.get("ref") for e in events if e.get("type") == "diagnosis" and e.get("ref")}

    # 工作流（项目级过滤）
    from core.workflow import project_status
    workflow = project_status(project_id)

    # 诊断 run：run 档案 project_id==pid 或 项目 diagnosis 事件 ref==run_id 或 客户匹配（并集）
    diagnosis_runs = _collect_diagnosis_runs(project_id, customer, diag_refs)

    # 数据作战流任务（补 URL，供前端「续做」跳转）
    from dataprep.service import list_tasks
    dataprep_runs = [_dataprep_summary(t) for t in list_tasks(_SCAN_LIMIT)
                     if t.get("project_id") == project_id][:_SECTION_LIMIT]

    # 映射任务（补 URL，供前端「续做」跳转）
    from mapping.service import list_mapping_runs
    mapping_runs = [_mapping_summary(r) for r in list_mapping_runs(_SCAN_LIMIT)
                    if r.get("project_id") == project_id][:_SECTION_LIMIT]

    # 交付物案例（补 HTML/PDF URL，供前端直接打开）
    from cases.archive import list_cases
    cases = [_case_summary(c) for c in list_cases(_SCAN_LIMIT)
             if c.get("project_id") == project_id
             or (customer and c.get("customer") == customer)][:_SECTION_LIMIT]

    # 可复用资产（补一键接入 URL，供前端 adopt）
    from assets.archive import list_assets
    assets = [_asset_summary(a) for a in list_assets(limit=_SCAN_LIMIT)
              if a.get("project_id") == project_id
              or (customer and a.get("customer") == customer)][:_SECTION_LIMIT]

    # RAG 索引：kb_run_id 属于本项目数据作战流 run
    dataprep_run_ids = {t.get("run_id") for t in dataprep_runs}
    from retrieval.service import list_indexed
    indexed_kbs = [k for k in list_indexed()
                   if k.get("kb_run_id") in dataprep_run_ids][:_SECTION_LIMIT]

    counts = {
        "diagnosis": len(diagnosis_runs),
        "dataprep": len(dataprep_runs),
        "mapping": len(mapping_runs),
        "deliverables": len(cases),
        "assets": len(assets),
        "rag": len(indexed_kbs),
        "workflow_progress": _workflow_progress(workflow),
    }

    return {
        "project": project,
        "workflow": workflow,
        "counts": counts,
        "diagnosis_runs": diagnosis_runs,
        "dataprep_runs": dataprep_runs,
        "mapping_runs": mapping_runs,
        "cases": cases,
        "assets": assets,
        "indexed_kbs": indexed_kbs,
        "events": events,
    }


# ---------- 各分区摘要构造 ----------


def _case_summary(c: dict) -> dict:
    case_id = c.get("case_id")
    return {
        "case_id": case_id,
        "source_type": c.get("source_type", ""),
        "run_id": c.get("run_id"),
        "project_id": c.get("project_id"),
        "title": c.get("title", ""),
        "conclusion": c.get("conclusion", ""),
        "has_pdf": c.get("has_pdf", False),
        "html_url": f"/api/v1/cases/{case_id}/render.html" if case_id else "",
        "pdf_url": f"/api/v1/cases/{case_id}/export.pdf" if case_id and c.get("has_pdf") else None,
        "created_at": c.get("created_at", ""),
    }


def _asset_summary(a: dict) -> dict:
    asset_id = a.get("asset_id")
    return {
        "asset_id": asset_id,
        "kind": a.get("kind", ""),
        "title": a.get("title", ""),
        "summary": a.get("summary", ""),
        "customer": a.get("customer", ""),
        "project_id": a.get("project_id"),
        "payload_url": a.get("payload_url", ""),
        "adopt_url": f"/api/v1/assets/{asset_id}/adopt" if asset_id else "",
        "created_at": a.get("created_at", ""),
    }


def _dataprep_summary(t: dict) -> dict:
    run_id = t.get("run_id")
    return {
        "run_id": run_id,
        "name": t.get("name", ""),
        "status": t.get("status", ""),
        "progress": t.get("progress"),
        "progress_total": t.get("progress_total"),
        "next_step": t.get("next_step"),
        "project_id": t.get("project_id"),
        "customer": t.get("customer", ""),
        "url": f"/api/v1/dataprep/{run_id}" if run_id else "",   # 断点续接入口
    }


def _mapping_summary(r: dict) -> dict:
    run_id = r.get("run_id")
    return {
        "run_id": run_id,
        "name": r.get("name", ""),
        "status": r.get("status", ""),
        "project_id": r.get("project_id"),
        "mapping_count": r.get("mapping_count"),
        "has_samples": r.get("has_samples"),
        "has_validation": r.get("has_validation"),
        "success_rate": r.get("success_rate"),
        "no_fail_rate": r.get("no_fail_rate"),
        "created_at": r.get("created_at", ""),
        "url": f"/api/v1/mapping/{run_id}" if run_id else "",   # 断点续接入口
    }


def _collect_diagnosis_runs(project_id: str, customer: str, diag_refs: set) -> list:
    """诊断 run 过滤：run 档案 project_id==pid 或 项目 diagnosis 事件 ref==run_id 或 客户匹配（并集）。"""
    from diagnosis.orchestrator import get_archive, list_runs
    out = []
    for run_id in list_runs(_SCAN_LIMIT):
        try:
            a = get_archive(run_id)
        except FileNotFoundError:
            continue
        report = a.get("report") or {}
        if (a.get("project_id") == project_id or run_id in diag_refs
                or (customer and report.get("customer_name") == customer)):
            out.append(_diag_summary(run_id, a, report))
    return out[:_SECTION_LIMIT]


def _diag_summary(run_id: str, archive: dict, report: dict) -> dict:
    return {
        "run_id": run_id,
        "name": archive.get("name") or (archive.get("requirement") or "")[:18],
        "requirement": (archive.get("requirement") or "")[:60],
        "version": report.get("version", ""),
        "confirmed": archive.get("confirmed", False),
        "customer_name": report.get("customer_name", ""),
        "project_id": archive.get("project_id"),
        "url": f"/api/v1/diagnosis/{run_id}/state",   # 续做入口（前端 resumeDiagnosis）
        "archive_url": f"/api/v1/diagnosis/archive/{run_id}",
    }


def _workflow_progress(workflow: list) -> int:
    if not workflow:
        return 0
    done = sum(1 for s in workflow if s.get("done"))
    return int(round(done / len(workflow) * 100))
