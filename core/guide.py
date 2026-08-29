"""功能说明层：长篇参考文献式使用指南 + 连贯工作流叙事 + 动态使用建议

每一部分都写成完整长文（定位/场景/前置/详细步骤/输入输出/参数/衔接/常见问题），
不是一两句话——让 FDE 真正能照着上手。文本人工维护（Q23）。
"""

# =====================================================================
# 一、每模块长篇使用指南
# =====================================================================

MODULE_GUIDES = {
    "diagnosis": {
        "name": "需求诊断",
        "position": "FDE 工作流阶段①。把客户说不清、头脑中比写出来复杂 10 倍的需求，通过多 Agent 对抗评审 + 人工复核，压成一份客户能拍板、能打印的正式报告。",
        "scenario": "适用场景：任何「要不要做 AI / 值不值得做 / 该往哪个方向投入」的决策时刻；尤其适合需要反复和客户对齐、客户自己也说不清需求的现场。",
        "prerequisites": "前置条件：1) .env 已配置 DEEPSEEK_API_KEY（诊断调真实 DeepSeek）；2) 对客户需求有一份尽量完整的文字描述（现状、目标、约束、数据来源、用户规模、验收人）。",
        "steps": [
            {"title": "① 输入需求", "detail": "在「客户需求描述」里写完整：业务现状、想解决的痛点、期望产出、数据情况（有无、质量、格式）、用户量、部署约束（本地/云、网络）、验收人。写得越全，Generator 打分越准，Critic 也越能查出遗漏。"},
            {"title": "② 看对抗评审结果", "detail": "Generator 独立打分给出理由；Critic 盲审独立再打分，两者不一致处就是分歧（低置信维度会进「需确认」清单）。重点看：Critic 标出的「未覆盖需求要点 / 矛盾 / 过度自信」——这些是客户没说清、需要你追问的地方。"},
            {"title": "③ 人工复核打分 + Reviewer 再评", "detail": "基于 Generator 分做人工调整（可改分数、写人工理由），提交后 Reviewer 盲审人工分：逐维「同意 / 修正」，并检测整体偏置（如人工系统性偏高）。分歧本身是过程信息，会保留进报告。"},
            {"title": "④ 强制确认 → 定稿", "detail": "不勾选「我已人工确认」不能生成正式报告。确认后产出 v 版定稿报告（含置信度/分歧/最终结论/建议）。"},
            {"title": "⑤ 生成可打印交付物", "detail": "在「案例 / 交付物」面板点「把当前诊断生成交付物」，得到 HTML/PDF 版报告，可打印或直接发给客户。"},
            {"title": "⑥ 客户反馈 → 下一版", "detail": "客户看完报告返回意见：上传反馈文件（txt/pdf）或粘贴文本 → 系统提炼成「客户意见条目」→ 增量重评只改受影响的维度 → 生成 v2（带相对上一版变更清单）→ 再发客户确认。这是完整的版本循环。"},
        ],
        "io": "输入：需求文本 + 可选自定义中立提示词 + 客户反馈文件。输出：v 版定稿报告 + HTML/PDF 交付物 + run_id 档案（tmp/web/diagnosis/<run_id>/archive.json）。",
        "params": "关键参数：评估提示词（默认严格中立，可自定义，改动后报告标注「提示词已修改」）；置信度 = Generator 与 Critic 一致度（≥0.8 高 / 0.6-0.8 中 / <0.6 低→强制确认）。",
        "handoff": "产出衔接：定稿报告自动挂到项目档案；可「从诊断带入五步裁剪」预填约束；可生成交付物发给客户；客户反馈驱动 v2/v3 版本循环。",
        "pitfalls": "常见问题/坑：1) 需求写得太短 → 打分与遗漏都不可靠，尽量写全；2) 未配置 key → 自动降级为规则兜底（结果标注「规则兜底」，不是 AI 评估）；3) 语义去重等模型依赖需本地预置；4) 客户反馈没上传就生成 v2 → 系统会提示「尚无客户反馈」。",
        "example": "示例：给「医院病案室基于病历的智能归档分类」做诊断 → 5 维打分 + Critic 指出「未覆盖标注质量/准确率目标」→ 人工复核把生成性下调 → 生成 PDF 发给信息科主任 → 主任反馈「准确率要求 95%」→ 增量重评 v2。",
    },
    "cropper": {
        "name": "五步裁剪",
        "position": "FDE 工作流阶段①→④ 的决策枢纽。根据客户约束（预算/硬件/环境/数据/用户/合规），五步裁剪出「该上哪些模块、删掉哪些、怎么简化、怎么排期」。",
        "scenario": "适用场景：诊断之后，决定这个客户到底上哪几个模块、方案怎么简化。是「客户掰扯 → 方案」的关键一步。",
        "prerequisites": "前置条件：最好先做一次需求诊断（可从诊断结论带入，自动预填预算）；否则至少知道客户预算、硬件、网络、数据量、用户数。",
        "steps": [
            {"title": "① 录入客户约束", "detail": "基础（客户ID/预算/周期）、硬件（CPU/内存/GPU/存储）、环境（OS/是否Docker/网络/外网/带宽）、数据（总量/日新增/格式/质量）、用户（总数/并发）、合规（驻留/PII/等级）。逐项如实填。"},
            {"title": "② 从诊断带入（推荐）", "detail": "在下方「接线：诊断结论 → 裁剪预填」填诊断 run_id（或留空用最近一次），系统按诊断总分自动预填预算（<10 分→2 万保守裁剪；≥20 分→20 万全量），并可人工改。"},
            {"title": "③ 生成裁剪方案", "detail": "五步执行：质疑每项需求 → 删除能删的模块（预算<3 万删 monitor/flywheel/deploy；数据<1000 删 flywheel；用户<5 删 monitor 等）→ 简化保留模块（无 GPU 只留 ReAct、本地模型；带宽低监控/飞轮转批量）→ 加速给排期 → 建议自动化项。"},
            {"title": "④ 生成交付物", "detail": "点「把该方案生成交付物」→ HTML/PDF 版本，发给客户确认启用模块与简化方案。"},
        ],
        "io": "输入：客户约束（CustomerConstraints）+ 可选诊断 run_id。输出：启用/删除模块、简化配置、自动化建议、排期建议 + 可打印交付物。",
        "params": "关键规则（当前为「起点模板」，人工可改）：budget<30000 删 monitor/flywheel/deploy；total_records<1000 删 flywheel；total_users<5 删 monitor；无 GPU 只保留 ReAct + 本地模型；带宽<50Mbps 监控/飞轮降级批量；合规 critical 且无 GPU 删原型组装器。",
        "handoff": "产出衔接：方案可生成交付物挂项目档案；按「启用模块」清单逐个推进数据准备→原型→部署；历史裁剪方案沉淀为案例供下次参考。",
        "pitfalls": "常见问题/坑：1) 约束是死规则当起点，客户场景特殊必须人工改；2) 从诊断带入只预填预算，其他约束仍需人工填；3) 方案删模块不代表客户不能加回，最终以客户确认为准。",
        "example": "示例：预算 5 万、数据 500 条、3 个用户的客户 → 自动删 data_flywheel 和 monitor，原型只留 ReAct 本地模型 → 生成 PDF 给客户确认。",
    },
    "data_prep": {
        "name": "数据准备",
        "position": "FDE 工作流阶段②，最重的基石（占现场 30-40% 时间）。把客户「又脏又乱」的数据洗成高质量资产，并构建评测集。",
        "scenario": "适用场景：任何 AI 项目启动前；尤其数据格式混乱、重复多、含 PII、需要评测集的时候。原则：数据准备好之前不进原型。",
        "prerequisites": "前置条件：数据文件（csv/json/pdf）或数据库连接串；语义去重需要本地已缓存 ChromaDB 模型（约 79MB）。",
        "steps": [
            {"title": "① 上传数据，跑完整管道", "detail": "选择 csv/json/pdf 文件 + 设置评测集样本数，点「上传并运行」。管道 = 接入 → 质量评估 → 清洗（字符级去重 + 语义去重 + 异常过滤 + PII 脱敏）→ 评测集构建。"},
            {"title": "② 看质量报告与统计", "detail": "结果展示原始/清洗后/评测集条数 + 质量报告（重复率/PII 类型/覆盖度）。重点确认清洗后的数据没被误删。"},
            {"title": "③ 需要人工标注 → 标注管理", "detail": "下方「人工标注工作台」建任务（可手动粘贴，或从数据作战流 cleaned_data 建任务），每样本两列（标注员 A/B）分别打标签，逐行一致性，分歧改判到一致后构建评测集（一致样本进评测集）。"},
            {"title": "④ RAG 场景 → 知识库分块", "detail": "数据作战流「知识库」步骤分块 + 质检后自动索引（ChromaDB，显示「已索引 · RAG 就绪」），即可到 ④ 原型 tab 选该知识库做检索问答。"},
        ],
        "io": "输入：数据文件或源路径 + 标注样本 + 文档文本。输出：cleaned_data.json / eval_set.json / quality_report.json / cleaning_stats.json；标注一致性统计 + eval_set；知识库分块 + 质检 + ChromaDB 索引。",
        "params": "关键参数：eval_samples（评测集样本数）；语义去重阈值（0.85）；分块大小/重叠。产物在 output_dir。",
        "handoff": "产出衔接：清洗后数据与评测集 → 原型验证；标注一致样本 → 评测集；质检通过的分块 → 自动索引进检索（RAG 就绪，④ 原型可选该知识库做检索问答）。v1.11.0 起「数据未达标不进原型」门禁判定为：数据作战流 run 的 quality_report 产物真实存在（数据被真实评估过＝达标）；④ 原型 tab 绑定项目后运行前会显示该门禁状态（未过需人工勾选「强制继续」）。",
        "pitfalls": "常见问题/坑：1) 语义去重首次运行需联网下载 79MB 模型，内网需预置；2) 扫描版 PDF 会被自动跳过（提示）；3) 数据全短句时异常过滤可能误删，注意看清洗统计。",
        "example": "示例：上传 3 万条工单 CSV → 清洗去掉 1200 条重复/PII → 建 200 条双人标注 → 165 条一致进评测集 → 质检通过的知识库分块供 RAG 使用。",
    },
    "prototype_assembler": {
        "name": "现场原型",
        "position": "FDE 工作流阶段③。用真实数据快速验证核心假设（1-2 周内）；四个模板（知识问答 / 信息抽取 / 多步推理 / 反思型）全部真调 DeepSeek，其中 knowledge_qa 可基于客户知识库做 RAG 检索问答（带引用）验证「基于客户文档的问答」这个最主流假设。",
        "scenario": "适用场景：数据就绪后验证「这个 AI 方案在客户数据上到底行不行」；尤其基于客户文档的 RAG 问答、结构化信息抽取、多步推理、需自检修正的生成任务。",
        "prerequisites": "前置条件：已配置 DEEPSEEK_API_KEY；数据准备阶段产出的样本/知识库（已索引，RAG 就绪）。",
        "steps": [
            {"title": "① 选模板", "detail": "四个模板均真调 DeepSeek（下拉旁标注「真调 DeepSeek」，知识问答另标「RAG 就绪」）。信息抽取返回结构化实体，多步推理按计划分步求解，反思型先作答再自检修正。"},
            {"title": "② 选知识库（可选）", "detail": "选一个已索引知识库（来自 ③ 数据作战流 knowledge_base 步骤自动索引，或手动索引）→ knowledge_qa 走 RAG 检索问答。"},
            {"title": "③ 输入问题运行", "detail": "输入客户真实问题，点「运行原型」。返回真实 DeepSeek 回答；RAG 问答基于知识库分块回答并带引用（引用分块展示在结果下方）。LLM 调用失败时结果区诚实提示（不装成功）。"},
            {"title": "④ 迭代", "detail": "基于回答质量调整提示词、分块参数或知识库内容，再跑。短迭代验证是阶段③的关键。"},
        ],
        "io": "输入：模板名 + 用户输入 + 可选 kb_run_id。输出：Agent 运行结果字符串 + llm_mode +（RAG）引用分块 sources。",
        "params": "关键参数：模板；llm_call / plan_generator / step_executor / answer_generator（可注入自定义函数）；kb_run_id（走 RAG）；top_k（默认 5）。",
        "handoff": "产出衔接：假设验证通过 → 部署集成；真实调用自动计入 monitor 成本看板。",
        "pitfalls": "常见问题/坑：1) 原型回答不等于生产质量，别把 demo 当交付；2) RAG 需先索引知识库，未索引会 404；3) 未配置 DEEPSEEK_API_KEY 时模板诚实降级（返回错误说明），配置后即可真调。",
        "example": "示例：设备运维手册索引后问「E001 故障如何排查？」→ 回答带引用分块；或对故障工单跑信息抽取模板，得到「设备E001 | 设备 | 状态=运行中」这类结构化实体。",
    },
    "deploy_hardener": {
        "name": "部署加固",
        "position": "FDE 工作流阶段④。生成 Docker/裸机部署配置 + 降级预案 + 部署前环境检查；配合字段映射应对系统集成。",
        "scenario": "适用场景：方案验证通过后落地生产环境；客户有 Docker 或只能裸机部署时。",
        "prerequisites": "前置条件：.env 已配置 POSTGRES_*/REDIS_URL/CHROMA_*（部署前检查需要）。",
        "steps": [
            {"title": "① 选部署模式", "detail": "docker-compose（生成 compose + Dockerfile + degradation.yaml）或 bare-metal（生成 systemd 服务）。"},
            {"title": "② 生成配置", "detail": "点「生成部署配置」，产物写入服务器磁盘，可下载。部署前会自动做环境变量检查（缺失即报错）。"},
            {"title": "③ 系统集成 → 字段映射", "detail": "现场最痛的是适配器/字段映射（占技术量 60-70%）：到 ⑨ 字段映射工作台，LLM 初判映射、人工调整、导出适配器代码。"},
        ],
        "io": "输入：project_dir + 部署模式 + 镜像名/应用路径。输出：docker-compose.yml / Dockerfile / degradation.yaml / systemd 服务。",
        "params": "关键参数：mode（docker-compose / bare-metal）；image_name；app_path。",
        "handoff": "产出衔接：部署配置 → 上线；映射适配器 → 系统集成；上线后 monitor 看成本。",
        "pitfalls": "常见问题/坑：1) 部署前检查会因缺环境变量报错，先确保 .env 齐全；2) Dockerfile 写入临时项目目录，不会污染仓库根。",
        "example": "示例：客户内网隔离 + 无 GPU → 生成 bare-metal systemd 服务 + 本地模型部署配置。",
    },
    "monitor": {
        "name": "监控面板",
        "position": "贯穿整个 FDE 过程的成本/健康看板：真实 LLM 用量（调用/token/成本）自动来自 core/llm.py 计费打点，不是手动编造。",
        "scenario": "适用场景：向客户/内部汇报本工具用了多少模型成本；排查 LLM 调用失败。",
        "prerequisites": "无需额外配置；LLM 调用自动计入。",
        "steps": [
            {"title": "① 看真实 LLM 用量", "detail": "「真实 LLM 用量（计费打点）」卡片：调用数/成功/失败/Token/成本，按模型分布。这是自动数据，用于成本汇报。"},
            {"title": "② 补充手动记录", "detail": "可手动记录一次调用（成功/延迟/token/模型）作为补充指标。"},
            {"title": "③ 看告警", "detail": "错误率<95%、P99>3000ms、降级次数>0 会触发告警。"},
        ],
        "io": "输入：LLM 自动打点 + 手动 record_request。输出：指标/告警/真实用量与成本。",
        "params": "关键参数：MODEL_PRICES（元/百万 token，可据实调整）。",
        "handoff": "产出衔接：成本数据用于交付汇报；失败告警提示排查 key/网络。",
        "pitfalls": "常见问题/坑：1) 手动指标是内存存储，重启清空；2) 真实用量是进程内累计，重启清空。",
        "example": "示例：跑完一次诊断（3 次调用）→ 真实成本约 0.004 元（deepseek-chat）。",
    },
    "data_flywheel": {
        "name": "数据飞轮",
        "position": "让线上反馈回流成评测集与可复用资产，形成「反馈→标注→评测→改进」闭环。",
        "scenario": "适用场景：原型/生产上线后收集用户反馈，持续改进。",
        "prerequisites": "已有线上反馈或人工审核结果。",
        "steps": [
            {"title": "① 记录反馈", "detail": "填 request_id/用户输入/模型输出/类型（dislike/audit_fail/low_confidence）/备注，进标注池。"},
            {"title": "② 更新评测集", "detail": "用标注池更新评测集（需已有 eval_set.json）。"},
            {"title": "③ 导出资产", "detail": "把可复用组件/模板导出为资产清单（project_assets.json）。"},
        ],
        "io": "输入：反馈记录。输出：标注池 / 评测集更新 / 资产清单。",
        "params": "关键参数：feedback_type；num_samples。",
        "handoff": "产出衔接：评测集 → 数据准备；资产 → 案例库沉淀。",
        "pitfalls": "常见问题/坑：1) 标注池默认 JSON 文件持久化，重启不丢；2) 评测集更新需先有 eval_set.json。",
        "example": "示例：100 条 dislike 反馈 → 标注池 → 20 条进评测集更新。",
    },
    "cases": {
        "name": "案例/交付物",
        "position": "把诊断/裁剪/文档包等产出，打包成可打印、可发给客户、可检索复用的交付物——这是「用真实落地项目建立说服力」的核心层。",
        "scenario": "适用场景：任何要「拿给客户看」的产出（报告/方案/文档包）；积累可复用的历史案例。",
        "prerequisites": "已有定稿的诊断 run_id（或裁剪方案/项目）。",
        "steps": [
            {"title": "① 生成交付物", "detail": "诊断定稿后点「把当前诊断生成交付物」→ HTML/PDF；裁剪方案/项目文档包同理。"},
            {"title": "② 查看/下载", "detail": "打开 HTML（可直接浏览器打印成 PDF）或下载 PDF。"},
            {"title": "③ 检索复用", "detail": "案例库按关键词/标签检索，下次交付自动带出相关案例（诊断 start 时自动带出）。"},
        ],
        "io": "输入：诊断 run_id / 裁剪方案 / 项目上下文。输出：deliverable.html/pdf + archive.json（带标签）。",
        "params": "关键参数：tags（自动生成：来源/版本/结论）。",
        "handoff": "产出衔接：交付物自动挂项目档案；案例沉淀供检索复用（Agent 记忆基础）。",
        "pitfalls": "常见问题/坑：1) PDF 生成需本机 Chrome（无则回退 HTML，浏览器可打印）；2) 案例检索是文本匹配，复杂语义检索二期。",
        "example": "示例：诊断 v1 定稿 → 生成 PDF 发给客户 → 下次相似需求诊断时自动带出该案例。",
    },
    "projects": {
        "name": "项目档案",
        "position": "以项目为中心保存完整过程记录（诊断/会议/现场问题/迭代/交付物），解决「文件多、找不到」；同时展示工作流进度与门禁。",
        "scenario": "适用场景：每个现场项目建一个档案，所有过程/产物有去处；复盘时能完整回溯。",
        "prerequisites": "可空项目；诊断/案例会自动挂进来。",
        "steps": [
            {"title": "① 创建项目", "detail": "填项目名 + 客户。诊断定稿/案例生成会自动创建/复用同客户项目并挂事件。"},
            {"title": "② 追加过程记录", "detail": "会议/现场问题/迭代等，选类型 + 标题 + 详情 + ref（run/case id）追加到时间线。"},
            {"title": "③ 看工作流进度", "detail": "自动展示 5 阶段状态与门禁（诊断确认/数据达标/文档包确认）。"},
            {"title": "④ 打开作战台", "detail": "项目作战台（warroom）一个视图拉齐全部产物：诊断/数据任务/映射/交付物/资产/RAG 分区，各区一键跳转续做；顶部看工作流进度与门禁（未过显示「门禁未过：reason」）。"},
            {"title": "⑤ 生成项目文档包", "detail": "LLM 起草架构/API 文档/运维手册/SOP → HTML/PDF，给客户交接用。"},
        ],
        "io": "输入：项目名 + 事件。输出：项目时间线 + 工作流状态 + 文档包。",
        "params": "关键参数：事件类型（meeting/issue/iteration/note/diagnosis/case）。",
        "handoff": "产出衔接：项目 = 完整留痕 + 交付物 + 工作流；文档包进案例库。",
        "pitfalls": "常见问题/坑：1) 同一客户的项目会自动复用（按客户名匹配），如需多项目请改客户名；2) 文档包内容依赖项目事件/诊断上下文，事件记得记全。",
        "example": "示例：诊断定稿自动建「制造客户 项目」→ 追加会议/现场问题 → 生成文档包给客户。",
    },
    "mapping": {
        "name": "字段映射工作台",
        "position": "应对 FDE 阶段④最痛的适配器/字段映射（占技术量 60-70%）：LLM 初判映射 → 导入真实样例 → 实跑校验 → 人工修正迭代 → 导出适配器代码。",
        "scenario": "适用场景：要对接客户老旧系统、做字段映射/数据转换/写适配器时；现场高频刚需。",
        "prerequisites": "知道源字段和目标字段（字段名 + 示例值）；最好有真实源数据 CSV（列名=源字段名）用于实跑校验。",
        "steps": [
            {"title": "① 填源/目标字段", "detail": "每行「字段名|示例值」，如 customer_name|张三。目标字段同理。"},
            {"title": "② LLM 初判", "detail": "系统让 LLM 基于字段名/示例值建议映射（含规则类型与置信度）。"},
            {"title": "③ 人工调整", "detail": "逐行改目标/源/规则/表达式，保存（run_id 断点续接，可中断再回来）。"},
            {"title": "④ 导入真实样例", "detail": "上传真实源数据 CSV（列名=源字段名），系统存档案（原始行数 + 预览）。"},
            {"title": "⑤ 试运行校验", "detail": "系统对每条映射实跑 transform 生成映射值，LLM 校验每条映射 pass/warn/fail + 理由，汇总成功率（逐字段）。"},
            {"title": "⑥ 修正重跑", "detail": "失败的映射改源/规则/表达式 → 保存 → 再试运行校验，直到成功率达标。"},
            {"title": "⑦ 导出适配器", "detail": "导出 mapping_config.json + adapter.py（含 transform 函数），接到你的集成代码。"},
        ],
        "io": "输入：源/目标字段列表 + 真实样例 CSV。输出：映射建议 + 实跑校验报告（逐字段 + 成功率）+ 适配器配置/代码 + run_id。",
        "params": "关键参数：规则（direct/concat/split/lookup/formula/other）；校验抽样行数（默认 20）。",
        "handoff": "产出衔接：适配器 → 部署集成；校验通过的映射配置可沉淀为可复用映射组件。",
        "pitfalls": "常见问题/坑：1) LLM 初判按字段名/示例猜，复杂转换需人工补公式；2) concat 用「+」分隔源字段名；3) lookup/other 规则需人工实现，实跑会判 fail 并提示；4) 样例 CSV 列名必须等于源字段名。",
        "example": "示例：源 full_address|北京市… → 目标 address → direct 映射；源 name+phone → 目标 contact → concat；上传真实订单 CSV 实跑校验成功率。",
    },
    "annotation": {
        "name": "数据标注管理",
        "position": "人工双人标注工作台 → 一致性检测 → 评测集构建。数据质量决定模型上限，评测集决定能否衡量。",
        "scenario": "适用场景：需要构建带标注的评测集、或验证标注一致性时。",
        "prerequisites": "待标注样本（手动粘贴每行一条，或从数据作战流 cleaned_data 产物前 N 条）。",
        "steps": [
            {"title": "① 建标注任务", "detail": "手动粘贴样本，或从数据作战流建任务（下拉选 run + 样本数，样本源诚实标注）。"},
            {"title": "② 双人打标签", "detail": "每样本两列：标注员 A / 标注员 B 分别存各自的标签；可覆盖。"},
            {"title": "③ 看一致性", "detail": "逐行徽标（未标/仅A/仅B/一致✅/分歧⚠️）；顶部一致性统计（一致 N / 分歧 M / 未标 K）。"},
            {"title": "④ 分歧处理", "detail": "分歧样本单独列出（两标注员标签对照），给任一标注员改标签后保存，重算一致性直到一致。"},
            {"title": "⑤ 构建评测集", "detail": "点「构建评测集」输出 eval_set.json（instruction/content + output/标签），一致样本进评测集、分歧不进。"},
        ],
        "io": "输入：样本 + 标签。输出：一致性统计 + 每样本 consistency 明细 + eval_set.json。",
        "params": "关键参数：标签由人工填；一致性要求 ≥2 人同标签；分歧需改判到一致。",
        "handoff": "产出衔接：一致样本 → 评测集 → 数据准备/飞轮；从数据作战流建任务时样本来自 cleaned_data。",
        "pitfalls": "常见问题/坑：1) 单标签样本不算一致（需 ≥2 人）；2) 分歧样本不进评测集，需人工复核改判；3) 数据作战流「标注」步骤是规则自动打标（流水线便利），要精标请到人工标注工作台。",
        "example": "示例：3 条工单 → A/B 标注 → 1 条一致（物流）、1 条分歧（退款/物流）→ 分歧改判 → 一致进评测集。",
    },
    "kb": {
        "name": "知识库构建",
        "position": "RAG 场景的基础：把长文档分块（带重叠）+ 质检（空块/重复/过短/超长），为后续向量化/检索做准备。",
        "scenario": "适用场景：搭建基于文档的问答（RAG）前，把客户文档切成合理分块。",
        "prerequisites": "长文档文本。",
        "steps": [
            {"title": "① 粘贴文档", "detail": "把长文档内容粘贴进来。"},
            {"title": "② 设置分块参数", "detail": "分块大小（默认 500 字符）+ 重叠（默认 50）。"},
            {"title": "③ 看质检报告", "detail": "空块/重复/过短（<20 字）/超长（>2000 字）统计与问题清单。"},
        ],
        "io": "输入：文档文本。输出：chunks + quality 报告。",
        "params": "关键参数：chunk_size / overlap。",
        "handoff": "产出衔接：质检通过的分块 → 接 ChromaDB 向量化 → RAG 检索。",
        "pitfalls": "常见问题/坑：1) 分块太大会切碎语义，太小会碎片化；2) 重复内容会被标记，先清洗再入库。",
        "example": "示例：50KB 运维手册 → 120 块（大小 500/重叠 50）→ 检出 3 块重复，去重后入库。",
    },
    "retrieval": {
        "name": "RAG 检索问答",
        "position": "RAG 场景的核心链路：把知识库分块向量化（ChromaDB）→ 检索 → 基于知识库问答（带引用）。数据作战流「知识库」步骤完成后自动索引，RAG 就绪。",
        "scenario": "适用场景：搭建「基于客户文档的问答」——用真实文档验证 RAG 核心假设（原型阶段最主流场景）。",
        "prerequisites": "知识库分块（kb.service 产出，或数据作战流 knowledge_base 步骤产物）；ChromaDB 已装且默认嵌入模型已缓存（~/.cache/chroma/onnx_models，内网需预置）。",
        "steps": [
            {"title": "① 造分块", "detail": "在 ③ 数据作战流跑完 knowledge_base 步骤（自动索引，显示「已索引 · RAG 就绪」）；或用 ④ 原型 tab 的「手动索引」直接粘贴分块。"},
            {"title": "② 选择知识库", "detail": "④ 原型 tab 顶部下拉会自动列出已索引的知识库（kb_run_id · 块数 · 时间）。"},
            {"title": "③ 输入问题运行", "detail": "选 knowledge_qa 模板 + 知识库 + 真实问题 → 运行：回答基于知识库分块并带引用（[1][2]…），下方展示引用分块；知识库不足以回答时模型会诚实说不知道。"},
        ],
        "io": "输入：kb_run_id + 分块（或数据作战流 run_id）。输出：检索 hits（chunk/score/source）+ 带引用回答 + 引用分块。",
        "params": "关键参数：top_k（默认 5）；collection 名 kb_<run_id>；档案 tmp/web/retrieval/<kb_run_id>/archive.json。",
        "handoff": "产出衔接：检索命中 → RAG 问答；引用分块可人工核对；原型验证通过 → 部署集成。",
        "pitfalls": "常见问题/坑：1) 过短分块（<20 字）会在索引时过滤（否则嵌入向量泛化导致排序失真）；2) 未索引就 query 会 404 提示先索引；3) 语义相似但无关的块也可能被召回，答案是否可信靠模型判断 + 引用分块人工核对。",
        "example": "示例：设备运维手册分块 → 索引 kb_ops_001 → 问「E001 故障如何排查？」→ 召回含 E001 的分块 → 回答「电源模块异常，先查电源线/适配器电压 [1]」。",
    },
    "core": {
        "name": "统一底座",
        "position": "所有模块共享的地基：配置/安全/日志/版本/降级/模块注册 + 统一 LLM 客户端（计费打点）。",
        "scenario": "适用场景：无需单独操作；但改配置、排查 LLM 调用失败时要知道它的存在。",
        "prerequisites": "无。",
        "steps": [
            {"title": "① 配置", "detail": "改 .env（数据库/模型 key/日志/端口），重启进程生效。敏感配置只走环境变量。"},
            {"title": "② LLM 调用", "detail": "所有模块统一走 core/llm.py，自动记录每次调用 token/耗时/成本（喂 monitor）。"},
            {"title": "③ 排查", "detail": "LLM 调用失败看 /tmp/webui_server.log 或 monitor 失败计数。"},
        ],
        "io": "输入：环境变量/请求。输出：配置单例/日志/LLM 文本或 JSON。",
        "params": "关键参数：.env 的 DEEPSEEK_API_KEY/BASE_URL/DEFAULT_MODEL/API_PORT 等。",
        "handoff": "产出衔接：底座贯穿所有模块。",
        "pitfalls": "常见问题/坑：1) 未配置 key 时诊断/映射会降级兜底；2) 端口默认 8100。",
        "example": "无。",
    },
}


# =====================================================================
# 二、连贯工作流（长篇阶段叙述）
# =====================================================================

WORKFLOW_PHASES = [
    {
        "phase": 1, "name": "需求诊断",
        "goal": "把客户说不清的需求，压成一份客户能拍板、能打印的正式报告。",
        "narrative": "这是整个交付的「地基」。客户嘴上说的往往不是真实痛点，人脑里想的比写出来的复杂 10 倍。多 Agent 对抗评审（Generator 打分 + Critic 盲审）负责挖出分歧和遗漏，人工复核负责把你从现场听来的、文本之外的信息补进去，强制确认保证「发给客户前一定看过」。产出 v 版报告 + 可打印交付物。",
        "modules": ["diagnosis"],
        "how": "输入尽量完整的需求 → 看 Generator/Critic 分歧与置信度 → 人工复核打分（补现场信息）→ Reviewer 再评 → 强制确认定稿 → 生成交付物发给客户 → 客户反馈回来上传 → 增量重评 v2…",
        "io": "输入：需求文本 + 客户反馈。产出：定稿报告 + HTML/PDF 交付物。",
        "gate": "发客户前必须人工确认",
        "handoff": "衔接：报告自动挂项目档案；可「从诊断带入裁剪」决定上哪些模块。",
        "pitfalls": "常见问题：需求写太短打分失真；未配 key 会规则兜底；客户反馈需上传才触发 v2。",
    },
    {
        "phase": 2, "name": "数据准备",
        "goal": "把脏数据洗成高质量资产并建评测集；数据未达标不进原型。",
        "narrative": "数据准备占现场 30-40% 时间，是隐藏的「大胃王」，也是决定模型上限的第一性。数据作战流 6 步（导入→清洗→质量→标注→评测集→知识库）+ run_id 断点续接（刷新/重连不丢）+ 知识库自动索引 RAG 就绪；人工双人标注工作台（标注员 A/B/一致性/分歧处理）产出最可靠的评测集。质量报告和评测集覆盖率是你判断「能不能进原型」的依据。",
        "modules": ["dataprep", "data_prep", "annotation", "kb"],
        "how": "建数据作战流任务上传数据 → 顺序推进 清洗/质量/标注/评测集/知识库（断点续接）→ 需要精标就到人工双人标注工作台（A/B 一致性 → 分歧改判 → 评测集）→ 知识库步骤完成后自动索引 → 数据达标（有质量报告）后进原型。",
        "io": "输入：数据文件/样本/文档。产出：清洗数据 + 评测集 + 知识库分块。",
        "gate": "数据未达标不进原型",
        "handoff": "衔接：清洗数据与评测集 → 原型验证；质检分块 → 向量化。",
        "pitfalls": "常见问题：语义去重需预置模型；扫描版 PDF 跳过；短文本易被异常过滤误删。",
    },
    {
        "phase": 3, "name": "现场原型",
        "goal": "用真实数据在 1-2 周内验证核心假设。",
        "narrative": "数据就绪后，原型可以在 1-2 天内拉起。四个模板（知识问答 / 信息抽取 / 多步推理 / 反思型）全部真调 DeepSeek，直接问客户真实问题看回答质量。这个阶段的价值是「用最小成本验证假设」，不是交付生产。",
        "modules": ["prototype_assembler"],
        "how": "选模板（4 模板均真调 DeepSeek；knowledge_qa 可走 RAG）→ 输入客户真实问题 → 看回答质量 → 迭代。",
        "io": "输入：模板 + 问题。产出：验证结论。",
        "gate": None,
        "handoff": "衔接：假设验证通过 → 部署集成。",
        "pitfalls": "常见问题：原型回答不等于生产质量，别把 demo 当交付；未配置 DEEPSEEK_API_KEY 时模板诚实降级（返回错误说明）。",
    },
    {
        "phase": 4, "name": "部署集成",
        "goal": "把验证方案整合进客户生产系统（配置 + 适配器/映射）。",
        "narrative": "真正难的从来不是 demo，而是拿数据、搞权限、写适配器（占技术量 60-70%）、让系统进日常流程。部署加固生成 Docker/裸机配置 + 降级预案；字段映射工作台用 LLM 初判 + 人工调整应对适配器/映射这个最大的现场痛点。",
        "modules": ["deploy_hardener", "mapping"],
        "how": "选部署模式生成配置（部署前检查）→ 系统集成用字段映射工作台做适配器 → 导出代码接入。",
        "io": "输入：部署模式/字段列表。产出：部署配置 + 适配器代码。",
        "gate": None,
        "handoff": "衔接：上线后 monitor 看成本，交付阶段生成文档。",
        "pitfalls": "常见问题：部署前检查缺环境变量报错；映射初判需人工复核。",
    },
    {
        "phase": 5, "name": "交付沉淀",
        "goal": "生成客户能带走的交付物/文档，并把过程与资产沉淀下来供下次复用。",
        "narrative": "文档是写给你离开后客户自己看的。项目作战台（warroom）一个视图拉齐全部产物（诊断/数据作战流/映射/交付物/资产/RAG/工作流进度/时间线），分区可一键跳转续做；项目文档包（架构/API 文档/运维手册/SOP）由 LLM 起草 + 模板；案例层把所有产出打包成可打印/可检索的交付物；资产沉淀（诊断方案/数据作战流沉淀/映射配置）→ 下次交付自动带出、一键接入。这层直接兑现「用真实落地项目建立强说服力」的北极星。",
        "modules": ["cases", "projects", "assets"],
        "how": "打开 ⑧ 项目作战台一个视图拉齐全部产物（分区一键跳转续做）→ 项目页生成文档包 → 诊断/裁剪/文档包生成交付物 → 案例库沉淀可检索 → 资产沉淀（数据作战流 deposit / 映射导出自动注册）→ 下次交付自动带出/一键接入 → 项目档案完整留痕。",
        "io": "输入：项目/诊断上下文。产出：文档包 + 交付物 + 案例 + 项目档案。",
        "gate": "文档包需人工确认",
        "handoff": "衔接：案例沉淀 → 下次交付自动带出（Agent 记忆）。",
        "pitfalls": "常见问题：PDF 需 Chrome；文档包内容依赖事件记录，记得记全。",
    },
]
CROSS_CUTTING = ["monitor", "data_flywheel", "assets"]


# =====================================================================
# 三、完整操作示例（放使用指南最前面，照着点一遍就上手）
# =====================================================================

WALKTHROUGH = {
    "title": "💻 完整操作示例 · AI助教与智能批改（照着点一遍就上手）",
    "scenario": "客户：教学管理部门。需求：搭建基于大模型的 AI 助教系统，支持作业自动批改、课件智能生成、学情数据分析，教师备课时间减半，用户约 300 名教师。",
    "flow": "完整链路（v11 真实试运行）：① 需求诊断（多 Agent 对抗 + 人工确认定稿）→ ② 数据作战流 6 步（导入→清洗→质量→标注→评测集→知识库，断点续接 + 知识库自动索引 RAG 就绪）→ ③ 原型 + RAG（knowledge_qa 带知识库，过数据门禁）→ ④ 字段映射（导入真实样例 + 实跑校验 + 导出适配器）→ ⑤ 部署配置 → ⑥ 项目作战台（warroom 全分区拉齐）→ ⑦ 项目文档包 → ⑧ 资产沉淀（下次交付自动带出/一键接入）。完整可复现示例见 `examples/pilot_example.py`（`--stub` 秒级复现、默认真调 DeepSeek）；本页下方示例为一个教学场景的逐步点按。",
    "steps": [
        {"step": 1, "tab": "① 需求诊断", "action": "在「客户需求描述」粘贴上面的需求文本（尽量写全：现状/目标/约束/数据/用户/验收人），点「开始诊断（Generator + Critic 对抗）」。",
         "response": "返回 Generator 打分（生成性5/推理复杂度4/不确定性容忍3/数据可得3/实时4）、Critic 盲审独立打分、置信度（高 0.9）、2 处分歧、3 个澄清问题、相关历史案例（自动带出）。",
         "note": "重点看：Critic 标出的「未覆盖要点/矛盾/过度自信」和低置信维度——这些是你要追问客户的地方。"},
        {"step": 2, "tab": "① 需求诊断", "action": "人工复核：把「生成性」+1，写理由「AI助教需要生成批改意见/课件内容，生成性应更高」，点「提交人工打分，请 Reviewer 评审」。",
         "response": "Reviewer 盲审人工分：逐维「同意/修正」+ 偏置检测。本案例 Reviewer 同意生成性 5 分（理由：作业批改/课件生成均需生成新内容），未检出偏置。分歧保留进报告。"},
        {"step": 3, "tab": "① 需求诊断", "action": "在「③ 确认并生成正式报告」填客户名称（教学管理部门）、需求摘要（AI助教与智能批改）、验收人（教务处主任），勾选「我已人工确认」，点「生成正式报告」。",
         "response": "v1 定稿报告：总分 19、结论「推荐使用 AI，但需谨慎」、置信度高、分歧记录；诊断事件自动挂到「教学管理部门 项目」档案，报告返回 project_id。"},
        {"step": 4, "tab": "① 需求诊断", "action": "滚到「案例 / 交付物（可打印 · 可发客户）」面板，点「把当前诊断生成交付物」。",
         "response": "生成 deliverable.html + deliverable.pdf，标题「教学管理部门 · AI助教与智能批改」；点「打开 HTML」可打印/发送，或「下载 PDF」；案例自动挂项目档案，进入案例库可检索。"},
        {"step": 5, "tab": "② 五步裁剪", "action": "下方「接线：诊断结论 → 裁剪预填」填 run_id（或留空用最近一次诊断），点「诊断结论带入裁剪」。",
         "response": "按诊断总分 19 自动预填预算 10 万；裁剪方案：启用 diagnosis/data_prep/prototype_assembler/deploy_hardener/monitor，删除 data_flywheel，简化配置（无 GPU→ReAct+本地模型等）。点「把该方案生成交付物」可导出裁剪方案 PDF 发给客户。"},
        {"step": 6, "tab": "⑧ 项目档案", "action": "打开「教学管理部门」项目（诊断定稿时已自动创建），看顶部「工作流进度」。",
         "response": "5 阶段状态：需求诊断 ✓（门禁通过）、数据准备 ✓、现场原型 待做、部署集成 待做、交付沉淀 ✓（文档包已生成）；项目时间线含「需求诊断定稿 v1」「生成交付物 v1」事件；可继续追加会议/现场问题记录。"},
        {"step": 7, "tab": "⑧ 项目档案", "action": "点「生成项目文档包（Q18）」，选章节（架构说明/API文档/运维手册/SOP）。",
         "response": "LLM 起草各章节 → 生成文档包 HTML/PDF，可下载发给客户交接（写给客户离开后自己能看懂）。"},
        {"step": 8, "tab": "① 需求诊断", "action": "客户看完报告返回意见：在「④ 客户反馈 → 生成下一版」上传反馈文件（txt/pdf）或粘贴文本，点「提炼客户意见」→ 再点「生成下一版」。",
         "response": "系统提炼「客户意见条目」→ 增量重评只改受影响的维度 → 生成 v2（带相对 v1 变更清单）→ 再次确认 → 再发客户。这是完整的版本循环。"},
    ],
    "tip": "上手口诀：诊断 → 交付物 → 裁剪 → 文档包 → 客户反馈 → v2。不确定下一步时，看本页最顶的「动态使用建议」——它会根据你当前状态告诉你该做什么。",
}


def walkthrough() -> dict:
    return WALKTHROUGH


def workflow_guide() -> dict:
    return {"phases": WORKFLOW_PHASES, "cross_cutting": CROSS_CUTTING, "walkthrough": WALKTHROUGH}


# =====================================================================
# 三、动态使用建议（基于状态的长篇建议）
# =====================================================================

def suggestions() -> list:
    """根据当前系统状态给出「下一步」长篇建议（为什么/怎么做/前置/产出/跳转）"""
    from diagnosis.orchestrator import get_archive, list_runs
    from cases.archive import list_cases
    from projects.archive import list_projects

    confirmed = [r for r in list_runs(30) if _confirmed(get_archive, r)]
    cases = list_cases(50)
    diag_cases = [c for c in cases if c.get("source_type") == "diagnosis"]
    doc_packages = [c for c in cases if c.get("source_type") == "doc_package"]
    projects = list_projects(20)
    from annotation.service import ANN_ROOT
    ann = [p.name for p in ANN_ROOT.iterdir() if (p / "archive.json").exists()] if ANN_ROOT.exists() else []
    from mapping.service import MAPPING_ROOT
    maps = [p.name for p in MAPPING_ROOT.iterdir() if (p / "archive.json").exists()] if MAPPING_ROOT.exists() else []
    from dataprep.service import list_tasks
    dtasks = list_tasks(30)
    from retrieval.service import list_indexed
    indexed_kbs = list_indexed()
    from assets.archive import list_assets
    assets_n = len(list_assets(limit=500))

    out = []

    if not confirmed:
        out.append({
            "priority": 1, "title": "从第一次需求诊断开始",
            "why": "整个交付链的地基是需求诊断——它决定要不要做 AI、往哪个方向投。现在系统里还没有任何已确认的诊断，说明还没开始压测过客户需求。",
            "how": ["在 ① 需求诊断填客户需求（现状/目标/约束/数据/用户/验收人，尽量写全）",
                    "点「开始诊断」等 Generator + Critic 对抗评审出结果",
                    "人工复核打分 → 强制确认 → 生成 v1 定稿报告"],
            "prereq": ".env 已配置 DEEPSEEK_API_KEY（否则会规则兜底并标注）",
            "produce": "v1 定稿报告 + 置信度/分歧，可继续生成交付物",
            "tab": "tab-diagnosis",
        })
    if confirmed and not diag_cases:
        out.append({
            "priority": 1, "title": "把诊断变成能发给客户的东西",
            "why": f"你已有 {len(confirmed)} 个已确认诊断，但还没生成可打印交付物。诊断的价值一半在「能拿给客户看」——HTML/PDF 才能打印、发送、建立说服力。",
            "how": ["打开 ① 需求诊断", "滚到「案例 / 交付物」面板", "点「把当前诊断生成交付物」，得到 HTML（可打印）与 PDF（若本机有 Chrome）"],
            "prereq": "至少一个已确认定稿的诊断",
            "produce": "deliverable.html/pdf + 结构化案例（可检索）",
            "tab": "tab-diagnosis",
        })
    if confirmed:
        out.append({
            "priority": 2, "title": "从诊断结论带入五步裁剪",
            "why": "诊断告诉你值不值得做；裁剪决定做哪几个模块、怎么简化。用诊断总分自动预填预算，能省去重复沟通。",
            "how": ["打开 ② 五步裁剪", "下方「接线：诊断结论 → 裁剪预填」填 run_id（或留空用最近）",
                    "看自动预填的预算与诊断上下文，人工补齐其他约束", "生成裁剪方案，可再生成交付物"],
            "prereq": "至少一个已确认诊断",
            "produce": "裁剪方案（启用/删除/简化/排期）",
            "tab": "tab-cropper",
        })
    if confirmed and not projects:
        out.append({
            "priority": 2, "title": "建立项目档案，让过程有去处",
            "why": "你有诊断但没建项目。项目档案是「文件多、找不到」的解药——诊断/案例会自动挂进项目时间线，后续会议/现场问题也有地方记。",
            "how": ["打开 ⑧ 项目档案", "填项目名 + 客户，点「创建项目」", "之后诊断定稿/案例生成会自动挂到同客户项目"],
            "prereq": "无（可先建项目）",
            "produce": "项目时间线 + 自动挂接的过程记录",
            "tab": "tab-projects",
        })
    if projects and confirmed and not doc_packages:
        out.append({
            "priority": 2, "title": "生成项目文档包给客户交接",
            "why": "文档是写给你离开后客户自己看的。项目文档包（架构/API 文档/运维手册/SOP）是 FDE 阶段⑤的刚需。",
            "how": ["打开 ⑧ 项目档案，点开项目", "点「生成项目文档包（Q18）」", "LLM 起草 → 得到 HTML/PDF 文档包，可下载发给客户"],
            "prereq": "已建项目 + 至少一条诊断/事件上下文",
            "produce": "项目文档包（HTML/PDF）",
            "tab": "tab-projects",
        })
    if not maps:
        out.append({
            "priority": 3, "title": "用字段映射工作台应对系统集成",
            "why": "适配器/字段映射占现场技术量 60-70%，是 FDE 阶段④最痛的坑。LLM 初判 + 人工调整 + 导出适配器，能显著提速。",
            "how": ["打开 ⑨ 字段映射", "填源/目标字段（字段名|示例值）", "LLM 初判映射 → 人工调整 → 导出 adapter.py"],
            "prereq": "知道要对接的源/目标字段",
            "produce": "映射配置 + 适配器代码（run_id 断点续接）",
            "tab": "tab-mapping",
        })
    if confirmed and not ann:
        out.append({
            "priority": 3, "title": "建标注任务，数据质量决定上限",
            "why": "数据准备占现场 30-40% 时间，评测集决定能不能衡量质量。双人标注一致性是最可靠的评测集来源。",
            "how": ["打开 ③ 数据准备", "下方「标注与评测集管理」建任务、粘贴样本", "双人打标签 → 看一致性 → 构建评测集"],
            "prereq": "一批待标注样本",
            "produce": "一致性统计 + eval_set.json",
            "tab": "tab-dataprep",
        })
    if confirmed and not dtasks:
        out.append({
            "priority": 2, "title": "建数据作战流任务：把真实数据跑成资产",
            "why": f"你已有 {len(confirmed)} 个已确认诊断，但还没有数据作战流任务。数据作战流是「数据未达标不进原型」门禁的载体——用真实数据跑 6 步（导入→清洗→质量→标注→评测集→知识库），run_id 断点续接、产物真实落盘、知识库自动索引 RAG 就绪。",
            "how": ["打开 ③ 数据准备", "新建数据作战流任务：上传 csv/json 真实数据（可带项目/客户）",
                    "顺序推进 清洗→质量→标注→评测集→知识库，中断可续接（刷新不丢）",
                    "知识库步骤完成后自动索引，④ 原型即可选该知识库做 RAG"],
            "prereq": "一批真实数据文件（csv/json）",
            "produce": "cleaned_data/quality_report/eval_set + 已索引知识库（RAG 就绪）",
            "tab": "tab-dataprep",
        })
    if indexed_kbs:
        out.append({
            "priority": 2, "title": "知识库就绪后跑 RAG 原型",
            "why": f"已有 {len(indexed_kbs)} 个已索引知识库（RAG 就绪）。用真实问题跑 knowledge_qa 模板验证「基于客户文档的问答」这个最主流假设，回答带引用分块。",
            "how": ["打开 ④ 原型运行", "选 knowledge_qa 模板 + 已索引知识库", "输入客户真实问题，运行看带引用的回答"],
            "prereq": "至少一个已索引知识库",
            "produce": "带引用分块的 RAG 回答 + llm_mode",
            "tab": "tab-prototype",
        })
    if dtasks:
        out.append({
            "priority": 2, "title": "沉淀资产 / 一键接入",
            "why": f"你有 {len(dtasks)} 个数据作战流任务。数据作战流 deposit 可沉淀 4 类可复用资产（评测集/知识库分块/清洗规则/质量报告），mapping 导出自动注册映射配置；资产库支持检索/建议/一键接入 adopt——下次交付自动带出（项目越多、工具越强）。",
            "how": ["在 ③ 数据作战流任务详情点「沉淀资产」",
                    "或打开 ⑪ 资产库检索/筛选资产，点「一键接入」",
                    "adopt：映射配置预填新映射 run / 数据资产复制到目标数据任务 / 交付物登记引用"],
            "prereq": "已跑完数据作战流（或已有可复用资产）",
            "produce": "可复用资产入库 + 下次交付自动带出/一键接入",
            "tab": "tab-assets",
        })
    if projects:
        out.append({
            "priority": 2, "title": "打开作战台看项目进度",
            "why": "项目作战台一个视图拉齐该项目全部产物（诊断/数据作战流/映射/交付物/资产/RAG/工作流进度/时间线），分区一键跳转续做；门禁未过会诚实显示原因。",
            "how": ["打开 ⑧ 项目档案，点开一个项目进入作战台",
                    "看概览统计卡 + 工作流进度 + 各产物分区",
                    "从任一分区一键跳转续做（跳 ③/⑨ 预填项目/客户、跳 ①/③/⑨ 续做指定 run）"],
            "prereq": "至少一个项目",
            "produce": "全产物聚合视图 + 工作流进度/门禁状态",
            "tab": "tab-projects",
        })
    if not assets_n and (confirmed or dtasks):
        out.append({
            "priority": 3, "title": "沉淀第一批可复用资产",
            "why": "资产库（⑪）是「项目越多、工具越强」的载体：诊断定稿自动注册诊断方案，数据作战流 deposit 沉淀评测集/知识库分块/清洗规则/质量报告，mapping 导出注册映射配置。现在还没有任何资产，沉淀后下次交付会自动带出/一键接入。",
            "how": ["完成一次数据作战流 → 点「沉淀资产」", "或导出一次映射适配器（自动注册）", "打开 ⑪ 资产库确认已入库，可检索/筛选"],
            "prereq": "至少一个已确认诊断或数据任务",
            "produce": "registry.json 中的可复用资产 + related_assets 自动带出",
            "tab": "tab-assets",
        })

    out.sort(key=lambda x: x["priority"])
    return out


def _confirmed(get_archive, run_id) -> bool:
    try:
        return bool(get_archive(run_id).get("confirmed"))
    except Exception:
        return False


def get_guide(key: str) -> dict:
    """返回模块的长篇使用指南"""
    if key not in MODULE_GUIDES:
        raise KeyError(f"未知模块: {key}")
    return MODULE_GUIDES[key]
