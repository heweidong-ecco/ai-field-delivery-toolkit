/* AI 项目现场交付工具包 · FDE 操作台 */
"use strict";

const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

/* ---------- 基础工具 ---------- */

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch (_) { /* 非 JSON */ }
  if (!res.ok) {
    let detail = data && (data.detail ?? data.message);
    // v10.0：后端门禁 403 detail 可能是 {message, gate_reason}，解包成可读字符串
    if (detail && typeof detail === "object") detail = detail.message || detail.gate_reason || JSON.stringify(detail);
    throw new Error(detail || `请求失败 (${res.status})`);
  }
  return data;
}

function showMsg(container, text, type = "info") {
  container.innerHTML = `<div class="alert ${type}">${text}</div>`;
}

function renderJSON(container, title, data) {
  container.innerHTML = `<div class="card"><h3>${title}</h3><pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre></div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function kvTable(obj, keys) {
  const rows = (keys || Object.keys(obj)).map(k => {
    const v = obj[k];
    return `<tr><th>${escapeHtml(k)}</th><td>${v === undefined || v === null ? "" : escapeHtml(JSON.stringify(v))}</td></tr>`;
  }).join("");
  return `<table class="kv">${rows}</table>`;
}

/* 横向 CSS 柱状图：{label: value} */
function barsChart(container, data, opts = {}) {
  const entries = Object.entries(data || {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) { container.innerHTML = `<p class="hint">暂无数据</p>`; return; }
  const max = Math.max(...entries.map(e => e[1]), 1e-9);
  const fmt = opts.fmt || (v => v);
  container.innerHTML = entries.map(([k, v]) => `
    <div class="bar-row">
      <span class="lbl">${escapeHtml(k)}</span>
      <span class="track"><span class="fill" style="width:${Math.round((v / max) * 100)}%"></span></span>
      <span class="val">${escapeHtml(fmt(v))}</span>
    </div>`).join("");
}

/* ---------- 标签页 ---------- */

$$(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => {
    $$(".nav-item").forEach(b => b.classList.remove("active"));
    $$(".tab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    $("#" + btn.dataset.tab).classList.add("active");
  });
});

/* 服务状态 */
$("#health-btn").addEventListener("click", async () => {
  try {
    const h = await api("/health");
    const mods = (h.modules || []).map(m => m.name).join(", ") || "（空）";
    $("#health-status").textContent = `服务正常 · 模块: ${mods}`;
  } catch (e) {
    $("#health-status").textContent = `服务异常: ${e.message}`;
  }
});

/* ---------- ① 需求诊断（多 Agent 对抗一期） ---------- */

let diagRunId = null;
let diagPrompt = "";
let diagLastStart = null;   // start 结果（填充复核面板用）
let diagClarifyAnswers = {}; // 澄清问题回答

async function loadDiagPrompt() {
  try {
    const r = await api("/api/v1/diagnosis/default-prompt");
    diagPrompt = r.prompt;
    $("#diag-prompt").value = r.prompt;
  } catch (_) { /* 后端未启动时忽略 */ }
}
loadDiagPrompt();

$("#diag-prompt-reset").addEventListener("click", () => {
  $("#diag-prompt").value = diagPrompt;
});

const DIAG_DIMS = ["generation", "reasoning", "uncertainty", "data", "real_time"];
const DIAG_NAMES = {
  generation: "生成性", reasoning: "推理复杂度", uncertainty: "不确定性容忍度",
  data: "数据可得性", real_time: "实时性要求",
};
const RV_SCORE = {
  generation: "rv_generation", reasoning: "rv_reasoning", uncertainty: "rv_uncertainty",
  data: "rv_data", real_time: "rv_real_time",
};

function confidenceBadge(c) {
  if (!c) return "";
  const map = { high: ["ok", "高置信"], medium: ["warning", "中置信"], low: ["critical", "低置信"] };
  const [cls, label] = map[c.level] || ["info", c.level];
  return `<span class="badge ${cls}">${label}（一致度 ${(c.overall * 100).toFixed(0)}%）</span>`;
}

function divTable(list) {
  if (!list || !list.length) return '<p class="hint">无分歧</p>';
  return `<table class="kv"><tr><th>维度</th><th>分歧来源</th><th>A</th><th>B</th><th>Δ</th></tr>` +
    list.map(d => `<tr><td>${DIAG_NAMES[d.dimension] || d.dimension}</td><td>${escapeHtml(d.source)}</td><td>${d.a}</td><td>${d.b}</td><td>${d.delta > 0 ? "+" : ""}${d.delta}</td></tr>`).join("") + `</table>`;
}

function scoreRows(scores, reasons) {
  return DIAG_DIMS.map(k => `<tr><td>${DIAG_NAMES[k]}</td><td>${scores && scores[k] != null ? scores[k] : "-"}</td><td>${escapeHtml((reasons && reasons[k]) || "")}</td></tr>`).join("");
}

const card = (title, inner) => `<div class="card"><h3>${title}</h3>${inner}</div>`;

/* ---------- 完整输出渲染（多 Agent 对抗过程全文，不只显示总结） ---------- */

function listHtml(items) {
  if (!items || !items.length) return '<p class="hint">（无）</p>';
  return `<ul>${items.map(i => `<li>${escapeHtml(typeof i === "object" ? JSON.stringify(i, null, 2) : i)}</li>`).join("")}</ul>`;
}

function objListHtml(items, keys) {
  if (!items || !items.length) return '<p class="hint">（无）</p>';
  return items.map(it => {
    if (typeof it !== "object" || it === null) return `<div class="card" style="margin-bottom:6px">${escapeHtml(it)}</div>`;
    const parts = (keys || []).map(([f, l]) => {
      const v = it[f];
      if (v === undefined || v === null || v === "") return "";
      const vs = Array.isArray(v) ? v.join("、") : String(v);
      return `<p><b>${escapeHtml(l)}：</b>${escapeHtml(vs)}</p>`;
    }).join("");
    return `<div class="card" style="margin-bottom:6px">${parts}</div>`;
  }).join("");
}

function dimAnalysisHtml(agent) {
  const da = (agent && agent.dimension_analysis) || {};
  const scores = (agent && agent.dimension_scores) || {};
  const reasons = (agent && agent.reasons) || {};
  return DIAG_DIMS.map(k => {
    const e = (da[k] && typeof da[k] === "object") ? da[k] : {};
    const score = e.score != null ? e.score : scores[k];
    const analysis = e.analysis || reasons[k] || "";
    const evidence = e.evidence || "";
    const implications = e.implications || "";
    return `<div class="card" style="margin-bottom:6px">
      <p><b>${DIAG_NAMES[k]} · ${score != null ? score + "/5" : "-"}</b></p>
      <p><b>完整论证：</b>${escapeHtml(analysis)}</p>
      ${evidence ? `<p class="hint">引用需求原文：${escapeHtml(evidence)}</p>` : ""}
      ${implications ? `<p class="hint">对客户影响：${escapeHtml(implications)}</p>` : ""}</div>`;
  }).join("") || '<p class="hint">（无）</p>';
}

function qText(q) {
  if (typeof q === "string") return q;
  if (q && typeof q === "object") return q.question || "";
  return "";
}

function fullGeneratorHtml(gen) {
  if (!gen) return "";
  const ru = gen.requirement_understanding || {};
  const scope = gen.scope || {};
  const qs = (gen.clarification_questions || []).map(q => typeof q === "string" ? { question: q, why: "" } : q);
  const qHtml = qs.map((q, i) =>
    `<p><b>问题${i + 1}：</b>${escapeHtml(q.question || "")}${q.why ? `<span class="hint">（为什么问：${escapeHtml(q.why)}）</span>` : ""}</p>`
  ).join("") || '<p class="hint">（无）</p>';
  const draftSecs = gen.draft_sections ? objListHtml(
    Object.entries(gen.draft_sections).map(([k, v]) => ({ title: k, content: v })),
    [["title", "章节"], ["content", "草稿内容"]]) : '<p class="hint">（无）</p>';
  return `
    ${card("需求理解与背景", `<p>${escapeHtml(ru.background || "")}</p>
      <b>痛点：</b>${listHtml(ru.pain_points)}
      <b>目标：</b>${listHtml(ru.goals)}
      <b>约束：</b>${listHtml(ru.constraints)}`)}
    ${card("范围（做什么/不做什么）", `<b>做什么：</b>${listHtml(scope.in_scope)}<b>不做什么：</b>${listHtml(scope.out_of_scope)}`)}
    ${card("功能需求条目", listHtml(gen.functional_requirements))}
    ${card("非功能需求", objListHtml(gen.non_functional_requirements, [["title", "类别"], ["detail", "要求"], ["standard", "验收口径"]]))}
    ${card("数据与资源要求",
      `<b>数据来源：</b>${listHtml((gen.data_requirements || {}).data_sources)}
       <p class="hint">数据量：${escapeHtml((gen.data_requirements || {}).data_volume || "—")} ｜ 数据质量：${escapeHtml((gen.data_requirements || {}).data_quality || "—")}</p>
       <p class="hint">安全合规：${escapeHtml((gen.data_requirements || {}).security_compliance || "—")}</p>
       <b>所需资源：</b>${listHtml((gen.data_requirements || {}).resources)}`)}
    ${card("风险（含缓解）", objListHtml(gen.risks, [["risk", "风险"], ["likelihood", "可能性"], ["impact", "影响"], ["mitigation", "缓解"]]))}
    ${card("假设", listHtml(gen.assumptions))}
    ${card("澄清问题", qHtml)}
    ${card("分阶段实施建议", objListHtml(gen.implementation_phases, [["phase", "阶段"], ["focus", "重点"], ["deliverables", "交付物"], ["risks", "风险"]]))}
    ${card("各章节草稿", draftSecs)}`;
}

function fullCriticHtml(crit) {
  if (!crit) return "";
  const risks = [...(crit.coverage_gaps || []).map(x => `未覆盖：${x}`),
                 ...(crit.inconsistencies || []).map(x => `矛盾：${x}`),
                 ...(crit.over_confidence_flags || []).map(x => `过度自信：${x}`)]
    .map(x => `<li>${escapeHtml(x)}</li>`).join("");
  return `
    ${card("独立逐维论证（盲审）", dimAnalysisHtml(crit))}
    ${card("覆盖审计（逐条对原文）", objListHtml(crit.coverage_audit, [["requirement_text", "需求原文"], ["covered", "已覆盖"], ["note", "说明"]]))}
    ${card("内部矛盾（引原文）", objListHtml(crit.contradictions, [["statement_a", "表述A"], ["statement_b", "表述B"], ["evidence", "原文"], ["explanation", "说明"]]))}
    ${card("过度自信审计", objListHtml(crit.over_confidence_audit, [["claim", "断言"], ["evidence_strength", "依据强度"], ["concern", "担忧"]]))}
    ${card("反方论证", objListHtml(crit.counter_arguments, [["target", "针对点"], ["argument", "论证"], ["basis", "依据"]]))}
    <p><b>风险提示：</b></p><ul>${risks || "<li>（无）</li>"}</ul>`;
}

function fullReviewerHtml(rev) {
  if (!rev) return "";
  const vd = DIAG_DIMS.map(k => {
    const v = (rev.verdicts || {})[k] || {};
    const tag = v.verdict === "agree" ? '<span class="badge ok">同意</span>' : `<span class="badge del">修正→${v.adjusted_score}</span>`;
    return `<div class="card" style="margin-bottom:6px"><p><b>${DIAG_NAMES[k]}</b> ${tag}</p>
      <p class="hint">${escapeHtml(v.full_analysis || v.reason || "")}</p>
      ${v.counter_to_human ? `<p class="hint">对人工的反方论证：${escapeHtml(v.counter_to_human)}</p>` : ""}</div>`;
  }).join("");
  const ba = rev.bias_analysis || {};
  return `
    ${card("逐维完整评审", vd)}
    ${card("偏置分析",
      `<p>${ba.detected ? `<span class="badge del">检出偏置（${escapeHtml(ba.direction || "")}）</span>` : '<span class="badge ok">未检出明显偏置</span>'}</p>
       <p class="hint">${escapeHtml(ba.detail || "")}</p>
       ${ba.evidence ? `<p class="hint">证据：${escapeHtml(ba.evidence)}</p>` : ""}`)}
    ${card("需再确认清单", objListHtml(rev.need_reconfirm, [["item", "再确认项"], ["reason", "原因"]]))}`;
}

function deliverableHtml(r) {
  const d = r.deliverable || {};
  if (!d.html_url) return "";
  return `<div class="card" style="border:2px solid #2563eb">
    <h3>正式报告已生成（多章节需求文档）</h3>
    <p><a class="badge" href="${d.html_url}" target="_blank" style="font-size:14px;padding:6px 16px">打开报告（HTML）</a>
    ${d.pdf_url ? `<a class="badge" href="${d.pdf_url}" target="_blank" style="font-size:14px;padding:6px 16px">打开报告（PDF）</a>` : `<span class="badge del">PDF 不可用（需 Chrome 浏览器打印）</span>`}</p>
    <p class="hint">保存路径：<code>${escapeHtml(d.path || "")}</code></p>
  </div>`;
}

// 用 Generator 分数/理由填充人工复核面板（供人工调整），并生成澄清问题输入
function fillReviewPanel(gen) {
  DIAG_DIMS.forEach(k => {
    $("[name=" + RV_SCORE[k] + "]").value = (gen.dimension_scores && gen.dimension_scores[k]) || 3;
    $("[name=rv_reason_" + k + "]").value = (gen.reasons && gen.reasons[k]) || "";
  });
  const qs = gen.clarification_questions || [];
  $("#diag-clarify").innerHTML = qs.map((q, i) => {
    const text = qText(q);
    return `<label style="grid-column:1/-1">澄清问题 ${i + 1}（可选回答）<textarea name="clarify_${i}" rows="2" placeholder="${escapeHtml(text)}"></textarea></label>`;
  }).join("");
}

// ---- Step 1：开始诊断（Generator + Critic 对抗） ----
$("#diag-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const requirement = f.requirement.value.trim();
  const promptTemplate = f.prompt.value.trim();
  const out = $("#diag-result");
  if (!requirement) { showMsg(out, "请先填写客户需求描述", "warning"); return; }
  showMsg(out, "多 Agent 对抗诊断中（Generator + Critic 独立打分，需数秒）…");
  try {
    const r = await api("/api/v1/diagnosis/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ requirement, prompt_template: promptTemplate || null }),
    });
    diagRunId = r.run_id;
    diagLastStart = r;
    diagClarifyAnswers = {};

    out.innerHTML = startResultHtml(r);
    fillReviewPanel(r.generator);
    bindAdoptButtons(out, { customer: "", assets: r.related_assets || [], autoTarget: true });
    $("#diag-review").classList.remove("hidden");
    out.insertAdjacentHTML("afterbegin", `<div class="alert info">对抗评审完成，结果如下。请进行人工复核打分。</div>`);
  } catch (e) { showMsg(out, e.message, "critical"); }
});

function startResultHtml(r) {
  const gen = r.generator || {}, crit = r.critic || {}, conf = r.confidence || {};
  return `
    ${card(`对抗评审完成 ${confidenceBadge(conf)}`, `<p>Generator 与 Critic 独立打分后对比得出一致度；低置信维度（<code>${(conf.needs_confirm || []).join("、") || "无"}</code>）须人工确认。</p>
      <p class="hint">完整对抗推理过程（需求理解/深度论证/覆盖审计/反方论证）如下，非仅总结。</p>`)}
    ${card(`Generator 完整输出 · ${escapeHtml(gen.summary || "")}`,
      `<table class="kv"><tr><th>维度</th><th>分</th><th>理由</th></tr>${scoreRows(gen.dimension_scores, gen.reasons)}</table>
       ${fullGeneratorHtml(gen)}`)}
    ${card("Critic 盲审（完整独立评审）", fullCriticHtml(crit))}
    ${card("Generator vs Critic 分歧", divTable(r.divergences))}
    ${r.related_cases && r.related_cases.length ? card("相关历史案例（自动带出）", r.related_cases.map(c => `<a class="badge" href="/api/v1/cases/${escapeHtml(c.case_id)}/render.html" target="_blank">${escapeHtml(c.title)}</a>`).join(" ")) : ""}
    ${r.related_assets && r.related_assets.length ? relatedAssetsHtml(r.related_assets) : ""}`;
}

// ---- 历史诊断 / 继续执行 ----
$("#diag-history-btn").addEventListener("click", async () => {
  const out = $("#diag-history-result");
  try {
    const r = await api("/api/v1/diagnosis/runs");
    const rows = (r.runs || []).map(x => `
      <tr>
        <td><input class="diag-name" data-run="${escapeHtml(x.run_id)}" value="${escapeHtml(x.name)}" style="width:100%"></td>
        <td>${escapeHtml(x.requirement)}</td>
        <td>${x.version || "-"}${x.confirmed ? ' <span class="badge ok">已确认</span>' : ' <span class="badge del">未定稿</span>'}</td>
        <td>
          <button class="ghost diag-continue" data-run="${escapeHtml(x.run_id)}">继续执行</button>
          <button class="ghost diag-rename" data-run="${escapeHtml(x.run_id)}">重命名</button>
          <a class="badge" href="#" data-diag-view="${escapeHtml(x.run_id)}">查看档案</a>
        </td>
      </tr>`).join("");
    out.innerHTML = `<table class="kv"><tr><th>名字（可改，人工命名）</th><th>需求</th><th>版本/状态</th><th>操作</th></tr>${rows || "<tr><td colspan=4>暂无历史诊断</td></tr>"}</table>`;
    $$(".diag-continue", out).forEach(b => b.addEventListener("click", () => resumeDiagnosis(b.dataset.run)));
    $$(".diag-rename", out).forEach(b => b.addEventListener("click", async () => {
      const input = out.querySelector(`.diag-name[data-run="${b.dataset.run}"]`);
      const nm = (input && input.value.trim()) || "";
      if (!nm) { showMsg(out, "请先输入名字再点重命名", "warning"); return; }
      try {
        await api(`/api/v1/diagnosis/${b.dataset.run}/rename`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: nm }),
        });
        showMsg(out, `已重命名为「${escapeHtml(nm)}」`, "info");
      } catch (e) { showMsg(out, e.message, "critical"); }
    }));
    $$("[data-diag-view]", out).forEach(a => a.addEventListener("click", async (ev) => {
      ev.preventDefault();
      try {
        const arch = await api("/api/v1/diagnosis/archive/" + a.dataset.diagView);
        out.innerHTML += `<pre>${escapeHtml(JSON.stringify(arch, null, 2))}</pre>`;
      } catch (e) { showMsg(out, e.message, "critical"); }
    }));
  } catch (e) { showMsg(out, e.message, "critical"); }
});

// 恢复历史诊断：加载执行状态，从当前进度继续
async function resumeDiagnosis(runId) {
  const out = $("#diag-result");
  try {
    const st = await api("/api/v1/diagnosis/" + runId + "/state");
    diagRunId = st.run_id;
    diagLastStart = { generator: st.generator || {}, critic: st.critic || {}, confidence: st.confidence || {}, divergences: st.divergences || [] };
    out.innerHTML = startResultHtml(diagLastStart);
    fillReviewPanel(st.generator || {});
    // 若已有历史人工分，用历史分恢复（否则用 Generator 基线）
    if (st.human_review && st.human_review.scores) {
      DIAG_DIMS.forEach(k => { $("[name=" + RV_SCORE[k] + "]").value = st.human_review.scores[k] ?? 3; });
    }
    if (st.reviewer && (st.reviewer.summary || st.reviewer.verdicts)) {
      out.insertAdjacentHTML("beforeend",
        `<div class="card"><h3>已完成的 Reviewer 评审（完整过程）</h3>${fullReviewerHtml(st.reviewer)}</div>`);
    }
    if (st.deliverable && st.deliverable.html_url) {
      out.insertAdjacentHTML("beforeend", `<div class="card" style="border:2px solid #2563eb">
        <h3>正式报告（已定稿）</h3>
        <p><a class="badge" href="${st.deliverable.html_url}" target="_blank" style="font-size:14px;padding:6px 16px">打开报告（HTML）</a>
        ${st.deliverable.pdf_url ? `<a class="badge" href="${st.deliverable.pdf_url}" target="_blank" style="font-size:14px;padding:6px 16px">打开报告（PDF）</a>` : ""}</p>
        <p class="hint">保存路径：<code>${escapeHtml(st.deliverable.path || "")}</code></p>
      </div>`);
    }
    $("#diag-review").classList.remove("hidden");
    $("#diag-finalize-form").classList.remove("hidden");
    out.insertAdjacentHTML("afterbegin",
      `<div class="alert info">已恢复历史诊断「${escapeHtml(st.name || runId)}」${st.version ? `（当前 ${st.version}）` : ""}，从当前进度继续。</div>`);
  } catch (e) { showMsg(out, e.message, "critical"); }
}

// ---- Step 2：人工打分 + Reviewer 再评分 ----
$("#diag-review-submit").addEventListener("click", async () => {
  const out = $("#diag-review-result");
  if (!diagRunId) { showMsg(out, "请先完成「开始诊断」", "warning"); return; }
  const scores = {}, reasons = {};
  DIAG_DIMS.forEach(k => {
    scores[k] = +$("[name=" + RV_SCORE[k] + "]").value;
    reasons[k] = $("[name=rv_reason_" + k + "]").value.trim()
      || ((diagLastStart.generator.reasons && diagLastStart.generator.reasons[k]) || "");
  });
  // 澄清回答
  const clarify = {};
  (diagLastStart.generator.clarification_questions || []).forEach((q, i) => {
    const v = $("[name=clarify_" + i + "]").value.trim();
    if (v) clarify[qText(q)] = v;
  });

  showMsg(out, "Reviewer 盲审人工打分中…");
  try {
    const r = await api("/api/v1/diagnosis/review", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        run_id: diagRunId, human_scores: scores, human_reasons: reasons,
        human_summary: $("[name=rv_summary]").value.trim() || null,
        clarify_answers: Object.keys(clarify).length ? clarify : null,
      }),
    });
    const rev = r.reviewer || {};
    const verdicts = (rev.verdicts || {});
    const vd = DIAG_DIMS.map(k => {
      const v = verdicts[k] || {};
      const tag = v.verdict === "agree" ? `<span class="badge ok">同意</span>` : `<span class="badge del">修正→${v.adjusted_score}</span>`;
      return `<tr><td>${DIAG_NAMES[k]}</td><td>${scores[k]}</td><td>${tag}</td><td>${escapeHtml(v.reason || "")}</td></tr>`;
    }).join("");
    const bias = rev.bias || {};
    const biasHtml = bias.detected
      ? `<span class="badge del">检测到偏置（${escapeHtml(bias.direction || "")}）</span> ${escapeHtml(bias.detail || "")}`
      : `<span class="badge ok">未检测到明显偏置</span>`;

    out.innerHTML = `
      ${card("Reviewer 盲审人工打分", `<table class="kv"><tr><th>维度</th><th>人工分</th><th>AI 评审</th><th>理由</th></tr>${vd}</table>
        <p>${biasHtml}</p><p class="hint">${escapeHtml(rev.summary || "")}</p>`)}
      ${card("当前全部分歧（Reviewer vs 人工 / Generator vs 人工）", divTable(r.divergences))}`;
    $("#diag-finalize-form").classList.remove("hidden");
    showMsg(out, "人工复核完成。可继续调整打分再提交，或进入确认定稿。", "info");
  } catch (e) { showMsg(out, e.message, "critical"); }
});

// ---- Step 3：确认定稿 ----
$("#diag-finalize-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#diag-finalize-result");
  if (!diagRunId) { showMsg(out, "请先完成前两步", "warning"); return; }
  if (!f.confirmed.checked) { showMsg(out, "请勾选「我已人工确认」后再生成正式报告", "warning"); return; }
  try {
    const r = await api("/api/v1/diagnosis/finalize", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        run_id: diagRunId,
        customer_name: f.customer_name.value,
        requirement_summary: f.requirement_summary.value,
        interview_notes: f.interview_notes.value,
        decision_maker: f.decision_maker.value,
        confirmed: true,
      }),
    });
    out.innerHTML = renderFinalReport(r);
    if (r.project_id) {
      out.innerHTML += `<p class="hint">已自动挂项目档案：<button class="ghost" data-goto-project="${escapeHtml(r.project_id)}">查看项目</button></p>`;
    }
    $$("[data-goto-project]", out).forEach(b => b.addEventListener("click", () => gotoProject(b.dataset.gotoProject)));
    $("#diag-version-panel").classList.remove("hidden");
  } catch (e) { showMsg(out, e.message, "critical"); }
});

// ---- 二期：客户反馈 → 下一版 ----
$("#diag-feedback-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#diag-feedback-result");
  if (!diagRunId) { showMsg(out, "请先完成一次诊断定稿", "warning"); return; }
  const fd = new FormData();
  fd.append("run_id", diagRunId);
  const file = f.file.files[0];
  const txt = f.text.value.trim();
  if (file) fd.append("file", file);
  if (!file && !txt) { showMsg(out, "请上传文件或粘贴反馈文本", "warning"); return; }
  if (txt) fd.append("feedback_text", txt);
  showMsg(out, "提炼客户意见中…");
  try {
    const r = await api("/api/v1/diagnosis/feedback", { method: "POST", body: fd });
    const items = (r.items || []).map(x =>
      `<div class="card" style="margin-bottom:6px">${escapeHtml(x.item)}
        <span class="badge">${escapeHtml(x.dimension || "未映射")}</span>
        <span class="badge">${escapeHtml(x.intent || "")}</span></div>`).join("");
    out.innerHTML = `
      <div class="card"><h3>客户意见条目（${(r.items || []).length}）</h3>${items}
      <p class="hint">触达维度：${escapeHtml((r.touched_dimensions || []).join("、") || "无")} ｜ 倾向：${escapeHtml(r.summary || "")}</p></div>`;
    $("#diag-next-version").classList.remove("hidden");
  } catch (e) { showMsg(out, e.message, "critical"); }
});

$("#diag-next-version").addEventListener("click", async () => {
  const out = $("#diag-next-result");
  if (!diagRunId) return;
  showMsg(out, "增量重评中（Generator + Critic 只重评触达维度）…");
  try {
    const r = await api("/api/v1/diagnosis/next-version", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: diagRunId, mode: "incremental" }),
    });
    const gen = r.generator || {}, crit = r.critic || {}, conf = r.confidence || {};
    const chg = (r.changelog || []).map(c =>
      `<tr><td>${DIAG_NAMES[c.dimension] || c.dimension}</td><td>${escapeHtml(c.role)}</td><td>${c.prev}</td><td>${c.curr}</td></tr>`).join("");
    out.innerHTML = `
      ${card(`${r.version} 增量重评草稿 ${confidenceBadge(conf)}`, `<p>触达维度：${escapeHtml((r.touched_dimensions || []).join("、") || "无")}（仅这些维度重评，其余沿用上一版）</p>`)}
      ${card("相对上一版变更清单", chg ? `<table class="kv"><tr><th>维度</th><th>角色</th><th>上一版</th><th>新版</th></tr>${chg}</table>` : '<p class="hint">无变化</p>')}
      ${card(`Generator（${r.version}）完整输出`,
        `<table class="kv"><tr><th>维度</th><th>分</th><th>理由</th></tr>${scoreRows(gen.dimension_scores, gen.reasons)}</table>${fullGeneratorHtml(gen)}`)}
      ${card(`Critic 盲审（${r.version}）完整独立评审`, fullCriticHtml(crit))}
      ${card("分歧", divTable(r.divergences))}`;
    fillReviewPanel(gen);
    $("#diag-review").classList.remove("hidden");
    $("#diag-finalize-form").classList.remove("hidden");
  } catch (e) { showMsg(out, e.message, "critical"); }
});

// ---- 二期：档案检索 ----
$("#diag-runs-btn").addEventListener("click", async () => {
  const out = $("#diag-runs-result");
  try {
    const r = await api("/api/v1/diagnosis/runs");
    const rows = (r.runs || []).map(x =>
      `<tr><td><code>${escapeHtml(x.run_id)}</code></td><td>${escapeHtml(x.requirement)}</td><td>${x.versions}</td><td>${x.confirmed ? "已确认" : "未确认"}</td>
       <td><button class="ghost" data-run="${escapeHtml(x.run_id)}">查看档案</button></td></tr>`).join("");
    out.innerHTML = `<div class="card"><h3>最近诊断</h3><table class="kv"><tr><th>run_id</th><th>需求</th><th>版本数</th><th>状态</th><th></th></tr>${rows || "<tr><td colspan=5>暂无</td></tr>"}</table></div>`;
    $$("[data-run]", out).forEach(btn => btn.addEventListener("click", async () => {
      try {
        const a = await api("/api/v1/diagnosis/archive/" + btn.dataset.run);
        out.innerHTML += `<div class="card"><h3>档案 ${escapeHtml(btn.dataset.run)}</h3><pre>${escapeHtml(JSON.stringify(a, null, 2))}</pre></div>`;
      } catch (e) { showMsg(out, e.message, "critical"); }
    }));
  } catch (e) { showMsg(out, e.message, "critical"); }
});

// ---- 一期：案例/交付物（可打印 / 发客户） ----
$("#diag-case-create").addEventListener("click", async () => {
  const out = $("#diag-case-result");
  if (!diagRunId) { showMsg(out, "请先完成一次诊断定稿", "warning"); return; }
  showMsg(out, "生成可打印交付物中…");
  try {
    const r = await api("/api/v1/cases/create", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_type: "diagnosis", run_id: diagRunId }),
    });
    out.innerHTML = `<div class="card"><h3>交付物已生成</h3>
      <p><a class="badge" href="${r.urls.html}" target="_blank">打开 HTML（可打印/发送）</a>
      ${r.urls.pdf ? `<a class="badge" href="${r.urls.pdf}" target="_blank">下载 PDF</a>` : '<span class="badge del">PDF 不可用（需 Chrome）</span>'}</p>
      <p class="hint">${escapeHtml(r.title)} ｜ 结论：${escapeHtml(r.conclusion)}</p>
      ${r.project_id ? `<p class="hint">已自动挂项目档案：<button class="ghost" data-goto-project="${escapeHtml(r.project_id)}">查看项目</button></p>` : ""}</div>`;
    $$("[data-goto-project]", out).forEach(b => b.addEventListener("click", () => gotoProject(b.dataset.gotoProject)));
  } catch (e) { showMsg(out, e.message, "critical"); }
});

$("#case-search-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#diag-case-result");
  try {
    const r = await api(`/api/v1/cases/search?q=${encodeURIComponent(f.q.value)}&tags=${encodeURIComponent(f.tags.value)}`);
    const rows = (r.cases || []).map(c =>
      `<tr><td>${escapeHtml(c.title)}</td><td>${escapeHtml(c.conclusion)}</td><td>${escapeHtml((c.tags || []).join("、"))}</td>
       <td><a class="badge" href="/api/v1/cases/${escapeHtml(c.case_id)}/render.html" target="_blank">HTML</a>
       ${c.has_pdf ? `<a class="badge" href="/api/v1/cases/${escapeHtml(c.case_id)}/export.pdf" target="_blank">PDF</a>` : ""}</td></tr>`).join("");
    out.innerHTML = `<div class="card"><h3>案例检索结果（${(r.cases || []).length}）</h3><table class="kv"><tr><th>标题</th><th>结论</th><th>标签</th><th>交付物</th></tr>${rows || "<tr><td colspan=4>无匹配</td></tr>"}</table></div>`;
  } catch (e) { showMsg(out, e.message, "critical"); }
});

$("#diag-case-list").addEventListener("click", async () => {
  const out = $("#diag-case-result");
  try {
    const r = await api("/api/v1/cases");
    const rows = (r.cases || []).map(c =>
      `<tr><td>${escapeHtml(c.title)}</td><td>${escapeHtml(c.conclusion)}</td><td>${escapeHtml(c.version || "")}</td>
       <td><a class="badge" href="/api/v1/cases/${escapeHtml(c.case_id)}/render.html" target="_blank">HTML</a>
       ${c.has_pdf ? `<a class="badge" href="/api/v1/cases/${escapeHtml(c.case_id)}/export.pdf" target="_blank">PDF</a>` : ""}</td></tr>`).join("");
    out.innerHTML = `<div class="card"><h3>案例库</h3><table class="kv"><tr><th>标题</th><th>结论</th><th>版本</th><th>交付物</th></tr>${rows || "<tr><td colspan=4>暂无</td></tr>"}</table></div>`;
  } catch (e) { showMsg(out, e.message, "critical"); }
});

function renderFinalReport(r) {
  const gen = r.generator || {}, crit = r.critic || {}, hr = r.human_review || {};
  const rev = r.reviewer || {}, conf = r.confidence || {}, fc = r.final_conclusion || {};
  const recs = (r.recommendations || []).map(x => `<li>${escapeHtml(x)}</li>`).join("");
  const needConfirm = r.needs_confirmation
    ? `<span class="badge del">需确认项存在</span>` : `<span class="badge ok">已确认</span>`;

  return `
    ${deliverableHtml(r)}
    ${card(`正式报告 · ${escapeHtml(r.customer_name)} ${needConfirm}`, `
      <p><b>需求摘要：</b>${escapeHtml(r.requirement_summary)}<br>
      <span class="hint">访谈：${escapeHtml(r.interview_notes || "—")} ｜ 验收人：${escapeHtml(r.decision_maker || "—")} ｜ 提示词已修改：${r.prompt_modified ? "是" : "否"} ｜ run_id：<code>${escapeHtml(r.run_id || "")}</code></span></p>
      <p>${confidenceBadge(conf)} ${conf.needs_confirm && conf.needs_confirm.length ? `<span class="badge del">低置信需确认：${escapeHtml(conf.needs_confirm.join("、"))}</span>` : ""}</p>`)}
    ${card("Generator 完整输出（需求文档草稿）",
      `<table class="kv"><tr><th>维度</th><th>分</th><th>理由</th></tr>${scoreRows(gen.dimension_scores, gen.reasons)}</table>
      <p class="hint">总结：${escapeHtml(gen.summary || "—")}</p>${fullGeneratorHtml(gen)}`)}
    ${card("Critic 盲审（完整独立评审）", fullCriticHtml(crit))}
    ${card("人工复核", `<table class="kv"><tr><th>维度</th><th>分</th><th>人工理由</th></tr>${scoreRows(hr.scores, hr.reasons)}</table>
      <p class="hint">人工意见：${escapeHtml(hr.summary || "—")}</p>`)}
    ${card("Reviewer 完整评审（评人工）", fullReviewerHtml(rev))}
    ${card("分歧记录（过程信息）", divTable(r.divergences))}
    ${card(`最终结论 · ${escapeHtml(fc.conclusion || "")}（${fc.total_score != null ? fc.total_score + "/25" : "-"}）`, `
      <p class="hint">${escapeHtml(fc.basis || "")}</p>
      <ol>${recs || "<li>无建议</li>"}</ol>`)}
  `;
}

/* ---------- ② 五步裁剪 ---------- */

$("#crop-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const bool = v => v === "true";
  const body = {
    customer_id: f.customer_id.value,
    budget: +f.budget.value,
    timeline_weeks: +f.timeline_weeks.value,
    hardware: {
      cpu: f.hardware_cpu.value,
      memory_gb: +f.hardware_memory.value,
      gpu: f.hardware_gpu.value.trim() || null,
      storage_gb: +f.hardware_storage.value,
    },
    environment: {
      os: f.env_os.value,
      docker: bool(f.env_docker.value),
      network: f.env_network.value,
      external_access: bool(f.env_external.value),
      network_bandwidth_mbps: +f.env_bandwidth.value,
    },
    data: {
      total_records: +f.data_records.value,
      daily_new: +f.data_daily.value,
      formats: f.data_formats.value.split(",").map(s => s.trim()).filter(Boolean),
      quality: f.data_quality.value,
    },
    users: { total_users: +f.users_total.value, concurrent_peak: +f.users_peak.value },
    compliance: {
      data_residency: f.comp_residency.value,
      pii_sensitive: bool(f.comp_pii.value),
      compliance_level: f.comp_level.value,
    },
  };
  const out = $("#crop-result");
  try {
    const p = await api("/api/v1/cropper/plan", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const badges = arr => arr.map(m => `<span class="badge">${escapeHtml(m)}</span>`).join(" ");
    out.innerHTML = `
      <div class="card">
        <h3>裁剪方案 · ${escapeHtml(p.customer_id)}（${p.plan_version}）</h3>
        <p><b>启用模块：</b><br>${badges(p.enabled_modules || [])}</p>
        <p><b>删除模块：</b><br>${(p.deleted_modules || []).map(m => `<span class="badge del">${escapeHtml(m)}</span>`).join(" ") || "（无）"}</p>
        <p><b>简化配置：</b><br><pre>${escapeHtml(JSON.stringify(p.simplifications, null, 2))}</pre></p>
        <p><b>排期建议：</b>${escapeHtml(JSON.stringify(p.timeline_suggestion))}</p>
        <p><b>自动化建议：</b><br>${(p.automations || []).map(m => `<span class="badge ok">${escapeHtml(m)}</span>`).join(" ") || "（无）"}</p>
        <button id="crop-case-btn" type="button" class="ghost" style="margin-top:8px">把该方案生成交付物</button>
        <div id="crop-case-result"></div>
      </div>`;
    $("#crop-case-btn").addEventListener("click", async () => {
      const o = $("#crop-case-result");
      try {
        const r = await api("/api/v1/cases/create-crop", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plan: p }),
        });
        o.innerHTML = `<p class="hint">裁剪交付物已生成：<a class="badge" href="${r.urls.html}" target="_blank">HTML</a>${r.urls.pdf ? ` <a class="badge" href="${r.urls.pdf}" target="_blank">PDF</a>` : ""}</p>`;
      } catch (e) { showMsg(o, e.message, "critical"); }
    });
  } catch (e) { showMsg(out, e.message, "critical"); }
});

/* ---------- ③ 数据准备 ---------- */

/* 数据作战流 · 项目级数据准备流水线（可断点续接 · 产物沉淀复用） */

const DATAFLOW_STEP_NAMES = {
  import: "导入数据", clean: "清洗", quality: "质量报告",
  annotate: "标注", eval_set: "评测集", knowledge_base: "知识库",
};
const DATAFLOW_PRODUCT_KEYS = {
  import: "raw_data", clean: "cleaned_data", quality: "quality_report",
  annotate: "annotation_eval_set", eval_set: "eval_set", knowledge_base: "chunks",
};

$("#dataprep-flow-create").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const file = f.file.files[0];
  const out = $("#dataprep-flow-detail");
  if (!file) { showMsg(out, "请选择 csv/json 真实数据文件", "warning"); return; }
  const fd = new FormData();
  fd.append("name", f.name.value.trim());
  fd.append("customer", f.customer.value.trim());
  fd.append("project_id", f.project_id.value.trim());
  fd.append("file", file);
  showMsg(out, "上传并自动跑 导入/清洗/质量 前三步（语义去重可能耗时）…");
  try {
    const st = await api("/api/v1/dataprep/create", { method: "POST", body: fd });
    renderDataFlowDetail(st);
    // v6.0：自动带出相关数据资产（一键接入 = 复制到当前 run 的 products 继续用）
    const relBox = $("#dataprep-related-assets");
    if (st.related_assets && st.related_assets.length) {
      relBox.innerHTML = relatedAssetsHtml(st.related_assets);
      bindAdoptButtons(relBox, {
        customer: f.customer.value.trim(),
        target_run_id: st.run_id,
        assets: st.related_assets,
        autoTarget: true,
        onAdopted: () => resumeDataFlow(st.run_id),
      });
    } else {
      relBox.innerHTML = "";
    }
    await listDataFlow();
  } catch (e) { showMsg(out, e.message, "critical"); }
});

$("#dataprep-flow-list").addEventListener("click", listDataFlow);

async function listDataFlow() {
  const out = $("#dataprep-flow-list-result");
  try {
    const r = await api("/api/v1/dataprep/runs");
    const rows = (r.runs || []).map(x => `
      <tr>
        <td>${escapeHtml(x.name)}</td>
        <td>${escapeHtml(x.source)}</td>
        <td>${escapeHtml(x.status)} <span class="badge">${x.progress}/${x.progress_total}</span></td>
        <td>
          <button class="ghost df-continue" data-run="${escapeHtml(x.run_id)}">查看/继续</button>
          <button class="ghost df-rename" data-run="${escapeHtml(x.run_id)}">重命名</button>
        </td>
      </tr>`).join("");
    out.innerHTML = `<table class="kv"><tr><th>任务名</th><th>数据源</th><th>状态/进度</th><th>操作</th></tr>${rows || "<tr><td colspan=4>暂无任务</td></tr>"}</table>`;
    $$(".df-continue", out).forEach(b => b.addEventListener("click", () => resumeDataFlow(b.dataset.run)));
    $$(".df-rename", out).forEach(b => b.addEventListener("click", async () => {
      const cur = (r.runs || []).find(x => x.run_id === b.dataset.run);
      const nm = prompt("人工命名：", (cur && cur.name) || "");
      if (!nm || !nm.trim()) return;
      try {
        await api(`/api/v1/dataprep/${b.dataset.run}/rename`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: nm.trim() }),
        });
        showMsg($("#dataprep-flow-list-result"), `已重命名为「${escapeHtml(nm.trim())}」`, "info");
        await listDataFlow();
        await resumeDataFlow(b.dataset.run);
      } catch (e) { showMsg($("#dataprep-flow-list-result"), e.message, "critical"); }
    }));
  } catch (e) { showMsg(out, e.message, "critical"); }
}

async function resumeDataFlow(runId) {
  const out = $("#dataprep-flow-detail");
  try {
    const st = await api("/api/v1/dataprep/" + runId);
    renderDataFlowDetail(st);
  } catch (e) { showMsg(out, e.message, "critical"); }
}

function renderDataFlowDetail(st) {
  const out = $("#dataprep-flow-detail");
  const done = (st.done_steps || []);
  const stepsHtml = (st.steps || []).map(s => {
    const prod = st.products[DATAFLOW_PRODUCT_KEYS[s.step]] || null;
    let p = (prod && prod.exists)
      ? `<a class="badge" href="${escapeHtml(prod.url)}" target="_blank">下载 ${escapeHtml(prod.filename)}</a>` : "";
    if (s.step === "annotate") {
      // 诚实标注：数据作战流「标注」步骤是规则自动打标（流水线便利）；人工精标走下方「人工标注工作台」
      p += ` <span class="badge">规则自动打标</span>`;
      if (prod && prod.exists) {
        p += ` <button class="ghost ann-fine" data-run="${escapeHtml(st.run_id)}">去人工标注工作台精标</button>`;
      }
    }
    const kbRag = (s.step === "knowledge_base" && s.indexed)
      ? `<span class="badge ok">已索引 · RAG 就绪（${escapeHtml(s.collection || "")}）</span>` : "";
    return `<tr><td>${DATAFLOW_STEP_NAMES[s.step] || s.step}</td><td><span class="badge ok">${escapeHtml(s.status)}</span></td><td>${escapeHtml((s.at || "").slice(0, 19).replace("T", " "))}</td><td>${p} ${kbRag}</td></tr>`;
  }).join("");
  const notDone = ["annotate", "eval_set", "knowledge_base"].filter(s => !done.includes(s));
  const stepBtns = notDone.map(s => `<button class="ghost df-step" data-step="${s}">${DATAFLOW_STEP_NAMES[s]}</button>`).join("");
  const nextBtn = st.next_step
    ? `<button class="ghost df-next" type="button">顺序推进下一步（${DATAFLOW_STEP_NAMES[st.next_step] || st.next_step}）</button>` : "";
  const depositBtn = (st.deposited_assets || []).length < 4
    ? `<button id="df-deposit" type="button" class="primary">沉淀可复用资产</button>` : "";
  const deposited = (st.deposited_assets || []).map(a =>
    `${escapeHtml(a.asset_type)} <a class="badge" href="${escapeHtml(a.payload_url)}" target="_blank">asset.json</a>`).join(" ") || "（未沉淀）";
  out.innerHTML = `
    <div class="card">
      <h3>数据作战流 · ${escapeHtml(st.name)} <code>${escapeHtml(st.run_id)}</code> <span class="badge">${escapeHtml(st.status)}</span> 进度 ${st.progress}/${st.progress_total}</h3>
      <p class="hint">数据源：${escapeHtml(st.source)} ｜ 客户：${escapeHtml(st.customer || "—")} ｜ 项目：<code>${escapeHtml(st.project_id || "—")}</code></p>
      <table class="kv"><tr><th>步骤</th><th>状态</th><th>完成时间</th><th>产物</th></tr>${stepsHtml || "<tr><td colspan=4>尚无步骤</td></tr>"}</table>
      <p style="margin-top:8px"><b>继续：</b>${stepBtns} ${nextBtn} ${depositBtn || (done.length >= 6 ? '<span class="badge ok">全部完成</span>' : "")}</p>
      <p><b>已沉淀资产：</b>${deposited}</p>
      ${st.next_step ? `<p class="hint">下一步待执行：${DATAFLOW_STEP_NAMES[st.next_step] || st.next_step}</p>` : ""}
    </div>`;
  $$(".df-step", out).forEach(b => b.addEventListener("click", () => continueDataFlow(st.run_id, b.dataset.step, {})));
  $$(".df-next", out).forEach(b => b.addEventListener("click", () => continueDataFlow(st.run_id, null, { run_next: true })));
  $$(".ann-fine", out).forEach(b => b.addEventListener("click", () => openAnnWorkbenchFromDataprep(b.dataset.run)));
  const dp = $("#df-deposit");
  if (dp) dp.addEventListener("click", () => depositDataFlow(st.run_id));
}

async function continueDataFlow(runId, step, extra) {
  const out = $("#dataprep-flow-detail");
  const label = step ? (DATAFLOW_STEP_NAMES[step] || step) : "下一步";
  showMsg(out, `执行 ${label}…`);
  try {
    const body = Object.assign({ step: step || null, num_samples: 100, sample_size: 20, chunk_size: 500, overlap: 50 }, extra || {});
    const st = await api(`/api/v1/dataprep/${runId}/step`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    renderDataFlowDetail(st);
    await listDataFlow();
  } catch (e) { showMsg(out, e.message, "critical"); }
}

async function depositDataFlow(runId) {
  const out = $("#dataprep-flow-detail");
  showMsg(out, "沉淀可复用资产中…");
  try {
    const r = await api(`/api/v1/dataprep/${runId}/deposit`, { method: "POST" });
    out.insertAdjacentHTML("beforeend", `<div class="alert ok">已沉淀 ${r.count} 项可复用资产：${(r.deposited || []).map(a => escapeHtml(a.asset_type)).join("、")}。可在「案例检索」中搜到。</div>`);
    await resumeDataFlow(runId);
  } catch (e) { showMsg(out, e.message, "critical"); }
}

/* 接线：诊断 → 裁剪 */
$("#crop-from-diag-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#crop-from-diag-result");
  const run_id = f.run_id.value.trim() || diagRunId;
  if (!run_id) { showMsg(out, "请先完成一次诊断，或填写 run_id", "warning"); return; }
  try {
    const r = await api("/api/v1/cropper/from-diagnosis/" + run_id);
    const dc = r.diagnosis_context || {};
    const plan = r.plan || {};
    out.innerHTML = `<div class="card"><h3>诊断 → 裁剪接线</h3>
      <p><span class="badge">诊断总分 ${dc.total_score}</span> <span class="badge">${escapeHtml(dc.conclusion)}</span> ${dc.needs_confirmation ? '<span class="badge del">需确认</span>' : ""}</p>
      <p class="hint">已按诊断结论预填预算：${escapeHtml(JSON.stringify(r.prefilled_constraints))}（可人工改）</p>
      <p><b>启用模块：</b>${(plan.enabled_modules || []).map(m => `<span class="badge">${escapeHtml(m)}</span>`).join(" ")}</p>
      <p><b>删除模块：</b>${(plan.deleted_modules || []).map(m => `<span class="badge del">${escapeHtml(m)}</span>`).join(" ") || "（无）"}</p>
      <pre>${escapeHtml(JSON.stringify(plan.simplifications, null, 2))}</pre></div>`;
  } catch (e) { showMsg(out, e.message, "critical"); }
});

$("#dataprep-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const file = f.file.files[0];
  const out = $("#dataprep-result");
  if (!file) { showMsg(out, "请先选择文件", "warning"); return; }
  const fd = new FormData();
  fd.append("file", file);
  fd.append("eval_samples", String(+f.eval_samples.value || 100));
  showMsg(out, "正在上传并运行数据准备管道（语义去重可能耗时）…");
  try {
    const r = await api("/api/v1/data-prep/run", { method: "POST", body: fd });
    const links = (r.artifacts || []).map(a =>
      `<a class="badge" href="${a}" target="_blank">下载 ${a.split("/").pop()}</a>`).join(" ");
    out.innerHTML = `
      <div class="card">
        <h3>数据准备完成</h3>
        <div class="metric-cards">
          <div class="mc"><div class="v">${r.raw_count}</div><div class="k">原始条数</div></div>
          <div class="mc"><div class="v">${r.cleaned_count}</div><div class="k">清洗后</div></div>
          <div class="mc"><div class="v">${r.eval_set_count}</div><div class="k">评测集</div></div>
        </div>
        <p>输出目录：<code>${escapeHtml(r.output_dir)}</code></p>
        <p>产物：${links || "（无）"}</p>
        ${r.warning ? `<p class="hint">${escapeHtml(r.warning)}</p>` : ""}
        ${r.quality_report ? `<h3>质量报告</h3>${kvTable(r.quality_report, ["total", "unique", "duplicate_rate", "pii_types", "coverage"])}` : ""}
      </div>`;
  } catch (e) { showMsg(out, e.message, "critical"); }
});

/* ---------- ④ 原型运行（v5.0：RAG 知识库检索问答 + 引用分块展示） ---------- */

async function loadTemplates() {
  try {
    const r = await api("/api/v1/prototype/templates");
    window.__protoTemplateMeta = r.meta || {};
    const sel = $("#proto-templates");
    sel.innerHTML = r.templates.map(t =>
      `<option value="${escapeHtml(t)}">${escapeHtml((window.__protoTemplateMeta[t] && window.__protoTemplateMeta[t].label) || t)}</option>`).join("");
    updateProtoTemplateDesc();
  } catch (_) { /* 后端未启动时忽略 */ }
}

function updateProtoTemplateDesc() {
  const sel = $("#proto-templates");
  const meta = (window.__protoTemplateMeta || {})[sel.value] || {};
  const badges = [];
  if (meta.llm) badges.push(`<span class="badge ok">${escapeHtml(meta.llm)}</span>`);
  if (meta.rag_ready) badges.push('<span class="badge ok">RAG 就绪</span>');
  const desc = $("#proto-template-desc");
  if (desc) desc.innerHTML = `${badges.join(" ")} ${meta.detail ? escapeHtml(meta.detail) : ""}`;
}

function protoBadges(template, rag) {
  const meta = (window.__protoTemplateMeta || {})[template] || {};
  const parts = [];
  if (meta.llm) parts.push(`<span class="badge ok">${escapeHtml(meta.llm)}</span>`);
  if (meta.rag_ready) parts.push('<span class="badge ok">RAG 就绪</span>');
  if (rag) parts.push('<span class="badge ok">RAG 知识库问答</span>');
  return parts.join(" ");
}

loadTemplates();
$("#proto-templates").addEventListener("change", updateProtoTemplateDesc);

async function loadKbs() {
  try {
    const r = await api("/api/v1/retrieval/indexed");
    const sel = $("#proto-kb");
    const opts = (r.kbs || []).map(k =>
      `<option value="${escapeHtml(k.kb_run_id)}">${escapeHtml(k.kb_run_id)} · ${k.chunk_count}块 · ${escapeHtml((k.indexed_at || "").slice(0, 19).replace("T", " "))}</option>`).join("");
    sel.innerHTML = `<option value="">（不使用知识库 / 普通问答）</option>${opts}`;
  } catch (_) { /* 后端未启动时忽略 */ }
}
loadKbs();

$("#retrieval-indexed-refresh").addEventListener("click", async () => {
  try {
    await loadKbs();
    showMsg($("#retrieval-index-result"), "已刷新已索引知识库列表", "info");
  } catch (e) { showMsg($("#retrieval-index-result"), e.message, "critical"); }
});

$("#retrieval-index-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#retrieval-index-result");
  const kb_run_id = f.kb_run_id.value.trim();
  if (!kb_run_id) { showMsg(out, "请填写 kb_run_id", "warning"); return; }
  const chunks = f.chunks.value.split("\n").map(s => s.trim()).filter(Boolean);
  const body = { kb_run_id };
  if (chunks.length) body.chunks = chunks;
  showMsg(out, "索引进 ChromaDB 中…");
  try {
    const r = await api("/api/v1/retrieval/index", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    out.innerHTML = `<div class="alert ok">已索引 collection <code>${escapeHtml(r.collection)}</code>（${r.chunk_count} 块），RAG 就绪。可在上方下拉选择该知识库做检索问答。</div>`;
    await loadKbs();
  } catch (e) { showMsg(out, e.message, "critical"); }
});

/* v10.0：④ 原型运行 —— 数据达标门禁（真阻断 + 前端诚实展示 + 强制继续通道） */

let protoGateBlocked = false;

async function updateProtoGate() {
  const pid = ($("#proto-project-id").value || "").trim();
  const out = $("#proto-gate-status");
  const force = $("#proto-force");
  const runBtn = $("#proto-run-btn");
  if (!pid) {
    protoGateBlocked = false;
    out.innerHTML = '<span class="hint">未绑定项目：不检查数据达标门禁（运行响应附 gate.checked=false）</span>';
    force.disabled = true; force.checked = false;
    runBtn.disabled = false;
    return;
  }
  try {
    const g = await api(`/api/v1/workflow/gate?stage=data_prep&project_id=${encodeURIComponent(pid)}`);
    if (g.allowed) {
      protoGateBlocked = false;
      out.innerHTML = '<span class="badge ok">数据达标门禁：通过</span>';
      force.disabled = true; force.checked = false;
      runBtn.disabled = false;
    } else {
      protoGateBlocked = true;
      out.innerHTML = `<span class="badge del">数据达标门禁：未过</span> <span class="hint">${escapeHtml(g.reason)}（需勾选「强制继续」才能运行）</span>`;
      force.disabled = false; force.checked = false;
      runBtn.disabled = true;
    }
  } catch (e) {
    protoGateBlocked = false;
    out.innerHTML = `<span class="hint">门禁查询失败：${escapeHtml(e.message)}（不阻断运行）</span>`;
    force.disabled = true; force.checked = false;
    runBtn.disabled = false;
  }
}

$("#proto-project-id").addEventListener("input", updateProtoGate);
$("#proto-force").addEventListener("change", () => {
  if (protoGateBlocked) $("#proto-run-btn").disabled = !$("#proto-force").checked;
});
updateProtoGate();  // 初始展示「未绑定项目」提示（项目 ID 为空）

$("#proto-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#proto-result");
  const body = { template: f.template.value, user_input: f.user_input.value };
  if (f.kb_run_id.value) body.kb_run_id = f.kb_run_id.value;
  const pid = (f.project_id.value || "").trim();
  if (pid) {
    body.project_id = pid;
    if (f.force.checked) body.force = true;
  }
  // 前端门禁：未过且未勾选强制时禁止请求（与后端 403 双保险）
  if (protoGateBlocked && !f.force.checked) {
    showMsg(out, "数据达标门禁未过，请勾选「强制继续」后再运行（后端同样会 403 拦截）", "warning");
    return;
  }
  try {
    const r = await api("/api/v1/prototype/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const sources = (r.sources || []).map((s, i) => `
      <div class="card" style="margin-bottom:6px">
        <p class="hint">引用分块 ${i + 1} · 相似度 ${s.score != null ? s.score.toFixed(4) : "-"} · 来源 <code>${escapeHtml(s.source || "")}</code></p>
        <p>${escapeHtml(s.chunk || "")}</p>
      </div>`).join("");
    const gateLine = r.gate ? (r.gate.checked
      ? `<span class="badge ${r.gate.allowed ? "ok" : "del"}">数据达标门禁：${r.gate.allowed ? "通过" : "未过"}</span> <span class="hint">${escapeHtml(r.gate.reason || "")}</span>`
      : `<span class="badge">门禁未检查（未绑定项目）</span>`) : "";
    const override = r.gate_override
      ? `<p class="hint"><span class="badge del">强制继续 gate_override=true</span> ${escapeHtml(r.gate_reason || "")}</p>` : "";
    out.innerHTML = `
      <div class="card"><h3>运行结果（模板 ${escapeHtml(f.template.value)}）</h3>
        <pre>${escapeHtml(r.result)}</pre>
        <p class="hint">${protoBadges(f.template.value, !!r.rag)} LLM 模式：${escapeHtml(r.llm_mode)}${r.rag ? "（回答基于知识库分块，引用见下）" : ""}</p>
        ${gateLine ? `<p class="hint">${gateLine}</p>` : ""}
        ${override}
      </div>
      ${r.rag ? `<div class="card"><h3>引用分块（${(r.sources || []).length}）</h3>${sources || '<p class="hint">（无）</p>'}</div>` : ""}`;
  } catch (e) { showMsg(out, e.message, "critical"); }
});

/* ---------- ⑤ 部署配置 ---------- */

$("#deploy-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#deploy-result");
  showMsg(out, "正在生成部署配置…");
  try {
    const r = await api("/api/v1/deploy/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: f.mode.value,
        image_name: f.image_name.value,
        app_path: f.app_path.value,
      }),
    });
    const rows = Object.entries(r).filter(([k]) => k !== "artifacts").map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(JSON.stringify(v))}</td></tr>`).join("");
    const links = (r.artifacts || []).map(a =>
      `<a class="badge" href="${a}" target="_blank">下载 ${a.split("/").pop()}</a>`).join(" ");
    out.innerHTML = `<div class="card"><h3>部署配置已生成</h3><table class="kv">${rows}</table>
      <p>产物：${links || "（无）"}</p>
      <p class="hint">文件已写入服务器磁盘（${escapeHtml(r.output_dir)}）。</p></div>`;
  } catch (e) { showMsg(out, e.message, "critical"); }
});

/* ---------- ⑥ 监控面板 ---------- */

async function refreshMonitor() {
  const out = $("#monitor-result");
  try {
    const r = await api("/api/v1/monitor/metrics");
    const m = r.metrics || {};
    const real = r.real_llm_usage || {};
    const cards = [
      ["总请求", m.total_requests], ["成功率", m.success_rate], ["P99(ms)", m.p99_latency_ms],
      ["总成本(元)", m.total_cost], ["降级次数", m.degradation_count], ["总Token", m.total_tokens],
    ].map(([k, v]) => `<div class="mc"><div class="v">${escapeHtml(v)}</div><div class="k">${k}</div></div>`).join("");

    const alerts = (r.alerts || []).map(a =>
      `<div class="alert ${a.severity || "info"}">【${escapeHtml(a.severity || "")}】${escapeHtml(a.rule_name)} · 当前值 ${escapeHtml(a.current_value)}（阈值 ${escapeHtml(a.threshold)}）</div>`
    ).join("") || `<p class="hint">无告警</p>`;

    const realCards = [
      ["真实调用", real.calls], ["成功", real.success_calls], ["失败", real.error_calls],
      ["真实Token", real.total_tokens], ["真实成本(元)", real.cost],
    ].map(([k, v]) => `<div class="mc"><div class="v">${escapeHtml(v ?? "-")}</div><div class="k">${k}</div></div>`).join("");

    out.innerHTML = `
      <div class="card"><h3>指标（手动记录）</h3><div class="metric-cards">${cards}</div></div>
      <div class="card"><h3>告警</h3>${alerts}</div>
      <div class="card"><h3>真实 LLM 用量（core/llm.py 计费打点）</h3><div class="metric-cards">${realCards || '<p class="hint">暂无</p>'}</div>
        <div id="chart-real-cost"></div></div>
      <div class="card"><h3>成本分布（按模型，元）</h3><div id="chart-cost"></div></div>
      <div class="card"><h3>按小时调用量</h3><div id="chart-hour"></div></div>
      <div class="card"><h3>错误分布（按模型）</h3><div id="chart-error"></div></div>`;
    barsChart($("#chart-real-cost"), real.cost_by_model || {}, { fmt: v => v.toFixed(4) });
    barsChart($("#chart-cost"), m.cost_by_model || {}, { fmt: v => v.toFixed(4) });
    barsChart($("#chart-hour"), m.calls_by_hour || {});
    barsChart($("#chart-error"), m.error_by_model || {});
  } catch (e) { showMsg(out, e.message, "critical"); }
}
refreshMonitor();
$("#monitor-refresh").addEventListener("click", refreshMonitor);

$("#monitor-record-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#monitor-result");
  try {
    await api("/api/v1/monitor/record", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        success: f.success.value === "true",
        latency_ms: +f.latency_ms.value,
        input_tokens: +f.input_tokens.value,
        output_tokens: +f.output_tokens.value,
        model: f.model.value,
      }),
    });
    showMsg(out, "已记录");
    refreshMonitor();
  } catch (e) { showMsg(out, e.message, "critical"); }
});

/* ---------- ⑦ 数据飞轮 ---------- */

$("#flywheel-feedback-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#flywheel-result");
  try {
    const r = await api("/api/v1/flywheel/feedback", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request_id: f.request_id.value,
        user_input: f.user_input.value,
        model_output: f.model_output.value,
        feedback_type: f.feedback_type.value,
        note: f.note.value,
      }),
    });
    out.innerHTML = `<div class="card"><h3>反馈已记录</h3>${kvTable(r, ["request_id", "feedback_type", "id"])}</div>`;
  } catch (e) { showMsg(out, e.message, "critical"); }
});

$("#flywheel-pool").addEventListener("click", async () => {
  const out = $("#flywheel-result");
  try {
    const r = await api("/api/v1/flywheel/pool");
    const items = (r.pool || []).map(it => `<div class="card" style="margin-bottom:8px">
      <b>#${it.id}</b> [${escapeHtml(it.feedback_type)}] ${escapeHtml(it.request_id)}<br>
      <span class="hint">输入：${escapeHtml(it.user_input)}<br>输出：${escapeHtml(it.model_output)}</span></div>`).join("");
    out.innerHTML = `<h3>标注池（${(r.pool || []).length} 条）</h3>${items || '<p class="hint">暂无数据</p>'}`;
  } catch (e) { showMsg(out, e.message, "critical"); }
});

$("#flywheel-export-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#flywheel-result");
  try {
    const r = await api("/api/v1/flywheel/export-assets", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: f.project_id.value, project_summary: f.project_summary.value }),
    });
    out.innerHTML = `<div class="card"><h3>资产已导出（${r.total_assets} 项）</h3>${kvTable(r, ["total_assets", "output_path", "project_id"])}</div>`;
  } catch (e) { showMsg(out, e.message, "critical"); }
});

/* ---------- 知识库分块/质检 ---------- */

$("#kb-chunk-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#kb-result");
  try {
    const r = await api("/api/v1/kb/chunk", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: f.text.value, chunk_size: +f.chunk_size.value || 500, overlap: +f.overlap.value || 50 }),
    });
    const q = r.quality || {};
    const chunks = (r.chunks || []).slice(0, 5).map(c => `<div class="card" style="margin-bottom:6px">${escapeHtml(c.slice(0, 120))}…</div>`).join("");
    out.innerHTML = `<div class="card"><h3>分块 ${r.chunk_count} 块 · 质检</h3>
      <p>${["empty", "duplicates", "too_short", "too_long"].map(k => `${k}:${q[k] ?? 0}`).join(" ｜ ")}</p>
      <p class="hint">${escapeHtml((q.issues || []).join("；"))}</p>${chunks}</div>`;
  } catch (e) { showMsg(out, e.message, "critical"); }
});

/* ---------- ⑧ 项目档案（完整过程记录） ---------- */

function gotoProject(pid) {
  $$(".nav-item").forEach(x => x.classList.remove("active"));
  $$(".tab").forEach(x => x.classList.remove("active"));
  document.querySelector('[data-tab="tab-projects"]').classList.add("active");
  $("#tab-projects").classList.add("active");
  loadProjectDetail(pid);
}

async function refreshProjects() {
  const out = $("#project-list-result");
  try {
    const r = await api("/api/v1/projects");
    const rows = (r.projects || []).map(p =>
      `<tr><td><a href="#" class="proj-open" data-pid="${escapeHtml(p.project_id)}">${escapeHtml(p.name)}</a></td>
       <td>${escapeHtml(p.customer)}</td><td>${(p.events || []).length}</td></tr>`).join("");
    out.innerHTML = `<table class="kv"><tr><th>项目</th><th>客户</th><th>事件数</th></tr>${rows || "<tr><td colspan=3>暂无</td></tr>"}</table>`;
    $$(".proj-open", out).forEach(a => a.addEventListener("click", ev => {
      ev.preventDefault();
      loadProjectDetail(a.dataset.pid);
    }));
  } catch (e) { showMsg(out, e.message, "critical"); }
}

/* v7.0：项目作战台 —— 带上下文跳转辅助 + 分区渲染 */

function workflowPanelHtml(steps) {
  const rows = (steps || []).map(s => {
    const done = s.done ? `<span class="badge ok">已完成</span>` : `<span class="badge del">未完成</span>`;
    // v10.0：门禁未过附真实 reason（gate_check 的结果，不造假）
    let gate = "";
    if (s.gate) {
      gate = s.gate_passed
        ? `<span class="badge ok">门禁通过</span>`
        : `<span class="badge del">门禁未过${s.gate_reason ? "：" + escapeHtml(s.gate_reason) : ""}</span>`;
    }
    const ev = (s.evidence || []).map(x => `<span class="badge">${escapeHtml(x)}</span>`).join(" ");
    return `<tr><td>${escapeHtml(s.name)}</td><td>${escapeHtml(s.desc)}</td><td>${done} ${gate}</td><td>${ev || ""}</td></tr>`;
  }).join("");
  return `<div class="panel"><h3>工作流进度（标准骨架 + 门禁 · 按本项目判定）</h3>
    <table class="kv"><tr><th>步骤</th><th>说明</th><th>状态</th><th>证据</th></tr>${rows || "<tr><td colspan=4>—</td></tr>"}</table></div>`;
}

function wrSection(title, count, bodyHtml, emptyText, jumpBtn) {
  return `<div class="panel warroom-section">
    <div class="sec-head"><h3>${escapeHtml(title)} <span class="badge">${count}</span></h3>${jumpBtn || ""}</div>
    ${bodyHtml || `<p class="wr-empty">${emptyText}</p>`}
  </div>`;
}

function wrJumpBtn(tabKey, ctx, label) {
  return `<button type="button" class="ghost wr-jump" data-tab="${escapeHtml(tabKey)}"
    data-proj="${escapeHtml((ctx && ctx.project_id) || "")}" data-cust="${escapeHtml((ctx && ctx.customer) || "")}"
    data-run="${escapeHtml((ctx && ctx.run_id) || "")}">${escapeHtml(label)}</button>`;
}

function bindWarroomJumps(root) {
  $$(".wr-jump", root).forEach(b => b.addEventListener("click", () => {
    gotoTab(b.dataset.tab, {
      project_id: b.dataset.proj || "",
      customer: b.dataset.cust || "",
      run_id: b.dataset.run || "",
    });
  }));
}

async function loadProjectDetail(pid) {
  const out = $("#project-detail");
  try {
    const w = await api("/api/v1/projects/" + pid + "/warroom");
    const p = w.project || {};
    const counts = w.counts || {};
    const events = w.events || [];
    const customer = p.customer || "";
    const projCtx = { project_id: pid, customer };

    // 头部 + 概览统计卡
    const header = `
      <div class="panel">
        <h3>${escapeHtml(p.name)} <span class="badge">${escapeHtml(customer)}</span>
          <span class="hint" style="font-weight:normal">${escapeHtml(p.project_id || "")} · 创建于 ${escapeHtml((p.created_at || "").slice(0, 19).replace("T", " "))}</span></h3>
        <div class="warroom-stats">
          <div class="stat"><b>${counts.diagnosis ?? 0}</b><span>诊断</span></div>
          <div class="stat"><b>${counts.dataprep ?? 0}</b><span>数据任务</span></div>
          <div class="stat"><b>${counts.mapping ?? 0}</b><span>映射</span></div>
          <div class="stat"><b>${counts.deliverables ?? 0}</b><span>交付物</span></div>
          <div class="stat"><b>${counts.assets ?? 0}</b><span>资产</span></div>
          <div class="stat"><b>${counts.rag ?? 0}</b><span>RAG</span></div>
          <div class="stat"><b>${counts.workflow_progress ?? 0}%</b><span>工作流进度</span></div>
        </div>
      </div>`;

    const wfHtml = workflowPanelHtml(w.workflow || []);

    // 诊断（点击续做 → 跳 ① 恢复历史诊断）
    const diagRows = (w.diagnosis_runs || []).map(r => `
      <tr>
        <td><code>${escapeHtml(r.run_id)}</code></td>
        <td>${escapeHtml(r.requirement || r.name || "")}</td>
        <td>${escapeHtml(r.version || "")}</td>
        <td>${r.confirmed ? '<span class="badge ok">已确认</span>' : '<span class="badge del">未确认</span>'}</td>
        <td><button type="button" class="ghost wr-jump" data-tab="tab-diagnosis" data-run="${escapeHtml(r.run_id)}">续做</button></td>
      </tr>`).join("");
    const diagHtml = wrSection("诊断", (w.diagnosis_runs || []).length,
      `<table class="kv"><tr><th>run_id</th><th>需求</th><th>版本</th><th>状态</th><th></th></tr>${diagRows}</table>`,
      "暂无诊断（去需求诊断新建）", wrJumpBtn("tab-diagnosis", projCtx, "去诊断"));

    // 数据作战流任务
    const dpRows = (w.dataprep_runs || []).map(t => `
      <tr>
        <td><code>${escapeHtml(t.run_id)}</code></td>
        <td>${escapeHtml(t.name || "")}</td>
        <td><span class="badge">${escapeHtml(t.status || "")}</span></td>
        <td>${t.progress ?? 0}/${t.progress_total ?? 0}</td>
        <td>${escapeHtml(t.next_step || "—")}</td>
        <td><button type="button" class="ghost wr-jump" data-tab="tab-dataprep" data-run="${escapeHtml(t.run_id)}">续做</button></td>
      </tr>`).join("");
    const dpHtml = wrSection("数据作战流任务", (w.dataprep_runs || []).length,
      `<table class="kv"><tr><th>run_id</th><th>任务</th><th>状态</th><th>进度</th><th>下一步</th><th></th></tr>${dpRows}</table>`,
      "暂无数据任务（去数据作战流新建）", wrJumpBtn("tab-dataprep", projCtx, "去数据作战流"));

    // 字段映射
    const mpRows = (w.mapping_runs || []).map(r => `
      <tr>
        <td><code>${escapeHtml(r.run_id)}</code></td>
        <td>${escapeHtml(r.name || "")}</td>
        <td><span class="badge">${escapeHtml(r.status || "")}</span></td>
        <td>${r.mapping_count ?? 0} 条</td>
        <td>${r.success_rate != null ? (r.success_rate * 100).toFixed(0) + "%" : "—"}</td>
        <td><button type="button" class="ghost wr-jump" data-tab="tab-mapping" data-run="${escapeHtml(r.run_id)}">续做</button></td>
      </tr>`).join("");
    const mpHtml = wrSection("字段映射", (w.mapping_runs || []).length,
      `<table class="kv"><tr><th>run_id</th><th>任务</th><th>状态</th><th>映射</th><th>成功率</th><th></th></tr>${mpRows}</table>`,
      "暂无映射任务（去字段映射新建）", wrJumpBtn("tab-mapping", projCtx, "去映射"));

    // 交付物（HTML/PDF 链接）
    const caseRows = (w.cases || []).map(c => `
      <tr>
        <td>${escapeHtml(c.title || c.case_id || "")}</td>
        <td>${escapeHtml(c.source_type || "")}</td>
        <td>${escapeHtml((c.conclusion || "").slice(0, 40))}</td>
        <td><a class="badge" href="${escapeHtml(c.html_url || "#")}" target="_blank">HTML</a>
          ${c.pdf_url ? `<a class="badge" href="${escapeHtml(c.pdf_url)}" target="_blank">PDF</a>` : ""}</td>
      </tr>`).join("");
    const caseHtml = wrSection("交付物", (w.cases || []).length,
      `<table class="kv"><tr><th>标题</th><th>类型</th><th>结论</th><th>交付物</th></tr>${caseRows}</table>`,
      "暂无交付物（可在诊断定稿后生成，或用下方「生成项目文档包」）", "");

    // 可复用资产（一键接入）
    const assetRows = (w.assets || []).map(a => `
      <tr>
        <td>${escapeHtml(a.kind || "")}</td>
        <td>${escapeHtml(a.title || "")}</td>
        <td>${escapeHtml(a.customer || "")}</td>
        <td><button type="button" class="ghost wr-adopt" data-asset="${escapeHtml(a.asset_id)}">一键接入</button></td>
      </tr>`).join("");
    const assetHtml = wrSection("可复用资产", (w.assets || []).length,
      `<table class="kv"><tr><th>类型</th><th>标题</th><th>客户</th><th></th></tr>${assetRows}</table>`,
      "暂无资产（数据任务沉淀 / 诊断定稿后自动入库）", "");

    // RAG 索引状态
    const ragRows = (w.indexed_kbs || []).map(k => `
      <tr>
        <td><code>${escapeHtml(k.kb_run_id || "")}</code></td>
        <td>${escapeHtml(k.collection || "")}</td>
        <td>${k.chunk_count ?? 0} 块</td>
        <td>${escapeHtml((k.indexed_at || "").slice(0, 19).replace("T", " "))}</td>
      </tr>`).join("");
    const ragHtml = wrSection("RAG 索引", (w.indexed_kbs || []).length,
      `<table class="kv"><tr><th>kb_run_id</th><th>collection</th><th>分块</th><th>索引时间</th></tr>${ragRows}</table>`,
      "暂无 RAG 索引（数据作战流跑 knowledge_base 并索引后出现）", "");

    // 手动事件表单 + 文档包按钮（保留既有能力）
    const eventForm = `
      <div class="panel">
        <h3>过程记录（手动追加）</h3>
        <form id="project-event-form">
          <div class="grid">
            <label>类型 <select name="type"><option>meeting</option><option>issue</option><option>iteration</option><option>note</option><option>diagnosis</option><option>case</option></select></label>
            <label>标题 <input type="text" name="title" value=""></label>
            <label>详情 <input type="text" name="detail" value=""></label>
            <label>ref(run/case id) <input type="text" name="ref" value=""></label>
          </div>
          <button type="submit">追加过程记录</button>
        </form>
        <button id="project-doc-btn" type="button" class="ghost" style="margin-top:8px">生成项目文档包（Q18）</button>
        <div id="project-doc-result"></div>
      </div>`;

    // 时间线
    const tl = events.map(e =>
      `<div class="card" style="margin-bottom:6px"><b>[${escapeHtml(e.type)}] ${escapeHtml(e.title)}</b>
       <span class="hint">${escapeHtml(e.created_at)}</span>
       ${e.detail ? `<p class="hint">${escapeHtml(e.detail)}</p>` : ""}
       ${e.ref ? `<p class="hint">ref: <code>${escapeHtml(e.ref)}</code></p>` : ""}</div>`).join("");

    out.innerHTML = header + wfHtml + diagHtml + dpHtml + mpHtml + caseHtml + assetHtml + ragHtml + eventForm +
      `<h3>项目时间线（${events.length} 条）</h3>${tl || '<p class="hint">暂无记录</p>'}`;

    // 绑定：带上下文跳转 + 资产一键接入
    bindWarroomJumps(out);
    $$(".wr-adopt", out).forEach(b => b.addEventListener("click", async () => {
      try {
        const r = await adoptAsset(b.dataset.asset, projCtx);
        showMsg($("#project-detail"), `已一键接入资产（${escapeHtml(r.kind || "")}），可去对应工具续做。`, "info");
        await loadProjectDetail(pid);
      } catch (e) { showMsg($("#project-detail"), e.message, "critical"); }
    }));

    // 项目文档包（Q18）—— v10.0：需人工确认（发客户前确认），未勾选不发请求
    $("#project-doc-btn").addEventListener("click", () => {
      const o = $("#project-doc-result");
      o.innerHTML = `
        <div class="panel">
          <p class="hint">文档包门禁：需人工确认（发客户前确认）。勾选下方确认后再生成；未勾选不会发请求。</p>
          <label style="display:flex;gap:6px;align-items:center">
            <input type="checkbox" id="doc-pkg-confirm"> 我已人工确认文档内容定稿，确认可发客户
          </label>
          <button type="button" id="doc-pkg-confirm-go" class="ghost" style="margin-top:6px">确认并生成文档包</button>
        </div>`;
      $("#doc-pkg-confirm-go").addEventListener("click", async () => {
        const c = $("#doc-pkg-confirm");
        if (!c || !c.checked) {
          showMsg(o, "请先勾选「我已人工确认…」再生成文档包（未确认不发请求）", "warning");
          return;
        }
        showMsg(o, "LLM 起草项目文档包中（架构/API 文档/运维手册/SOP）…");
        try {
          const r = await api("/api/v1/cases/create-doc-package", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ run_id: null, project_id: pid, sections: ["架构说明", "API 文档", "运维手册", "SOP"], confirmed: true }),
          });
          o.innerHTML = `<div class="alert ok">已确认并生成项目文档包（confirmed=true）</div>
            <p class="hint">文档包已生成：<a class="badge" href="${r.urls.html}" target="_blank">打开 HTML</a>${r.urls.pdf ? ` <a class="badge" href="${r.urls.pdf}" target="_blank">PDF</a>` : ""}</p>`;
          await loadProjectDetail(pid);
        } catch (e) { showMsg(o, e.message, "critical"); }
      });
    });

    // 手动事件表单
    $("#project-event-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const f = ev.target;
      try {
        await api(`/api/v1/projects/${pid}/events`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ type: f.type.value, title: f.title.value, detail: f.detail.value, ref: f.ref.value || null }),
        });
        await loadProjectDetail(pid);
        await refreshProjects();
      } catch (e) { showMsg($("#project-detail"), e.message, "critical"); }
    });
  } catch (e) { showMsg(out, e.message, "critical"); }
}

$("#project-create-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  try {
    const p = await api("/api/v1/projects", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: f.name.value, customer: f.customer.value }),
    });
    f.name.value = ""; f.customer.value = "";
    await refreshProjects();
    await loadProjectDetail(p.project_id);
  } catch (e) { showMsg($("#project-list-result"), e.message, "critical"); }
});

$("#project-list-btn").addEventListener("click", refreshProjects);
refreshProjects();

/* ---------- ⑨ 字段映射工作台（集成工作流：导入样例 → 实跑校验 → 修正 → 导出） ---------- */

let mappingRunId = null;

function parseFields(text) {
  return text.split("\n").map(l => l.trim()).filter(Boolean).map(l => {
    const [name, ...rest] = l.split("|");
    return { name: (name || "").trim(), sample: (rest.join("|") || "").trim() };
  });
}

function renderMappings(m) {
  return (m.mappings || []).map((x, i) =>
    `<tr>
      <td><input name="m_target_${i}" value="${escapeHtml(x.target || "")}" style="width:100%"></td>
      <td><input name="m_source_${i}" value="${escapeHtml(x.source || "")}" style="width:100%"></td>
      <td><select name="m_rule_${i}">${["direct", "concat", "split", "lookup", "formula", "other"].map(r => `<option ${r === x.rule ? "selected" : ""}>${r}</option>`).join("")}</select></td>
      <td><input name="m_expr_${i}" value="${escapeHtml(x.expression || "")}" style="width:100%"></td>
      <td><span class="badge">${escapeHtml(x.confidence || "")}</span></td>
      <td id="m_verdict_${i}" style="white-space:nowrap"></td>
    </tr>`).join("");
}

function verdictBadge(v) {
  if (!v) return "";
  return { pass: '<span class="badge ok">pass</span>',
           warn: '<span class="badge warning">warn</span>',
           fail: '<span class="badge del">fail</span>' }[v] || escapeHtml(v);
}

function renderSampleInfo(samples) {
  if (!samples) return '<p class="hint">尚未导入样例数据。</p>';
  const rows = (samples.preview || []).map(r => `<tr>${samples.columns.map(c => `<td>${escapeHtml(String(r[c] ?? ""))}</td>`).join("")}</tr>`).join("");
  return `
    <p class="hint">已导入 <b>${samples.row_count}</b> 行（${escapeHtml(samples.filename || "")}）· 列：${escapeHtml((samples.columns || []).join("、"))}</p>
    <table class="kv"><tr>${samples.columns.map(c => `<th>${escapeHtml(c)}</th>`).join("")}</tr>${rows}</table>`;
}

function renderValidation(v) {
  if (!v) return "";
  const rows = (v.per_field || []).map(f => `
    <tr>
      <td><b>${escapeHtml(f.target)}</b></td>
      <td>${escapeHtml(f.source || "—")}</td>
      <td>${escapeHtml(f.rule)}</td>
      <td>${verdictBadge(f.verdict)}</td>
      <td>${escapeHtml(f.reason || "")}</td>
    </tr>`).join("");
  const ex = (v.per_field || []).slice(0, 3).map(f => `
    <details style="border-left:3px solid var(--accent)">
      <summary>${escapeHtml(f.target)} · 样例（源值 → 映射值 · pass ${f.pass}/fail ${f.fail}）</summary>
      <table class="kv"><tr><th>源值</th><th>映射值</th><th>执行</th></tr>
      ${(f.examples || []).map(e => `<tr>
        <td>${escapeHtml(String(e.source_value ?? ""))}</td>
        <td>${escapeHtml(String(e.output ?? "None"))}</td>
        <td>${e.ok ? '<span class="badge ok">通过</span>' : '<span class="badge del">' + escapeHtml(e.note || "") + "</span>"}</td>
      </tr>`).join("")}
      </table>
    </details>`).join("");
  return `
    <p class="hint">严格通过率 <b style="font-size:1.1em">${(v.success_rate * 100).toFixed(0)}%</b>
      · 无失败率（pass+warn）<b style="font-size:1.1em">${((v.no_fail_rate ?? v.success_rate) * 100).toFixed(0)}%</b>
      · pass ${v.counts.pass} / warn ${v.counts.warn} / fail ${v.counts.fail}
      · 抽样 <b>${v.sampled_rows}</b> 行 / 共 <b>${v.total_rows}</b> 行（校验时间 ${escapeHtml((v.validated_at || "").slice(0, 19).replace("T", " "))}）</p>
    <table class="kv" id="mapping-validation-table"><tr><th>目标</th><th>源</th><th>规则</th><th>校验</th><th>理由</th></tr>${rows}</table>
    ${ex}
    <p class="hint">修正方法：在上方映射表改「源/规则/表达式」→ 点「保存人工调整」→ 再点「试运行校验」重跑，成功率/无失败率变化可见。</p>`;
}

function renderMappingWorkspace(r) {
  const out = $("#mapping-result");
  const samples = r.samples || null;
  const validation = r.validation || null;
  out.innerHTML = `
    <div class="card">
      <h3>映射任务 <code>${escapeHtml(r.run_id)}</code> <span class="badge">${escapeHtml(r.status || "draft")}</span></h3>
      <p class="hint">${escapeHtml(r.notes || "")}</p>
      <table class="kv" id="mapping-table"><tr><th>目标</th><th>源</th><th>规则</th><th>表达式</th><th>置信</th><th>校验</th></tr>${renderMappings(r)}</table>
      <button id="mapping-save" type="button" class="primary">保存人工调整</button>
      <button id="mapping-export" type="button" class="ghost">导出适配器</button>
      <div id="mapping-export-result"></div>
    </div>
    <div class="card">
      <h3>导入真实样例数据（CSV，列名=源字段名）</h3>
      <div class="row">
        <input type="file" id="mapping-sample-file" accept=".csv">
        <button id="mapping-sample-upload" type="button" class="primary">上传样例</button>
      </div>
      <div id="mapping-sample-info">${renderSampleInfo(samples)}</div>
    </div>
    <div class="card">
      <h3>试运行校验（实跑映射 → LLM 校验正确性）</h3>
      <button id="mapping-validate" type="button" class="primary">试运行校验</button>
      <button id="mapping-preview" type="button" class="ghost">逐行预览</button>
      <div id="mapping-validation">${renderValidation(validation)}</div>
    </div>`;
  $("#mapping-save").addEventListener("click", saveMappings);
  $("#mapping-export").addEventListener("click", exportAdapter);
  $("#mapping-sample-upload").addEventListener("click", uploadSamples);
  $("#mapping-validate").addEventListener("click", validateMappings);
  $("#mapping-preview").addEventListener("click", previewRows);
  if (validation) applyVerdicts(validation);
}

function applyVerdicts(v) {
  (v.per_field || []).forEach((f, i) => {
    const el = document.getElementById(`m_verdict_${i}`);
    if (el) el.innerHTML = verdictBadge(f.verdict);
  });
}

$("#mapping-create-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#mapping-result");
  const source = parseFields(f.source.value), target = parseFields(f.target.value);
  if (!source.length || !target.length) { showMsg(out, "请填写源/目标字段（每行：字段名|示例值）", "warning"); return; }
  showMsg(out, "LLM 初判映射中…");
  try {
    const r = await api("/api/v1/mapping/create", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: f.name.value, source_fields: source, target_fields: target,
        customer: f.customer.value, project_id: f.project_id.value,
      }),
    });
    mappingRunId = r.run_id;
    renderMappingWorkspace(r);
    // v6.0：自动带出相关映射配置资产（一键接入 = 导入历史映射预填新 run）
    const relBox = $("#mapping-related-assets");
    if (r.related_assets && r.related_assets.length) {
      relBox.innerHTML = relatedAssetsHtml(r.related_assets);
      bindAdoptButtons(relBox, {
        customer: f.customer.value,
        assets: r.related_assets,
        autoTarget: true,
      });
    } else {
      relBox.innerHTML = "";
    }
    // 新建时若带了样例 CSV，立即上传
    const fileEl = f.sample_file;
    if (fileEl && fileEl.files && fileEl.files[0]) {
      await uploadSamples(fileEl.files[0]);
    }
    showMsg(out, `映射任务已创建（run_id=${mappingRunId}，可断点续接）`, "info");
  } catch (e) { showMsg(out, e.message, "critical"); }
});

async function saveMappings() {
  const out = $("#mapping-result");
  const rows = document.querySelectorAll("#mapping-table tr").length - 1;
  const mappings = [];
  for (let i = 0; i < rows; i++) {
    mappings.push({
      target: document.querySelector(`[name=m_target_${i}]`).value,
      source: document.querySelector(`[name=m_source_${i}]`).value,
      rule: document.querySelector(`[name=m_rule_${i}]`).value,
      expression: document.querySelector(`[name=m_expr_${i}]`).value,
    });
  }
  try {
    const r = await api(`/api/v1/mapping/${mappingRunId}/update`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mappings }),
    });
    showMsg(out, `已保存 ${r.mappings.length} 条映射（run_id=${mappingRunId}，可断点续接）`, "info");
  } catch (e) { showMsg(out, e.message, "critical"); }
}

async function uploadSamples(fileOrEvent) {
  const out = $("#mapping-result");
  const file = fileOrEvent instanceof File ? fileOrEvent : document.getElementById("mapping-sample-file").files[0];
  if (!file) { showMsg($("#mapping-sample-info"), "请选择 CSV 文件", "warning"); return; }
  const fd = new FormData();
  fd.append("file", file);
  try {
    const r = await api(`/api/v1/mapping/${mappingRunId}/samples`, { method: "POST", body: fd });
    $("#mapping-sample-info").innerHTML = renderSampleInfo(r);
    showMsg(out, `已导入样例 ${r.row_count} 行（列：${r.columns.join("、")}），可点「试运行校验」`, "info");
  } catch (e) { showMsg(out, e.message, "critical"); }
}

async function validateMappings() {
  const out = $("#mapping-result");
  showMsg($("#mapping-validation"), "实跑映射 + LLM 校验中…（可能需要几秒）");
  try {
    const r = await api(`/api/v1/mapping/${mappingRunId}/validate`, { method: "POST" });
    $("#mapping-validation").innerHTML = renderValidation(r);
    applyVerdicts(r);
  } catch (e) { showMsg($("#mapping-validation"), e.message, "critical"); }
}

async function previewRows() {
  const out = $("#mapping-result");
  try {
    const m = await api(`/api/v1/mapping/${mappingRunId}`);
    const rows = ((m.samples || {}).preview || []).slice(0, 3);
    if (!rows.length) { showMsg($("#mapping-validation"), "尚无样例数据，请先导入", "warning"); return; }
    let html = "<h4>逐行预览（源数据 → 各目标字段映射值）</h4>";
    for (const row of rows) {
      const vr = await api(`/api/v1/mapping/${mappingRunId}/validate-row`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ row }),
      });
      const cells = (vr.per_field || []).map(f =>
        `<tr><td>${escapeHtml(f.target)}</td><td>${escapeHtml(String(f.value ?? "None"))}</td><td>${f.ok ? '<span class="badge ok">通过</span>' : '<span class="badge del">未过</span>'}</td></tr>`).join("");
      html += `<div class="card"><p class="hint">行：${escapeHtml(JSON.stringify(row))}</p>
        <table class="kv"><tr><th>目标</th><th>映射值</th><th>执行</th></tr>${cells}</table></div>`;
    }
    $("#mapping-validation").innerHTML = html;
  } catch (e) { showMsg($("#mapping-validation"), e.message, "critical"); }
}

async function loadMappingRun(runId) {
  try {
    const r = await api(`/api/v1/mapping/${runId}`);
    mappingRunId = runId;
    renderMappingWorkspace(r);
  } catch (e) { showMsg($("#mapping-runs-result"), e.message, "critical"); }
}

async function listMappingRuns() {
  const el = $("#mapping-runs-result");
  el.innerHTML = "加载中…";
  try {
    const r = await api("/api/v1/mapping/runs");
    const rows = (r.runs || []).map(x => `
      <tr>
        <td><button class="ghost" data-load-run="${escapeHtml(x.run_id)}">${escapeHtml(x.run_id)}</button></td>
        <td>${escapeHtml(x.name || "")}</td>
        <td><span class="badge">${escapeHtml(x.status || "")}</span></td>
        <td>${x.has_samples ? "样例" : "—"}</td>
        <td>${x.has_validation ? "校验" : "—"}</td>
        <td>${x.success_rate != null ? (x.success_rate * 100).toFixed(0) + "%" : "—"}</td>
        <td>${escapeHtml((x.created_at || "").slice(0, 19).replace("T", " "))}</td>
      </tr>`).join("");
    el.innerHTML = rows
      ? `<table class="kv"><tr><th>run_id</th><th>任务名</th><th>状态</th><th>样例</th><th>校验</th><th>成功率</th><th>创建时间</th></tr>${rows}</table>`
      : '<p class="hint">暂无映射任务</p>';
    el.querySelectorAll("[data-load-run]").forEach(b => b.addEventListener("click", () => loadMappingRun(b.dataset.loadRun)));
  } catch (e) { el.innerHTML = `<div class="alert critical">${escapeHtml(e.message)}</div>`; }
}

$("#mapping-runs-btn").addEventListener("click", listMappingRuns);

async function exportAdapter() {
  const out = $("#mapping-result");
  try {
    const r = await api(`/api/v1/mapping/${mappingRunId}/export`, { method: "POST" });
    document.querySelector("#mapping-export-result").innerHTML =
      `<pre>${escapeHtml(r.adapter_code)}</pre><p class="hint">配置：${escapeHtml(r.config_path)}</p>`;
  } catch (e) { showMsg(out, e.message, "critical"); }
}

/* ---------- ⑪ 资产库（v6.0：项目越多、工具越强） ---------- */

function assetKindLabel(kind) {
  const m = {
    mapping_config: "字段映射配置", eval_set: "评测集", kb_chunks: "知识库分块",
    cleaning_rules: "清洗规则", quality_report: "质量报告",
    diagnosis_plan: "诊断方案", doc_package: "文档包",
  };
  return m[kind] || kind || "";
}

function assetBadgesHtml(a) {
  return `<span class="badge">${escapeHtml(assetKindLabel(a.kind))}</span>` +
    (a.tags || []).map(t => ` <span class="badge">${escapeHtml(t)}</span>`).join("");
}

async function adoptAsset(assetId, opts = {}) {
  const body = {
    project_id: opts.project_id || "",
    customer: opts.customer || "",
    target_run_id: opts.target_run_id || "",
  };
  return api(`/api/v1/assets/${assetId}/adopt`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}

function assetAdoptResultHtml(r) {
  if (r.run_id) {
    return `<p class="hint">已一键接入：新映射任务 <code>${escapeHtml(r.run_id)}</code>（${r.mappings ? r.mappings.length : 0} 条映射已预填），已跳转映射工作区续做。</p>`;
  }
  const tgt = r.target_run_id ? `（payload 已写入 run <code>${escapeHtml(r.target_run_id)}</code>）` : "";
  return `<p class="hint">${escapeHtml(r.note || "已接入")}${tgt}</p>`;
}

function relatedAssetsHtml(items) {
  if (!items || !items.length) return "";
  const rows = items.map(s => {
    const a = s.asset || {};
    return `<div class="card" style="margin-bottom:6px">
      <p><b>${escapeHtml(a.title || "")}</b> ${assetBadgesHtml(a)}
        <button class="ghost adopt-btn" data-asset="${escapeHtml(a.asset_id)}" style="float:right">一键接入</button></p>
      <p class="hint">${escapeHtml(s.reason || "")} ｜ 客户：${escapeHtml(a.customer || "—")} ｜ ${escapeHtml((a.created_at || "").slice(0, 10))}
        ${a.payload_url ? ` ｜ <a class="badge" href="${escapeHtml(a.payload_url)}" target="_blank">下载资产</a>` : ""}</p>
      <div class="adopt-out" data-for="${escapeHtml(a.asset_id)}"></div>
    </div>`;
  }).join("");
  return `<div class="card" style="border-left:4px solid var(--accent)">
    <h3>💡 相关可复用资产（自动带出 · 一键接入复用）</h3>${rows}</div>`;
}

/* 绑定容器内「一键接入」按钮：mapping_config → 跳转 ⑨ 工作区；数据资产 → 写目标 run / 登记引用 */
function bindAdoptButtons(container, ctx) {
  container.querySelectorAll(".adopt-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const assetId = btn.dataset.asset;
      const out = container.querySelector(`.adopt-out[data-for="${assetId}"]`);
      const item = (ctx.assets || []).find(x =>
        (x.asset ? x.asset.asset_id : x.asset_id) === assetId);
      const kind = item ? (item.asset || item).kind : "";
      const opts = {
        customer: ctx.customer || "", project_id: ctx.project_id || "",
        target_run_id: ctx.target_run_id || "",
      };
      // 资产库手动接入数据资产时，可选目标 run；自动带出场景（ctx.autoTarget）已带好目标 run 不再询问
      if (!ctx.autoTarget && !opts.target_run_id && kind &&
          !["mapping_config", "diagnosis_plan", "doc_package"].includes(kind)) {
        const t = prompt("写入目标数据作战流 run_id（可选；留空则仅登记项目资产引用）：");
        if (t === null) return;
        opts.target_run_id = t.trim();
      }
      if (out) out.innerHTML = "接入中…";
      try {
        const r = await adoptAsset(assetId, opts);
        if (out) out.innerHTML = assetAdoptResultHtml(r);
        if (r.run_id) {
          gotoTab("tab-mapping");
          await loadMappingRun(r.run_id);
        } else if (r.target_run_id && ctx.onAdopted) {
          ctx.onAdopted(r);
        }
      } catch (e) {
        if (out) out.innerHTML = `<div class="alert critical">${escapeHtml(e.message)}</div>`;
      }
    });
  });
}

async function renderAssetList(items) {
  const out = $("#asset-search-result");
  const rows = (items || []).map(a => `
    <tr>
      <td>${escapeHtml(a.title)}</td>
      <td>${assetBadgesHtml(a)}</td>
      <td>${escapeHtml(a.customer || "—")}</td>
      <td>${escapeHtml((a.created_at || "").slice(0, 10))}</td>
      <td>
        <div style="white-space:nowrap">
          <button class="ghost asset-detail" data-asset="${escapeHtml(a.asset_id)}">详情</button>
          <button class="ghost adopt-btn" data-asset="${escapeHtml(a.asset_id)}">一键接入</button>
          ${a.payload_url ? `<a class="badge" href="${escapeHtml(a.payload_url)}" target="_blank">下载</a>` : ""}
        </div>
        <div class="adopt-out" data-for="${escapeHtml(a.asset_id)}"></div>
      </td>
    </tr>`).join("");
  out.innerHTML = `<div class="card"><h3>资产库（${(items || []).length}）</h3>
    <table class="kv"><tr><th>标题</th><th>类型/标签</th><th>客户</th><th>注册时间</th><th>操作</th></tr>
      ${rows || '<tr><td colspan=5>暂无资产（先在数据沉淀 / 映射导出 / 诊断定稿 产生资产）</td></tr>'}</table>
    <div id="asset-detail-box"></div></div>`;
  out.querySelectorAll(".asset-detail").forEach(btn => btn.addEventListener("click", async () => {
    const box = $("#asset-detail-box");
    try {
      const a = await api(`/api/v1/assets/${btn.dataset.asset}`);
      box.innerHTML = `<div class="card"><h3>资产详情 <code>${escapeHtml(a.asset_id)}</code></h3>${kvTable(a)}</div>`;
    } catch (e) { box.innerHTML = `<div class="alert critical">${escapeHtml(e.message)}</div>`; }
  }));
  bindAdoptButtons(out, { customer: "", assets: items || [], autoTarget: false });
}

$("#asset-search-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const qs = new URLSearchParams();
  if (f.q.value.trim()) qs.set("q", f.q.value.trim());
  if (f.kind.value) qs.set("kinds", f.kind.value);
  if (f.tags.value.trim()) qs.set("tags", f.tags.value.trim());
  if (f.customer.value.trim()) qs.set("customer", f.customer.value.trim());
  try {
    const r = await api(`/api/v1/assets/search?${qs.toString()}`);
    renderAssetList(r.assets || []);
  } catch (e) { showMsg($("#asset-search-result"), e.message, "critical"); }
});

$("#asset-list-refresh").addEventListener("click", async () => {
  try {
    const r = await api("/api/v1/assets/list");
    renderAssetList(r.assets || []);
  } catch (e) { showMsg($("#asset-search-result"), e.message, "critical"); }
});

// 页面加载时预填资产库（数据量小，直接列出）
api("/api/v1/assets/list").then(r => {
  if (document.querySelector("#tab-assets")) renderAssetList(r.assets || []);
}).catch(() => { /* 后端未启动时忽略 */ });

/* ---------- ⑩ 功能说明（动态建议 + 工作流指南 + 详细指南） ---------- */

function gotoTab(tabKey, ctx) {
  ctx = ctx || {};
  $$(".nav-item").forEach(x => x.classList.remove("active"));
  $$(".tab").forEach(x => x.classList.remove("active"));
  document.querySelector(`[data-tab="${tabKey}"]`).classList.add("active");
  $("#" + tabKey).classList.add("active");
  // v7.0 带上下文跳转：跳 ③/⑨ 预填 create 表单的项目/客户；跳 ①/③/⑨ 续做指定 run
  if (tabKey === "tab-dataprep") {
    const f = $("#dataprep-flow-create");
    if (f) {
      if (ctx.project_id) f.project_id.value = ctx.project_id;
      if (ctx.customer) f.customer.value = ctx.customer;
    }
    if (ctx.run_id) resumeDataFlow(ctx.run_id);
  } else if (tabKey === "tab-mapping") {
    const f = $("#mapping-create-form");
    if (f) {
      if (ctx.project_id) f.project_id.value = ctx.project_id;
      if (ctx.customer) f.customer.value = ctx.customer;
    }
    if (ctx.run_id) loadMappingRun(ctx.run_id);
  } else if (tabKey === "tab-diagnosis") {
    if (ctx.run_id) resumeDiagnosis(ctx.run_id);
  }
}

function guideBodyHtml(g) {
  const stepsHtml = (g.steps || []).map(s =>
    `<p><b>${escapeHtml(s.title)}</b> — ${escapeHtml(s.detail)}</p>`).join("");
  return `
    <p>${escapeHtml(g.position || "")}</p>
    <h4>适用场景</h4><p>${escapeHtml(g.scenario || "—")}</p>
    <h4>前置条件</h4><p>${escapeHtml(g.prerequisites || "—")}</p>
    <h4>使用步骤</h4>${stepsHtml || '<p>（无）</p>'}
    <h4>输入 / 输出</h4><p class="hint">${escapeHtml(g.io || "—")}</p>
    <h4>关键参数</h4><p class="hint">${escapeHtml(g.params || "—")}</p>
    <h4>产出衔接</h4><p class="hint">${escapeHtml(g.handoff || "—")}</p>
    <h4>常见问题 / 坑</h4><p class="hint">${escapeHtml(g.pitfalls || "—")}</p>
    ${g.example ? `<h4>示例</h4><p>${escapeHtml(g.example)}</p>` : ""}`;
}

async function loadGuide() {
  const out = $("#manifests-result");
  out.innerHTML = "加载使用指南中…";
  try {
    const [wf, sug, man] = await Promise.all([
      api("/api/v1/guide/workflow"),
      api("/api/v1/guide/suggestions"),
      api("/api/v1/manifests"),
    ]);

    // 💡 动态使用建议 → 每建议可展开
    const sugHtml = (sug.suggestions || []).map(s => `
      <details class="article" style="border-left:3px solid var(--accent)">
        <summary><b>💡 ${escapeHtml(s.title)}</b></summary>
        <div class="body">
          <p><b>为什么：</b>${escapeHtml(s.why)}</p>
          <h4>怎么做</h4><ol>${(s.how || []).map(h => `<li>${escapeHtml(h)}</li>`).join("")}</ol>
          <p class="hint"><b>前置条件：</b>${escapeHtml(s.prereq || "—")} ｜ <b>产出：</b>${escapeHtml(s.produce || "—")}</p>
          <button class="ghost" data-goto-tab="${escapeHtml(s.tab)}">去这个页面操作 →</button>
        </div>
      </details>`).join("");

    // 🔀 工作流 → 每阶段可展开
    const wfHtml = (wf.phases || []).map(p => `
      <details class="article">
        <summary><b>阶段${p.phase} · ${escapeHtml(p.name)}</b> ${p.gate ? `<span class="badge del">门禁：${escapeHtml(p.gate)}</span>` : ""}</summary>
        <div class="body">
          <p><b>目标：</b>${escapeHtml(p.goal)}</p>
          <p>${escapeHtml(p.narrative)}</p>
          <p class="hint"><b>涉及模块：</b>${escapeHtml((p.modules || []).join("、"))}</p>
          <h4>怎么做</h4><p>${escapeHtml(p.how)}</p>
          <p class="hint"><b>输入 / 产出：</b>${escapeHtml(p.io)}</p>
          ${p.handoff ? `<p class="hint"><b>衔接下一步：</b>${escapeHtml(p.handoff)}</p>` : ""}
          ${p.pitfalls ? `<p class="hint"><b>常见问题：</b>${escapeHtml(p.pitfalls)}</p>` : ""}
        </div>
      </details>`).join("");
    const cross = (wf.cross_cutting || []).join("、");

    // 模块指南 → 可展开 + 懒加载（首次展开才取详情）
    const modHtml = (man.manifests || []).map(m => `
      <details class="article" data-lazy-key="${escapeHtml(m.key)}">
        <summary><b>${escapeHtml(m.name)}</b>
          ${m.needs_review && m.needs_review !== "否" ? `<span class="badge del">${escapeHtml(m.needs_review)}</span>` : ""}
          <span class="hint">${escapeHtml(m.intro)}</span>
        </summary>
        <div class="body"><div data-guide-detail="${escapeHtml(m.key)}"><p class="hint">展开后加载详细指南…</p></div></div>
      </details>`).join("");

    // 💻 完整操作示例（放最前面）
    const wt = wf.walkthrough;
    let wtHtml = "";
    if (wt) {
      const wsteps = (wt.steps || []).map(s => `
        <details class="article" style="border-left:3px solid var(--ok)">
          <summary><b>第 ${s.step} 步 · ${escapeHtml(s.tab)}</b></summary>
          <div class="body">
            <p><b>点击 / 操作：</b>${escapeHtml(s.action)}</p>
            <p><b>看到什么响应：</b>${escapeHtml(s.response)}</p>
            ${s.note ? `<p class="hint"><b>注意：</b>${escapeHtml(s.note)}</p>` : ""}
          </div>
        </details>`).join("");
      wtHtml = `
        <div class="card" style="border:2px solid var(--ok)">
          <h3>${escapeHtml(wt.title)}</h3>
          <p class="hint"><b>客户需求：</b>${escapeHtml(wt.scenario)}</p>
          <p class="hint"><b>完整链路：</b>${escapeHtml(wt.flow)}</p>
          ${wsteps}
          <p class="hint"><b>💡 ${escapeHtml(wt.tip)}</b></p>
        </div>`;
    }

    out.innerHTML = `
      ${wtHtml}
      <button id="guide-expand-all" type="button" class="ghost">展开全部</button>
      <button id="guide-collapse-all" type="button" class="ghost">收起全部</button>
      <h2>💡 动态使用建议 · 现在该做什么（点开展开步骤）</h2>
      ${sugHtml || '<p class="hint">暂无建议（从第一次需求诊断开始）</p>'}
      <h2>🔀 FDE 连贯工作流 · 全貌（点开展开）</h2>
      ${wfHtml}
      <p class="hint">贯穿模块：${escapeHtml(cross)}（成本监控 / 反馈飞轮）</p>
      <h2>模块详细使用指南 · 逐个上手（点开展开）</h2>
      ${modHtml || '<p class="hint">无</p>'}`;

    // 去操作跳转
    $$("[data-goto-tab]", out).forEach(b => b.addEventListener("click", () => gotoTab(b.dataset.gotoTab)));
    // 模块指南懒加载：首次展开时取详情
    $$("details[data-lazy-key]", out).forEach(d => {
      d.addEventListener("toggle", () => {
        if (!d.open) return;
        const el = d.querySelector("[data-guide-detail]");
        if (!el || el.dataset.loaded) return;
        el.dataset.loaded = "1";
        api("/api/v1/guide/" + el.dataset.guideDetail).then(r => {
          el.innerHTML = guideBodyHtml(r.guide || {});
        }).catch(() => { el.innerHTML = "<p class='hint'>指南加载失败</p>"; });
      });
    });
    // 全部展开/收起
    $("#guide-expand-all").addEventListener("click", () => $$("details.article", out).forEach(d => d.open = true));
    $("#guide-collapse-all").addEventListener("click", () => $$("details.article", out).forEach(d => d.open = false));
  } catch (e) { showMsg(out, e.message, "critical"); }
}

$("#manifests-load").addEventListener("click", loadGuide);
loadGuide();  // 页面加载即填充使用指南（含最前的完整操作示例）

/* ---------- 标注与评测集管理（v9.0：人工双人标注工作台） ---------- */

let annRunId = null;
let annWorkbenchRunId = null;

/* 从数据作战流建任务：加载已完成清洗的数据作战流 run 进下拉 */
async function loadAnnDataprepRuns() {
  const sel = $("#ann-dataprep-runs");
  if (!sel) return;
  try {
    const r = await api("/api/v1/dataprep/runs");
    const runs = (r.runs || []).filter(x => x.products && x.products.cleaned_data && x.products.cleaned_data.exists);
    sel.innerHTML = runs.map(x =>
      `<option value="${escapeHtml(x.run_id)}">${escapeHtml(x.name)}（${escapeHtml(x.run_id)} · ${x.progress}/${x.progress_total}）</option>`).join("")
      || `<option value="">（无已完成清洗的数据作战流任务，请先跑清洗）</option>`;
  } catch (_) {
    sel.innerHTML = `<option value="">（加载失败）</option>`;
  }
}

/* 数据作战流衔接：标注步骤跑完后，「去人工标注工作台精标」 */
async function openAnnWorkbenchFromDataprep(dataprepRunId) {
  const out = $("#ann-result");
  if (!dataprepRunId) { showMsg(out, "缺少数据作战流 run_id", "warning"); return; }
  showMsg(out, "创建人工标注任务中…");
  try {
    const r = await api("/api/v1/annotation/from-dataprep", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataprep_run_id: dataprepRunId, sample_size: 20 }),
    });
    renderAnnWorkbench(r);
    const panel = $("#ann-result").closest(".panel");
    if (panel) panel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) { showMsg(out, e.message, "critical"); }
}

$("#ann-from-dataprep-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#ann-result");
  const dataprep_run_id = f.dataprep_run_id.value.trim();
  if (!dataprep_run_id) { showMsg(out, "请选择数据作战流任务（或先跑清洗）", "warning"); return; }
  const sample_size = +f.sample_size.value || 20;
  try {
    const r = await api("/api/v1/annotation/from-dataprep", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataprep_run_id, sample_size, name: "" }),
    });
    renderAnnWorkbench(r);
  } catch (e) { showMsg(out, e.message, "critical"); }
});

$("#ann-create-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  const out = $("#ann-result");
  const items = f.items.value.split("\n").map(s => s.trim()).filter(Boolean);
  if (!items.length) { showMsg(out, "请填写待标注样本", "warning"); return; }
  try {
    const r = await api("/api/v1/annotation/create", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: f.name.value, items }),
    });
    annRunId = r.run_id;
    renderAnnWorkbench(r);
  } catch (e) { showMsg(out, e.message, "critical"); }
});

$("#ann-list-btn").addEventListener("click", async () => {
  const out = $("#ann-list-result");
  try {
    const r = await api("/api/v1/annotation/runs");
    const rows = (r.tasks || []).map(x => `
      <tr>
        <td>${escapeHtml(x.name)}</td>
        <td><code>${escapeHtml(x.run_id)}</code></td>
        <td>${x.total}</td>
        <td><span class="badge ok">一致 ${x.stats.agreed}</span> <span class="badge del">分歧 ${x.stats.disagreed}</span> <span class="badge">未标 ${x.stats.unlabeled}</span></td>
        <td><button class="ghost ann-open" data-run="${escapeHtml(x.run_id)}">打开工作台</button></td>
      </tr>`).join("");
    out.innerHTML = `<table class="kv"><tr><th>任务名</th><th>run_id</th><th>样本</th><th>一致性</th><th>操作</th></tr>${rows || "<tr><td colspan=5>暂无标注任务</td></tr>"}</table>`;
    $$(".ann-open", out).forEach(b => b.addEventListener("click", async () => {
      const runId = b.dataset.run;
      try {
        const t = await api(`/api/v1/annotation/${runId}`);
        renderAnnWorkbench(t);
      } catch (e) { showMsg(out, e.message, "critical"); }
    }));
  } catch (e) { showMsg(out, e.message, "critical"); }
});

function annConsistencyBadge(status) {
  const map = {
    unlabeled: '<span class="badge">未标</span>',
    only_a: '<span class="badge">仅A</span>',
    only_b: '<span class="badge">仅B</span>',
    only_one: '<span class="badge">仅一人</span>',
    agreed: '<span class="badge ok">一致</span>',
    disagreed: '<span class="badge del">分歧</span>',
  };
  return map[status] || `<span class="badge">${escapeHtml(status)}</span>`;
}

/* v9.0：人工双人标注工作台（独立函数，不动旧 renderAnnTask 逻辑） */
function renderAnnWorkbench(t) {
  const out = $("#ann-result");
  annWorkbenchRunId = t.run_id;
  annRunId = t.run_id;
  const items = t.items || [];
  const stats = t.stats || { agreed: 0, disagreed: 0, unlabeled: 0, total: items.length };

  const rows = items.map(it => {
    const labels = it.labels || {};
    const aVal = labels.A || labels.a || "";
    const bVal = labels.B || labels.b || "";
    const st = it.consistency || "unlabeled";
    return `<tr>
      <td>#${it.id}</td>
      <td>${escapeHtml(it.content)}</td>
      <td><input name="annA_${it.id}" value="${escapeHtml(aVal)}" placeholder="标注员 A" data-ann-item="${it.id}" data-ann-annotator="A" class="ann-input" style="width:100%"></td>
      <td><input name="annB_${it.id}" value="${escapeHtml(bVal)}" placeholder="标注员 B" data-ann-item="${it.id}" data-ann-annotator="B" class="ann-input" style="width:100%"></td>
      <td>${annConsistencyBadge(st)}</td>
    </tr>`;
  }).join("");

  const dis = items.filter(it => (it.consistency || "") === "disagreed");
  const disRows = dis.map(it => {
    const labels = it.labels || {};
    const labelHtml = Object.entries(labels)
      .map(([k, v]) => `<b>${escapeHtml(k)}：</b>${escapeHtml(v)}`).join(" ｜ ") || "—";
    return `<tr>
      <td>#${it.id}</td>
      <td>${escapeHtml(it.content)}</td>
      <td colspan="2">${labelHtml}</td>
    </tr>`;
  }).join("");

  const src = t.source || {};
  const sourceHtml = src.type
    ? `<p class="hint">样本来源：${src.type === "dataprep" ? "数据作战流（人工标注）" : "手动粘贴"}${src.dataprep_run_id ? ` ｜ 数据作战流 run <code>${escapeHtml(src.dataprep_run_id)}</code> ｜ 样本数 ${src.sample_size || ""}` : ""}</p>`
    : "";

  out.innerHTML = `
    <div class="card">
      <h3>人工标注工作台 <code>${escapeHtml(t.run_id)}</code> <span class="badge">${escapeHtml(t.name || "")}</span></h3>
      ${sourceHtml}
      <p><b>一致性统计：</b><span class="badge ok">一致 ${stats.agreed}</span> <span class="badge del">分歧 ${stats.disagreed}</span> <span class="badge">未标 ${stats.unlabeled}</span> <span class="badge">共 ${stats.total}</span></p>
      <p class="hint">每行两列：标注员 A / 标注员 B 分别存各自的标签。两列都填且相同 → 一致；不同 → 分歧。改标签后点「保存标注」重算一致性。</p>
      <table class="kv" id="ann-wb-table"><tr><th>ID</th><th>样本</th><th>标注员 A</th><th>标注员 B</th><th>状态</th></tr>${rows}</table>
      <p style="margin-top:8px">
        <button id="ann-wb-save" type="button" class="primary">保存标注</button>
        <button id="ann-wb-refresh" type="button" class="ghost">刷新一致性</button>
        <button id="ann-wb-build" type="button" class="ghost">构建评测集</button>
      </p>
      <div id="ann-wb-msg"></div>
      <div id="ann-wb-build-result"></div>
    </div>
    ${dis.length ? `<div class="card"><h3>分歧样本（需处理到一致）</h3>
      <table class="kv"><tr><th>ID</th><th>样本</th><th>标注员 A</th><th>标注员 B</th></tr>${disRows}</table>
      <p class="hint">在下方工作台给任一标注员改标签后点「保存标注」，一致性会重算，直到无分歧。</p></div>` : ""}`;

  $("#ann-wb-save").addEventListener("click", saveAnnWorkbench);
  $("#ann-wb-refresh").addEventListener("click", refreshAnnWorkbench);
  $("#ann-wb-build").addEventListener("click", buildAnnWorkbench);
}

function annWbMsg(html, type) {
  const box = $("#ann-wb-msg");
  if (box) box.innerHTML = `<div class="alert ${type}">${html}</div>`;
}

async function saveAnnWorkbench() {
  const runId = annWorkbenchRunId;
  const inputs = $$("#ann-wb-table .ann-input");
  const toSave = [];
  for (const inp of inputs) {
    const val = inp.value.trim();
    if (!val) continue;
    toSave.push({ item_id: +inp.dataset.annItem, annotator: inp.dataset.annAnnotator, label: val });
  }
  if (!toSave.length) { annWbMsg("没有可保存的标注（请至少填一个标注员的标签）", "warning"); return; }
  try {
    for (const s of toSave) {
      await api(`/api/v1/annotation/${runId}/label`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(s),
      });
    }
    await refreshAnnWorkbench();
    annWbMsg(`已保存 ${toSave.length} 条标注并重算一致性`, "ok");
  } catch (e) {
    showMsg($("#ann-result"), e.message, "critical");
  }
}

async function refreshAnnWorkbench() {
  const out = $("#ann-result");
  try {
    const t = await api(`/api/v1/annotation/${annWorkbenchRunId}`);
    renderAnnWorkbench(t);
  } catch (e) { showMsg(out, e.message, "critical"); }
}

async function buildAnnWorkbench() {
  const runId = annWorkbenchRunId;
  try {
    const r = await api(`/api/v1/annotation/${runId}/build-eval`, { method: "POST" });
    const box = $("#ann-wb-build-result");
    box.innerHTML = `
      <div class="alert ok">评测集构建完成：一致 ${r.agreed} 条 / 分歧 ${r.disagreements} 条（分歧样本不进评测集）</div>
      <p><a class="badge" href="/artifacts/annotation/${escapeHtml(runId)}/eval_set.json" target="_blank">下载评测集 eval_set.json</a></p>
      <pre>${escapeHtml(JSON.stringify((r.eval_set || []).slice(0, 3), null, 2))}</pre>`;
  } catch (e) { showMsg($("#ann-result"), e.message, "critical"); }
}

/* 保留旧单标注员渲染（兼容旧逻辑，面板已升级为双人工作台） */
function renderAnnTask(t) {
  const out = $("#ann-result");
  const rows = (t.items || []).map(it =>
    `<tr><td>#${it.id}</td><td>${escapeHtml(it.content)}</td>
      <td><input name="ann_label_${it.id}" value="${escapeHtml((Object.values(it.labels) || [])[0] || "")}" style="width:100%"></td></tr>`).join("");
  out.innerHTML = `
    <div class="card"><h3>标注任务 <code>${escapeHtml(t.run_id)}</code></h3>
      <table class="kv" id="ann-table"><tr><th>ID</th><th>样本</th><th>标签（同一人先标，双人后比一致性）</th></tr>${rows}</table>
      <button id="ann-save" type="button" class="primary">保存标注</button>
      <button id="ann-build" type="button" class="ghost">构建评测集</button>
      <div id="ann-build-result"></div></div>`;
  $("#ann-save").addEventListener("click", async () => {
    const rowsEls = document.querySelectorAll("#ann-table tr").length - 1;
    for (let i = 0; i < rowsEls; i++) {
      const labelEl = document.querySelector(`[name=ann_label_${i + 1}]`);
      if (!labelEl || !labelEl.value.trim()) continue;
      await api(`/api/v1/annotation/${annRunId}/label`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_id: i + 1, annotator: "user", label: labelEl.value.trim() }) });
    }
    showMsg(out, "标注已保存", "info");
  });
  $("#ann-build").addEventListener("click", async () => {
    try {
      const r = await api(`/api/v1/annotation/${annRunId}/build-eval`, { method: "POST" });
      document.querySelector("#ann-build-result").innerHTML =
        `<p class="hint">评测集 ${r.agreed} 条（一致）/ 分歧 ${r.disagreements} 条</p><pre>${escapeHtml(JSON.stringify(r.eval_set.slice(0, 3), null, 2))}</pre>`;
    } catch (e) { showMsg($("#ann-result"), e.message, "critical"); }
  });
}

loadAnnDataprepRuns();
