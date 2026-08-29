"""工作流 SOP 骨架 + 硬性门禁（Q21）

标准骨架：诊断→数据→原型→部署→交付；硬性门禁只设关键质量点（数据未达标不进原型、发客户前必须确认）。
各步骤状态基于项目事件 + 模块档案（诊断/数据作战流/映射/案例/文档包）判定。

v7.0 修复：project_status(project_id) 传入项目 ID 时**按本项目判定**（不再被其它项目产物撑高）；
project_id 为空时保持原全局判定（兼容历史调用）。

v10.0：质量门禁从「状态展示」变为「真阻断判定」——新增 gate_check(stage_key, project_id)
统一判定关键质量点（诊断须人工确认 / 数据须真实质量评估 / 文档包须人工确认），
project_status 的 gate_passed 对齐该判定并附带 gate_reason（只增字段，不破坏旧行为）。
"""

from typing import Optional

STEPS = [
    {"key": "diagnosis", "name": "① 需求诊断", "desc": "多 Agent 对抗评审 + 人工强制确认", "gate": "发客户前必须人工确认"},
    {"key": "data_prep", "name": "② 数据准备", "desc": "清洗 / 标注 / 评测集（含知识库）", "gate": "数据未达标不进原型"},
    {"key": "prototype", "name": "③ 现场原型", "desc": "真实数据验证核心假设", "gate": None},
    {"key": "deploy", "name": "④ 部署集成", "desc": "配置生成 + 字段映射/适配器", "gate": None},
    {"key": "deliver", "name": "⑤ 交付沉淀", "desc": "项目文档包 + 案例归档", "gate": "文档包需人工确认"},
]

GATE_REASONS = {
    "diagnosis": "发客户前必须人工确认",
    "data_prep": "数据未达标不进原型（缺少质量评估）",
    "deliver": "文档包需人工确认",
}


def skeleton() -> list:
    return [dict(s) for s in STEPS]


def gate_check(stage_key: str, project_id: Optional[str] = None) -> dict:
    """质量门禁判定（v10.0，真阻断的依据）：只做判定，不负责拦截。

    返回 {allowed, reason, evidence, stage, mode}：
    - diagnosis：允许 = 该项目有已确认诊断（项目 diagnosis 事件，或诊断 run 档案
      project_id==pid 且 confirmed）；
    - data_prep：允许 = 该项目有 dataprep run（project_id==pid）**且其 quality_report
      产物真实存在**（数据被真实评估过＝达标）；
    - deliver：允许 = 该项目有已确认诊断 且 存在带 project_id 的 doc_package 案例。
    - project_id 为空：用全局判定（全局有已确认诊断 / 全局有 quality_report 产物），
      reason 注明「全局判定」。
    """
    if stage_key not in GATE_REASONS:
        raise ValueError(f"未知门禁阶段: {stage_key}，可选: {list(GATE_REASONS)}")
    if stage_key == "diagnosis":
        allowed, evidence = _gate_diagnosis(project_id)
    elif stage_key == "data_prep":
        allowed, evidence = _gate_data_prep(project_id)
    else:  # deliver
        allowed, evidence = _gate_deliver(project_id)
    reason = GATE_REASONS[stage_key]
    mode = "global" if not project_id else "project"
    if mode == "global":
        reason += "（全局判定）"
    return {"allowed": allowed, "reason": reason, "evidence": evidence, "stage": stage_key, "mode": mode}


def _gate_diagnosis(project_id: Optional[str]) -> tuple:
    """已确认诊断：诊断 run 档案 project_id==pid 且 confirmed；或项目 diagnosis 事件（finalize 后才挂）。"""
    evidence = []
    confirmed_runs = []
    diag_events = []
    if project_id:
        from projects.archive import get_project
        try:
            diag_events = [e for e in get_project(project_id).get("events", []) if e.get("type") == "diagnosis"]
        except FileNotFoundError:
            diag_events = []
        if diag_events:
            evidence.append(f"项目诊断事件×{len(diag_events)}")
        from diagnosis.orchestrator import get_archive, list_runs
        confirmed_runs = [rid for rid in list_runs(_SCAN)
                          if get_archive(rid).get("project_id") == project_id and _confirmed(rid)]
    else:
        from diagnosis.orchestrator import list_runs
        confirmed_runs = [rid for rid in list_runs(_SCAN) if _confirmed(rid)]
    if confirmed_runs:
        evidence.append(f"已确认诊断×{len(confirmed_runs)}")
    return bool(confirmed_runs or diag_events), evidence


def _gate_data_prep(project_id: Optional[str]) -> tuple:
    """数据达标：dataprep run（project_id==pid）且其 quality_report 产物文件真实存在。"""
    from dataprep.service import list_tasks
    all_runs = list_tasks(_SCAN)
    runs = all_runs if not project_id else [t for t in all_runs if t.get("project_id") == project_id]
    with_qr = [t for t in runs if (t.get("products") or {}).get("quality_report", {}).get("exists")]
    evidence = ([f"数据任务×{len(runs)}"] if runs else []) + ([f"质量报告产物×{len(with_qr)}"] if with_qr else [])
    return bool(with_qr), evidence


def _gate_deliver(project_id: Optional[str]) -> tuple:
    """文档包门禁：有已确认诊断 且 存在带 project_id 的 doc_package 案例。"""
    diag_ok, diag_ev = _gate_diagnosis(project_id)
    from cases.archive import list_cases
    all_cases = list_cases(_SCAN)
    doc_pkgs = [c for c in all_cases if c.get("source_type") == "doc_package"
                and (not project_id or c.get("project_id") == project_id)]
    evidence = diag_ev + ([f"文档包×{len(doc_pkgs)}"] if doc_pkgs else [])
    return diag_ok and bool(doc_pkgs), evidence


def project_status(project_id: Optional[str] = None) -> list:
    """各步骤状态：done / gate_passed / evidence

    - project_id 为空：按全局档案判定（历史行为，兼容旧调用）。
    - project_id 传入：**按本项目判定**——诊断 run / 数据作战流 run / 映射 run / 案例
      的 project_id 都必须等于该项目（或命中项目事件），不再被其它项目产物撑高。
    - v10.0：gate_passed 对齐 gate_check（真阻断判定），并附 gate_reason（只增字段）。
    """
    events = []
    if project_id:
        from projects.archive import get_project
        try:
            events = get_project(project_id).get("events", [])
        except FileNotFoundError:
            events = []
    etypes = {e.get("type") for e in events}

    if project_id:
        return _project_status(project_id, events, etypes)
    return _global_status(events, etypes)


def _project_status(project_id: str, events: list, etypes: set) -> list:
    """按本项目判定：每步 done 都必须有本项目自己的产物证据。"""
    # 本项目证据（全部按 project_id 过滤真实档案）
    from diagnosis.orchestrator import get_archive, list_runs
    diag_runs = [rid for rid in list_runs(_SCAN)
                 if get_archive(rid).get("project_id") == project_id]
    confirmed_diag = sum(1 for rid in diag_runs if _confirmed(rid))

    from dataprep.service import list_tasks
    dp_runs = [t for t in list_tasks(_SCAN) if t.get("project_id") == project_id]

    from mapping.service import list_mapping_runs
    mp_runs = [r for r in list_mapping_runs(_SCAN) if r.get("project_id") == project_id]

    from cases.archive import list_cases
    cases = [c for c in list_cases(_SCAN) if c.get("project_id") == project_id]
    doc_packages = [c for c in cases if c.get("source_type") == "doc_package"]

    status = []
    for s in STEPS:
        key = s["key"]
        evidence, done = [], False
        if key == "diagnosis":
            diag_ev = [e for e in events if e.get("type") == "diagnosis"]
            evidence = ([f"项目诊断事件×{len(diag_ev)}"] if diag_ev else []) + \
                       ([f"诊断 run×{len(diag_runs)}"] if diag_runs else []) + \
                       ([f"已确认诊断×{confirmed_diag}"] if confirmed_diag else [])
            done = bool(diag_ev) or bool(diag_runs)
        elif key == "data_prep":
            dp_ev = [e for e in events if e.get("type") == "dataprep"]
            evidence = ([f"数据任务×{len(dp_runs)}"] if dp_runs else []) + \
                       ([f"项目事件:{e.get('title')}" for e in dp_ev] if dp_ev else [])
            done = bool(dp_runs) or bool(dp_ev)
        elif key == "prototype":
            evidence = [f"{e.get('type')}:{e.get('title')}" for e in events
                        if e.get("type") in ("prototype", "iteration")]
            done = bool(evidence)
        elif key == "deploy":
            dp_ev = [e for e in events if e.get("type") == "deploy"]
            evidence = ([f"映射任务×{len(mp_runs)}"] if mp_runs else []) + \
                       ([f"项目事件:{e.get('title')}" for e in dp_ev] if dp_ev else [])
            done = bool(mp_runs) or bool(dp_ev)
        elif key == "deliver":
            case_ev = [e for e in events if e.get("type") == "case"]
            evidence = ([f"项目案例×{len(cases)}"] if cases else []) + \
                       ([f"文档包×{len(doc_packages)}"] if doc_packages else []) + \
                       ([f"项目事件:{e.get('title')}" for e in case_ev] if case_ev else [])
            done = bool(cases) or bool(case_ev)
        gate_passed, gate_reason = None, None
        if s.get("gate"):
            try:
                g = gate_check(key, project_id)
                gate_passed, gate_reason = g["allowed"], g["reason"]
            except Exception:
                gate_passed, gate_reason = None, None
        status.append({"key": key, "name": s["name"], "desc": s["desc"], "gate": s["gate"],
                       "done": done, "gate_passed": gate_passed, "gate_reason": gate_reason,
                       "evidence": evidence})
    return status


def _global_status(events: list, etypes: set) -> list:
    """全局判定（project_id 为空时保持的历史行为，兼容旧调用）。"""
    # 全局证据
    from diagnosis.orchestrator import list_runs
    confirmed_diag = sum(1 for rid in list_runs(_SCAN) if _confirmed(rid))
    from cases.archive import list_cases
    cases = list_cases(_SCAN)
    doc_packages = [c for c in cases if c.get("source_type") == "doc_package"]
    diag_cases = [c for c in cases if c.get("source_type") == "diagnosis"]

    from annotation.service import ANN_ROOT
    annotation_tasks = [p.name for p in ANN_ROOT.iterdir() if (p / "archive.json").exists()] if ANN_ROOT.exists() else []
    from mapping.service import MAPPING_ROOT
    mapping_tasks = [p.name for p in MAPPING_ROOT.iterdir() if (p / "archive.json").exists()] if MAPPING_ROOT.exists() else []

    status = []
    for s in STEPS:
        key = s["key"]
        evidence, done = [], False
        if key == "diagnosis":
            evidence = ([f"项目诊断事件×{len([e for e in events if e.get('type') == 'diagnosis'])}"]
                        if "diagnosis" in etypes else []) + ([f"已确认诊断×{confirmed_diag}"] if confirmed_diag else [])
            done = confirmed_diag > 0 or "diagnosis" in etypes
        elif key == "data_prep":
            evidence = ([f"标注任务×{len(annotation_tasks)}"] if annotation_tasks else []) + \
                       ([f"诊断交付物×{len(diag_cases)}"] if diag_cases else [])
            done = bool(annotation_tasks) or bool(diag_cases)
        elif key == "prototype":
            evidence = [f"{e.get('type')}:{e.get('title')}" for e in events
                        if e.get("type") in ("prototype", "iteration")]
            done = bool(evidence)
        elif key == "deploy":
            evidence = ([f"映射任务×{len(mapping_tasks)}"] if mapping_tasks else []) + \
                       [f"项目事件:{e.get('title')}" for e in events if e.get("type") == "deploy"]
            done = bool(mapping_tasks) or any(e.get("type") == "deploy" for e in events)
        elif key == "deliver":
            evidence = ([f"文档包×{len(doc_packages)}"] if doc_packages else []) + \
                       [f"项目事件:{e.get('title')}" for e in events if e.get("type") == "case"]
            done = bool(doc_packages) or any(e.get("type") == "case" for e in events)
        gate_passed, gate_reason = None, None
        if s.get("gate"):
            try:
                g = gate_check(key, None)
                gate_passed, gate_reason = g["allowed"], g["reason"]
            except Exception:
                gate_passed, gate_reason = None, None
        status.append({"key": key, "name": s["name"], "desc": s["desc"], "gate": s["gate"],
                       "done": done, "gate_passed": gate_passed, "gate_reason": gate_reason,
                       "evidence": evidence})
    return status


_SCAN = 500  # 按项目过滤时扫描的全局档案条数上限


def _confirmed(run_id: str) -> bool:
    from diagnosis.orchestrator import get_archive
    try:
        return bool(get_archive(run_id).get("confirmed"))
    except Exception:
        return False
