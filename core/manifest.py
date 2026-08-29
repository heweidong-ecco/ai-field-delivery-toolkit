"""模块 manifest（自描述）：每模块的简介/使用规范/适用场景/案例检索词/API

Q22-24 决策落地：结构自动聚合（操作台/API 文档从本文件生成），
简介/规范文本人工维护（判断性内容人工写才可靠）。

manifest 字段：
- intro: 一句话简介（入口层·简要）
- detail: 详细说明（详情层）
- spec: 输入/输出/用法
- needs_review: 是否需对抗评审/人工确认
- cases_query: 案例检索关键词（说明页挂真实案例/最佳实践）
- api: 相关端点
"""

MANIFESTS = {
    "core": {
        "key": "core",
        "name": "统一底座",
        "intro": "配置/安全/日志/版本/降级/模块注册 + 统一 LLM 客户端（计费打点）",
        "detail": "所有模块的共享地基：配置中心、PII 脱敏、注入拦截、日志、版本管理、降级管理、模块注册、FastAPI 入口。core/llm.py 统一 DeepSeek 客户端并记录每次调用的 token/耗时/成本，喂给监控看板。",
        "spec": "输入：环境变量(.env)/模块请求。输出：配置单例、日志、LLM 文本或 JSON。",
        "needs_review": "否",
        "cases_query": "",
        "api": ["/health", "/api/v1/registry/register"],
    },
    "diagnosis": {
        "key": "diagnosis",
        "name": "需求诊断",
        "intro": "输入客户需求，多 Agent 对抗评审（Generator/Critic/Reviewer 盲审）打分并生成可打印交付物",
        "detail": "五维（生成性/推理复杂度/不确定性容忍度/数据可得性/实时性）AI 评估；Generator 打分 → Critic 盲审 → 人工复核 → Reviewer 再评分 → 强制确认定稿；支持版本循环（v1→客户反馈→v2→…）与可打印交付物。置信度 = Generator 与 Critic 一致度。v2.0+ 增加非技术全景可行性（商业价值/组织承接/集成/合规/风险）+ 商务提案（投入分期/里程碑/甲方责任清单/试点退出/替代方案，供洽谈）。",
        "spec": "输入：客户需求文本 + 可选自定义中立提示词 + 客户反馈文件。输出：v 版定稿报告 + HTML/PDF 交付物 + 案例存档。",
        "needs_review": "对抗评审 + 人工强制确认",
        "cases_query": "诊断",
        "api": ["/diagnosis/start", "/diagnosis/review", "/diagnosis/finalize", "/diagnosis/feedback", "/diagnosis/next-version",
                "/diagnosis/runs", "/diagnosis/{run_id}/state", "/diagnosis/{run_id}/rename", "/diagnosis/archive/{run_id}",
                "/diagnosis/ai", "/cases/create"],
    },
    "cropper": {
        "key": "cropper",
        "name": "五步裁剪",
        "intro": "按客户约束（预算/硬件/网络/合规）裁剪出「哪些模块该上、怎么简化」；可从诊断结论带入",
        "detail": "五步（质疑→删除→简化→加速→自动化）基于客户约束生成启用/删除模块、简化配置、排期建议。规则作为「起点模板」人工可改；支持从诊断结论（总分/结论/置信度）自动预填约束。",
        "spec": "输入：客户约束（CustomerConstraints）+ 可选诊断 run_id。输出：裁剪方案（启用/删除/简化/排期）。",
        "needs_review": "建议人工确认",
        "cases_query": "裁剪",
        "api": ["/cropper/plan", "/cropper/from-diagnosis/{run_id}"],
    },
    "data_prep": {
        "key": "data_prep",
        "name": "数据准备",
        "intro": "数据接入→质量评估→清洗（含语义去重）→评测集构建",
        "detail": "支持 csv/json/pdf/db 接入；清洗含字符级去重 + 语义去重（ChromaDB）、异常过滤、PII 脱敏；构建评测集。数据作战流见 dataprep 模块（项目级 6 步流水线：断点续接 + 产物沉淀复用，为主载体）。",
        "spec": "输入：数据文件或数据源路径。输出：cleaned_data/eval_set/quality_report JSON。",
        "needs_review": "否（数据达标是硬门禁）",
        "cases_query": "数据",
        "api": ["/data-prep/run", "/annotation/create", "/kb/chunk"],
    },
    "dataprep": {
        "key": "dataprep",
        "name": "数据作战流",
        "intro": "数据作战流:以项目为单位、可断点续接的 6 步数据流水线",
        "detail": "导入→清洗→质量→标注→评测集→知识库 六步，以 run_id 断点续接（刷新/重连不丢），每步产物真实落盘；`/deposit` 沉淀 4 类可复用资产（评测集/知识库分块/清洗规则/质量报告 → search_cases 可检索 + assets 注册）；知识库步骤自动索引 ChromaDB，RAG 就绪。",
        "spec": "输入：csv/json 真实数据（multipart）+ 可选项目/客户。输出：run_id + 每步产物（cleaned_data/quality_report/eval_set/chunks）+ 已索引知识库。",
        "needs_review": "否（数据达标是硬门禁）",
        "cases_query": "数据",
        "api": ["/dataprep/create", "/dataprep/runs", "/dataprep/{run_id}", "/dataprep/{run_id}/step",
                "/dataprep/{run_id}/rename", "/dataprep/{run_id}/deposit"],
    },
    "prototype_assembler": {
        "key": "prototype_assembler",
        "name": "原型组装",
        "intro": "按模板组装 Agent 原型；4 个模板全部真调 DeepSeek",
        "detail": "知识问答（可走 RAG）、信息抽取、多步推理、反思型四个模板均真调 DeepSeek（core/llm.py），用于现场快速验证核心假设；LLM 失败时诚实降级（返回错误说明，不装成功）。",
        "spec": "输入：模板名 + 用户输入 + 可选 kb_run_id。输出：Agent 运行结果字符串 + llm_mode +（RAG）引用分块。",
        "needs_review": "否",
        "cases_query": "原型",
        "api": ["/prototype/templates", "/prototype/run"],
    },
    "deploy_hardener": {
        "key": "deploy_hardener",
        "name": "部署加固",
        "intro": "生成 Docker/裸机部署配置 + 降级预案 + 部署前环境检查",
        "detail": "docker-compose 或 bare-metal(systemd) 两种模式；生成 degradation.yaml、Dockerfile、compose、服务文件；部署前环境变量检查。",
        "spec": "输入：project_dir + 部署模式。输出：部署配置文件。",
        "needs_review": "否",
        "cases_query": "部署",
        "api": ["/deploy/run"],
    },
    "monitor": {
        "key": "monitor",
        "name": "监控面板",
        "intro": "指标/告警/看板 + 真实 LLM 用量与成本（计费打点自动喂）",
        "detail": "手动记录调用指标 + core/llm.py 自动打点的真实调用/token/成本。告警规则：错误率、P99、降级。",
        "spec": "输入：record_request(手动) 或 LLM 自动打点。输出：指标/告警/真实用量汇总。",
        "needs_review": "否",
        "cases_query": "",
        "api": ["/monitor/record", "/monitor/metrics"],
    },
    "data_flywheel": {
        "key": "data_flywheel",
        "name": "数据飞轮",
        "intro": "反馈回流 → 评测集更新 → 资产导出",
        "detail": "收集 dislike/audit_fail 等反馈进标注池，更新评测集，导出可复用资产。",
        "spec": "输入：反馈记录。输出：标注池/评测集更新/资产清单。",
        "needs_review": "否",
        "cases_query": "飞轮",
        "api": ["/flywheel/feedback", "/flywheel/pool", "/flywheel/export-assets"],
    },
    "cases": {
        "key": "cases",
        "name": "案例/交付物",
        "intro": "诊断定稿 → 可打印 HTML/PDF 交付物 + 结构化案例存档 + 检索",
        "detail": "把诊断报告（及后续项目文档包）打包成可打印/可发客户的交付物，结构化存档（标签），跨案例检索（Agent 记忆基础）。",
        "spec": "输入：诊断 run_id 或项目上下文。输出：deliverable.html/pdf + archive.json。",
        "needs_review": "否（内容来自已确认产出）",
        "cases_query": "诊断",
        "api": ["/cases/create", "/cases", "/cases/search", "/cases/create-crop", "/cases/create-doc-package"],
    },
    "projects": {
        "key": "projects",
        "name": "项目档案",
        "intro": "以项目为中心保存完整过程记录（诊断/会议/现场问题/迭代/交付物时间线）",
        "detail": "解决「文件多、找不到」痛点：诊断定稿、案例生成自动挂项目；会议/现场问题手动追加；项目工作流进度展示。v7.0 项目作战台：一个项目打开，诊断/数据作战流/映射/交付物/资产/RAG/工作流进度/时间线全部真实拉齐，分区可一键跳转续做；v10.0 质量门禁真阻断（数据未达标 403/未确认 400）。",
        "spec": "输入：项目名 + 客户 + 事件。输出：项目时间线 + 工作流状态 + warroom 聚合视图。",
        "needs_review": "否",
        "cases_query": "",
        "api": ["/projects", "/projects/{pid}", "/projects/{pid}/events", "/projects/{pid}/warroom"],
    },
    "mapping": {
        "key": "mapping",
        "name": "字段映射工作台",
        "intro": "集成工作流：LLM 初判 + 导入真实样例 + 实跑校验(pass/warn/fail+理由) + 人工修正迭代 + 导出适配器 + 断点续接",
        "detail": "直击 FDE 阶段④适配器/字段映射（占技术量 60-70%）：LLM 基于字段名/示例初判映射，人工可改；把真实源样例 CSV 丢进去实跑 transform，逐字段生成映射值并 LLM 校验正确性，失败可修正重跑到达标再导出适配器；任务按 run_id 存档（样例/校验结果可续接）并挂项目档案。导出适配器后自动注册为可复用映射配置资产（新任务可一键接入）。",
        "spec": "输入：源/目标字段列表 + 真实样例 CSV。输出：映射建议 + 实跑校验报告（逐字段 + 成功率）+ adapter.py/配置 + run_id。",
        "needs_review": "建议人工复核映射",
        "cases_query": "映射",
        "api": ["/mapping/create", "/mapping/runs", "/mapping/{run_id}", "/mapping/{run_id}/update",
                "/mapping/{run_id}/samples", "/mapping/{run_id}/validate", "/mapping/{run_id}/validate-row",
                "/mapping/{run_id}/export"],
    },
    "annotation": {
        "key": "annotation",
        "name": "数据标注管理",
        "intro": "人工双人标注工作台 → 一致性 → 评测集构建",
        "detail": "人工双人标注工作台：每样本两列（标注员 A / B）分别存标签，逐行一致性（未标/仅A/仅B/一致/分歧），分歧可改判到一致；可从数据作战流 cleaned_data 建任务（source 诚实标注），一致样本进评测集，分歧单独列出待复核；list_tasks 按 mtime 倒序。",
        "spec": "输入：待标注样本（手动粘贴 或 数据作战流 cleaned_data 前 N 条）。输出：一致性统计 + 每样本 consistency 明细 + eval_set.json。",
        "needs_review": "否",
        "cases_query": "标注",
        "api": ["/annotation/create", "/annotation/from-dataprep", "/annotation/runs", "/annotation/{run_id}", "/annotation/{run_id}/label", "/annotation/{run_id}/build-eval"],
    },
    "kb": {
        "key": "kb",
        "name": "知识库构建",
        "intro": "长文本分块 + 质检（RAG 最小件）",
        "detail": "文档分块（滑动窗口带重叠）+ 质检（空块/重复/过短/超长），为 RAG 知识库提供最小件；向量化可接 ChromaDB。",
        "spec": "输入：文档文本。输出：chunks + quality 报告。",
        "needs_review": "否",
        "cases_query": "",
        "api": ["/kb/chunk"],
    },
    "retrieval": {
        "key": "retrieval",
        "name": "RAG 检索问答",
        "intro": "知识库分块 → 向量化(ChromaDB) → 检索 → 问答(带引用)",
        "detail": "打通「数据作战流知识库产物 → 索引 → 检索 → 带引用问答」闭环：分块索引进 ChromaDB（真实向量化，本机已缓存 MiniLM 离线可用），query 向量检索 top_k 相关分块，RAG 问答基于知识库内容回答并标注引用分块；知识库不足以回答时诚实说不知道。",
        "spec": "输入：kb_run_id + 知识库分块（或数据作战流 run_id 自动读取其 knowledge_base 产物）。输出：collection/chunk_count + 检索 hits + {answer, sources}。",
        "needs_review": "否",
        "cases_query": "RAG",
        "api": ["/retrieval/index", "/retrieval/query", "/retrieval/indexed"],
    },
    "assets": {
        "key": "assets",
        "name": "可复用资产库",
        "intro": "资产库:项目越多、工具越强",
        "detail": "注册表 tmp/web/assets/registry.json；diagnosis/dataprep/mapping 自动入库（幂等）；新任务 related_assets 自动带出（规则评分 + reason）；一键接入 adopt（mapping_config 预填新 run / 数据资产复制到目标 run / 交付物登记引用）；挂项目 asset_reuse 事件。",
        "spec": "输入：自动注册（诊断定稿/数据作战流沉淀/映射导出）或检索关键词/类型/客户。输出：资产列表/检索/建议 + adopt 接入结果。",
        "needs_review": "否",
        "cases_query": "资产",
        "api": ["/assets/list", "/assets/search", "/assets/suggest", "/assets/{asset_id}", "/assets/{asset_id}/adopt"],
    },
}


def get_manifest(key: str) -> dict:
    m = MANIFESTS.get(key)
    if not m:
        raise KeyError(f"未知模块: {key}")
    return m


def list_manifests() -> list:
    """返回所有模块 manifest（自动聚合，供操作台说明/API 文档生成）"""
    return list(MANIFESTS.values())
