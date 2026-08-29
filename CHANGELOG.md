# Changelog

All notable changes to this project will be documented in this file.

## [1.14.0] - 2026-08-29

### Changed
- Web 操作台界面全面重设计（v13.0）：从「早期最简样式、观感老旧」重设计为 **Ant Design Pro 企业后台风**（按用户选定参考）
  - `web/style.css` 完整重写：AntD 5 色板（浅蓝主色 `#4096ff`、中性灰阶、AntD Tag/Alert 语义色）、浅灰内容底 `#f5f5f5` + 白色卡片/页头卡（清晰边界）、规范表格（表头 #fafafa + 行 hover）、AntD 按钮/输入（focus 蓝描边）、统计卡、柱状图、响应式（≤900px 侧栏 off-canvas 抽屉）
  - `web/index.html` 重构：顶栏（面包屑 + 服务状态）+ **中深灰蓝侧边栏 #26364a（150px，AntD 深 Sider）**，logo 置顶；11 个 tab 内容原样迁入；导航选中 = 浅蓝圆角胶囊 + 白字
  - **去 emoji**：导航/标题/按钮/消息提示中全部 emoji 与圈号（①②③…✔✘📄⚠️ 等）清除，纯文字
  - **`web/app.js` 零改动业务逻辑**（仅清理可见 emoji/圈号显示文本，node --check 通过）；92 个静态 DOM ID 全保留、76 个表单 name 0 丢失；nav `data-tab` 与 section id 一一对应
  - 移动端汉堡开合由 index.html 内联脚本负责，不触碰 app.js
  - `pytest tests/` 163 passed
- 版本收口（Git 前）：`pyproject.toml` / `core/__init__.py` 包版本 1.2.0 → **1.14.0**，与 README 当前版本对齐（消除版本双轨）；`.gitignore` 移除对 `notes/` 决策记录的误忽略

## [1.13.0] - 2026-08-29

### Changed
- 功能说明/文档同步（v12.0）：经 v3-v11 九轮迭代后，「功能说明/manifest/指南/文档」部分条目滞后甚至事实错误，本轮按总工程师审计清单**逐项修复**（纯文档/自描述，无业务代码行为变更）：
  - `core/manifest.py`：新增 `dataprep`（数据作战流 6 步 + 断点续接 + 沉淀资产 + 知识库自动索引）与 `assets`（可复用资产注册表：自动入库/related_assets 自动带出/adopt 一键接入）条目；`projects` 补 v7.0 作战台 + v10.0 门禁；`diagnosis` 补非技术全景可行性 + 商务提案；`data_prep` 指向 dataprep；`cases`/`mapping` 补新端点
  - `core/guide.py`：工作流阶段② 补数据作战流（modules 加 dataprep、narrative 改 6 步 + 断点续接 + RAG 就绪 + 双人标注）；阶段⑤ 提作战台与资产复用；CROSS_CUTTING 补 `assets`；WALKTHROUGH 纳入 v11 真实链路（指向 `examples/pilot_example.py`）；`suggestions()` 读 dataprep/retrieval/assets 状态补「建数据作战流任务」「知识库就绪后跑 RAG 原型」「沉淀资产/一键接入」「打开作战台看项目进度」建议；projects 指南加「打开作战台」步骤
  - `README.md`：版本 v1.12.0 → v1.13.0；模块说明表开发状态与功能模块状态表对齐（全 ✅ 已完成）；使用示例表补 annotation/cases/kb/mapping/projects 行 + retrieval/assets 注明「见 pilot 全链路」
  - `docs/api.md`：按 `core/api.py` 全量补齐 v3-v11 全部端点（dataprep/retrieval/assets/projects-warroom/workflow/manifests/guide/cases-crop-doc-package/mapping-samples-validate-update/annotation-runs-from-dataprep/diagnosis 全套）；版本注记更新（README v1.13.0 / pyproject 1.2.0 / health 读包版本 1.2.0）
  - `docs/usage-guide.md`：总览表补 dataprep/retrieval/assets + 更新 projects(作战台)/mapping(实跑校验)/annotation(双人工作台)；「7 个标签页」改「11 个标签页」；修正 6.2 末句（诊断多 Agent / 映射初判与校验 / RAG / 原型 4 模板均真调 DeepSeek，未配置 key 时诊断/映射规则兜底、原型/检索诚实报错）；端到端示例补 v11 全链路（指向 pilot）
  - `docs/统一底座架构设计.md`：目录结构补齐 dataprep/mapping/annotation/kb/retrieval/assets/projects/cases；错误码表补 400/403/404/429 并注明实际 API 返回原始 JSON + HTTP 状态码；3.3 接口契约标注为设计期契约并指向 docs/api.md；顶部加注记
  - `CLAUDE.md`：修正 3 处滞后事实（LLM 调用默认真调可注入覆盖 / 11 个标签页 / 目录结构以 README 为准）
  - `core/main.py`：`/health` version 由硬编码 `"0.1.0"` 改为读取包版本（`pyproject.toml`，1.2.0），不再误导
- `refactor/文档同步/更新日志-v12.0.md`（套 v11.0 模板，7 类验收自评；测试全绿 163 passed，manifest/guide 改动不破坏既有用例）

### Fixed
- 文档事实错误（滞后清单逐项修复）：manifest 缺 dataprep/assets；README 开发状态列过时（待开发/开发中）；usage-guide 标签页数与 LLM 调用表述错误；docs/api.md 端点缺失；`/health` 版本号误导。

## [1.12.0] - 2026-08-29

### Added
- 真实试运行（v11.0，北极星：用真实落地项目建立说服力）：把全工具链在一套真实制造业客户项目上完整跑通，产出可发给客户的交付物包，README 沉淀「真实案例」。本轮**不新增业务能力**，是全能力合成演练（新增文件为主，既有代码零改动）。
  - 固定真实数据集提交仓库 `examples/data/manufacturing_sensors.csv`（42 行：注塑/CNC 加工/冲压/空压/装配产线，温度/压力/振动/转速/电流，含时间戳与状态）与 `examples/data/retail_inventory.csv`（32 行零售库存），从历史产物提炼列结构后人工造得更完整，非教学场景
  - 端到端试运行脚本 `examples/pilot_example.py`：同一客户「某汽车零部件制造厂」走完整项目流程（需求诊断 start→review→finalize(confirmed) / 数据作战流 create→六步→deposit / 原型+RAG(knowledge_qa+kb_run_id+project_id 过数据门禁) / 字段映射 create→samples→validate→export / 部署配置 docker-compose / 项目作战台 warroom / 项目文档包 confirmed 放行），产出客户交付物包 `tmp/web/pilot/<客户>/`（客户项目总览.md + 诊断交付物.html + 项目文档包.html + warroom.json + 免责声明）
  - LLM 策略诚实标注：默认真调 DeepSeek（约 12 次调用，耗时约 2.5 分钟），`--stub` 全打桩（确定性 JSON/固定文本/固定哈希嵌入）可复现、CI 用；输出报告 `llm_mode` 字段区分 real/stub
  - README 新增「真实案例」小节 + 示例表加 pilot 行；版本 v1.11.0 → v1.12.0
  - `refactor/真实试运行/更新日志-v11.0.md`（套 v10.0 模板，7 类验收自评；第 4 类「客户交付物包可发客户」标「待总工程师判断」，第 6 节甲方验收留待总工程师填写）

### Fixed/Changed
- 新增测试 `tests/test_pilot.py`（2 用例，打桩模式全链路回归）：固定数据集提交校验（行数/列结构/非教学关键词）；`run_pilot(stub=True, max_rows=8)` 全链路断言——项目存在、诊断定稿（confirmed + project_id 落盘）、数据任务 6 步全完成且评测集/知识库分块/质量报告产物落盘、原型可跑（qa 模板 + RAG + 数据门禁放行）、映射导出（成功率>0）、部署产物、warroom 全分区计数>0 且工作流 100%、文档包存在、客户交付物包 4 文件齐全 + 免责声明 + warroom 快照可解析
- 兼容：既有代码零改动；`pytest tests/` **163 passed**（161 旧 + 2 新，旧用例零改动全绿）；新测试打桩 LLM、隔离 tmp（diagnosis/dataprep/cases/projects/mapping/retrieval 档案根全指向 tmp）、语义去重/RAG 嵌入固定哈希，1.9s 完成

## [1.11.0] - 2026-08-29

### Added
- 门禁硬化（v10.0）：质量门禁从「状态展示」变为「真阻断」——`core/workflow.py` 新增 `gate_check(stage_key, project_id=None)` 统一判定关键质量点，全部基于真实档案（非写死）：
  - `diagnosis`：允许 = 该项目有已确认诊断（项目 diagnosis 事件，或诊断 run 档案 project_id==pid 且 confirmed）；reason「发客户前必须人工确认」
  - `data_prep`：允许 = 该项目有 dataprep run（project_id==pid）**且其 quality_report 产物文件真实存在**（数据被真实评估过＝达标）；reason「数据未达标不进原型（缺少质量评估）」
  - `deliver`：允许 = 该项目有已确认诊断 且 存在带 project_id 的 doc_package 案例；reason「文档包需人工确认」
  - project_id 为空时按全局判定（全局有已确认诊断 / 全局有 quality_report 产物），reason 注明「（全局判定）」
  - `project_status` 的 `gate_passed` 对齐 gate_check，并新增 `gate_reason` 字段（只增字段，旧字段/旧行为不破坏）
- `core/api.py` 新增 `GET /workflow/gate?stage=&project_id=`：返回 gate_check 结果，供前端运行前展示「数据达标 / 文档包确认」门禁状态（注册在 `/workflow/{project_id}` 之前避免路由遮蔽）
- 新增测试 `tests/test_gates.py`（15 用例，非教学场景：制造业传感器 CSV，LLM 全打桩、语义去重打桩、诊断/dataprep/cases/projects 档案根隔离到 tmp）：门禁判定真实（gate_check 基于真实档案）、原型数据门禁 403 可验证、force 强制通道 gate_override、未传 project_id 不拦、裁剪/文档包确认门禁 400/200、finalize 强制 confirmed 回归、`/workflow/gate` 端点
- `refactor/门禁硬化/更新日志-v10.0.md`（套 v9.0 模板，7 类验收自评；第 7 类前端可用性标「待总工程师判断」，第 6 节甲方验收留待总工程师填写）

### Fixed/Changed
- 门禁从展示变阻断（真阻断 + 诚实强制继续通道）：
  - `POST /prototype/run`：`PrototypeRunRequest` 增可选 `project_id: str=""` 与 `force: bool=False`（只增字段，旧调用不传则行为不变）。传 project_id 时先过「数据未达标不进原型」门禁：未通过且非 force → **HTTPException 403**（detail 含 gate_reason）；force=true 通过时响应附加 `gate_override:true + gate_reason` 诚实记录；未传 project_id → 不拦，响应附 `gate:{checked:false}`
  - `GET /cropper/from-diagnosis/{run_id}`：诊断未定稿确认（confirmed=false）→ **HTTPException 400**「诊断未定稿确认,禁止据此裁剪发客户」
  - `POST /cases/create-doc-package`：`DocPackageRequest` 增 `confirmed: bool=False`；要求 confirmed=true **或** 该项目已有已确认诊断，否则 → 400 带 reason「文档包需人工确认」；响应附加 `gate` 结果（confirmation 诚实区分 request_confirmed / confirmed_diagnosis）；生成的文档包落盘 project_id（供后续 deliver 门禁判定）
  - `/diagnosis/finalize` 已强制 confirmed（既有，保留不破坏）
- 前端（`web/index.html + app.js`，零构建，诚实）：④ 原型表单加 project_id 输入 + 运行前展示「数据达标门禁」状态（未过禁用运行按钮 + 强制继续 checkbox + 响应 gate_override 徽标）；⑧ 项目页文档包按钮改为「确认已人工定稿」checkbox（未勾选不发请求）；warroom 工作流门禁未过步骤显示「门禁未过：\<reason\>」；`api()` 错误解包升级支持对象 detail（兼容旧字符串 detail）
- `README.md`：版本 v1.10.0 → v1.11.0；模块状态表新增「质量门禁」行；项目作战台行同步
- 兼容：`PrototypeRunRequest`/`DocPackageRequest` 只增字段；旧调用（不传 project_id/confirmed）行为不变；`project_status` 旧字段不动（只增 gate_reason）；`pytest tests/` 161 passed（原 146 + 新增 15，旧用例零改动）；`node --check web/app.js` 通过

## [1.10.0] - 2026-08-29

### Added
- 标注人工工作台（v9.0）：把「服务层是真双人标注、前端是单标注员壳」做实为**真实可用的手工双人标注工作台**
  - `annotation/service.py` 新增 `list_tasks(limit=50)`（扫描 `tmp/web/annotation/`，按 archive.json mtime 倒序返回 run_id/name/total/stats）
  - `annotation/service.py` 新增 `create_annotation_task_from_dataprep(dataprep_run_id, sample_size=20, name=None)`：读数据作战流 `cleaned_data` 产物取前 N 条 content 作为待标注样本，自动命名；**样例来源诚实标注**（任务档案新增 `source` 字段 `{type: "dataprep", dataprep_run_id, dataprep_name, sample_size}`，只增字段）；cleaned_data 缺失/不存在诚实报错
  - `annotation/service.py::get_task` 增加每样本一致性明细：每个 item 新增 `consistency` 字段（unlabeled 未标 / only_a 仅A / only_b 仅B / only_one 仅一人非A/B / agreed 一致 / disagreed 分歧），stats 计数改用同一判定函数（空字符串标签视为未标），旧字段 stats/items/labels 不变
- `core/api.py` 新增端点（旧 annotation 端点不动）：`GET /annotation/runs`（注册在 `GET /annotation/{run_id}` 之前避免路由遮蔽）、`POST /annotation/from-dataprep`
- 前端（`web/index.html + app.js`，零构建）：③ tab 标注面板升级为「人工标注工作台」
  - 从数据作战流建任务（下拉选有 cleaned_data 的 dataprep run + 样本数）+ 手动粘贴样本建任务（两条路径都进新工作台）
  - `renderAnnWorkbench`（独立新函数，旧 `renderAnnTask` 函数体原样保留）：每样本两列输入（标注员 A / 标注员 B，可分别存），逐行一致性徽标（未标/仅A/仅B/一致✅/分歧⚠️）；顶部实时一致性统计（一致 N / 分歧 M / 未标 K / 共 T）
  - 分歧样本单独列出一节（两标注员标签对照），改任一标注员标签后「保存标注」重算一致性直到一致
  - 构建评测集（`build-eval`）→ 一致/分歧条数 + 一致样本生成评测集（`/artifacts/annotation/<run_id>/eval_set.json` 可下载）
  - 「列出标注任务」→ `GET /annotation/runs`，可打开历史任务进工作台续做
  - 数据作战流衔接与诚实标注：`renderDataFlowDetail` 标注步骤产物标「规则自动打标」（流水线便利，保留），产物旁新增「去人工标注工作台精标」按钮（带该 run 样本源）→ 建 from-dataprep 任务；人工工作台明示「人工标注」
- 新增测试 `tests/test_annotation_workbench.py`（7 用例，非教学场景：制造业传感器 CSV，隔离 ANN_ROOT/ARCHIVE_ROOT 到 tmp，语义去重打桩固定哈希向量不联网）：from_dataprep 建任务样本来自真实 cleaned_data 且 source 诚实标注、双人标注 A/B → get_task 一致性 stats 正确且每样本 consistency 明细正确、分歧检出与改判后 build_eval 只含一致样本、list_tasks 按 mtime 倒序、API 全链路（from-dataprep/label/get/build-eval/runs/评测集落盘）、旧端点不破坏
- `refactor/标注人工工作台/更新日志-v9.0.md`（套 v8.0 模板，7 类验收自评；第 7 类前端可用性标「待总工程师判断」，第 6 节甲方验收留待总工程师填写）

### Changed
- `core/manifest.py` / `core/guide.py`：annotation 模块说明更新为「人工双人标注工作台」（from-dataprep 建任务 / 逐行一致性 / 分歧改判 / 构建评测集）；data_prep 指南第③步同步更新；api 列表只增 `/annotation/from-dataprep`、`/annotation/runs`、`/annotation/{run_id}/label`
- `README.md`：版本 v1.9.0 → v1.10.0；模块状态表 annotation / 数据标注管理行更新
- 兼容：`create_annotation_task` / `add_label` / `build_eval_set` 签名与行为不变；`get_task` stats 字段不变（只增每样本 consistency）；旧 annotation API/UI/数据作战流流水线（规则打标）不破坏；`renderAnnTask` 函数体原样保留；`pytest tests/` 146 passed（原 139 + 新增 7，旧用例零改动）；`node --check web/app.js` 通过

## [1.9.0] - 2026-08-29

### Added
- 原型模板做实（v8.0）：`prototype_assembler/templates/` 下三个占位模板改为真实 LLM 驱动（4 个模板全部真调 DeepSeek，core/llm.py）
  - `extract_agent.py`：注入 `_extract_llm_call`（ReAct），信息抽取角色，返回结构化抽取结果（`实体名 | 类型 | 属性键=属性值`）
  - `reasoning_agent.py`：注入 `_reasoning_plan_generator` / `_reasoning_step_executor` / `_reasoning_answer_generator`（Plan-Execute），多步推理逐步求解后汇总最终答案
  - `reflexion_agent.py`：注入 `_reflexion_llm_call`（先作答 → 评估 → 反思修正 → 重试），反思历史经 `agent._reflection_history` 传给 llm_call，把评估反馈拼进 system prompt 让模型针对修正
  - 三个模板的 `create_*_agent()` 签名不变（assembler / API / 前端不破坏）；LLM 调用失败（LLMError）时诚实降级：返回错误说明（如「信息抽取未能完成（LLM 调用失败：…）」），绝不伪装成功
- `prototype_assembler/loops/reflexion.py::ReflexionLoop._call_llm` 支持 `agent.llm_call` 注入（v8.0）：带 `finish:` 前缀解析、经 `agent._reflection_history` 传递反思历史；未注入时回退占位实现（旧接口兼容）
- `prototype_assembler/assembler.py`：新增 `TEMPLATE_META` 模板元信息（label / llm / rag_ready / detail），供前端诚实标注
- `core/api.py`：`GET /prototype/templates` 返回 `meta`（元信息，旧 `templates` 列表保留）；`POST /prototype/run` 的 `llm_mode` 诚实判定（ReAct/Reflexion 看 `llm_call`，Plan-Execute 看 `plan_generator`/`step_executor`/`answer_generator`）
- 前端（`web/index.html + app.js`，零构建）：模板选择下拉用元信息 label 渲染，下拉下方显示所选模板「真调 DeepSeek / RAG 就绪」徽标 + 说明；结果区显示模板徽标 + llm_mode，诚实标注每个模板是否真实 LLM
- 新增测试 `tests/test_prototype_real.py`（11 用例，非教学场景：设备运维/工单估算/故障说明，LLM 全部打桩 monkeypatch `core.llm.chat`）：三个模板 agent 运行产生真实 LLM 驱动输出（非占位默认值）、含模板角色行为（结构化抽取 / 推理分步（计划+执行+汇总） / 反思修正（第二次调用携带评估反馈））、LLMError 时诚实降级、qa_agent 不回归、`/prototype/run` 对三个真调模板返回 `llm_mode=llm`、`/prototype/templates` 返回元信息且旧结构不破坏
- `refactor/原型模板做实/更新日志-v8.0.md`（套 v7.0 模板，7 类验收自评；第 7 类前端可用性标「待总工程师判断」）

### Changed
- `core/manifest.py`：原型组装 intro/detail 更新为「4 个模板全部真调 DeepSeek；LLM 失败诚实降级」
- `core/guide.py`：现场原型 section 更新（四个模板说明 / 参数含 plan_generator 等 / 坑：未配置 key 时诚实降级）
- `README.md`：版本 v1.8.0 → v1.9.0；模块状态表与示例表更新为「4 个模板全部真调 DeepSeek」
- 兼容：`create_*_agent()` 签名不变；`/prototype/templates` 旧 `templates` 列表保留；`llm_mode` 旧逻辑（只看 `llm_call`）扩展为看全部注入（旧模板无注入仍返回 placeholder，行为兼容）；`ReflexionLoop` 未注入 llm_call 时回退占位；`pytest tests/` 139 passed（原 128 + 新增 11）；`node --check web/app.js` 通过

## [1.8.0] - 2026-08-29

### Added
- 新增 `projects/warroom.py` 项目作战台聚合（v7.0）：`build_warroom(project_id)` 真实跨模块拉取并过滤
  - 返回 `{project, workflow, counts, diagnosis_runs, dataprep_runs, mapping_runs, cases, assets, indexed_kbs, events}`
  - 诊断 run 过滤取并集：run 档案 `project_id==pid` 或 项目 `diagnosis` 事件 `ref==run_id` 或 客户匹配
  - 数据作战流 / 映射 run / 交付物案例 / 可复用资产 按 `project_id==pid`（资产与案例额外客户匹配）过滤
  - RAG 索引：`list_indexed()` 中 `kb_run_id` 属于本项目数据作战流 run
  - 每类给摘要字段（名字/状态/进度/成功率/URL 可跳转），控制条数不返回巨量数据
- 新端点 `GET /api/v1/projects/{pid}/warroom`（旧 `GET /projects/{pid}` 不动）；未知项目 404
- 诊断 project_id 落盘（聚合/按项目过滤的可靠基础）：`core/api.py::diagnosis_finalize` 把所属项目
  `project_id` 写入诊断 run 档案（只增字段，旧档案兼容）；`cases/service.py::create_diagnosis_case`
  新增可选 `project_id` 参数（显式传入优先，否则回退读 run 档案），case meta 落 `project_id`；
  `GET /api/v1/diagnosis/runs` 列表项带 `project_id`（只增字段）
- `core/api.py::diagnosis_finalize` 项目事件 `ref` 改用 `req.run_id`（此前 report 内 run_id 恒为空导致事件 ref 为空）
- 前端（`web/index.html + app.js`，零构建）：⑧ tab 升级为「项目作战台」
  - `loadProjectDetail(pid)` 改请求 `GET /projects/{pid}/warroom`：头部（项目名+客户+创建时间）、概览统计卡（诊断/数据任务/映射/交付物/资产/RAG/工作流进度%）、工作流进度（带门禁，项目级）、各产物分区（诊断续做 / 数据任务续做 / 映射续做 / 交付物 HTML/PDF / 资产一键接入 / RAG 索引状态）、保留手动事件表单 + 文档包按钮 + 时间线；空分区诚实显示占位提示
  - `gotoTab(tabKey, ctx)` 带上下文跳转：跳 ③/⑨ 预填 create 表单的项目/客户，跳 ①/③/⑨ 续做指定 run；`gotoProject` 保持兼容
- 新增测试 `tests/test_projects.py`（5 用例，非教学场景：制造业设备字段映射/某汽车制造厂）：warroom 聚合真实（建项目→诊断 finalize(打桩)→数据任务→映射→RAG 档案→各分区数量正确 + URL 可跳 + 交付物 HTML 可下载）；workflow 按项目过滤（两项目一个有产物一个没有，互不污染）；诊断 finalize 落盘 project_id（run 档案 + /diagnosis/runs + case meta）；warroom 端点结构 + 旧端点不破坏；project_id 为空保持全局判定
  - LLM 全部打桩；语义去重用固定哈希向量替代 chromadb 嵌入；RAG 档案手写（不触发 ChromaDB）；资产注册表由 conftest 隔离
- `refactor/项目作战台/更新日志-v7.0.md`（套 v6.0 模板，7 类验收自评；第 5 类前端标「待总工程师判断」）

### Changed
- `core/workflow.py::project_status(project_id)` 真修：传入项目 ID 时每步 done 按本项目判定
  - diagnosis：项目有 `diagnosis` 事件 或 诊断 run 档案 `project_id==pid`
  - data_prep：dataprep run `project_id==pid` 或 项目有 `dataprep` 事件
  - prototype：项目事件 type∈prototype/iteration
  - deploy：项目有 mapping run `project_id==pid` 或 `deploy` 事件
  - deliver：项目有 case `project_id==pid` 或 文档包 case
  - `project_id` 为空保持原全局判定（兼容历史调用）
- 明确：`/workflow/{project_id}` 行为从「全局判定」修正为「按项目判定」是有意修复（见更新日志）
- `projects/warroom.py` 各分区摘要（诊断 run/数据任务/映射/交付物/资产）均补 `url` 可跳转
- 新增：`projects/warroom.py`、`tests/test_projects.py`、`refactor/项目作战台/更新日志-v7.0.md`
- 修改：`core/api.py`（diagnosis_finalize 落盘 project_id + 事件 ref 修正 + warroom 端点 + /diagnosis/runs 带 project_id）、`cases/service.py`（create_diagnosis_case 可选 project_id）、`core/workflow.py`（按项目过滤）、`web/index.html`（⑧ 作战台）、`web/app.js`（作战台渲染 + gotoTab ctx）、`web/style.css`（warroom 统计卡样式）、`README.md`（v1.8.0）、`CHANGELOG.md`
- 兼容：旧 `GET /projects/{pid}` / `GET /workflow/{project_id}` / `/diagnosis/runs` / `/cases` 字段只增不改；`pytest tests/` 128 passed（原 123 + 新增 5）；`node --check web/app.js` 通过

### Fixed
- `core/workflow.py`：`project_status(project_id)` 此前多处看全局档案不按项目过滤（`workflow.py` 诊断/标注/映射/文档包证据来自全局），某项目状态会被其它项目产物撑高 → v7.0 改为按本项目判定（见 Changed）

## [1.7.0] - 2026-08-29

### Added
- 新增 `assets/` 可复用资产注册表：项目越多、工具越强（v6.0 资产复用闭环）
  - `assets/archive.py`：注册表持久化 `tmp/web/assets/registry.json`；条目 schema（asset_id/kind/title/summary/tags/origin{run_id,module,case_id}/project_id/customer/payload_url/payload_path/meta/created_at）；`register_asset`（按 (kind, run_id) 幂等去重）、`list_assets`（按 kind 过滤）、`search_assets`（关键词/类型/标签/客户）、`get_asset`
  - `assets/service.py`：`suggest(query, kinds, customer, top_k)` 规则评分自动带出（关键词命中 + 标签命中 + 同客户 + 同类资产 + 时间衰减，返回 `[{asset, score, reason}]`，确定性/离线/可测）；`adopt_asset` 一键接入 —— mapping_config 读历史映射预填新 mapping run（draft，可续做）、数据资产复制 payload 到目标 dataprep run 的 products 并挂项目 `asset_reuse` 事件、诊断方案/文档包登记为项目资产引用；`register_from_mapping` / `register_from_dataprep` / `register_from_diagnosis` 挂接
- 注册挂接：`mapping/service.py::export_mapping` 导出成功后自动注册 kind=mapping_config 资产（meta 含 source/target 字段 + 映射数 + adapter 路径，payload_url 指向 adapter/mapping_config.json，幂等）；`dataprep/service.py::_deposit_one` 沉淀后自动注册 4 类数据资产（引用 cases 的 payload_url 不复制 payload）；`core/api.py::diagnosis_finalize` 定稿生成交付物后自动注册 kind=diagnosis_plan（幂等，失败不阻断）
- `mapping/service.py::create_mapping` 新增可选 `prefill_mappings`：提供时跳过 LLM 初判、直接用历史映射预填（旧调用不传则行为不变）
- 自动带出（响应新增 `related_assets` 字段，不改旧字段/不破坏旧契约）：
  - `POST /api/v1/mapping/create` → 按任务名 + 源/目标字段 suggest（kind=mapping_config）
  - `POST /api/v1/dataprep/create` → 按任务名 + 文件名 suggest（kind∈cleaning_rules/eval_set/kb_chunks/quality_report）
  - `POST /api/v1/diagnosis/start` → 保留 `related_cases`，新增 `related_assets`（含 diagnosis_plan 等）
- 通用检索端点：`GET /api/v1/assets/list`、`GET /api/v1/assets/search?q=&kinds=&tags=&customer=`、`GET /api/v1/assets/{asset_id}`、`POST /api/v1/assets/{asset_id}/adopt`（body {project_id?, customer?, target_run_id?}）
- 前端（`web/index.html + app.js`）：⑪ 资产库 tab（检索/筛选 kind+tags+q + 列表 + 详情 + 一键接入，映射配置接入后跳转 ⑨ 工作区续做）；③ 数据作战流创建表单下方渲染 `related_assets`（一键接入=复制到当前 run 的 products）；⑨ 字段映射创建表单下方渲染 `related_assets`（一键接入=导入历史映射）；① 诊断保持相关案例并新增相关资产展示；零构建
- 新增测试 `tests/test_assets.py`（10 用例，非教学场景：制造业/零售/物流）：注册/列表/检索/建议（规则评分 + reason + 幂等）、mapping export 注册资产、dataprep deposit 注册资产、mapping/dataprep/diagnosis 创建返回 related_assets、adopt mapping_config 建新 run 预填、adopt 数据资产写目标 run + 挂项目事件、通用检索端点；LLM 全部打桩、ChromaDB 用确定性 fake 嵌入、注册表隔离

### Changed
- 新增：`assets/`（`__init__.py` / `archive.py` / `service.py`）、`tests/test_assets.py`、`refactor/资产复用闭环/更新日志-v6.0.md`
- 修改：`mapping/service.py`（prefill_mappings + export 注册资产）、`dataprep/service.py`（_deposit_one 注册资产）、`core/api.py`（related_assets + 资产端点）、`web/index.html`（⑪ tab + related_assets 容器）、`web/app.js`（⑪ 资产库 + 自动带出渲染 + 一键接入）、`README.md`、`CHANGELOG.md`
- 兼容：诊断 v2.2 / 数据作战流 v3.0 / 集成工作台 v4.0 / RAG v5.0 / 前端既有 10 标签均不动；`pytest tests/` 123 passed（原 113 + 新增 10）；`node --check web/app.js` 通过

### Fixed
- `mapping/service.py::create_mapping` 存档补持久化 `customer`（v6.0 总工程师审查发现）：此前 mapping 存档未存客户 → 真实 export 路径注册的 mapping_config 资产 customer 为空 → 旗舰 kind 的「同客户」自动带出信号与按客户检索失效；补 `customer` 字段（只增不改，旧档案兼容）并在 `tests/test_assets.py::test_assets_mapping_export_registers` 补断言

## [1.6.0] - 2026-08-29

### Added
- 新增 `retrieval/` RAG 检索模块：打通「数据作战流知识库产物 → 索引 → 检索 → 问答(带引用)」闭环
  - `retrieval/service.py`：`index_knowledge(kb_run_id, chunks)`（真实向量化写 ChromaDB collection `kb_<run_id>`，过滤过短分块，索引档案 `tmp/web/retrieval/<kb_run_id>/archive.json`）、`retrieve(kb_run_id, query, top_k)`（真实 ChromaDB 最近邻检索，返回 `[{chunk, score, source}]`）、`rag_answer(kb_run_id, query, llm_call)`（检索 → 组装 prompt「基于知识库回答，不确定说不知道，标注引用分块」→ 调 core/llm → `{answer, sources}`）、`list_indexed`
  - 默认嵌入用 ChromaDB MiniLM（本机已缓存，离线可用）；macOS CoreML 批量嵌入偶发崩溃 → 强制 CPUExecutionProvider 稳定
- 数据作战流衔接：`dataprep/service.py` `kb_step` 完成后自动索引进检索，产物/步骤记录 `indexed: true` + collection（失败不阻断流程）；新增 `load_kb_chunks(run_id)` 供重建索引
- 原型 QA 接知识库：`create_qa_agent(kb_run_id, top_k)` 运行时检索知识库分块做上下文再答（带引用），引用分块缓存 `agent.last_sources`；`assembler.create/run` 支持 kwargs 透传
- 新增 API（`core/api.py`）：`POST /api/v1/retrieval/index`（{kb_run_id, chunks?}，缺省自动读数据作战流产物）、`POST /api/v1/retrieval/query`（{kb_run_id, query, top_k} → {answer, sources}）、`GET /api/v1/retrieval/indexed`（列出已索引知识库）；`POST /prototype/run` 增加可选 `kb_run_id`，有则走 RAG 并返回 `rag:true + sources`
- 前端（`web/index.html + app.js`）：④ 原型 tab 增「选择知识库（列出已索引 kb_run_id）+ 问题」→ 运行 → 展示回答 + 引用分块；手动索引面板；③ 数据作战流知识库步骤显示「已索引 · RAG 就绪」；零构建
- 新增测试 `tests/test_retrieval.py`（6 用例，非教学场景：设备运维手册/故障处理指南）：分块 → 索引 → 检索（query 命中相关块）→ rag_answer（LLM 打桩返回含引用）+ sources 截断前 100 字 + 未索引报错 + 数据作战流 kb 产物可索引（闭环）+ API 索引/查询 + 原型带 kb_run_id 走 RAG；检索用确定性 fake 嵌入（字符二元组袋），RAG 问答 LLM 打桩；真实链路 DeepSeek 冒烟单独验证
- `core/manifest.py` / `core/guide.py` 补 retrieval 模块（RAG 检索问答）manifest + 长篇指南

### Changed
- `retrieval/service.py`（新）/ `retrieval/__init__.py`（新）/ `dataprep/service.py` / `prototype_assembler/templates/qa_agent.py` / `prototype_assembler/assembler.py` / `core/api.py` / `core/manifest.py` / `core/guide.py` / `web/index.html` / `web/app.js` / `README.md` / `CHANGELOG.md` / `refactor/原型知识库打通/更新日志-v5.0.md`
- 兼容：原型 QA 普通问答（不带 kb_run_id 走原逻辑）、数据作战流 v3.0、集成工作台 v4.0、诊断 v2.2、前端 10 标签均不动；`pytest tests/` 113 passed（原 107 + 新增 6）

## [1.5.0] - 2026-08-29

### Added
- 字段映射工作台升级为「集成工作台」：从「映射表格 + LLM 初判 + 导出」升级为「导入真实样例 → 实跑映射 → 校验正确性 → 人工修正迭代 → 导出」的集成工作流
  - `mapping/service.py` 新增 `import_samples`（上传真实样例 CSV，列名=源字段名 → 存档案 samples：原始行数 + 预览 + 全量行）
  - 新增 `validate_mapping`（`_apply_transform` 对每条源数据行真实执行 transform，与 export adapter 语义一致；「映射校验」LLM 逐字段判断 `pass/warn/fail + 理由`；汇总 `{total_rows, mapped_rows, per_field, counts, success_rate, no_fail_rate}`；结果存档案 validation 可续接）
  - 新增 `validate_row`（单行试运行）、`list_mapping_runs`（断点续接入口）
  - `create_mapping` 新增 `project_id`/`customer` 参数；创建/调整/校验均挂项目档案（`mapping` 事件，ref=run_id）
  - 旧接口 `create/update/export` 兼容不动
- 新增 API（`core/api.py`）：`GET /api/v1/mapping/runs`、`POST /api/v1/mapping/{run_id}/samples`、`POST /api/v1/mapping/{run_id}/validate`、`POST /api/v1/mapping/{run_id}/validate-row`
- 前端（`web/index.html + app.js`）：⑨ 字段映射 tab 集成工作流——新建表单增 客户/项目 ID/样例 CSV；工作区三步卡片（① 导入样例 → ② 试运行校验：成功率/无失败率 + 逐字段 verdict 徽标 + 理由 + 源值→映射值展开 + 逐行预览 → 修正重跑）；「历史映射 / 继续」列表恢复完整档案；零构建
- 新增测试 `tests/test_mapping_integration.py`（非教学场景：制造业设备字段映射 + 物流订单字段映射）：创建→导入真实样例 CSV→validate（含失败）→修正→重跑（成功率/无失败率变化可见）→导出；校验 LLM 打桩不真实调用

### Changed
- `mapping/service.py` / `mapping/__init__.py` / `core/api.py` / `core/manifest.py` / `core/guide.py` / `web/index.html` / `web/app.js` / `README.md` / `CHANGELOG.md` / `refactor/集成工作台/更新日志-v4.0.md`
- 兼容：诊断 v2.2 / 数据作战流 v3.0 / 案例 / 项目 / 前端 10 标签等既有能力均不动；`pytest tests/` 107 passed（原 103 + 新增 4）

## [1.4.0] - 2026-08-29

### Added
- 新增 `dataprep/` 数据作战流模块：项目级数据准备流水线（以项目为单位、可断点续接、产物沉淀复用）
  - `dataprep/archive.py`：run_id 档案（`tmp/web/dataprep/<run_id>/archive.json`），字段 name/project_id/source/status/steps/products/created_at/updated_at；create/load/update/rename/list
  - `dataprep/service.py`：六步流水线（每步可单独执行、可续接、产物真实落盘）
    1. 导入数据（csv/json，检测源类型/行数）→ 2. 清洗（字符去重+语义去重+异常过滤+归一化+PII 脱敏）→ 3. 质量报告（DataQualityEvaluator）→ 4. 标注（复用 annotation：双人规则打标签+一致性→一致样本评测集）→ 5. 评测集（EvalSetBuilder）→ 6. 知识库（kb.service 分块+质检）
  - 全部步骤纯规则/现成模块，不依赖 LLM；`get_state(run_id)` 断点续接、`continue_step(run_id, step)` 继续
  - 任务创建挂项目档案（传 project_id 则 add_event，否则按客户自动建/复用，参考 `_ensure_project`）
  - 资产沉淀：评测集 / 知识库分块 / 清洗规则说明 / 质量报告 → cases/archive 带标签沉淀，`search_cases` 可检索
- 新增 API（`core/api.py`）：`POST /api/v1/dataprep/create`（上传文件→建任务+自动跑前三步）、`GET /api/v1/dataprep/runs`、`GET /api/v1/dataprep/{run_id}`、`POST /api/v1/dataprep/{run_id}/step`（指定步或 run_next 顺序推进）、`POST /api/v1/dataprep/{run_id}/rename`、`POST /api/v1/dataprep/{run_id}/deposit`；产物下载复用 `/artifacts`
- 前端（`web/index.html + app.js`）：③ 数据准备 tab 顶部新增「数据作战流」面板（列出任务/名字/状态/进度/继续/新建上传/查看各步产物/继续按钮/沉淀资产入口），复用①需求诊断「历史诊断/继续」交互风格，零构建
- 新增测试 `tests/test_dataprep.py`（非教学场景：制造业传感器 CSV + 零售库存 CSV）：上传→清洗→质量→标注（双人分歧≥1）→评测集→知识库→断点续接（get_state 后继续）→资产沉淀可检索→项目事件可见

### Changed
- `core/api.py` / `web/index.html` / `web/app.js` / `README.md` / `CHANGELOG.md` / `refactor/数据准备重构/更新日志-v3.0.md`
- 兼容：诊断 v2.2 / 案例 / 项目 / 前端 10 标签 / `data-prep/run`（旧接口）等既有能力均不动；`pytest tests/` 103 passed（原 99 + 新增 4）

## [1.3.2] - 2026-08-29

### Added
- 需求诊断输出深度重构（v2.2）：报告新增「商务提案（供洽谈讨论）」章节（第 14 章，附录顺延 15/16）
  - 新增商务评估 LLM 调用 `run_commercial_proposal`（`diagnosis/agents.py`），基于诊断上下文（技术 5 维 + 非技术可行性 + 范围/风险/假设/分阶段/需求）起草商务提案
  - 定稿（`finalize`）自动生成并写入档案 `report.business_proposal`，LLM 失败用规则兜底不阻断定稿；新增独立 `commercial_proposal(run_id)` 函数
  - 五块内容齐全：投入估算与分期（试点/一期/二期，区间+依据）/ 时间里程碑（何时看到第一个能用的东西）/ 甲方乙方责任清单（具体到条目、阻塞开工标注）/ 试点范围与退出机制（可量化成功标准 + 退出条件）/ 替代方案与不做的代价（对比 + 机会成本）
  - 明确标注「此为讨论用初步估算，最终以商务洽谈确认为准」

### Changed
- `diagnosis/agents.py` / `diagnosis/orchestrator.py` / `cases/render.py` / `tests/test_api.py`
- 兼容：5 维打分/置信度/分歧/多轮累积/对抗内联/非技术可行性/打开按钮等既有能力不变；新增渲染用例（`test_diagnosis_report_v22_business_proposal`）

## [1.3.1] - 2026-08-29

### Added
- 需求诊断输出深度重构（v2.1）：可行性评估从 5 维技术扩展为全景
  - Generator 新增 `non_tech_feasibility`（商业价值与 ROI / 组织承接与变革阻力 / 系统集成复杂度 / 合规与安全 / 风险全景，每项含 `{item 评估, basis 依据, signal 红/黄/绿, advice 建议}` + `overall_recommendation` 综合建议）
  - Critic 新增 `non_tech_audit`（五项非技术独立盲审 + `audit_note` 分歧点 + `overall_audit_note`）
  - 报告新增第 7 章「整体可行性评估」：技术 5 维得分概览 + 非技术各维 Generator vs Critic 内联对抗 + 综合建议
  - 对抗评审过程内联进正文：第 6 章每个维度分析块内新增「对抗评审过程」可读块（Generator 立场 / Critic 盲审立场与分歧 / Reviewer 对人工分的评审 / 采纳结论），非 JSON；执行摘要新增「对抗评审速览」
  - 附录 A 完整原文保留（含非技术字段）
- 兼容：5 维打分/置信度/分歧/多轮累积/打开按钮等既有能力不变；`next_version` merge 保留非技术字段；新增渲染用例（`test_diagnosis_report_v21_sections`）

### Changed
- `diagnosis/agents.py` / `diagnosis/orchestrator.py` / `cases/render.py` / `tests/test_api.py`
- 归一化新增 `_normalize_non_tech_gen` / `_normalize_non_tech_crit` 兜底，旧字段与新接口均不受破坏

## [1.3.0] - 2026-08-29

### Added
- 需求诊断输出深度重构（v2.0）：三 Agent 无长度限制完整 schema（Generator 需求理解/深度逐维论证/范围/功能+非功能需求/数据资源/风险/假设/澄清问题/分阶段建议/章节草稿；Critic 覆盖审计/矛盾/过度自信/反方论证；Reviewer 逐维完整评审/偏置分析/需再确认清单）
- 完整过程留痕：档案新增 `generator_full` / `critic_full` / `reviewer_full` + `agent_log[]`，`get_run_state` 返回完整输出
- 报告从「一页打分表」重写为「多章节需求文档」（封面/修订历史/执行摘要/需求背景/目标范围/功能+非功能需求/五维深度分析/数据资源/风险/假设/开放问题/分阶段/验收标准/附录A 完整对抗评审/附录B 多轮反馈）
- 定稿后自动生成交付物（HTML + 尽力 PDF），前端醒目「打开报告」按钮 + 保存路径，交付物信息写入档案
- 多轮累积：客户反馈条目织入功能/非功能/开放问题/验收标准对应章节，报告随版本变厚（附录 B 记录每轮反馈）
- `core/llm.py` `chat_json` 支持 `max_tokens` 透传（长输出不截断）

### Changed
- `diagnosis/agents.py` / `orchestrator.py` / `archive.py` / `feedback.py` / `cases/render.py` / `core/api.py` / `web/app.js`
- 兼容旧字段：`dimension_scores` / `reasons` / `verdicts` / `bias` 由新 schema 归一化推导，置信度/分歧/旧接口不受破坏

## [1.2.0] - 2026-08-28

### Added
- 语义去重（基于向量相似度）
- 监控看板成本追踪与趋势图
- 裁剪引擎新增网络带宽与合规等级约束维度
- Reflexion 循环模式
- 长期记忆向量检索（嵌入语义去重模块）
- PDF 解析增强：区分文字版与扫描版
- 部署前环境变量检查脚本

### Changed
- 数据清洗器支持可配置相似度去重与语义去重
- 监控指标收集器增加输入/输出 token 拆分与小时分桶
- 五步裁剪引擎规则扩展
- ReAct 与 Plan-Execute 循环支持注入自定义函数

### Fixed
- 修复 EvalSet.coverage 字段类型错误
- 修复 PDF 解析扫描版乱码问题
- 修复数据去重误删问题

## [1.1.0] - 2026-08-27

### Added
- PDF 解析质量检测与扫描版跳过
- 去重策略支持相似度阈值
- 流式输出自动重连（指数退避）
- 部署前环境变量检查脚本
- PDF 解析与去重单元测试

### Changed
- 数据清洗器增加可配置去重策略

## [0.1.0] - 2026-08-26

### Added
- 统一底座：配置、安全、日志、版本、降级、模块注册、数据库
- 数据准备器：接入、评估、清洗、评测集构建
- 原型组装器：Agent Harness、ReAct/Plan-Execute 循环、记忆、工具、上下文、结构化输出、流式、三个场景模板
- 五步裁剪引擎：7 类约束、五步执行、方案输出
- 部署加固器：Docker 化、降级预案、Compose、裸机
- 需求诊断器：五维评估、诊断报告
- 监控开箱器：基础指标、告警、看板
- 数据飞轮器：反馈回流、评测集更新、资产导出
- 发布与回滚脚本
- 全量单元测试与端到端测试