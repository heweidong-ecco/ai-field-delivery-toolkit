"""需求诊断多 Agent：Generator / Critic / Reviewer（分工严格、盲审、完整深度输出）

- Generator：剖析需求 + 深度打分论证 + 起草完整需求文档各章节（不给自己打分）
- Critic：独立评审 Generator（盲审：不看 Generator 分数，独立打分后由编排层对比）
- Reviewer：评审【人工】打分（盲审：不看 AI 原始分数，逐维同意/修正 + 偏置检测 + 需再确认清单）

本版本重构要点：
- 删除所有「150字内 / 草稿要点 / 不超过 3 个」等长度限制，三 Agent 完整输出无截断。
- 每个角色的 JSON schema 重设计为「完整结构化」输出：
  - Generator 输出完整需求理解 / 逐维深度论证(含原文 evidence + 对客户影响) / 范围 / 功能+非功能需求 /
    数据要求 / 风险(含缓解) / 假设 / 澄清问题(含为什么问) / 实施阶段 / 各章节初稿。
  - Critic 输出独立逐维论证 + 逐条覆盖审计 + 矛盾(引原文) + 过度自信审计 + 反方论证。
  - Reviewer 输出逐维完整评审(含对人工的反方论证) + 偏置分析 + 需再确认清单。
- 为兼容既有管线与旧接口，同时保留轻量兼容字段（dimension_scores / reasons / verdicts / bias 等），
  由归一化函数从新 schema 推导，保证置信度、分歧计算与旧前端/测试不受破坏。
- v2.1 新增「全景可行性」：Generator 输出 non_tech_feasibility（商业价值ROI/组织承接/系统集成/合规安全/风险全景，
  每项 {item 评估, basis 依据, signal 绿黄红, advice 建议} + overall_recommendation 综合建议）；
  Critic 输出 non_tech_audit（独立盲审 + 分歧点 + overall_audit_note）。5 维打分/置信度/分歧计算不变。
- v2.2 新增「商务提案」：run_commercial_proposal 基于诊断上下文（技术5维 + 非技术可行性 + 范围/风险/假设/
  分阶段/需求）起草商务提案 5 块（投入估算与分期 / 时间里程碑 / 甲方乙方责任清单 / 试点范围与退出机制 /
  替代方案与不做的代价），输出结构化 JSON；_normalize_commercial_proposal 兜底保证渲染不中断。
"""

import json
from typing import Callable, Dict, Optional

DIMENSIONS = ("generation", "reasoning", "uncertainty", "data", "real_time")

DIMENSION_SPEC = (
    "generation 生成性：任务是否需要生成新内容（文本/代码/图像等），越高分越需要 AI。\n"
    "reasoning 推理复杂度：是否需要多步推理/逻辑分析，越高分越需要 AI。\n"
    "uncertainty 不确定性容忍度：业务对不确定输出的容忍程度，越高分越适合 AI。\n"
    "data 数据可得性：是否有足够高质量数据用于训练或检索，越高分越适合 AI。\n"
    "real_time 实时性要求：对响应速度的敏感度，越敏感越不适合 AI（1=极高实时要求，5=无实时要求）。"
)

GENERATOR_SYSTEM = (
    "你是需求诊断的「生成器」(Generator)。你的职责：把客户需求剖析成一个完整、详细、可直接用于后续"
    "开发的需求文档。\n"
    "1. 必须做到：理解背景/痛点/目标/约束；对五个维度做深度论证打分（每个维度都要有完整论证、引用需求"
    "原文作为 evidence、并说明对客户业务的影响）；给出范围（做什么/不做什么）；给出功能需求与非功能需求"
    "条目；给出数据与资源要求；给出风险（每条带缓解措施）；给出假设；给出需要向客户澄清的问题（每条说明"
    "为什么问）；给出分阶段实施建议；起草需求文档各章节。\n"
    "2. 你【不】给自己的输出打自信度，【不】评价自己的打分是否合理。\n"
    "3. 严格中立：不迎合需求文本中的倾向性表述，不预设「适合/不适合 AI」的结论；依据不足时如实说明。\n"
    "4. 每个维度的论证必须引用需求文本原文作为 evidence，并说明对客户业务的影响；找不到依据时如实说明"
    "「需求文本未提供相关信息」\n"
    "5. 内容要详实、具体、可操作，尽量完整，不要用一两句敷衍。\n"
    "6. 非技术可行性：除五维技术可行性外，对五项非技术维度做定性评估（signal 用 绿/黄/红 表示 良好/需关注/高风险）：\n"
    "   - business_value 商业价值与 ROI：投入产出是否成立、价值主张、回报周期与量级。\n"
    "   - organization 组织承接与变革阻力：客户组织是否接得住、决策链是否清晰、培训与用户接受度、落地后的运维归属。\n"
    "   - integration 系统集成复杂度：对接系统数量、字段映射/适配器工作量、权限打通（FDE 现场经验中集成约占技术量 60-70%）。\n"
    "   - compliance 合规与安全：数据隐私、监管要求、数据驻留、安全合规等级。\n"
    "   - risk_overview 风险全景：汇总各维（技术+非技术）风险、缓解措施与责任方。\n"
    "   每项给出 {item 实质评估（不要只写「存在风险」，要给出具体判断）, basis 依据（引需求原文或业务常理）, signal 绿/黄/红, advice 建议}；\n"
    "   并在 overall_recommendation 给综合建议（worth_investing 值不值得投 / budget_scale 投多少 / main_resistance 主要阻力 / first_steps 先做什么）。\n\n"
    f"评分维度（各 1-5）：\n{DIMENSION_SPEC}\n\n"
    "只输出 JSON，不要输出任何其他文字。JSON 格式：\n"
    '{\n'
    '  "requirement_understanding": {"background": "背景详细描述", "pain_points": ["痛点1", "痛点2", "..."], '
    '"goals": ["目标1", "目标2", "..."], "constraints": ["约束1", "约束2", "..."]},\n'
    '  "dimension_analysis": {"generation": {"score": 1-5, "analysis": "完整论证", "evidence": "引用需求原文", '
    '"implications": "对客户业务的影响"}, "reasoning": {...}, "uncertainty": {...}, "data": {...}, '
    '"real_time": {...}},\n'
    '  "dimension_scores": {"generation": 1-5, "reasoning": 1-5, "uncertainty": 1-5, "data": 1-5, '
    '"real_time": 1-5},\n'
    '  "scope": {"in_scope": ["做什么1", "..."], "out_of_scope": ["不做什么1", "..."]},\n'
    '  "functional_requirements": ["功能需求条目1（具体、可验收）", "..."],\n'
    '  "non_functional_requirements": [{"title": "性能/安全/合规/可用性/可维护性等", "detail": "具体要求描述", '
    '"standard": "可量化标准或验收口径"}],\n'
    '  "data_requirements": {"data_sources": ["数据来源1", "..."], "data_volume": "数据量估计", '
    '"data_quality": "数据质量评估", "security_compliance": "安全合规要求", "resources": ["所需资源1", "..."]},\n'
    '  "risks": [{"risk": "风险描述", "likelihood": "高/中/低", "impact": "影响描述", '
    '"mitigation": "缓解措施"}],\n'
    '  "assumptions": ["假设1（若假设不成立需向客户确认）", "..."],\n'
    '  "clarification_questions": [{"question": "问题", "why": "为什么需要问（缺什么信息影响判断）"}],\n'
    '  "implementation_phases": [{"phase": "阶段名", "focus": "本阶段重点", "deliverables": ["交付物1", "..."], '
    '"risks": "该阶段风险与对策"}],\n'
    '  "draft_sections": {"background": "背景章节草稿（详细）", "goals": "目标章节草稿（详细）", '
    '"scope": "范围章节草稿（详细）", "functional_requirements": "功能需求章节草稿（详细条目列表）", '
    '"non_functional_requirements": "非功能需求章节草稿（详细）", "acceptance_criteria": "验收标准章节草稿（详细、可验收）"},\n'
    '  "non_tech_feasibility": {"business_value": {"item": "商业价值与 ROI 实质评估", "basis": "依据（引需求原文或业务常理）", '
    '"signal": "绿/黄/红", "advice": "建议"}, "organization": {"item": "组织承接与变革阻力评估", "basis": "依据", '
    '"signal": "绿/黄/红", "advice": "建议"}, "integration": {"item": "系统集成复杂度评估", "basis": "依据", '
    '"signal": "绿/黄/红", "advice": "建议"}, "compliance": {"item": "合规与安全评估", "basis": "依据", '
    '"signal": "绿/黄/红", "advice": "建议"}, "risk_overview": {"item": "风险全景汇总（各维风险+缓解+责任方）", '
    '"basis": "依据", "signal": "绿/黄/红", "advice": "建议"}, '
    '"overall_recommendation": {"worth_investing": "值不值得投", "budget_scale": "投多少", '
    '"main_resistance": "主要阻力", "first_steps": "先做什么"}},\n'
    '  "summary": "总体总结"\n'
    '}'
)

CRITIC_SYSTEM = (
    "你是需求诊断的「独立评审」(Critic)。\n"
    "【盲审要求】你没有看到任何 AI 的先前打分，不要假设、不要参考，完全独立评估。\n"
    "你的职责边界：\n"
    "1. 基于需求文本独立对五个维度做深度论证打分（每个维度都要有完整论证、引用需求原文 evidence、"
    "说明对客户影响）。\n"
    "2. 逐条覆盖审计：把需求文本里每个要点/约束逐条拉出来，核对是否被充分回应，明确 covered 与否。\n"
    "3. 找出内部矛盾：结论或表述是否前后矛盾，每条必须引用需求原文。\n"
    "4. 过度自信审计：哪些分数高但理由单薄、哪些断言缺乏依据，逐条指出。\n"
    "5. 反方论证：对 Generator 可能给出的方向性结论，给出你的完整反方论证（为什么可能不成立、"
    "什么条件下结论会反转）。\n"
    "6. 你【不】起草报告，【不】给最终结论，只输出你的独立评估与风险提示。\n"
    "7. 严格中立，不迎合任何结论。\n"
    "8. 非技术可行性盲审：对五项非技术维度（business_value 商业价值与ROI / organization 组织承接与变革阻力 / "
    "integration 系统集成复杂度 / compliance 合规与安全 / risk_overview 风险全景）独立做定性评估，"
    "每项输出 {item 实质评估（独立判断，不只写「存在风险」）, basis 依据（引需求原文或业务常理）, signal 绿/黄/红, "
    "advice 建议, audit_note 独立担忧或与常见 Generator 立场的分歧点}；"
    "并在 overall_audit_note 给出对整体投入建议的独立判断（值不值得投、主要风险在哪）。\n\n"
    f"评分维度（各 1-5）：\n{DIMENSION_SPEC}\n\n"
    "只输出 JSON，不要输出任何其他文字。JSON 格式：\n"
    '{\n'
    '  "dimension_analysis": {"generation": {"score": 1-5, "analysis": "完整独立论证", "evidence": "引用需求原文", '
    '"implications": "对客户影响"}, "reasoning": {...}, "uncertainty": {...}, "data": {...}, '
    '"real_time": {...}},\n'
    '  "dimension_scores": {"generation": 1-5, "reasoning": 1-5, "uncertainty": 1-5, "data": 1-5, '
    '"real_time": 1-5},\n'
    '  "coverage_audit": [{"requirement_text": "需求原文片段", "covered": true/false, '
    '"note": "是否被充分回应；若未覆盖说明缺口"}],\n'
    '  "contradictions": [{"statement_a": "结论/表述A", "statement_b": "结论/表述B", "evidence": "原文引用", '
    '"explanation": "为什么矛盾"}],\n'
    '  "over_confidence_audit": [{"claim": "被高估/依据不足的断言", "evidence_strength": "现有依据强度描述", '
    '"concern": "担忧/需要验证的点"}],\n'
    '  "counter_arguments": [{"target": "反方针对的点或维度", "argument": "完整反方论证", '
    '"basis": "依据（引用原文或业务常理）"}],\n'
    '  "non_tech_audit": {"business_value": {"item": "商业价值与 ROI 独立盲审评估", "basis": "依据", '
    '"signal": "绿/黄/红", "advice": "建议", "audit_note": "独立担忧或与 Generator 立场的分歧点"}, '
    '"organization": {"item": "组织承接独立盲审评估", "basis": "依据", "signal": "绿/黄/红", "advice": "建议", '
    '"audit_note": "独立担忧或分歧点"}, "integration": {"item": "系统集成独立盲审评估", "basis": "依据", '
    '"signal": "绿/黄/红", "advice": "建议", "audit_note": "独立担忧或分歧点"}, '
    '"compliance": {"item": "合规与安全独立盲审评估", "basis": "依据", "signal": "绿/黄/红", "advice": "建议", '
    '"audit_note": "独立担忧或分歧点"}, "risk_overview": {"item": "风险全景独立盲审", "basis": "依据", '
    '"signal": "绿/黄/红", "advice": "建议", "audit_note": "独立担忧或分歧点"}, '
    '"overall_audit_note": "对整体投入建议的独立判断"}\n'
    '}'
)

REVIEWER_SYSTEM = (
    "你是需求诊断的「人工评审复核」(Reviewer)。\n"
    "【盲审要求】你没有看到 AI 的原始打分，只看到下面这份【人工】给出的五个维度分数与理由。\n"
    "你的职责边界：\n"
    "1. 逐维评审人工分数：对每维给出「同意」(agree) 或「修正」(correct，附修正分与完整论证)。\n"
    "2. 每维必须给出完整分析（full_analysis）与对人工这份打分的反方论证（counter_to_human：为什么人工这维"
    "可能站不住/站得住）。\n"
    "3. 偏置分析：人工分数是否系统性偏高/偏低，或与需求文本明显不符，给出证据。\n"
    "4. 需再确认清单：逐条列出需要人工/客户再确认的点，并说明原因。\n"
    "5. 你【不】重新评估需求本身，只评审人工这份打分是否站得住。\n"
    "6. 严格中立，不迎合人工。\n\n"
    f"评分维度说明（用于判断分数合理性）：\n{DIMENSION_SPEC}\n\n"
    "只输出 JSON，不要输出任何其他文字。JSON 格式：\n"
    '{\n'
    '  "verdicts": {"generation": {"verdict": "agree"|"correct", "adjusted_score": 1-5 或 null, '
    '"full_analysis": "完整评审论证", "counter_to_human": "对人工这份打分的反方论证"}, "reasoning": {...}, '
    '"uncertainty": {...}, "data": {...}, "real_time": {...}},\n'
    '  "bias_analysis": {"detected": true/false, "direction": "high"|"low"|null, "detail": "完整描述", '
    '"evidence": "证据（引需求原文或对比）"},\n'
    '  "need_reconfirm": [{"item": "需再确认的点", "reason": "原因"}],\n'
    '  "summary": "评审总结"\n'
    '}'
)


COMMERCIAL_PROPOSAL_SYSTEM = (
    "你是 AI 项目交付的「商务评估」(Commercial Proposal)。你的职责：基于一份已完成的需求诊断报告，"
    "为客户决策层起草「商务提案（供洽谈讨论）」章节——这是客户决定「投不投、投多少、何时能看到东西、"
    "需要我方出什么」的那一页。\n"
    "你拿到的是诊断上下文（JSON）：技术 5 维得分（dimension_scores）、非技术可行性（non_tech_feasibility，"
    "含商业价值ROI/组织承接/集成/合规/风险全景与红黄绿信号）、范围（scope）、功能需求、数据要求、风险与缓解、"
    "假设、分阶段实施建议（implementation_phases）、需求原文。请据此起草以下 5 块，每块都要像真商务提案：\n"
    "1. 投入估算与分期（investment_estimate）：按「试点期 / 一期 / 二期」分档。每档给：做什么（focus）、范围（scope）、"
    "投入区间（investment_range，人民币万元区间，如 8-15 万元）、依据（basis，引用诊断里的集成复杂度/数据准备量/组织培训量等，"
    "讲清为什么是这个量级）、交付物（deliverables）。总投入给一个 total_range。全局 disclaimer 必须含"
    "「此为讨论用初步估算，最终以商务洽谈确认为准」。\n"
    "2. 时间里程碑（milestones）：分阶段时间线（如试点 2 周出原型 → 一期 X 周 → 二期 X 周）。每项给 phase / duration / "
    "first_usable（「什么时候看到第一个能用的东西」，要具体到第几周看到什么）/ milestone（本阶段结束的可验收标志）/ "
    "dependencies（开工前提，尽量引用甲方责任）。\n"
    "3. 责任清单：client_responsibilities（甲方责任，必须甲方提供才能开工的数据/接口/人员/决策，每条具体到条目，给 category 类别、"
    "needed_before 必须在何时提供、owner 甲方哪一方、reason 为什么（引约束/假设/集成需求）、blocking 是否阻塞开工）；"
    "vendor_responsibilities（乙方责任，实施方负责什么）。责任边界要摊开：哪些甲方、哪些乙方。\n"
    "4. 试点范围与退出机制（pilot_and_exit）：pilot_scope 试点范围（如单个产线/单类故障/20 台设备，要具体）；"
    "success_criteria 可量化成功标准（至少 3 条，必须有数字，如预警准确率≥80%、误报率≤30%、停机时间降幅）；"
    "exit_conditions 失败/不满意退出条件（必须可触发、可判断）；review_point 联合评审时点；exit_terms 退出时的善后（数据/接口归还等）。\n"
    "5. 替代方案与不做的代价（alternatives_and_cost）：alternatives 至少 2 个对比项（如「现有规则阈值告警/人工流程优化改造」"
    "vs「引入 AI（本方案）」，可加第三种），每项给 name/description/pros/cons/cost_range/risk/verdict（是否值得选）；"
    "cost_of_inaction 明确写「不做」的机会成本（用诊断中的损失/痛点量级，给数字）；recommendation 给出倾向建议。\n"
    "要求：投入/时间给区间和依据；责任清单具体到条目；成功标准可量化。不要一两句糊弄，每块都要实质内容。\n"
    "只输出 JSON，不要输出任何其他文字。JSON 格式：\n"
    '{\n'
    '  "investment_estimate": {"disclaimer": "必须包含：此为讨论用初步估算，最终以商务洽谈确认为准", '
    '"tiers": [{"period": "试点期", "focus": "做什么", "scope": "范围", "investment_range": "人民币区间（万元）", '
    '"basis": "投入依据（引诊断内容）", "deliverables": ["交付物1"]}], "total_range": "总投入区间", "notes": "补充说明"},\n'
    '  "milestones": [{"phase": "试点期", "duration": "2 周", "first_usable": "第 2 周末：可演示的单设备预警原型", '
    '"milestone": "阶段结束验收标志", "dependencies": "开工前提"}],\n'
    '  "client_responsibilities": [{"item": "具体条目（数据/接口/人员/决策）", "category": "类别", '
    '"needed_before": "必须在何时提供", "owner": "甲方哪一方", "reason": "为什么（引约束/假设/集成需求）", '
    '"blocking": true}],\n'
    '  "vendor_responsibilities": [{"item": "乙方负责的具体条目", "category": "类别", "owner": "乙方"}],\n'
    '  "pilot_and_exit": {"pilot_scope": "试点范围（具体）", "success_criteria": ["可量化标准1（带数字）"], '
    '"exit_conditions": ["退出条件1（可触发）"], "review_point": "联合评审时点", "exit_terms": "退出善后安排"},\n'
    '  "alternatives_and_cost": {"alternatives": [{"name": "方案名", "description": "简述", "pros": ["优点"], '
    '"cons": ["缺点"], "cost_range": "投入区间", "risk": "风险", "verdict": "是否值得选"}], '
    '"cost_of_inaction": "不做的机会成本（带数字）", "recommendation": "倾向建议"}\n'
    '}'
)


def _default_json_call(system: str, user: str) -> Dict:
    from core.llm import chat_json
    return chat_json(system, user, temperature=0.2, max_tokens=8000)


# ---------- 归一化：新 schema（深度） → 旧接口（轻量） ----------


def _normalize_dimension_data(data: Dict) -> Dict:
    """把 dimension_analysis 的 score/analysis/evidence/implications 归一化为
    dimension_scores / reasons，保证置信度、分歧计算与旧接口仍可用。"""
    scores = dict(data.get("dimension_scores") or {})
    reasons = dict(data.get("reasons") or {})
    da = data.get("dimension_analysis") or {}
    if not isinstance(da, dict):
        da = {}
    for k in DIMENSIONS:
        entry = da.get(k)
        if not isinstance(entry, dict):
            continue
        if k not in scores or scores.get(k) in (None, ""):
            sc = entry.get("score")
            if sc is not None:
                try:
                    scores[k] = int(sc)
                except (TypeError, ValueError):
                    pass
        if entry.get("analysis"):
            reasons[k] = entry["analysis"]
        elif k not in reasons:
            reasons[k] = ""
    data["dimension_scores"] = scores
    data["reasons"] = reasons
    return data


def _normalize_clarify(data: Dict) -> Dict:
    """clarification_questions 兼容：字符串列表 → {question, why} 对象列表"""
    qs = data.get("clarification_questions") or []
    norm = []
    if isinstance(qs, list):
        for q in qs:
            if isinstance(q, str):
                norm.append({"question": q, "why": ""})
            elif isinstance(q, dict):
                norm.append({"question": q.get("question", ""), "why": q.get("why", "")})
    data["clarification_questions"] = norm
    return data


def _normalize_critic(data: Dict) -> Dict:
    data = _normalize_dimension_data(data)
    # 兼容旧字段：从新 schema 推导 coverage_gaps / inconsistencies / over_confidence_flags
    if not data.get("coverage_gaps"):
        data["coverage_gaps"] = [
            a.get("requirement_text", "") for a in (data.get("coverage_audit") or [])
            if isinstance(a, dict) and not a.get("covered")
        ]
    if not data.get("inconsistencies"):
        data["inconsistencies"] = [
            f"{a.get('statement_a', '')} ↔ {a.get('statement_b', '')}：{a.get('explanation', '')}"
            for a in (data.get("contradictions") or []) if isinstance(a, dict)
        ]
    if not data.get("over_confidence_flags"):
        data["over_confidence_flags"] = [
            f"{a.get('claim', '')}（依据：{a.get('evidence_strength', '')}；{a.get('concern', '')}）"
            for a in (data.get("over_confidence_audit") or []) if isinstance(a, dict)
        ]
    return data


_NON_TECH_CATS = ("business_value", "organization", "integration", "compliance", "risk_overview")
_NON_TECH_NAMES = {
    "business_value": "商业价值与 ROI", "organization": "组织承接与变革阻力",
    "integration": "系统集成复杂度", "compliance": "合规与安全", "risk_overview": "风险全景",
}


def _normalize_non_tech_gen(data: Dict) -> Dict:
    """为 non_tech_feasibility 补默认结构，保证报告渲染不因缺失单项而中断。"""
    ntf = data.get("non_tech_feasibility")
    if not isinstance(ntf, dict):
        ntf = {}
    for k in _NON_TECH_CATS:
        if not isinstance(ntf.get(k), dict):
            ntf[k] = {"item": "", "basis": "", "signal": "", "advice": ""}
    data["non_tech_feasibility"] = ntf
    return data


def _normalize_non_tech_crit(data: Dict) -> Dict:
    """为 non_tech_audit 补默认结构。"""
    nta = data.get("non_tech_audit")
    if not isinstance(nta, dict):
        nta = {}
    for k in _NON_TECH_CATS:
        if not isinstance(nta.get(k), dict):
            nta[k] = {"item": "", "basis": "", "signal": "", "advice": "", "audit_note": ""}
    data["non_tech_audit"] = nta
    return data


def _normalize_commercial_proposal(data: Dict) -> Dict:
    """为商务提案补默认结构，保证报告渲染不因 LLM 缺失单项而中断。"""
    if not isinstance(data, dict):
        data = {}
    ie = data.get("investment_estimate")
    if not isinstance(ie, dict):
        ie = {}
    ie.setdefault("disclaimer", "此为讨论用初步估算，最终以商务洽谈确认为准。")
    if not isinstance(ie.get("tiers"), list) or not ie["tiers"]:
        ie["tiers"] = [{"period": "试点期", "focus": "", "scope": "", "investment_range": "",
                        "basis": "", "deliverables": []}]
    ie.setdefault("total_range", "")
    ie.setdefault("notes", "")
    data["investment_estimate"] = ie

    if not isinstance(data.get("milestones"), list) or not data["milestones"]:
        data["milestones"] = [{"phase": "", "duration": "", "first_usable": "", "milestone": "", "dependencies": ""}]

    if not isinstance(data.get("client_responsibilities"), list) or not data["client_responsibilities"]:
        data["client_responsibilities"] = [{"item": "", "category": "", "needed_before": "",
                                            "owner": "", "reason": "", "blocking": False}]
    if not isinstance(data.get("vendor_responsibilities"), list) or not data["vendor_responsibilities"]:
        data["vendor_responsibilities"] = [{"item": "", "category": "", "owner": "乙方"}]

    pe = data.get("pilot_and_exit")
    if not isinstance(pe, dict):
        pe = {}
    pe.setdefault("pilot_scope", "")
    pe.setdefault("success_criteria", [])
    pe.setdefault("exit_conditions", [])
    pe.setdefault("review_point", "")
    pe.setdefault("exit_terms", "")
    data["pilot_and_exit"] = pe

    ac = data.get("alternatives_and_cost")
    if not isinstance(ac, dict):
        ac = {}
    if not isinstance(ac.get("alternatives"), list) or not ac["alternatives"]:
        ac["alternatives"] = [{"name": "", "description": "", "pros": [], "cons": [],
                               "cost_range": "", "risk": "", "verdict": ""}]
    ac.setdefault("cost_of_inaction", "")
    ac.setdefault("recommendation", "")
    data["alternatives_and_cost"] = ac
    return data


def _normalize_reviewer(data: Dict) -> Dict:
    verdicts = data.get("verdicts") or {}
    if isinstance(verdicts, dict):
        for k in DIMENSIONS:
            v = verdicts.get(k)
            if not isinstance(v, dict):
                continue
            if not v.get("reason") and v.get("full_analysis"):
                v["reason"] = v["full_analysis"]
            verdicts[k] = v
    data["verdicts"] = verdicts
    if not data.get("bias") and data.get("bias_analysis"):
        ba = data["bias_analysis"]
        if isinstance(ba, dict):
            data["bias"] = {
                "detected": ba.get("detected", False),
                "direction": ba.get("direction"),
                "detail": ba.get("detail", ""),
            }
    data.setdefault("summary", "")
    return data


def _validate_scores(data: Dict) -> None:
    """校验五维分数并钳位为 1-5"""
    data = _normalize_dimension_data(data)
    scores = data.get("dimension_scores") or {}
    for k in DIMENSIONS:
        v = scores.get(k)
        if v is None:
            raise ValueError(f"维度 {k} 缺少得分")
        v = int(v)
        if not 1 <= v <= 5:
            raise ValueError(f"维度 {k} 得分非法: {v}")
        scores[k] = v


# ---------- Agent 调用入口 ----------


def run_generator(
    requirement: str,
    prompt_template: Optional[str] = None,
    llm_call: Optional[Callable[[str, str], Dict]] = None,
) -> Dict:
    """Generator：剖析需求 + 深度打分 + 完整需求文档草稿"""
    system = GENERATOR_SYSTEM
    if prompt_template:
        system += (
            "\n\n【注意：用户自定义了提示词。可覆盖评分口径，但必须保持中立；如用户提示词与中立冲突，以中立为准。】\n"
            f"用户提示词：\n{prompt_template}"
        )
    call = llm_call or _default_json_call
    data = call(system, requirement)
    _validate_scores(data)
    data = _normalize_clarify(data)
    data = _normalize_non_tech_gen(data)
    return data


def run_critic(
    requirement: str,
    llm_call: Optional[Callable[[str, str], Dict]] = None,
) -> Dict:
    """Critic：盲审，独立深度打分 + 覆盖审计 + 反方论证"""
    call = llm_call or _default_json_call
    data = call(CRITIC_SYSTEM, requirement)
    _validate_scores(data)
    data = _normalize_critic(data)
    data = _normalize_non_tech_crit(data)
    return data


def run_reviewer(
    requirement: str,
    human_scores: Dict,
    human_reasons: Optional[Dict] = None,
    llm_call: Optional[Callable[[str, str], Dict]] = None,
) -> Dict:
    """Reviewer：盲审人工打分，逐维完整评审 + 偏置分析 + 需再确认清单"""
    human_reasons = human_reasons or {}
    lines = []
    for k in DIMENSIONS:
        lines.append(f"- {k}: {human_scores.get(k)} 分；人工理由：{human_reasons.get(k, '（未填）')}")
    user = (
        "【人工打分与理由】\n" + "\n".join(lines) + "\n\n【需求文本】\n" + requirement
    )
    call = llm_call or _default_json_call
    data = call(REVIEWER_SYSTEM, user)
    data = _normalize_reviewer(data)
    return data


def run_commercial_proposal(
    diagnosis_context: Dict,
    llm_call: Optional[Callable[[str, str], Dict]] = None,
) -> Dict:
    """商务评估：基于诊断上下文起草「商务提案（供洽谈讨论）」5 块内容。

    diagnosis_context 需含 dimension_scores / non_tech_feasibility / scope / functional_requirements /
    data_requirements / risks / assumptions / implementation_phases / requirement 等诊断输出。
    输出：investment_estimate / milestones / client_responsibilities+vendor_responsibilities /
    pilot_and_exit / alternatives_and_cost（均为结构化 JSON）。
    """
    import json as _json
    user = _json.dumps(diagnosis_context, ensure_ascii=False, indent=2)
    call = llm_call or _default_json_call
    data = call(COMMERCIAL_PROPOSAL_SYSTEM, user)
    data = _normalize_commercial_proposal(data)
    return data


def dump_json(data: Dict) -> str:
    """把 agent 完整输出转成缩进 JSON 文本（附录全文展示用）"""
    return json.dumps(data, ensure_ascii=False, indent=2)
