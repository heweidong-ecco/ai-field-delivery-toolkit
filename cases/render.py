"""交付物渲染：诊断报告 → 自包含可打印 HTML（+ 尽力 PDF via Chrome headless）

v2.0 重构：诊断报告从「一页打分表」重写为「多轮累积的详细需求文档」，章节包括：
  封面/文档信息 / 执行摘要 / 需求理解与背景 / 目标与范围 / 功能需求 / 非功能需求 /
  五维可行性深度分析 / 数据与资源要求 / 风险与缓解 / 假设与依赖 / 开放问题与待澄清 /
  分阶段实施建议 / 验收标准 / 附录A 完整对抗评审过程 / 附录B 多轮客户反馈与版本演进。
每维可行性分析含「完整论证 + 引用需求原文的 evidence + 对客户影响」，附录不删减全文。

v2.1 增量：
- 每个维度分析块内新增「对抗评审过程」内联可读块（Generator 立场 / Critic 盲审立场与分歧 /
  Reviewer 对人工分的评审 / 采纳结论），通顺中文、禁止贴 JSON；附录 A 保留完整原文。
- 新增第 7 章「整体可行性评估」：技术 5 维得分概览 + 非技术各维（商业/组织/集成/合规/风险，
  每项 Generator 立场 vs Critic 盲审内联对抗）+ 综合建议（值不值得投/投多少/阻力/先做什么）。
- 执行摘要新增「对抗评审速览」：谁同意、谁分歧、Reviewer 修正、非技术信号分歧。

v2.2 增量：
- 新增第 14 章「商务提案（供洽谈讨论）」：投入估算与分期（试点/一期/二期，区间+依据，明确
  「此为讨论用初步估算，最终以商务洽谈确认为准」）/ 时间里程碑（何时看到第一个能用的东西）/
  甲方乙方责任清单（具体到条目）/ 试点范围与退出机制（可量化成功标准 + 退出条件）/
  替代方案与不做的代价（对比 + 机会成本）。
- 附录 A / 附录 B 顺延为第 15 / 16 章。
"""

import html as html_mod
import json as json_mod
import re

from core.logging.logger import get_logger

logger = get_logger()


def esc(value) -> str:
    return html_mod.escape(str(value if value is not None else ""))


def _json_pretty(value) -> str:
    """把对象转成缩进 JSON 文本（附录全文展示用）"""
    return json_mod.dumps(value, ensure_ascii=False, indent=2)


def _para(text) -> str:
    """多行文本 → 段落 HTML"""
    text = str(text or "").strip()
    if not text:
        return ""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        paras = [text]
    return "".join(f"<p>{esc(p)}</p>" for p in paras)


def _list(items) -> str:
    return "".join(f"<li>{esc(i)}</li>" for i in (items or [])) or "<li>（未提供）</li>"


def _obj_list(items, keys) -> str:
    """渲染对象列表：keys 为 (字段, 标签, 样式) 元组列表"""
    out = []
    for it in (items or []):
        if not isinstance(it, dict):
            out.append(f"<li>{esc(it)}</li>")
            continue
        parts = []
        for key, label, style in keys:
            v = it.get(key)
            if v in (None, ""):
                continue
            if isinstance(v, list):
                v = "、".join(str(x) for x in v)
            if style == "quote":
                parts.append(f'<div class="evidence">【{esc(label)}】{esc(v)}</div>')
            elif style == "label":
                parts.append(f"<p><b>{esc(label)}：</b>{esc(v)}</p>")
            else:
                parts.append(f"<p><b>{esc(label)}：</b>{esc(v)}</p>")
        if parts:
            out.append(f"<div class='box'>{''.join(parts)}</div>")
        else:
            out.append(f"<div class='box'>{esc(json_mod.dumps(it, ensure_ascii=False))}</div>")
    return "".join(out) or "<li>（未提供）</li>"


_DIM_NAMES = {
    "generation": "生成性", "reasoning": "推理复杂度", "uncertainty": "不确定性容忍度",
    "data": "数据可得性", "real_time": "实时性要求",
}
_DIM_EN = tuple(_DIM_NAMES.keys())

_NON_TECH_CATS = (
    ("business_value", "商业价值与 ROI"),
    ("organization", "组织承接与变革阻力"),
    ("integration", "系统集成复杂度"),
    ("compliance", "合规与安全"),
    ("risk_overview", "风险全景"),
)
_SIGNAL_COLORS = {"绿": "#16a34a", "黄": "#d97706", "红": "#dc2626"}


def _signal_badge(signal) -> str:
    """红/黄/绿 信号 → 彩色徽章（无信号返回空）"""
    s = str(signal or "").strip()
    if not s:
        return ""
    color = _SIGNAL_COLORS.get(s[0], "#6b7280")
    return f'<span class="sig" style="background:{color}">{esc(s)}</span>'


def _dim_interpretation(dim: str, score) -> str:
    """按得分档给出客户侧解读"""
    high = {
        "generation": "该任务需要大量生成新内容（批改意见/课件/总结等），AI 的生成能力是核心价值——请准备明确的输出格式与质量要求，并预留人工抽检。",
        "reasoning": "任务包含多步推理/分析，AI 的价值在于把复杂逻辑拆解清楚——请准备充分的业务规则与历史案例作为推理依据。",
        "uncertainty": "业务对 AI 的不确定性输出容忍度较高，实施阻力小——建议采用引用溯源提升可信度，并逐步让 AI 接管更多环节。",
        "data": "数据可得性高，主要工作将集中在清洗、标注与评测——这是决定效果上限的环节，建议尽早启动数据准备。",
        "real_time": "无强实时要求，可接受离线/批处理——架构成本低，可用高性价比模型。",
    }
    mid = {
        "generation": "任务对生成内容有需求但非核心——请明确哪些输出必须由 AI 生成、哪些可模板化，控制生成边界。",
        "reasoning": "推理复杂度中等——大部分场景可直接处理，复杂分支建议人工介入或加规则兜底。",
        "uncertainty": "业务对 AI 输出的准确性有一定要求——建议对关键输出加校验/人工复核，并标注置信度。",
        "data": "数据可得性中等——需先评估现有数据的覆盖度与质量，必要时补充采集或标注。",
        "real_time": "对响应速度有中等要求——需关注推理延迟，可考虑模型量化或缓存策略。",
    }
    low = {
        "generation": "任务以检索/分类/匹配为主、生成内容少——AI 的价值在于理解与命中而非创作，可控制生成类投入。",
        "reasoning": "任务较直接、推理负担低——实现与部署更简单，落地风险低。",
        "uncertainty": "业务对准确性要求很高（容错低）——必须配套人工审核、规则校验与兜底，AI 只做辅助。",
        "data": "数据可得性不足——这是当前最大风险，请优先解决数据来源/采集/标注，否则效果无法保证。",
        "real_time": "实时性要求很高——需重点评估推理性能、并发与延迟，必要时用轻量模型或边缘部署。",
    }
    s = int(score or 0)
    if s is None or s == 0:
        return ""
    if s >= 4:
        return high.get(dim, "")
    if s <= 2:
        return low.get(dim, "")
    return mid.get(dim, "")


# ---------- 章节渲染 ----------

def _chapter_cover(report) -> str:
    fc = report.get("final_conclusion", {})
    conf = report.get("confidence", {})
    conf_label = {"high": "高", "medium": "中", "low": "低"}.get(conf.get("level"), str(conf.get("level", "")))
    return f"""
    <div class="cover">
      <h1>需求诊断报告</h1>
      <div class="sub">AI 项目可行性 · 多 Agent 对抗评审 · 多轮累积需求文档</div>
      <table class="cover-table">
        <tr><th>客户</th><td>{esc(report.get('customer_name'))}</td></tr>
        <tr><th>报告版本</th><td>{esc(report.get('version'))}（前版：{esc(report.get('previous_version') or '—')}）</td></tr>
        <tr><th>生成日期</th><td>{esc(report.get('generated_at'))}</td></tr>
        <tr><th>验收人</th><td>{esc(report.get('decision_maker'))}</td></tr>
        <tr><th>总体结论</th><td>{esc(fc.get('conclusion'))}（可行性总分 <b>{fc.get('total_score')}/25</b>，置信度 {esc(conf_label)}）</td></tr>
        <tr><th>需求摘要</th><td>{esc(report.get('requirement_summary'))}</td></tr>
        <tr><th>run_id</th><td><code>{esc(report.get('run_id'))}</code></td></tr>
      </table>
      <p class="foot">本报告由 AI 项目现场交付工具包生成 · 已人工确认 · 作为后续需求开发与项目实施依据</p>
    </div>"""


def _chapter_revision_history(report) -> str:
    vh = report.get("version_history") or []
    rows = "".join(
        f"<tr><td>{esc(v.get('version'))}</td><td>{esc(v.get('generated_at'))}</td>"
        f"<td>{_changelog_text(v.get('changelog'))}</td></tr>"
        for v in vh
    ) or f"<tr><td>{esc(report.get('version'))}</td><td>{esc(report.get('generated_at'))}</td><td>首版</td></tr>"
    return f"""
    <h2>文档信息与修订历史</h2>
    <table class="rev-table"><tr><th>版本</th><th>时间</th><th>变更摘要</th></tr>{rows}</table>"""


def _changelog_text(changelog) -> str:
    if not changelog:
        return "—"
    parts = []
    for c in changelog:
        parts.append(f"{_DIM_NAMES.get(c.get('dimension'), c.get('dimension'))}: {c.get('prev')}→{c.get('curr')}({c.get('role')})")
    return "；".join(parts)


def _chapter_toc(report) -> str:
    chapters = [
        "执行摘要", "需求理解与背景", "项目目标与范围", "功能需求", "非功能需求",
        "五维可行性深度分析", "整体可行性评估", "数据与资源要求", "风险与缓解",
        "假设与依赖", "开放问题与待澄清", "分阶段实施建议", "验收标准",
        "商务提案（供洽谈讨论）",
        "附录 A · 完整对抗评审过程", "附录 B · 多轮客户反馈与版本演进",
    ]
    items = "".join(f"<li><a href='#ch{i + 1}'>{i + 1}. {esc(c)}</a></li>" for i, c in enumerate(chapters))
    return f"<h2>目录</h2><ol class='toc'>{items}</ol>"


def _inline_overall_adversarial(report) -> str:
    """执行摘要/整体可行性处的简短内联对抗说明：谁同意、谁分歧、Reviewer 修正、非技术信号分歧"""
    gen = report.get("generator", {}) or {}
    crit = report.get("critic", {}) or {}
    reviewer = report.get("reviewer", {}) or {}
    divergences = report.get("divergences") or []
    gen_scores = gen.get("dimension_scores") or {}
    crit_scores = crit.get("dimension_scores") or {}

    agree_dims = [k for k in _DIM_EN
                  if gen_scores.get(k) is not None and crit_scores.get(k) is not None
                  and gen_scores.get(k) == crit_scores.get(k)]
    div_dims = [d.get("dimension") for d in divergences if d.get("source") == "generator_vs_critic"]

    parts = []
    if agree_dims:
        parts.append("Generator 与 Critic 盲审在「" + "、".join(_DIM_NAMES[k] for k in agree_dims) + "」上一致")
    if div_dims:
        parts.append("在「" + "、".join(_DIM_NAMES[k] for k in div_dims) + "」上存在分歧（分歧即需贵方决策的信息）")
    tech_line = "；".join(parts) if parts else "（无技术维度打分数据）"

    rev_line = ""
    verdicts = reviewer.get("verdicts") if isinstance(reviewer, dict) else {}
    if isinstance(verdicts, dict) and verdicts:
        corrections = [(k, v.get("adjusted_score")) for k, v in verdicts.items()
                       if isinstance(v, dict) and v.get("verdict") == "correct"]
        if corrections:
            rev_line = "；Reviewer 对人工打分提出修正：" + "、".join(
                f"{_DIM_NAMES.get(k, k)}→{v}" for k, v in corrections)
        else:
            rev_line = "；Reviewer 认同人工打分"

    ntf = gen.get("non_tech_feasibility") or {}
    nta = crit.get("non_tech_audit") or {}
    signal_div = []
    for k, name in _NON_TECH_CATS:
        gs = (ntf.get(k) or {}).get("signal") if isinstance(ntf.get(k), dict) else ""
        cs = (nta.get(k) or {}).get("signal") if isinstance(nta.get(k), dict) else ""
        if gs and cs and str(gs).strip()[0] != str(cs).strip()[0]:
            signal_div.append(f"{name}（Generator {gs} vs Critic {cs}）")
    non_tech_line = ("；非技术层面存在信号分歧：" + "、".join(signal_div)) if signal_div else ""

    return f"<p class='meta'><b>对抗评审速览：</b>{esc(tech_line)}{esc(rev_line)}{esc(non_tech_line)}。</p>"


def _chapter_exec_summary(report) -> str:
    fc = report.get("final_conclusion", {})
    gen = report.get("generator", {}) or {}
    conf = report.get("confidence", {}) or {}
    conf_label = {"high": "高置信", "medium": "中置信", "low": "低置信"}.get(conf.get("level"), str(conf.get("level", "")))
    needs = conf.get("needs_confirm") or []
    needs_html = f"<p class='warn'>⚠ 以下维度置信度低，须经人工/贵方确认后方可采信：{'、'.join(needs)}</p>" if needs else ""
    scores = gen.get("dimension_scores") or {}
    score_rows = "".join(
        f"<tr><td>{_DIM_NAMES.get(k, k)}</td><td class='c'>{scores.get(k, '-')}/5</td></tr>"
        for k in _DIM_EN
    )
    recs = "".join(f"<li>{esc(r)}</li>" for r in (report.get("recommendations") or []))
    return f"""
    <h2 id="ch1">1. 执行摘要</h2>
    <div class="exec">
      <p class="concl"><b>总体结论：{esc(fc.get('conclusion'))}</b>（可行性总分 <b>{fc.get('total_score')}/25</b>，{esc(conf_label)}）</p>
      <p><b>一句话：</b>{esc(fc.get('suggestion'))}</p>
      <p class="meta">依据：{esc(fc.get('basis'))} ｜ 判定口径：{esc(report.get('prompt_modified') and '提示词已由客户修改，中立性不作承诺' or '默认严格中立提示词')}</p>
      {needs_html}
      {_inline_overall_adversarial(report)}
    </div>
    <h3>1.1 五维得分概览</h3>
    <table><tr><th>维度</th><th>得分</th></tr>{score_rows}</table>
    <h3>1.2 Generator 总体判断</h3>
    {_para(gen.get('summary'))}
    <h3>1.3 建议与下一步</h3>
    <ol>{recs or '<li>（无）</li>'}</ol>"""


def _chapter_requirement_understanding(report) -> str:
    gen = report.get("generator", {}) or {}
    ru = gen.get("requirement_understanding") or {}
    if not isinstance(ru, dict):
        ru = {}
    return f"""
    <h2 id="ch2">2. 需求理解与背景</h2>
    <h3>2.1 背景</h3>
    {_para(ru.get('background') or report.get('requirement_summary') or report.get('requirement'))}
    <h3>2.2 客户痛点</h3>
    <ul>{_list(ru.get('pain_points'))}</ul>
    <h3>2.3 项目目标</h3>
    <ul>{_list(ru.get('goals'))}</ul>
    <h3>2.4 约束条件</h3>
    <ul>{_list(ru.get('constraints'))}</ul>
    <div class="box"><p class="meta"><b>需求原文：</b></p>{_para(report.get('requirement'))}</div>"""


def _chapter_goals_scope(report) -> str:
    gen = report.get("generator", {}) or {}
    ru = gen.get("requirement_understanding") or {}
    scope = gen.get("scope") or {}
    if not isinstance(scope, dict):
        scope = {}
    goals_html = "".join(f"<li>{esc(g)}</li>" for g in (ru.get("goals") or [])) or "<li>（未提供）</li>"
    draft_scope = gen.get("draft_sections", {}).get("scope") if isinstance(gen.get("draft_sections"), dict) else ""
    return f"""
    <h2 id="ch3">3. 项目目标与范围</h2>
    <h3>3.1 项目目标</h3>
    <ul>{goals_html}</ul>
    <h3>3.2 做什么（In Scope）</h3>
    <ul>{_list(scope.get('in_scope'))}</ul>
    <h3>3.3 不做什么（Out of Scope）</h3>
    <ul>{_list(scope.get('out_of_scope'))}</ul>
    <h3>3.4 范围章节草稿</h3>
    {_para(draft_scope)}"""


def _chapter_functional(report) -> str:
    gen = report.get("generator", {}) or {}
    draft = gen.get("draft_sections") or {}
    if not isinstance(draft, dict):
        draft = {}
    weave = (gen.get("feedback_weave") or report.get("feedback_weave") or {})
    fw = weave.get("functional") if isinstance(weave, dict) else []
    feats = gen.get("functional_requirements") or []
    feat_rows = "".join(
        f"<li>{esc(f if isinstance(f, str) else json_mod.dumps(f, ensure_ascii=False))}</li>" for f in feats
    )
    fw_rows = "".join(f"<li>{esc(f)}</li>" for f in fw)
    return f"""
    <h2 id="ch4">4. 功能需求</h2>
    <h3>4.1 功能需求清单（可验收条目）</h3>
    <ul>{feat_rows or '<li>（Generator 未单独列条目，见下方章节草稿）</li>'}</ul>
    <h3>4.2 功能需求章节草稿</h3>
    {_para(draft.get('functional_requirements'))}
    {('<h3>4.3 客户反馈新增/修订的功能需求</h3><ul>' + fw_rows + '</ul>') if fw_rows else ''}"""


def _chapter_non_functional(report) -> str:
    gen = report.get("generator", {}) or {}
    draft = gen.get("draft_sections") or {}
    if not isinstance(draft, dict):
        draft = {}
    nfrs = gen.get("non_functional_requirements") or []
    nfr_boxes = _obj_list(nfrs, [("title", "类别", "label"), ("detail", "要求", "label"), ("standard", "验收口径", "label")])
    weave = (gen.get("feedback_weave") or report.get("feedback_weave") or {})
    fw = weave.get("non_functional") if isinstance(weave, dict) else []
    fw_rows = "".join(f"<li>{esc(f)}</li>" for f in fw)
    return f"""
    <h2 id="ch5">5. 非功能需求</h2>
    <h3>5.1 非功能需求条目（性能/安全/合规/可用性等）</h3>
    {nfr_boxes}
    <h3>5.2 非功能需求章节草稿</h3>
    {_para(draft.get('non_functional_requirements'))}
    {('<h3>5.3 客户反馈新增/修订的非功能需求</h3><ul>' + fw_rows + '</ul>') if fw_rows else ''}"""


def _dim_adversarial_block(k, gen, crit, reviewer, human_scores, divergences) -> str:
    """每个维度分析块内的「对抗评审过程」内联可读块（通顺中文，禁止贴 JSON/代码）"""
    da = gen.get("dimension_analysis") if isinstance(gen.get("dimension_analysis"), dict) else {}
    cda = crit.get("dimension_analysis") if isinstance(crit.get("dimension_analysis"), dict) else {}
    gen_entry = da.get(k) if isinstance(da.get(k), dict) else {}
    crit_entry = cda.get(k) if isinstance(cda.get(k), dict) else {}

    gen_score = gen_entry.get("score") or (gen.get("dimension_scores") or {}).get(k, "—")
    crit_score = crit_entry.get("score") or (crit.get("dimension_scores") or {}).get(k, "—")
    gen_analysis = gen_entry.get("analysis") or (gen.get("reasons") or {}).get(k, "") or ""
    crit_analysis = crit_entry.get("analysis") or (crit.get("reasons") or {}).get(k, "") or ""
    gen_evidence = gen_entry.get("evidence") or ""
    crit_evidence = crit_entry.get("evidence") or ""

    div = next((d for d in divergences if d.get("dimension") == k and d.get("source") == "generator_vs_critic"), None)
    if div:
        div_text = (f"双方在得分上存在分歧（Generator {div.get('a')} 分 vs Critic 盲审 {div.get('b')} 分），"
                    f"分歧即信息，需贵方决策。")
    else:
        div_text = "双方得分一致，技术维度上无分歧。"

    rev = "（未执行人工评审，Reviewer 无意见）"
    verdicts = reviewer.get("verdicts") if isinstance(reviewer, dict) else {}
    verdict = verdicts.get(k) if isinstance(verdicts, dict) else None
    if isinstance(verdict, dict) and verdict:
        v = verdict.get("verdict")
        human_v = human_scores.get(k, "-")
        if v == "agree":
            rev = (f"Reviewer 认同人工给 {human_v} 分。"
                   f"{verdict.get('full_analysis') or verdict.get('reason') or ''}"
                   + ((" 反方论证：" + verdict["counter_to_human"]) if verdict.get("counter_to_human") else ""))
        elif v == "correct":
            adj = verdict.get("adjusted_score")
            rev = (f"Reviewer 认为人工给 {human_v} 分偏高/偏低，建议修正为 {adj} 分。"
                   f"{verdict.get('full_analysis') or verdict.get('reason') or ''}")
        else:
            rev = f"Reviewer 意见：{verdict.get('full_analysis') or verdict.get('reason') or ''}"

    adopt = "双方一致，采纳该维度判断。"
    if isinstance(verdict, dict) and verdict.get("verdict") == "correct" and verdict.get("adjusted_score") is not None:
        adopt = (f"采纳 Reviewer 修正分 {verdict.get('adjusted_score')} 分（人工 {human_scores.get(k, '-')} 分作废）；"
                 f"本维度分歧留待贵方确认依据。")
    elif div:
        adopt = "技术维度双方分歧，判断留待客户决策（分歧本身是信息）。"

    return f"""
        <div class="adversarial">
          <h4>对抗评审过程 · {_DIM_NAMES[k]}</h4>
          <div class="ad-row"><b>Generator 立场（{esc(gen_score)}/5）：</b>{_para(gen_analysis) or '<span class=meta>（未提供）</span>'}</div>
          {('<div class="evidence"><b>Generator 引用原文：</b>' + esc(gen_evidence) + '</div>') if gen_evidence else ''}
          <div class="ad-row"><b>Critic 独立盲审立场（{esc(crit_score)}/5）：</b>{_para(crit_analysis) or '<span class=meta>（未提供）</span>'}</div>
          {('<div class="evidence"><b>Critic 引用原文：</b>' + esc(crit_evidence) + '</div>') if crit_evidence else ''}
          <div class="ad-row"><b>与 Generator 的分歧：</b>{esc(div_text)}</div>
          <div class="ad-row"><b>Reviewer 对人工分的评审：</b>{esc(rev)}</div>
          <div class="ad-concl"><b>采纳结论：</b>{esc(adopt)}</div>
        </div>"""


def _dim_deep_analysis(report) -> str:
    """逐维深度分析：完整论证 + evidence 原文引用 + 对客户影响 + 内联对抗评审过程"""
    gen = report.get("generator", {}) or {}
    crit = report.get("critic", {}) or {}
    reviewer = report.get("reviewer", {}) or {}
    human_scores = (report.get("human_review") or {}).get("scores") or {}
    divergences = report.get("divergences") or []
    da = gen.get("dimension_analysis") or {}
    scores = gen.get("dimension_scores") or {}
    reasons = gen.get("reasons") or {}
    blocks = []
    for k in _DIM_EN:
        entry = da.get(k) if isinstance(da, dict) else {}
        if not isinstance(entry, dict):
            entry = {}
        score = entry.get("score", scores.get(k))
        analysis = entry.get("analysis") or reasons.get(k) or ""
        evidence = entry.get("evidence") or ""
        implications = entry.get("implications") or _dim_interpretation(k, score)
        if score is None:
            score = scores.get(k)
        score_display = score if score is not None else "—"
        pct = (int(score) if score else 0) / 5 * 100
        blocks.append(f"""
        <div class="dim">
          <div class="dim-head"><b>{_DIM_NAMES[k]}</b> <span class="score">{score_display}/5</span>
            <div class="track"><div class="fill" style="width:{pct}%"></div></div></div>
          <p class="meta"><b>完整论证：</b></p>
          {_para(analysis)}
          {('<div class="evidence"><b>引用需求原文：</b>' + esc(evidence) + '</div>') if evidence else ''}
          {('<p><b>对贵方意味着：</b>' + esc(implications) + '</p>') if implications else ''}
          {_dim_adversarial_block(k, gen, crit, reviewer, human_scores, divergences)}
        </div>""")
    return "\n".join(blocks)


def _chapter_dimensions(report) -> str:
    gen = report.get("generator", {}) or {}
    crit = report.get("critic", {}) or {}
    gen_scores = gen.get("dimension_scores") or {}
    crit_scores = crit.get("dimension_scores") or {}
    divergences = report.get("divergences") or []
    cmp_rows = "".join(
        f"<tr><td>{_DIM_NAMES.get(k, k)}</td><td class='c'>{gen_scores.get(k, '-')}</td>"
        f"<td class='c'>{crit_scores.get(k, '-')}</td><td class='c'>{abs(int(gen_scores.get(k, 0)) - int(crit_scores.get(k, 0)))}</td></tr>"
        for k in _DIM_EN
    )
    div_note = ""
    if divergences:
        div_note = "<p class='meta'>以下维度 Generator 与 Critic 存在分歧（分歧即信息，需贵方决策）：" + "、".join(
            f"{_DIM_NAMES.get(d.get('dimension'), d.get('dimension'))}（{d.get('a')} vs {d.get('b')}）" for d in divergences
        ) + "</p>"
    return f"""
    <h2 id="ch6">6. 五维可行性深度分析</h2>
    <p class="meta">本节对每个维度的论证后，均内联「对抗评审过程」可读块（Generator 立场 / Critic 盲审立场与分歧 / Reviewer 对人工分的评审 / 采纳结论）；完整原始 JSON 见附录 A。</p>
    <h3>6.0 Generator vs Critic 独立打分对比</h3>
    <table><tr><th>维度</th><th>Generator</th><th>Critic（盲审）</th><th>差距</th></tr>{cmp_rows}</table>
    {div_note}
    {_dim_deep_analysis(report)}"""


def _non_tech_item_block(k, name, gen, crit) -> str:
    """非技术某维度：Generator 立场 vs Critic 盲审 内联对抗块（每项含评估/依据/红黄绿/建议）"""
    ntf = gen.get("non_tech_feasibility") if isinstance(gen, dict) else {}
    nta = crit.get("non_tech_audit") if isinstance(crit, dict) else {}
    g = ntf.get(k) if isinstance(ntf, dict) else {}
    c = nta.get(k) if isinstance(nta, dict) else {}
    if not isinstance(g, dict):
        g = {}
    if not isinstance(c, dict):
        c = {}
    g_item, g_basis, g_sig, g_advice = g.get("item"), g.get("basis"), g.get("signal"), g.get("advice")
    c_item, c_basis, c_sig, c_advice, c_note = c.get("item"), c.get("basis"), c.get("signal"), c.get("advice"), c.get("audit_note")

    diff = (bool(g_sig and c_sig and str(g_sig).strip()[0] != str(c_sig).strip()[0])) or bool(c_note)
    if diff:
        div_line = (f"<div class='ad-row'><b>分歧：</b>Generator 判 {esc(g_sig)}、Critic 盲审判 {esc(c_sig)}，"
                    f"两者立场不一，本项判断留待客户决策。</div>")
    elif g_sig or c_sig:
        div_line = "<div class='ad-row'><b>分歧：</b>双方信号一致（或 Critic 未提出异议），本项判断可采信。</div>"
    else:
        div_line = "<div class='ad-row'><b>分歧：</b>（双方均未提供独立评估，无法判定分歧。）</div>"

    return f"""
    <div class="adversarial">
      <h4>{esc(name)}</h4>
      <div class="ad-row"><b>Generator 立场</b>{_signal_badge(g_sig)}：{_para(g_item) or '<span class=meta>（未提供）</span>'}</div>
      {('<div class="evidence"><b>Generator 依据：</b>' + esc(g_basis) + '</div>') if g_basis else ''}
      {('<div class="ad-row"><b>Generator 建议：</b>' + esc(g_advice) + '</div>') if g_advice else ''}
      <div class="ad-row"><b>Critic 独立盲审</b>{_signal_badge(c_sig)}：{_para(c_item) or '<span class=meta>（未提供）</span>'}</div>
      {('<div class="evidence"><b>Critic 依据：</b>' + esc(c_basis) + '</div>') if c_basis else ''}
      {('<div class="ad-row"><b>Critic 担忧/分歧点：</b>' + esc(c_note) + '</div>') if c_note else ''}
      {('<div class="ad-row"><b>Critic 建议：</b>' + esc(c_advice) + '</div>') if c_advice else ''}
      {div_line}
    </div>"""


def _chapter_overall_feasibility(report) -> str:
    """7. 整体可行性评估：技术5维概览 + 非技术各维（Generator vs Critic 内联对抗）+ 综合建议"""
    gen = report.get("generator", {}) or {}
    crit = report.get("critic", {}) or {}
    reviewer = report.get("reviewer", {}) or {}
    human = (report.get("human_review") or {}).get("scores") or {}
    gen_scores = gen.get("dimension_scores") or {}
    crit_scores = crit.get("dimension_scores") or {}
    rev_scores = {}
    verdicts = reviewer.get("verdicts") if isinstance(reviewer, dict) else {}
    if isinstance(verdicts, dict):
        for k, v in verdicts.items():
            if isinstance(v, dict) and v.get("verdict") == "correct" and v.get("adjusted_score") is not None:
                rev_scores[k] = v["adjusted_score"]

    tech_rows = ""
    for k in _DIM_EN:
        adopt = rev_scores.get(k) or human.get(k) or gen_scores.get(k) or "—"
        tech_rows += (f"<tr><td>{_DIM_NAMES[k]}</td><td class='c'>{gen_scores.get(k, '-')}</td>"
                      f"<td class='c'>{crit_scores.get(k, '-')}</td><td class='c'>{human.get(k, '-')}</td>"
                      f"<td class='c'>{rev_scores.get(k, '-')}</td><td class='c'>{adopt}</td></tr>")

    non_tech_blocks = "".join(_non_tech_item_block(k, name, gen, crit) for k, name in _NON_TECH_CATS)

    ntf = gen.get("non_tech_feasibility") if isinstance(gen, dict) else {}
    or_ = ntf.get("overall_recommendation") if isinstance(ntf, dict) else {}
    nta = crit.get("non_tech_audit") if isinstance(crit, dict) else {}
    oan = nta.get("overall_audit_note") if isinstance(nta, dict) else ""

    overall_html = ""
    if isinstance(or_, dict) and or_:
        overall_html = f"""
        <div class="box">
          <p><b>值不值得投：</b>{esc(or_.get('worth_investing') or '—')}</p>
          <p><b>投多少：</b>{esc(or_.get('budget_scale') or '—')}</p>
          <p><b>主要阻力：</b>{esc(or_.get('main_resistance') or '—')}</p>
          <p><b>先做什么：</b>{esc(or_.get('first_steps') or '—')}</p>
        </div>"""
    crit_overall_html = f"<div class='ad-row'><b>Critic 盲审整体判断：</b>{_para(oan)}</div>" if oan else ""

    return f"""
    <h2 id="ch7">7. 整体可行性评估</h2>
    <p class="meta">本节把「技术可行性（五维打分）」与「非技术可行性（商业/组织/集成/合规/风险）」合并给出全景判断；非技术部分展示 Generator 立场与 Critic 盲审的独立对抗，完整原文见附录 A。</p>
    {_inline_overall_adversarial(report)}
    <h3>7.1 技术可行性：五维得分概览</h3>
    <table><tr><th>维度</th><th>Generator</th><th>Critic 盲审</th><th>人工</th><th>Reviewer 修正</th><th>采纳分</th></tr>{tech_rows}</table>
    <h3>7.2 非技术可行性（各维 Generator 立场 vs Critic 盲审）</h3>
    {non_tech_blocks or '<p class="meta">（非技术可行性未提供）</p>'}
    <h3>7.3 综合建议</h3>
    {overall_html or '<p class="meta">（Generator 未提供综合建议，见 1.3 建议与下一步）</p>'}
    {crit_overall_html}
    <p class="meta">综合建议为 Generator 基于技术+非技术全局给出的方向；Critic 盲审独立判断见上；最终投入与否由贵方拍板。</p>"""


def _chapter_data_resources(report) -> str:
    gen = report.get("generator", {}) or {}
    dr = gen.get("data_requirements") or {}
    if not isinstance(dr, dict):
        dr = {}
    da = gen.get("dimension_analysis") or {}
    data_dim = da.get("data") if isinstance(da, dict) else {}
    data_evidence = (data_dim or {}).get("evidence") if isinstance(data_dim, dict) else ""
    return f"""
    <h2 id="ch8">8. 数据与资源要求</h2>
    <h3>8.1 数据来源</h3>
    <ul>{_list(dr.get('data_sources'))}</ul>
    <h3>8.2 数据量估计</h3>
    {_para(dr.get('data_volume'))}
    <h3>8.3 数据质量评估</h3>
    {_para(dr.get('data_quality'))}
    <h3>8.4 安全与合规要求</h3>
    {_para(dr.get('security_compliance'))}
    <h3>8.5 所需资源</h3>
    <ul>{_list(dr.get('resources'))}</ul>
    {('<div class="evidence"><b>数据可得性维度的原文依据：</b>' + esc(data_evidence) + '</div>') if data_evidence else ''}
    <p class="meta">数据与资源是决定 AI 效果上限的环节，建议尽早确认数据来源、数据量与质量，必要时启动采集/标注。</p>"""


def _chapter_risks(report) -> str:
    gen = report.get("generator", {}) or {}
    crit = report.get("critic", {}) or {}
    risks = gen.get("risks") or []
    risk_boxes = _obj_list(risks, [("risk", "风险", "label"), ("likelihood", "可能性", "label"),
                                   ("impact", "影响", "label"), ("mitigation", "缓解措施", "label")])
    overconf = crit.get("over_confidence_audit") or []
    overconf_boxes = _obj_list(overconf, [("claim", "被高估的断言", "label"), ("evidence_strength", "现有依据强度", "label"),
                                          ("concern", "担忧", "label")])
    contradictions = crit.get("contradictions") or []
    contra_boxes = _obj_list(contradictions, [("statement_a", "表述A", "label"), ("statement_b", "表述B", "label"),
                                              ("evidence", "原文引用", "quote"), ("explanation", "矛盾说明", "label")])
    gaps = crit.get("coverage_gaps") or []
    gaps_list = "".join(f"<li>{esc(g)}</li>" for g in gaps)
    divergences = report.get("divergences") or []
    div_rows = "".join(
        f"<tr><td>{_DIM_NAMES.get(d.get('dimension'), d.get('dimension'))}</td><td>{esc(d.get('source'))}</td>"
        f"<td class='c'>{d.get('a')}</td><td class='c'>{d.get('b')}</td></tr>"
        for d in divergences) or "<tr><td colspan=4>（无）</td></tr>"
    return f"""
    <h2 id="ch9">9. 风险与缓解</h2>
    <h3>9.1 Generator 识别的风险（含缓解）</h3>
    {risk_boxes}
    <h3>9.2 Critic 过度自信审计</h3>
    {overconf_boxes or '<p class="meta">（未发现明显过度自信）</p>'}
    <h3>9.3 Critic 内部矛盾审计</h3>
    {contra_boxes or '<p class="meta">（未发现内部矛盾）</p>'}
    <h3>9.4 需求覆盖缺口</h3>
    <ul>{gaps_list}</ul>
    <h3>9.5 评审分歧记录（过程信息，本身是需决策信号）</h3>
    <table><tr><th>维度</th><th>分歧来源</th><th>A</th><th>B</th></tr>{div_rows}</table>"""


def _chapter_assumptions(report) -> str:
    gen = report.get("generator", {}) or {}
    assumptions = gen.get("assumptions") or []
    ru = gen.get("requirement_understanding") or {}
    constraints = ru.get("constraints") or []
    return f"""
    <h2 id="ch10">10. 假设与依赖</h2>
    <h3>10.1 关键假设</h3>
    <ul>{_list(assumptions)}</ul>
    <h3>10.2 约束与依赖</h3>
    <ul>{_list(constraints)}</ul>
    <p class="meta">以上假设若有不成立，请在后续沟通中向贵方确认，避免基于错误前提推进实施。</p>"""


def _chapter_open_questions(report) -> str:
    gen = report.get("generator", {}) or {}
    reviewer = report.get("reviewer", {}) or {}
    qs = gen.get("clarification_questions") or []
    q_rows = ""
    for i, q in enumerate(qs, 1):
        if isinstance(q, str):
            q_rows += f"<div class='box'><p><b>问题{i}：</b>{esc(q)}</p></div>"
        elif isinstance(q, dict):
            why = q.get("why") or ""
            q_rows += (f"<div class='box'><p><b>问题{i}：</b>{esc(q.get('question'))}</p>"
                       f"{('<p class=meta><b>为什么问：</b>' + esc(why) + '</p>') if why else ''}</div>")
    weave = (gen.get("feedback_weave") or report.get("feedback_weave") or {})
    fw = weave.get("open") if isinstance(weave, dict) else []
    fw_rows = "".join(f"<li>{esc(f)}</li>" for f in fw)
    reconfirm = reviewer.get("need_reconfirm") or []
    reconfirm_rows = _obj_list(reconfirm, [("item", "需再确认的点", "label"), ("reason", "原因", "label")])
    return f"""
    <h2 id="ch11">11. 开放问题与待澄清</h2>
    <h3>11.1 Generator 需向客户澄清的问题</h3>
    {q_rows or '<p class="meta">（暂无）</p>'}
    <h3>11.2 客户反馈中累积的开放问题</h3>
    <ul>{fw_rows or '<li>（暂无）</li>'}</ul>
    <h3>11.3 Reviewer 建议人工/客户再确认项</h3>
    {reconfirm_rows or '<p class="meta">（无）</p>'}"""


def _chapter_phased_plan(report) -> str:
    gen = report.get("generator", {}) or {}
    phases = gen.get("implementation_phases") or []
    phase_boxes = _obj_list(phases, [("phase", "阶段", "label"), ("focus", "重点", "label"),
                                     ("deliverables", "交付物", "label"), ("risks", "阶段风险与对策", "label")])
    recs = "".join(f"<li>{esc(r)}</li>" for r in (report.get("recommendations") or []))
    fc = report.get("final_conclusion", {})
    return f"""
    <h2 id="ch12">12. 分阶段实施建议</h2>
    <h3>12.1 Generator 建议的实施阶段</h3>
    {phase_boxes or '<p class="meta">（未提供，见 12.2 通用分阶段建议）</p>'}
    <h3>12.2 依据可行性结论的通用推进路径</h3>
    <p class="meta">总体结论：{esc(fc.get('conclusion'))}（{fc.get('total_score')}/25）</p>
    <ol>{recs or '<li>（无）</li>'}</ol>
    <p class="meta">建议先以最小闭环验证核心假设，再逐步扩展到全量场景；数据准备与标注应尽早启动。</p>"""


def _chapter_acceptance(report) -> str:
    gen = report.get("generator", {}) or {}
    draft = gen.get("draft_sections") or {}
    if not isinstance(draft, dict):
        draft = {}
    weave = (gen.get("feedback_weave") or report.get("feedback_weave") or {})
    fw = weave.get("acceptance") if isinstance(weave, dict) else []
    fw_rows = "".join(f"<li>{esc(f)}</li>" for f in fw)
    return f"""
    <h2 id="ch13">13. 验收标准</h2>
    <h3>13.1 验收标准章节草稿</h3>
    {_para(draft.get('acceptance_criteria'))}
    {('<h3>13.2 客户反馈累积的验收要求</h3><ul>' + fw_rows + '</ul>') if fw_rows else ''}
    <p class="meta">验收标准应以可量化、可操作的方式定义，并随需求演进持续补充。</p>"""


def _chapter_business_proposal(report) -> str:
    """14. 商务提案（供洽谈讨论）：投入估算与分期 / 时间里程碑 / 责任清单 / 试点与退出 / 替代方案与不做的代价"""
    bp = report.get("business_proposal") or {}
    if not isinstance(bp, dict):
        bp = {}

    ie = bp.get("investment_estimate") or {}
    if not isinstance(ie, dict):
        ie = {}
    disclaimer = ie.get("disclaimer") or "此为讨论用初步估算，最终以商务洽谈确认为准。"
    tiers = ie.get("tiers") or []
    tier_rows = ""
    for t in tiers:
        if not isinstance(t, dict):
            continue
        dl = "、".join(str(x) for x in t.get("deliverables") or [])
        tier_rows += f"""
        <div class="box">
          <p><b>{esc(t.get('period'))}</b> · 投入区间：<b>{esc(t.get('investment_range'))}</b></p>
          <p><b>做什么：</b>{esc(t.get('focus'))}</p>
          {('<p><b>范围：</b>' + esc(t.get('scope')) + '</p>') if t.get('scope') else ''}
          {('<p><b>投入依据：</b>' + esc(t.get('basis')) + '</p>') if t.get('basis') else ''}
          {('<p><b>交付物：</b>' + esc(dl) + '</p>') if dl else ''}
        </div>"""
    total_html = f"<p><b>总投入区间：</b>{esc(ie.get('total_range'))}</p>" if ie.get("total_range") else ""
    notes_html = f"<p class='meta'>{esc(ie.get('notes'))}</p>" if ie.get("notes") else ""

    ms = bp.get("milestones") or []
    ms_rows = "".join(
        f"<tr><td>{esc(m.get('phase'))}</td><td>{esc(m.get('duration'))}</td>"
        f"<td>{esc(m.get('first_usable'))}</td><td>{esc(m.get('milestone'))}</td>"
        f"<td>{esc(m.get('dependencies'))}</td></tr>"
        for m in ms if isinstance(m, dict)
    ) or "<tr><td colspan=5>（未提供）</td></tr>"

    _BLOCK_BADGE = '<span class="badge" style="background:#fee2e2;color:#b91c1c;border-color:#fecaca">阻塞开工</span>'
    cr = bp.get("client_responsibilities") or []
    cr_rows = "".join(
        f"<tr><td>{esc(c.get('item'))}</td><td>{esc(c.get('category'))}</td><td>{esc(c.get('needed_before'))}</td>"
        f"<td>{esc(c.get('owner'))}</td><td>{esc(c.get('reason'))}</td>"
        f"<td>{_BLOCK_BADGE if c.get('blocking') else '—'}</td></tr>"
        for c in cr if isinstance(c, dict)
    ) or "<tr><td colspan=6>（未提供）</td></tr>"
    vr = bp.get("vendor_responsibilities") or []
    vr_rows = "".join(
        f"<li><b>{esc(v.get('category'))}：</b>{esc(v.get('item'))}</li>"
        for v in vr if isinstance(v, dict) and v.get("item")
    ) or "<li>（未提供）</li>"

    pe = bp.get("pilot_and_exit") or {}
    if not isinstance(pe, dict):
        pe = {}
    success = pe.get("success_criteria") or []
    exit_cond = pe.get("exit_conditions") or []

    ac = bp.get("alternatives_and_cost") or {}
    if not isinstance(ac, dict):
        ac = {}
    alts = ac.get("alternatives") or []
    alt_boxes = ""
    for a in alts:
        if not isinstance(a, dict):
            continue
        alt_boxes += f"""
        <div class="box">
          <p><b>{esc(a.get('name'))}</b> · 投入：{esc(a.get('cost_range'))} · 结论：<b>{esc(a.get('verdict'))}</b></p>
          {('<p><b>简述：</b>' + esc(a.get('description')) + '</p>') if a.get('description') else ''}
          {('<p><b>优点：</b>' + esc('、'.join(a.get('pros') or [])) + '</p>') if a.get('pros') else ''}
          {('<p><b>缺点：</b>' + esc('、'.join(a.get('cons') or [])) + '</p>') if a.get('cons') else ''}
          {('<p><b>风险：</b>' + esc(a.get('risk')) + '</p>') if a.get('risk') else ''}
        </div>"""

    return f"""
    <h2 id="ch14">14. 商务提案（供洽谈讨论）</h2>
    <p class="meta">本章为基于诊断结论起草的商务提案，供贵方决策与洽谈讨论。<b>{esc(disclaimer)}</b> 投入/时间为初步估算区间，非报价承诺；责任清单为开工前提，请逐条确认。</p>

    <h3>14.1 投入估算与分期</h3>
    <p class="meta">按诊断范围、裁剪模块与分阶段建议给出初步投入区间（人民币，万元）。</p>
    {tier_rows or '<p class="meta">（未提供）</p>'}
    {total_html}
    {notes_html}

    <h3>14.2 时间里程碑</h3>
    <p class="meta">分阶段时间线；「第一个能用的东西」在试点期即可见到。</p>
    <table><tr><th>阶段</th><th>时长</th><th>何时看到第一个能用的东西</th><th>阶段里程碑</th><th>开工前提</th></tr>{ms_rows}</table>

    <h3>14.3 责任清单（摊开边界）</h3>
    <p class="meta">甲方责任为<b>必须提供才能开工</b>的数据/接口/人员/决策；乙方责任为实施方交付范围。标注「阻塞开工」的条目未落实前，对应阶段无法启动。</p>
    <table><tr><th>甲方责任条目</th><th>类别</th><th>须在何时提供</th><th>甲方责任方</th><th>依据/原因</th><th>是否阻塞</th></tr>{cr_rows}</table>
    <p><b>乙方责任：</b></p>
    <ul>{vr_rows}</ul>

    <h3>14.4 试点范围与退出机制</h3>
    <p><b>试点范围：</b>{esc(pe.get('pilot_scope') or '（未提供）')}</p>
    <p><b>可量化的成功标准：</b></p>
    <ul>{_list(success)}</ul>
    <p><b>失败/不满意退出条件：</b></p>
    <ul>{_list(exit_cond)}</ul>
    {('<p><b>联合评审时点：</b>' + esc(pe.get('review_point')) + '</p>') if pe.get('review_point') else ''}
    {('<p><b>退出善后：</b>' + esc(pe.get('exit_terms')) + '</p>') if pe.get('exit_terms') else ''}

    <h3>14.5 替代方案与不做的代价</h3>
    {alt_boxes or '<p class="meta">（未提供）</p>'}
    {('<div class="box"><p><b>不做的机会成本：</b>' + esc(ac.get('cost_of_inaction')) + '</p></div>') if ac.get('cost_of_inaction') else ''}
    {('<p class="meta"><b>倾向建议：</b>' + esc(ac.get('recommendation')) + '</p>') if ac.get('recommendation') else ''}"""


def _appendix_adversarial(report) -> str:
    """附录 A：完整对抗评审过程（Generator/Critic/Reviewer 全文，不删减）"""
    gen_full = report.get("generator_full") or report.get("generator") or {}
    crit_full = report.get("critic_full") or report.get("critic") or {}
    rev_full = report.get("reviewer_full") or report.get("reviewer") or {}
    agent_log = report.get("agent_log") or []
    log_rows = ""
    for e in agent_log:
        log_rows += f"<div class='box'><p><b>[{esc(e.get('step'))}] {esc(e.get('role'))}</b> · {esc(e.get('at'))}</p>" \
                    f"<pre class='json'>{esc(_json_pretty(e.get('output')))}</pre></div>"
    return f"""
    <h2 id="ch15">15. 附录 A · 完整对抗评审过程</h2>
    <p class="meta">本节保留 Generator / Critic / Reviewer 的完整原始输出（不删减，含 v2.1 新增的非技术可行性/非技术盲审），供贵方与审查方完整核查推理过程；正文各章为提炼后的可读呈现。</p>
    <h3>15.1 Generator 完整输出</h3>
    <pre class="json">{esc(_json_pretty(gen_full))}</pre>
    <h3>15.2 Critic（盲审）完整输出</h3>
    <pre class="json">{esc(_json_pretty(crit_full))}</pre>
    <h3>15.3 Reviewer（评审人工）完整输出</h3>
    <pre class="json">{esc(_json_pretty(rev_full))}</pre>
    <h3>15.4 全步骤过程留痕（agent_log）</h3>
    {log_rows or '<p class="meta">（无）</p>'}"""


def _appendix_feedback(report) -> str:
    """附录 B：多轮客户反馈与版本演进"""
    feedbacks = report.get("client_feedback") or []
    fb_rows = ""
    for i, fb in enumerate(feedbacks, 1):
        items = "".join(
            f"<li>{esc(it.get('item'))}<span class='badge'>{esc(it.get('dimension') or '未映射')}</span>"
            f"<span class='badge'>{esc(it.get('intent') or '')}</span></li>"
            for it in (fb.get("items") or [])
        )
        fb_rows += f"""
        <div class="box"><p><b>第 {i} 轮反馈</b> · 来源：{esc(fb.get('source'))} · {esc(fb.get('added_at'))}</p>
        <p class="meta">倾向：{esc(fb.get('summary'))} ｜ 触达维度：{esc('、'.join(fb.get('touched_dimensions') or []) or '无')}</p>
        <ul>{items or '<li>（无）</li>'}</ul></div>"""
    vh = report.get("version_history") or []
    vh_rows = "".join(
        f"<tr><td>{esc(v.get('version'))}</td><td>{esc(v.get('generated_at'))}</td>"
        f"<td>{_changelog_text(v.get('changelog'))}</td></tr>" for v in vh
    )
    current_vh = f"<tr><td>{esc(report.get('version'))}</td><td>{esc(report.get('generated_at'))}</td><td>当前版本</td></tr>"
    weave = report.get("feedback_weave") or {}
    if not isinstance(weave, dict):
        weave = {}
    weave_summary = "".join(
        f"<li><b>{esc(k)}</b>：{len(weave.get(k) or [])} 条</li>" for k in ("functional", "non_functional", "open", "acceptance")
    )
    return f"""
    <h2 id="ch16">16. 附录 B · 多轮客户反馈与版本演进</h2>
    <h3>16.1 版本历史</h3>
    <table class="rev-table"><tr><th>版本</th><th>时间</th><th>变更</th></tr>{vh_rows}{current_vh}</table>
    <h3>16.2 各轮客户反馈</h3>
    {fb_rows or '<p class="meta">（无客户反馈记录）</p>'}
    <h3>16.3 反馈织入需求章节统计</h3>
    <ul>{weave_summary}</ul>
    <p class="meta">报告随版本累积变厚：每轮客户反馈被提炼为条目并织入功能需求/非功能需求/开放问题/验收标准对应章节。</p>"""


# ---------- 主构建 ----------

def build_diagnosis_html(report: dict) -> str:
    """把诊断报告(v3.x)渲染成面向客户的多章节详细需求文档"""
    style = """
     body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; color:#1f2430;
            max-width: 920px; margin: 0 auto; padding: 0 32px 60px; line-height: 1.75; }
     h1 { font-size: 30px; } h2 { font-size: 19px; border-bottom: 2px solid #2563eb; padding-bottom: 6px;
          margin-top: 44px; color:#1e3a8a; } h3 { font-size: 15px; color:#1e3a8a; margin-top: 26px; }
     h4 { font-size: 13px; color:#374151; }
     table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 10px 0; }
     th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #e3e6ea; vertical-align: top; }
     th { background: #f1f5f9; color:#374151; font-weight: 600; } td.c { text-align:center; }
     ul, ol { padding-left: 22px; } li { margin: 3px 0; }
     .cover { text-align:center; padding: 70px 0 30px; border-bottom: 3px solid #2563eb; margin-bottom: 30px; }
     .cover .sub { color:#6b7280; font-size: 15px; margin: 6px 0 24px; }
     .cover-table { margin: 0 auto; width: 70%; font-size: 13px; }
     .cover-table th { text-align:right; width: 30%; background: transparent; }
     .meta { color:#6b7280; font-size: 12.5px; } .warn { color:#dc2626; font-weight: 600; }
     .exec { background: #f6f8fb; border: 1px solid #dbe3f0; border-radius: 10px; padding: 16px 20px; margin: 14px 0; }
     .concl { font-size: 15px; }
     .box { border: 1px solid #e3e6ea; border-radius: 8px; padding: 10px 14px; margin: 10px 0; }
     .dim { border: 1px solid #e3e6ea; border-radius: 10px; padding: 14px 18px; margin: 14px 0; }
     .dim-head { display: flex; align-items: center; gap: 12px; font-size: 15px; }
     .score { color:#2563eb; font-weight: 700; font-size: 16px; }
     .track { flex:1; background:#eef0f4; border-radius:6px; height:12px; }
     .fill { height:12px; border-radius:6px; background:#2563eb; }
     .evidence { background:#f8fafc; border-left:3px solid #94a3b8; padding:8px 14px; color:#475569;
                 font-style:italic; margin:8px 0; border-radius:0 6px 6px 0; font-size: 13px; }
     .badge { display:inline-block; padding:1px 8px; border-radius:12px; font-size:11px;
              background:#eff4ff; color:#2563eb; border:1px solid #d6e3ff; margin:0 3px; }
     .sig { display:inline-block; padding:1px 10px; border-radius:12px; color:#fff; font-size:11px; margin:0 4px; }
     .adversarial { border:1px solid #dbe3f0; border-radius:10px; padding:12px 16px; margin:12px 0;
                    background:#fafcff; }
     .adversarial h4 { margin:0 0 6px; color:#1e3a8a; }
     .ad-row { margin:6px 0; font-size:13px; }
     .ad-concl { margin:8px 0 2px; padding:8px 12px; background:#eef4ff; border-radius:6px; font-size:13px; }
     pre.json { background:#0f172a; color:#e2e8f0; padding:14px; border-radius:8px; font-size:11.5px;
                line-height:1.55; white-space:pre-wrap; word-break:break-all; }
     .toc { columns: 2; column-gap: 40px; }
     .toc a { color:#1e3a8a; text-decoration:none; }
     .rev-table td { font-size: 12px; }
     .foot { margin-top: 36px; color:#9aa3b2; font-size:11px; border-top:1px solid #e3e6ea; padding-top:10px; text-align:center; }
    """
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>需求诊断报告 {esc(report.get('version', ''))}</title>
<style>{style}</style></head><body>
{_chapter_cover(report)}
{_chapter_revision_history(report)}
{_chapter_toc(report)}
{_chapter_exec_summary(report)}
{_chapter_requirement_understanding(report)}
{_chapter_goals_scope(report)}
{_chapter_functional(report)}
{_chapter_non_functional(report)}
{_chapter_dimensions(report)}
{_chapter_overall_feasibility(report)}
{_chapter_data_resources(report)}
{_chapter_risks(report)}
{_chapter_assumptions(report)}
{_chapter_open_questions(report)}
{_chapter_phased_plan(report)}
{_chapter_acceptance(report)}
{_chapter_business_proposal(report)}
{_appendix_adversarial(report)}
{_appendix_feedback(report)}
<p class="foot">本报告由 AI 项目现场交付工具包生成 · 已人工确认 · 含完整对抗评审过程留痕，可作为后续需求开发与项目实施依据</p>
</body></html>"""


def build_doc_package_html(title: str, sections: dict) -> str:
    """Q18：项目文档包 HTML（架构说明/API 文档/运维手册/SOP，简单 Markdown 渲染）"""
    def md(text: str) -> str:
        out = []
        for line in str(text or "").splitlines():
            line = line.rstrip()
            if line.startswith("### "):
                out.append(f"<h4>{esc(line[4:])}</h4>")
            elif line.startswith("## "):
                out.append(f"<h3>{esc(line[3:])}</h3>")
            elif line.startswith("# "):
                out.append(f"<h2>{esc(line[2:])}</h2>")
            elif line.startswith("- "):
                out.append(f"<li>{esc(line[2:])}</li>")
            elif line.startswith("1. ") or re.match(r"^\d+\. ", line):
                cleaned = re.sub(r"^\d+\. ", "", line)
                out.append(f"<li>{esc(cleaned)}</li>")
            elif line.strip():
                out.append(f"<p>{esc(line)}</p>")
        return "\n".join(out)

    body = "".join(f"<h2>{esc(name)}</h2>{md(content)}" for name, content in (sections or {}).items())
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{esc(title)}</title>
<style>
 body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; color: #1f2430; max-width: 760px; margin: 24px auto; padding: 0 20px; }}
 h1 {{ font-size: 22px; }} h2 {{ font-size: 16px; border-bottom: 2px solid #2563eb; padding-bottom: 4px; margin-top: 24px; }}
 h3 {{ font-size: 14px; color: #374151; }} h4 {{ font-size: 13px; color: #6b7280; }}
 p {{ font-size: 12.5px; line-height: 1.6; }} li {{ font-size: 12.5px; margin: 2px 0; }}
 .foot {{ margin-top: 30px; color: #9aa3b2; font-size: 11px; border-top: 1px solid #e3e6ea; padding-top: 8px; }}
</style></head><body>
<h1>{esc(title)}</h1>
{body}
<p class="foot">本文档由 AI 项目现场交付工具包生成 · 供客户在项目交接后自行查阅</p>
</body></html>"""


def build_crop_plan_html(plan: dict) -> str:
    """裁剪方案交付物 HTML（可打印/发客户）"""
    enabled = "".join(f"<li>{esc(m)}</li>" for m in plan.get("enabled_modules", []))
    deleted = "".join(f"<li>{esc(m)}</li>" for m in plan.get("deleted_modules", []))
    automations = "".join(f"<li>{esc(a)}</li>" for a in plan.get("automations", []))
    simp = f"<pre>{esc(json_mod.dumps(plan.get('simplifications', {}), ensure_ascii=False, indent=2))}</pre>"
    timeline = esc(json_mod.dumps(plan.get("timeline_suggestion", {}), ensure_ascii=False, indent=2))
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>裁剪方案 {esc(plan.get('customer_id', ''))}</title>
<style>
 body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; color: #1f2430; max-width: 760px; margin: 24px auto; padding: 0 20px; }}
 h1 {{ font-size: 22px; }} h2 {{ font-size: 16px; border-bottom: 2px solid #2563eb; padding-bottom: 4px; margin-top: 24px; }}
 li {{ font-size: 12.5px; margin: 3px 0; }} pre {{ background: #f6f7f9; padding: 10px; border-radius: 6px; font-size: 12px; }}
 .foot {{ margin-top: 30px; color: #9aa3b2; font-size: 11px; border-top: 1px solid #e3e6ea; padding-top: 8px; }}
</style></head><body>
<h1>五步裁剪方案 · {esc(plan.get('customer_id', ''))}</h1>
<h2>启用模块</h2><ul>{enabled or '<li>（无）</li>'}</ul>
<h2>删除模块</h2><ul>{deleted or '<li>（无）</li>'}</ul>
<h2>简化配置</h2>{simp}
<h2>自动化建议</h2><ul>{automations or '<li>（无）</li>'}</ul>
<h2>排期建议</h2><pre>{timeline}</pre>
<p class="foot">本方案由 AI 项目现场交付工具包生成 · 供客户评估与确认</p>
</body></html>"""


def render_html_to_pdf(html_str: str, path: str) -> bool:
    """尽力生成 PDF（Chrome headless 打印）；失败返回 False，调用方回退 HTML（浏览器可原生打印成 PDF）"""
    import os
    import subprocess
    import tempfile
    try:
        chrome = os.environ.get("CHROME_PATH") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if not os.path.exists(chrome):
            chrome = "google-chrome"  # Linux 回退
        fd, html_path = tempfile.mkstemp(suffix=".html")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html_str)
        cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox", f"--print-to-pdf={path}", f"file://{html_path}"]
        subprocess.run(cmd, capture_output=True, timeout=120)
        os.unlink(html_path)
        return os.path.exists(path) and os.path.getsize(path) > 0
    except Exception as e:
        logger.warning(f"PDF 生成失败，回退 HTML: {e}")
        return False
