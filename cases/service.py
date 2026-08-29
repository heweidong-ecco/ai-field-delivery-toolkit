"""案例服务：从模块产出创建可打印交付物案例"""

from datetime import datetime

from cases.archive import case_dir, new_case_id, save_case
from cases.render import build_crop_plan_html, build_diagnosis_html, build_doc_package_html, render_html_to_pdf

DOC_PACKAGE_SYSTEM = (
    "你是 AI 项目交付文档起草助手。基于给定的项目上下文，起草指定的交付文档章节（写给客户离开后自己能看懂的）。\n"
    "要求：每章 150-300 字，用 Markdown（标题/列表）；内容具体可操作，不写空话；不确定处如实说明。\n"
    "只输出 JSON：{\"sections\": {\"<章节名>\": \"Markdown 内容\", ...}}"
)


def create_crop_case(plan: dict) -> dict:
    """Q13：裁剪方案 → 可打印交付物案例（HTML + PDF + 结构化存档）"""
    case_id = new_case_id()
    html = build_crop_plan_html(plan)
    d = case_dir(case_id)
    d.mkdir(parents=True, exist_ok=True)
    has_pdf = render_html_to_pdf(html, str(d / "deliverable.pdf"))
    metadata = {
        "case_id": case_id,
        "source_type": "cropper",
        "title": f"裁剪方案 · {plan.get('customer_id', '')}",
        "conclusion": f"启用 {len(plan.get('enabled_modules', []))} 模块 / 删除 {len(plan.get('deleted_modules', []))}",
        "summary": "五步裁剪（质疑→删除→简化→加速→自动化）方案交付物",
        "tags": ["裁剪方案", *plan.get("enabled_modules", [])[:2]],
        "has_pdf": has_pdf,
        "created_at": datetime.now().isoformat(),
    }
    save_case(case_id, metadata, html=html)
    return metadata


def create_doc_package(run_id: str = None, project_id: str = None, sections: list = None) -> dict:
    """Q18：项目文档包（架构说明/API 文档/运维手册/SOP），LLM 起草 + 模板 → HTML 交付物"""
    from core.llm import chat_json
    from diagnosis.orchestrator import get_archive
    from projects.archive import get_project

    sections = sections or ["架构说明", "API 文档", "运维手册", "SOP"]

    context_lines = []
    title_parts = []
    if run_id:
        report = get_archive(run_id).get("report") or {}
        title_parts.append(report.get("requirement_summary") or "需求诊断")
        context_lines.append(f"需求摘要：{report.get('requirement_summary')}")
        context_lines.append(f"需求原文：{(report.get('requirement') or '')[:200]}")
        context_lines.append(f"诊断结论：{(report.get('final_conclusion') or {}).get('conclusion')}")
        fc = report.get("final_conclusion") or {}
        context_lines.append(f"总分：{fc.get('total_score')}")
    if project_id:
        proj = get_project(project_id)
        title_parts.append(proj.get("name", ""))
        context_lines.append(f"项目：{proj.get('name')} / 客户：{proj.get('customer')}")
        context_lines.append("项目事件：" + "；".join(
            f"{e['type']}:{e['title']}" for e in proj.get("events", [])[-8:]))
    context = "\n".join(context_lines) or "（无项目上下文，按通用交付模板起草）"

    data = chat_json(DOC_PACKAGE_SYSTEM,
                     f"需要起草的章节：{sections}\n\n项目上下文：\n{context}", temperature=0.3)
    doc_sections = {k: (data.get("sections", {}) or {}).get(k, "（该章节未生成）") for k in sections}

    title = "项目文档包 · " + ("/".join(title_parts) if title_parts else "通用")
    case_id = new_case_id()
    html = build_doc_package_html(title, doc_sections)

    d = case_dir(case_id)
    d.mkdir(parents=True, exist_ok=True)
    has_pdf = render_html_to_pdf(html, str(d / "deliverable.pdf"))

    metadata = {
        "case_id": case_id,
        "source_type": "doc_package",
        "run_id": run_id,
        "project_id": project_id,
        "title": title,
        "conclusion": "项目文档包",
        "summary": f"章节：{'、'.join(sections)}",
        "tags": ["文档包", *sections[:2]],
        "has_pdf": has_pdf,
        "created_at": datetime.now().isoformat(),
    }
    save_case(case_id, metadata, html=html)
    return metadata


def create_diagnosis_case(run_id: str, project_id: str = None) -> dict:
    """把诊断定稿报告打包成可打印交付物案例（HTML + 尽力 PDF + 结构化元数据）

    v7.0：project_id 只增不改。显式传入优先；否则回退读诊断 run 档案的 project_id
    （diagnosis_finalize 已把所属项目落盘），历史诊断 run 无该字段则为 None。
    """
    from diagnosis.orchestrator import get_archive

    archive = get_archive(run_id)
    report = archive.get("report")
    if not report:
        raise ValueError(f"run {run_id} 尚无定稿报告，请先 finalize")
    pid = project_id or archive.get("project_id") or None

    case_id = new_case_id()
    html = build_diagnosis_html(report)

    d = case_dir(case_id)
    d.mkdir(parents=True, exist_ok=True)
    has_pdf = render_html_to_pdf(html, str(d / "deliverable.pdf"))

    fc = report.get("final_conclusion") or {}
    gen = report.get("generator") or {}
    metadata = {
        "case_id": case_id,
        "source_type": "diagnosis",
        "run_id": run_id,
        "project_id": pid,
        "version": report.get("version", ""),
        "title": f"{report.get('customer_name', '')} · {report.get('requirement_summary', '')}",
        "conclusion": fc.get("conclusion", ""),
        "total_score": fc.get("total_score"),
        "summary": gen.get("summary", ""),
        "tags": ["诊断", report.get("version", ""), fc.get("conclusion", "")],
        "has_pdf": has_pdf,
        "created_at": datetime.now().isoformat(),
    }
    save_case(case_id, metadata, html=html)
    return metadata
