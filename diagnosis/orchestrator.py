"""需求诊断多 Agent 管线编排（完整过程留痕版）

start（Generator + Critic 盲审 + 置信度 + 分歧 + 完整输出留痕）
  → review（人工打分 + Reviewer 盲审 + 分歧 + 完整输出留痕）
  → finalize（人工强制确认 → 定稿报告 + 归档 + 自动生成交付物）
  → next_version（客户反馈 → 增量/整轮重评 → 反馈织入需求章节 → 版本累积变厚）

完整过程留痕：
- 档案新增 generator_full / critic_full / reviewer_full：每次 Agent 完整输出原文+解析，每版本保留。
- 同时追加 agent_log[] 记录每一步的角色/时间/完整输出，保证中间产物不丢。
- get_run_state 返回完整输出，继续历史诊断时仍能看到完整对抗过程。
"""

from datetime import datetime
from typing import Callable, Dict, Optional

from core.logging.logger import get_logger
from diagnosis import agents
from diagnosis.archive import (
    BUDGET_MAX_CALLS, calls_used, compute_confidence, consume_call,
    create_run, load_run, new_run_id, update_run,
)
from diagnosis.feedback import categorize_feedback_items, extract_feedback_items, touched_dimensions

logger = get_logger()


class BudgetExceeded(RuntimeError):
    """单次诊断 LLM 调用超预算，需人工接管"""


def _call(run_id: str, fn: Callable):
    used = consume_call(run_id)
    if used == -1:
        raise BudgetExceeded(f"本次诊断 LLM 调用已超过预算（>{BUDGET_MAX_CALLS} 次），请人工接管")
    return fn()


def _score_divergences(scores_a: Dict, scores_b: Dict, source: str) -> list:
    rows = []
    for k in agents.DIMENSIONS:
        a, b = scores_a.get(k), scores_b.get(k)
        if a is not None and b is not None and int(a) != int(b):
            rows.append({"dimension": k, "source": source, "a": int(a), "b": int(b), "delta": int(b) - int(a)})
    return rows


def _budget(run_id: str) -> dict:
    return {"used": calls_used(run_id), "max": BUDGET_MAX_CALLS}


def _log_agent(run_id: str, step: str, role: str, output: Dict) -> None:
    """把一次 Agent 完整输出追加进 agent_log（过程留痕，不丢中间产物）"""
    data = load_run(run_id)
    if data is None:
        return
    log = list(data.get("agent_log", []))
    log.append({
        "step": step, "role": role, "at": datetime.now().isoformat(),
        "output": output,
    })
    update_run(run_id, agent_log=log)


def start_diagnosis(
    requirement: str,
    prompt_template: Optional[str] = None,
    clarify_answers: Optional[dict] = None,
    llm_call: Optional[Callable[[str, str], Dict]] = None,
) -> Dict:
    """第一步：Generator 深度剖析 + Critic 盲审 + 置信度 + 分歧 + 完整输出留痕"""
    requirement = (requirement or "").strip()
    if not requirement:
        raise ValueError("客户需求描述不能为空")

    run_id = new_run_id()
    create_run(run_id, {
        "name": f"需求诊断 {requirement[:18]}",
        "requirement": requirement,
        "prompt": prompt_template,
        "prompt_modified": bool(prompt_template),
    })
    if clarify_answers:
        update_run(run_id, rounds=[{"round": 1, "answers": clarify_answers}])

    generator = _call(run_id, lambda: agents.run_generator(requirement, prompt_template=prompt_template, llm_call=llm_call))
    critic = _call(run_id, lambda: agents.run_critic(requirement, llm_call=llm_call))

    confidence = compute_confidence(generator["dimension_scores"], critic["dimension_scores"])
    divergences = _score_divergences(generator["dimension_scores"], critic["dimension_scores"], "generator_vs_critic")

    update_run(run_id,
               scores={"generator": generator["dimension_scores"], "critic": critic["dimension_scores"]},
               generator=generator, critic=critic, confidence=confidence, divergences=divergences,
               generator_full=generator, critic_full=critic)
    _log_agent(run_id, "start", "generator", generator)
    _log_agent(run_id, "start", "critic", critic)

    logger.info(f"诊断 start 完成 run_id={run_id} 置信度={confidence['level']}")
    return {
        "run_id": run_id,
        "generator": generator,
        "generator_full": generator,
        "critic": critic,
        "critic_full": critic,
        "confidence": confidence,
        "divergences": divergences,
        "budget": _budget(run_id),
    }


def review_human(
    run_id: str,
    human_scores: Dict,
    human_reasons: Optional[Dict] = None,
    human_summary: Optional[str] = None,
    clarify_answers: Optional[dict] = None,
    llm_call: Optional[Callable[[str, str], Dict]] = None,
) -> Dict:
    """第二步：人工打分 + Reviewer 盲审人工 + 分歧 + 完整输出留痕"""
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"诊断档案不存在: {run_id}")
    requirement = data["requirement"]

    if clarify_answers:
        rounds = list(data.get("rounds", [])) + [{"round": len(data.get("rounds", [])) + 1, "answers": clarify_answers}]
        update_run(run_id, rounds=rounds)

    human_scores = {k: max(1, min(5, int(v))) for k, v in human_scores.items()}
    reviewer = _call(run_id, lambda: agents.run_reviewer(
        requirement, human_scores, human_reasons or {}, llm_call=llm_call))

    divergences = list(data.get("divergences", []))
    # Reviewer 修正 vs 人工
    for k, v in (reviewer.get("verdicts") or {}).items():
        if isinstance(v, dict) and v.get("verdict") == "correct" and v.get("adjusted_score") is not None:
            adj = int(v["adjusted_score"])
            divergences.append({
                "dimension": k, "source": "reviewer_vs_human",
                "a": human_scores.get(k), "b": adj, "delta": adj - human_scores.get(k),
            })
    # Generator(AI) vs 人工
    gen_scores = (data.get("scores") or {}).get("generator", {})
    divergences += _score_divergences(gen_scores, human_scores, "generator_vs_human")

    scores = dict(data.get("scores") or {})
    scores["human"] = human_scores
    scores["reviewer"] = {k: v.get("adjusted_score") for k, v in (reviewer.get("verdicts") or {}).items()
                          if isinstance(v, dict) and v.get("verdict") == "correct" and v.get("adjusted_score") is not None}

    update_run(run_id,
               scores=scores,
               human_review={"scores": human_scores, "reasons": human_reasons or {}, "summary": human_summary or ""},
               reviewer=reviewer, reviewer_full=reviewer, divergences=divergences)
    _log_agent(run_id, "review", "reviewer", reviewer)

    return {
        "run_id": run_id,
        "human_scores": human_scores,
        "reviewer": reviewer,
        "reviewer_full": reviewer,
        "divergences": divergences,
        "budget": _budget(run_id),
    }


def finalize(
    run_id: str,
    customer_name: str = "",
    requirement_summary: str = "",
    interview_notes: Optional[str] = None,
    decision_maker: Optional[str] = None,
    confirmed: bool = False,
) -> Dict:
    """第三步：人工强制确认 → 定稿报告（版本化，完整过程入档）+ 归档"""
    if not confirmed:
        raise ValueError("请先人工确认（confirmed=true）再生成正式报告")
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"诊断档案不存在: {run_id}")

    versions = list(data.get("versions", []))
    version = f"v{len(versions) + 1}"
    changelog = data.get("last_changelog", [])

    # v2.2：定稿时一并起草「商务提案（供洽谈讨论）」（LLM，失败用规则兜底，不阻断定稿）
    proposal = _draft_commercial_proposal(run_id, data)
    data["business_proposal"] = proposal

    report = _build_report(data, customer_name, requirement_summary, interview_notes, decision_maker, version)
    versions.append({"version": version, "report": report, "changelog": changelog})
    update_run(run_id, confirmed=True, report=report, versions=versions, last_changelog=[],
               business_proposal=proposal)
    logger.info(f"诊断定稿 run_id={run_id} 版本={version}")
    return report


def add_client_feedback(
    run_id: str,
    feedback_text: str,
    source: Optional[str] = None,
    llm_call: Optional[Callable[[str, str], Dict]] = None,
) -> Dict:
    """客户反馈：提炼意见条目并归档，返回触达维度（用于增量重评）"""
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"诊断档案不存在: {run_id}")
    requirement = data["requirement"]
    current_scores = (data.get("scores") or {}).get("generator", {})

    parsed = _call(run_id, lambda: extract_feedback_items(feedback_text, requirement, current_scores, llm_call=llm_call))
    items = parsed["items"]
    touched = touched_dimensions(items)

    entry = {
        "source": source or "手动粘贴",
        "summary": parsed.get("summary", ""),
        "items": items,
        "touched_dimensions": touched,
        "added_at": datetime.now().isoformat(),
    }
    feedbacks = list(data.get("client_feedback", [])) + [entry]
    update_run(run_id, client_feedback=feedbacks)
    logger.info(f"客户反馈已归档 run_id={run_id} 条目={len(items)} 触达={touched}")
    return {
        "run_id": run_id,
        "items": items,
        "summary": entry["summary"],
        "touched_dimensions": touched,
    }


def _weave_feedback(gen: Dict, feedbacks: list) -> Dict:
    """把客户反馈条目织入 Generator 输出的需求章节（功能/非功能/开放问题/验收标准），
    保证报告随版本累积变厚。返回带 feedback_weave 的生成器输出副本。"""
    all_items = [it for fb in feedbacks for it in (fb.get("items") or [])]
    cats = categorize_feedback_items(all_items)
    gen = dict(gen)
    gen["feedback_weave"] = cats
    return gen


def next_version(
    run_id: str,
    mode: str = "incremental",
    llm_call: Optional[Callable[[str, str], Dict]] = None,
) -> Dict:
    """生成下一版评估草稿：incremental（只重评客户意见触及维度）或 full（整轮重评）。

    完整过程留痕：新版 Generator/Critic 完整输出进 generator_full/critic_full + agent_log。
    反馈织入：把全部客户反馈条目归类进 gen.feedback_weave，报告随版本累积变厚。
    """
    if mode not in ("incremental", "full"):
        raise ValueError("mode 需为 incremental 或 full")
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"诊断档案不存在: {run_id}")
    requirement = data["requirement"]
    feedbacks = data.get("client_feedback", [])
    if not feedbacks:
        raise ValueError("尚无客户反馈，请先提交客户反馈再生成下一版")

    items = [it for fb in feedbacks for it in fb.get("items", [])]
    touched = touched_dimensions(items)
    feedback_context = "\n".join(f"- {it.get('item', '')}" for it in items)
    enhanced = requirement + "\n\n【客户反馈意见（需在评估中回应，并织入需求章节）】\n" + feedback_context

    new_gen = _call(run_id, lambda: agents.run_generator(enhanced, prompt_template=data.get("prompt"), llm_call=llm_call))
    new_crit = _call(run_id, lambda: agents.run_critic(enhanced, llm_call=llm_call))

    prev_gen = data.get("generator", {})
    prev_crit = data.get("critic", {})

    def merge(prev, new, touched_set):
        scores, reasons = {}, {}
        for k in agents.DIMENSIONS:
            if mode == "full" or k in touched_set:
                scores[k] = new["dimension_scores"][k]
                reasons[k] = (new.get("reasons", {}) or {}).get(k, (prev.get("reasons", {}) or {}).get(k, ""))
            else:
                scores[k] = (prev.get("dimension_scores", {}) or {}).get(k, 3)
                reasons[k] = (prev.get("reasons", {}) or {}).get(k, "")
        merged = {
            "dimension_scores": scores, "reasons": reasons,
            "summary": new.get("summary", prev.get("summary", "")),
            "draft_notes": new.get("draft_notes", prev.get("draft_notes", "")),
            "clarification_questions": new.get("clarification_questions", prev.get("clarification_questions", [])),
        }
        # 保留新 schema 的深度字段（完整输出随版本保留）；v2.1 含非技术可行性（Generator）与非技术盲审（Critic）
        for field in ("requirement_understanding", "dimension_analysis", "scope",
                      "functional_requirements", "non_functional_requirements", "data_requirements",
                      "risks", "assumptions", "implementation_phases", "draft_sections",
                      "non_tech_feasibility", "non_tech_audit"):
            if new.get(field):
                merged[field] = new[field]
            elif prev.get(field):
                merged[field] = prev[field]
        # 对齐 dimension_analysis 的 score 与合并后的 dimension_scores（增量模式非触达维度沿用上一版分数，
        # 深度分析的 score 必须与权威计分一致，避免报告内数字打架）
        da = merged.get("dimension_analysis")
        if isinstance(da, dict):
            for k in agents.DIMENSIONS:
                e = da.get(k)
                if isinstance(e, dict) and scores.get(k) is not None:
                    e["score"] = scores[k]
        return merged

    merged_gen = merge(prev_gen, new_gen, set(touched))
    merged_crit = merge(prev_crit, new_crit, set(touched))

    # 反馈织入需求章节
    merged_gen = _weave_feedback(merged_gen, feedbacks)

    # 变更清单：相对上一版
    changelog = []
    for k in agents.DIMENSIONS:
        pg = (prev_gen.get("dimension_scores", {}) or {}).get(k)
        if pg is not None and pg != merged_gen["dimension_scores"][k]:
            changelog.append({"dimension": k, "prev": pg, "curr": merged_gen["dimension_scores"][k], "role": "generator"})
        pc = (prev_crit.get("dimension_scores", {}) or {}).get(k)
        if pc is not None and pc != merged_crit["dimension_scores"][k]:
            changelog.append({"dimension": k, "prev": pc, "curr": merged_crit["dimension_scores"][k], "role": "critic"})

    confidence = compute_confidence(merged_gen["dimension_scores"], merged_crit["dimension_scores"])
    divergences = _score_divergences(merged_gen["dimension_scores"], merged_crit["dimension_scores"], "generator_vs_critic")

    update_run(run_id,
               generator=merged_gen, critic=merged_crit,
               generator_full=merged_gen, critic_full=merged_crit,
               scores={"generator": merged_gen["dimension_scores"], "critic": merged_crit["dimension_scores"]},
               confidence=confidence, divergences=divergences, last_changelog=changelog)
    _log_agent(run_id, "next_version", "generator", merged_gen)
    _log_agent(run_id, "next_version", "critic", merged_crit)

    return {
        "run_id": run_id, "mode": mode,
        "version": f"v{len(data.get('versions', [])) + 1}",
        "touched_dimensions": touched,
        "generator": merged_gen,
        "generator_full": merged_gen,
        "critic": merged_crit,
        "critic_full": merged_crit,
        "confidence": confidence, "divergences": divergences,
        "changelog": changelog,
        "budget": _budget(run_id),
    }


def get_archive(run_id: str) -> Dict:
    """返回完整档案（含版本历史 + 完整过程输出），用于回溯/审查"""
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"诊断档案不存在: {run_id}")
    return data


def list_runs(limit: int = 20) -> list:
    """列出最近 run（档案检索入口）"""
    from diagnosis.archive import list_run_ids
    return list_run_ids(limit)


def rename_run(run_id: str, name: str) -> dict:
    """给历史诊断设人工名字"""
    from diagnosis.archive import rename_run as _rename
    return _rename(run_id, name)


def get_run_state(run_id: str) -> dict:
    """返回可恢复的诊断执行状态（含完整对抗过程输出，用于「继续历史诊断」）"""
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"诊断档案不存在: {run_id}")
    report = data.get("report") or {}
    return {
        "run_id": run_id,
        "name": data.get("name", ""),
        "requirement": data.get("requirement", ""),
        "prompt": data.get("prompt"),
        "prompt_modified": data.get("prompt_modified", False),
        "generator": data.get("generator"),
        "generator_full": data.get("generator_full") or data.get("generator"),
        "critic": data.get("critic"),
        "critic_full": data.get("critic_full") or data.get("critic"),
        "confidence": data.get("confidence"),
        "divergences": data.get("divergences", []),
        "human_review": data.get("human_review"),
        "reviewer": data.get("reviewer"),
        "reviewer_full": data.get("reviewer_full") or data.get("reviewer"),
        "agent_log": data.get("agent_log", []),
        "deliverable": data.get("deliverable"),
        "confirmed": data.get("confirmed", False),
        "version": report.get("version"),
        "versions": len(data.get("versions", [])),
        "llm_calls": data.get("llm_calls", 0),
    }


# ---------- 商务提案（v2.2） ----------


def _commercial_context(data: Dict) -> Dict:
    """从诊断档案提取商务评估所需的上下文（技术5维 + 非技术可行性 + 范围/风险/假设/分阶段/需求）"""
    gen = data.get("generator") or {}
    return {
        "requirement": (data.get("requirement") or "")[:2000],
        "dimension_scores": gen.get("dimension_scores") or {},
        "non_tech_feasibility": gen.get("non_tech_feasibility") or {},
        "scope": gen.get("scope") or {},
        "functional_requirements": gen.get("functional_requirements") or [],
        "data_requirements": gen.get("data_requirements") or {},
        "risks": gen.get("risks") or [],
        "assumptions": gen.get("assumptions") or [],
        "implementation_phases": gen.get("implementation_phases") or [],
    }


def _fallback_commercial_proposal(data: Dict) -> Dict:
    """LLM 起草失败时的规则兜底：从诊断结构化字段生成一份可读、有依据的商务提案（5 块齐全）"""
    gen = data.get("generator") or {}
    ntf = gen.get("non_tech_feasibility") or {}
    if not isinstance(ntf, dict):
        ntf = {}
    or_ = ntf.get("overall_recommendation") if isinstance(ntf.get("overall_recommendation"), dict) else {}
    biz = ntf.get("business_value") if isinstance(ntf.get("business_value"), dict) else {}
    integ = ntf.get("integration") if isinstance(ntf.get("integration"), dict) else {}
    org = ntf.get("organization") if isinstance(ntf.get("organization"), dict) else {}
    scope = gen.get("scope") or {}
    if not isinstance(scope, dict):
        scope = {}
    phases = gen.get("implementation_phases") or []
    in_scope = "；".join(scope.get("in_scope") or []) or "按诊断范围推进"
    assumptions = gen.get("assumptions") or []
    risks = gen.get("risks") or []
    data_req = gen.get("data_requirements") or {}
    if not isinstance(data_req, dict):
        data_req = {}

    # 分期：把 implementation_phases 映射为 试点/一期/二期
    def _phase_tier(idx, default_period):
        ph = phases[idx] if idx < len(phases) else None
        if isinstance(ph, dict):
            return {
                "period": ph.get("phase") or default_period,
                "focus": ph.get("focus") or "",
                "scope": "；".join(ph.get("deliverables") or []) or in_scope,
                "investment_range": {"试点期": "5-12 万元", "一期": "15-35 万元", "二期": "30-80 万元"}.get(
                    ph.get("phase") or default_period, "视范围再定"),
                "basis": (f"按诊断分阶段建议「{ph.get('phase')}」；" + (ph.get("risks") or ""))[:120] or "依据诊断分阶段建议",
                "deliverables": ph.get("deliverables") or [],
            }
        return {"period": default_period, "focus": "", "scope": in_scope,
                "investment_range": "视范围再定", "basis": "依据诊断范围", "deliverables": []}

    tiers = [_phase_tier(0, "试点期"), _phase_tier(1, "一期"), _phase_tier(2, "二期")]

    # 甲方责任：从假设/数据要求/集成信号推导
    client_items = [{
        "item": a if isinstance(a, str) else "",
        "category": "数据/接口", "needed_before": "试点启动前", "owner": "甲方 IT/业务负责人",
        "reason": "该假设不成立则无法开工，需甲方确认", "blocking": True,
    } for a in assumptions if isinstance(a, str)][:5]
    if isinstance(data_req.get("data_sources"), list):
        client_items.append({
            "item": "提供数据源访问：" + "、".join(str(s) for s in data_req["data_sources"][:5]),
            "category": "数据/接口", "needed_before": "数据准备阶段前", "owner": "甲方 IT 部门",
            "reason": "数据可得性决定 AI 效果上限", "blocking": True,
        })
    client_items.append({
        "item": "指定业务对接人与决策链（含最终拍板人）",
        "category": "人员/决策", "needed_before": "试点启动前", "owner": "甲方管理层",
        "reason": (org.get("item") or "组织承接与决策链不明确会阻塞推进"), "blocking": True,
    })
    if integ.get("signal"):
        client_items.append({
            "item": "提供集成对接清单（系统、接口、字段、权限账号）",
            "category": "数据/接口", "needed_before": "一期启动前", "owner": "甲方 IT 部门",
            "reason": (integ.get("item") or "集成复杂度高，需甲方配合摸底"), "blocking": True,
        })

    # 乙方责任
    vendor_items = [
        {"item": "负责 AI 方案设计、模型开发、效果调优与评测", "category": "实施", "owner": "乙方"},
        {"item": "负责与甲方系统的集成开发、数据清洗与部署上线", "category": "集成/部署", "owner": "乙方"},
        {"item": "负责用户培训、上线支持与验收期运维", "category": "培训/运维", "owner": "乙方"},
    ]

    success = [
        "试点范围内首个核心场景达到可用（如命中率 ≥ 80%）",
        "关键指标相比现状有可量化提升（由甲方业务数据口径确认）",
        "试点期结束时双方联合评审可给出明确续投/退出结论",
    ]
    exit_cond = [
        "试点 4 周内核心场景指标未达到约定下限（如命中率 < 60%）",
        "甲方关键数据/接口在约定时点仍无法提供，导致试点停滞超过 2 周",
    ]

    return agents._normalize_commercial_proposal({
        "investment_estimate": {
            "disclaimer": "此为讨论用初步估算，最终以商务洽谈确认为准。",
            "tiers": tiers,
            "total_range": (or_.get("budget_scale") if or_ else "") or "视试点结论再定总量级",
            "notes": (biz.get("item") or "")[:200],
        },
        "milestones": [
            {"phase": t["period"], "duration": "2 周", "first_usable": "第 2 周末：试点范围首个可演示闭环",
             "milestone": "试点范围内核心场景跑通且指标可度量", "dependencies": "甲方按时提供责任清单中的条目"}
            for t in tiers
        ],
        "client_responsibilities": client_items,
        "vendor_responsibilities": vendor_items,
        "pilot_and_exit": {
            "pilot_scope": "取诊断 in_scope 的单个最小闭环（单一场景/单类样本）",
            "success_criteria": success,
            "exit_conditions": exit_cond,
            "review_point": "试点结束（约第 4 周）联合评审",
            "exit_terms": "退出时双方交接已建数据/接口访问方式并终止，不再产生增量费用",
        },
        "alternatives_and_cost": {
            "alternatives": [
                {"name": "现有规则/阈值告警改造", "description": "在既有系统上叠加规则阈值",
                 "pros": ["成本低、见效快"], "cons": ["对复杂/早期故障泛化差"],
                 "cost_range": "3-10 万元", "risk": "误报漏报率高，无法根除", "verdict": "可作为过渡，不替代 AI"},
                {"name": "人工流程优化（不引入 AI）", "description": "靠流程与培训减少停机",
                 "pros": ["无技术风险"], "cons": ["依赖人工经验、不可扩展"],
                 "cost_range": "持续人力成本", "risk": "改善天花板低", "verdict": "补充手段"},
                {"name": "引入 AI 预测性维护（本方案）", "description": "基于传感数据建模提前预警",
                 "pros": ["可量化降停机、可扩展"], "cons": ["需数据与集成配合"],
                 "cost_range": (or_.get("budget_scale") if or_ else "") or "5-80 万元分期",
                 "risk": "；".join((r.get("risk") or "") for r in risks[:2]) or "数据质量/集成是主要风险",
                 "verdict": "建议按试点-分期推进"},
            ],
            "cost_of_inaction": "不做则维持现状：痛点与损失量级参见需求原文与风险章节，且数据资产长期未被利用",
            "recommendation": (or_.get("first_steps") if or_ else "") or "先按试点范围跑最小闭环，用量化结果决定是否进入一期",
        },
    })


def _draft_commercial_proposal(run_id: str, data: Dict, llm_call: Optional[Callable[[str, str], Dict]] = None) -> Dict:
    """起草商务提案：优先 LLM，失败用规则兜底（不阻断 finalize）"""
    try:
        return _call(run_id, lambda: agents.run_commercial_proposal(_commercial_context(data), llm_call=llm_call))
    except Exception as e:
        logger.warning(f"商务提案 LLM 起草失败，使用规则兜底: {e}")
        return _fallback_commercial_proposal(data)


def commercial_proposal(run_id: str, llm_call: Optional[Callable[[str, str], Dict]] = None) -> Dict:
    """为一次诊断起草「商务提案（供洽谈讨论）」并写入档案 business_proposal，返回提案 JSON。

    可由 finalize 调用（定稿时一并生成），也可独立调用（未定稿时预演）。
    """
    data = load_run(run_id)
    if data is None:
        raise FileNotFoundError(f"诊断档案不存在: {run_id}")
    proposal = _draft_commercial_proposal(run_id, data, llm_call=llm_call)
    update_run(run_id, business_proposal=proposal)
    logger.info(f"商务提案已生成 run_id={run_id}")
    return proposal


# ---------- 报告组装 ----------

def _build_report(data: Dict, customer_name: str, requirement_summary: str,
                  interview_notes: Optional[str], decision_maker: Optional[str],
                  version: str = "v1") -> Dict:
    from diagnosis.checklist import AIFeasibilityChecklist

    generator = data.get("generator", {})
    critic = data.get("critic", {})
    reviewer = data.get("reviewer", {})
    human_review = data.get("human_review", {})
    human_scores = human_review.get("scores", {})
    confidence = data.get("confidence", {})
    divergences = data.get("divergences", [])

    final = AIFeasibilityChecklist().evaluate(human_scores) if human_scores else {}

    # 建议：先给基础下一步，再附分歧/低置信提示
    recommendations = []
    if final:
        recommendations = _next_steps(final["total_score"])
    for d in divergences:
        if abs(d["delta"]) >= 2:
            recommendations.append(
                f"维度「{agents.DIMENSIONS.index(d['dimension']) + 1}」存在分歧（{d['source']}：{d['a']} vs {d['b']}），建议人工复核依据。"
            )
    if confidence.get("needs_confirm"):
        recommendations.append("存在低置信度维度（Generator 与 Critic 不一致），相关维度必须经人工/客户确认后方可采信。")

    versions = data.get("versions", [])

    # 版本历史（附录 B：多轮版本演进）
    version_history = []
    for v in versions:
        rpt = v.get("report") or {}
        version_history.append({
            "version": v.get("version", ""),
            "changelog": v.get("changelog", []),
            "generated_at": rpt.get("generated_at", ""),
        })

    # 反馈织入（若 next_version 已生成则复用，否则由归档反馈即时计算）
    feedbacks = data.get("client_feedback", [])
    feedback_weave = generator.get("feedback_weave") or categorize_feedback_items(
        [it for fb in feedbacks for it in (fb.get("items") or [])])

    report = {
        "report_version": "3.1",
        "version": version,
        "previous_version": versions[-1]["version"] if versions else None,
        "changelog": data.get("last_changelog", []),
        "client_feedback": [
            {"source": fb.get("source"), "summary": fb.get("summary", ""),
             "items": fb.get("items", []), "touched_dimensions": fb.get("touched_dimensions", []),
             "added_at": fb.get("added_at", "")}
            for fb in feedbacks
        ],
        "feedback_weave": feedback_weave,
        "version_history": version_history,
        "generated_at": datetime.now().isoformat(),
        "run_id": data.get("run_id", ""),
        "customer_name": customer_name or "未填写",
        "requirement_summary": requirement_summary or data.get("requirement", ""),
        "interview_notes": interview_notes or "",
        "decision_maker": decision_maker or "未确认",
        "requirement": data.get("requirement", ""),
        "prompt_modified": data.get("prompt_modified", False),
        "generator": generator,
        "generator_full": data.get("generator_full") or generator,
        "critic": critic,
        "critic_full": data.get("critic_full") or critic,
        "human_review": human_review,
        "reviewer": reviewer,
        "reviewer_full": data.get("reviewer_full") or reviewer,
        "agent_log": data.get("agent_log", []),
        "confidence": confidence,
        "divergences": divergences,
        "final_conclusion": {
            "total_score": final.get("total_score"),
            "conclusion": final.get("conclusion"),
            "suggestion": final.get("suggestion"),
            "basis": "以人工复核打分为准",
        },
        "recommendations": recommendations,
        "needs_confirmation": bool(confidence.get("needs_confirm")) or any(abs(d["delta"]) >= 2 for d in divergences),
        "business_proposal": data.get("business_proposal") or {},
    }
    return report


def _next_steps(total: int) -> list:
    if total >= 20:
        return ["进入数据准备阶段", "确认数据来源和数据量", "确定评测集构建方案"]
    if total >= 15:
        return ["先构建小型原型验证核心假设", "准备小规模真实数据用于测试"]
    if total >= 10:
        return ["先用传统规则/检索方案验证", "收集用户反馈后再评估是否引入 AI"]
    return ["重新评估需求", "考虑传统解决方案"]
