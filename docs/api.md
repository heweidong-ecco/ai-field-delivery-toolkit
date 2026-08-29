# AI 项目现场交付工具包 - API 文档

本文档描述工具包提供的 HTTP API 和主要 Python API。HTTP API 由统一底座（`core/main.py` + `core/api.py`）提供，其他模块通过 Python 类和方法调用。

> 端点以 `core/api.py` 为准，按模块分组全量列出（v3-v11 迭代全部已实现）。所有 `POST` 请求体为 JSON（除标注的 `multipart` 上传）。

## 1. HTTP API（已实现）

所有模块端点统一挂在 `/api/v1` 前缀下，返回**原始 JSON**（不套 `{code,message,data}` 统一包装）。工作产物统一写入 `tmp/web/`（gitignore），经 `/artifacts/<模块>/<run_id>/...` 下载。

### 1.0 健康检查 / 模块注册

**GET** `/health`

```json
{ "status": "ok", "version": "1.2.0", "modules": [] }
```

> 注意：`version` 现读取包版本（`pyproject.toml [project].version`，当前 1.2.0），与包版本对齐；README 的「当前版本 v1.13.0」是**文档迭代版本号**（随功能说明/文档同步节奏递增），与库版本是两条独立的版本线。`modules` 会随模块注册而填充。

**POST** `/api/v1/registry/register`（测试用）

查询参数：`name`（模块名称）。返回 `{status, module}`。

> 接口调试可直接访问 FastAPI 自带的 Swagger UI：`http://localhost:8100/docs`。

### 1.1 需求诊断 diagnosis

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/v1/diagnosis/evaluate` | 五维 AI 适用性评估（手动打分） |
| POST | `/api/v1/diagnosis/ai` | 输入客户需求，LLM 中立视角打分（理由 + 总结） |
| GET  | `/api/v1/diagnosis/default-prompt` | 返回默认中立提示词 |
| POST | `/api/v1/diagnosis/report` | 生成诊断报告（支持 `manual_review` 人工复核打分） |
| POST | `/api/v1/diagnosis/start` | 多 Agent 一期：Generator 打分 + Critic 盲审 + 置信度 + 分歧 + 自动带出相关案例/资产 |
| POST | `/api/v1/diagnosis/review` | 人工打分 + Reviewer 盲审人工 + 分歧 |
| POST | `/api/v1/diagnosis/finalize` | 人工强制确认 → 定稿报告（自动挂项目档案 + 自动生成交付物 + 注册诊断方案资产） |
| POST | `/api/v1/diagnosis/feedback` | 上传/粘贴客户反馈 → 提炼客户意见条目（multipart） |
| POST | `/api/v1/diagnosis/next-version` | 生成下一版评估草稿（增量/整轮，含变更清单） |
| GET  | `/api/v1/diagnosis/runs` | 列出最近诊断 run（含人工名字/确认状态/project_id） |
| POST | `/api/v1/diagnosis/{run_id}/rename` | 给历史诊断设人工名字 |
| GET  | `/api/v1/diagnosis/{run_id}/state` | 返回可恢复的诊断执行状态（继续历史诊断） |
| GET  | `/api/v1/diagnosis/archive/{run_id}` | 返回完整档案（含版本历史） |

### 1.2 案例 / 交付物 cases

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/v1/cases/create` | 诊断定稿 → 可打印交付物案例（HTML + PDF + 结构化存档 + 自动挂项目） |
| POST | `/api/v1/cases/create-crop` | 裁剪方案 → 可打印交付物案例 |
| POST | `/api/v1/cases/create-doc-package` | 生成项目文档包（架构/API/运维/SOP，LLM 起草）；需人工确认（v10 门禁）否则 400 |
| GET  | `/api/v1/cases` | 列出案例 |
| GET  | `/api/v1/cases/search` | 跨案例检索（关键词 + 标签） |
| GET  | `/api/v1/cases/{case_id}` | 案例详情 |
| GET  | `/api/v1/cases/{case_id}/render.html` | 交付物 HTML |
| GET  | `/api/v1/cases/{case_id}/export.pdf` | 交付物 PDF |

### 1.3 项目档案 / 作战台 projects

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/v1/projects` | 创建项目 |
| GET  | `/api/v1/projects` | 列出项目 |
| GET  | `/api/v1/projects/{pid}` | 项目详情（事件时间线） |
| POST | `/api/v1/projects/{pid}/events` | 追加过程记录（meeting/issue/iteration/…） |
| GET  | `/api/v1/projects/{pid}/warroom` | 项目作战台聚合：诊断/数据作战流/映射/交付物/资产/RAG/工作流/时间线（v7） |

### 1.4 字段映射工作台 mapping

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/v1/mapping/create` | 创建映射任务，LLM 初判建议；自动带出相关映射配置资产 |
| GET  | `/api/v1/mapping/runs` | 列出最近映射任务（断点续接入口） |
| GET  | `/api/v1/mapping/{run_id}` | 映射任务详情 |
| POST | `/api/v1/mapping/{run_id}/update` | 人工调整映射（保存断点） |
| POST | `/api/v1/mapping/{run_id}/samples` | 导入真实样例数据 CSV（multipart，列名=源字段名） |
| POST | `/api/v1/mapping/{run_id}/validate` | 实跑校验：对真实样例执行 transform + LLM 逐条判定（pass/warn/fail） |
| POST | `/api/v1/mapping/{run_id}/validate-row` | 单行试运行：对给定一行源数据输出各目标字段映射值 |
| POST | `/api/v1/mapping/{run_id}/export` | 导出适配器配置 + Python 骨架（自动注册为可复用映射配置资产） |

### 1.5 可复用资产库 assets

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET  | `/api/v1/assets/list` | 列出可复用资产（可按 kind 过滤） |
| GET  | `/api/v1/assets/search` | 检索资产（关键词 + 类型 + 标签 + 客户） |
| GET  | `/api/v1/assets/suggest` | 规则评分自动带出相关资产（含 reason） |
| GET  | `/api/v1/assets/{asset_id}` | 资产详情 |
| POST | `/api/v1/assets/{asset_id}/adopt` | 一键接入：映射配置预填新 run / 数据资产复制到目标 run / 交付物登记引用 |

### 1.6 数据标注管理 annotation

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/v1/annotation/create` | 创建标注任务（手动粘贴样本，双人标注） |
| GET  | `/api/v1/annotation/runs` | 列出最近标注任务（含一致性统计） |
| POST | `/api/v1/annotation/from-dataprep` | 从数据作战流 cleaned_data 建任务（样本来源诚实标注） |
| GET  | `/api/v1/annotation/{run_id}` | 标注任务详情（每样本一致性明细） |
| POST | `/api/v1/annotation/{run_id}/label` | 打标签（标注员 A/B） |
| POST | `/api/v1/annotation/{run_id}/build-eval` | 从双人一致标注构建评测集 |

### 1.7 知识库构建 kb

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/v1/kb/chunk` | 长文本分块 + 质检（RAG 最小件） |

### 1.8 模块自描述 manifest / guide

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET  | `/api/v1/manifests` | 全部模块 manifest（功能说明数据源） |
| GET  | `/api/v1/manifests/{key}` | 单模块 manifest |
| GET  | `/api/v1/guide/workflow` | 连贯工作流：阶段 + 模块 + 产出 + 门禁 + 贯穿模块 |
| GET  | `/api/v1/guide/suggestions` | 动态使用建议：基于系统当前状态给出下一步 |
| GET  | `/api/v1/guide/{key}` | 某模块详细指南（manifest + 长篇步骤） |

### 1.9 工作流 SOP 骨架 + 质量门禁

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET  | `/api/v1/workflow/skeleton` | 工作流 SOP 骨架 |
| GET  | `/api/v1/workflow/gate` | 质量门禁判定（`stage` + 可选 `project_id`），供前端展示 |
| GET  | `/api/v1/workflow/{project_id}` | 项目工作流进度（按项目过滤） |

### 1.10 五步裁剪 cropper

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET  | `/api/v1/cropper/from-diagnosis/{run_id}` | 诊断结论 → 裁剪器约束预填（未定稿确认 400） |
| POST | `/api/v1/cropper/plan` | 客户约束 → 裁剪方案 |

### 1.11 数据准备 / 数据作战流 data_prep / dataprep

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/v1/data-prep/run` | 旧版一站式：上传 csv/json/pdf，执行清洗 + 评测集构建（multipart） |
| POST | `/api/v1/dataprep/create` | 新建数据作战流任务（csv/json，multipart；自动跑 导入/清洗/质量 前三步，返回可恢复状态） |
| GET  | `/api/v1/dataprep/runs` | 列出最近数据作战流任务（断点续接入口） |
| GET  | `/api/v1/dataprep/{run_id}` | 任务状态 + 各步产物 |
| POST | `/api/v1/dataprep/{run_id}/step` | 执行某步（annotate/eval_set/knowledge_base/…）或 `run_next` 顺序推进 |
| POST | `/api/v1/dataprep/{run_id}/rename` | 给数据作战流任务人工命名 |
| POST | `/api/v1/dataprep/{run_id}/deposit` | 沉淀可复用资产（评测集/知识库分块/清洗规则/质量报告） |

### 1.12 原型组装 prototype

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET  | `/api/v1/prototype/templates` | 列出 Agent 模板（含 meta：每模板「真调 DeepSeek / RAG 就绪」标注） |
| POST | `/api/v1/prototype/run` | 运行 Agent 原型（4 模板真调 DeepSeek；传 project_id 过数据门禁，未过 403 / force 强制记录 override） |

### 1.13 RAG 检索问答 retrieval

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/v1/retrieval/index` | 知识库分块索引进 ChromaDB（真实向量化；缺省 chunks 自动读数据作战流 knowledge_base 产物） |
| POST | `/api/v1/retrieval/query` | RAG 问答：检索 top_k 相关分块 → 调 LLM → `{answer, sources}` |
| GET  | `/api/v1/retrieval/indexed` | 列出已索引知识库（前端「选择知识库」下拉） |

### 1.14 部署加固 deploy

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/v1/deploy/run` | 生成 docker-compose / bare-metal 部署配置（含降级预案） |

### 1.15 监控 monitor

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/v1/monitor/record` | 记录一次调用指标 |
| GET  | `/api/v1/monitor/metrics` | 获取指标 + 告警 + 真实 LLM 用量/成本（计费打点自动喂） |

### 1.16 数据飞轮 data_flywheel

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/api/v1/flywheel/feedback` | 记录反馈 |
| GET  | `/api/v1/flywheel/pool` | 查看标注池 |
| POST | `/api/v1/flywheel/export-assets` | 导出可复用资产 |

## 2. 统一响应格式与错误码（设计契约，HTTP 层不套包装）

> ⚠️ **实际 API 返回原始 JSON + HTTP 状态码，未套 `{code,message,data}` 包装**。以下统一契约（`docs/统一底座架构设计.md` 定义）为设计期约定，不在 HTTP 层生效。

实际 HTTP 层使用的常见错误状态码：

| HTTP 状态码 | 含义 |
| ------ | ------ |
| 400 | 需人工确认 / 参数错误（如诊断未定稿确认禁止裁剪、文档包未确认） |
| 403 | 质量门禁未过（如数据未达标不进原型，未勾选强制继续） |
| 404 | 资源不存在（run_id / case_id / 项目不存在） |
| 429 | 预算超限（诊断/映射 LLM 调用超预算） |

目标统一响应结构（设计契约，未在 HTTP 层实现）：

```json
{ "code": 0, "message": "success", "data": {} }
```

设计期错误码列表：

| 错误码 | 含义               |
| ------ | ------------------ |
| 0      | 成功               |
| 1001   | 参数错误           |
| 1002   | 认证失败           |
| 1003   | 权限不足           |
| 1004   | 资源不存在         |
| 2001   | 数据接入失败       |
| 2002   | 数据质量不合格     |
| 2003   | 数据清洗失败       |
| 3001   | 模型调用失败       |
| 3002   | 模型超时           |
| 3003   | 结构化输出验证失败 |
| 3004   | 流式输出中断       |
| 4001   | Docker 构建失败    |
| 4002   | 部署失败           |
| 5001   | 监控数据上报失败   |
| 6001   | 反馈回流失败       |
| 7001   | 裁剪引擎约束不完整 |

## 3. Python API（模块级）

### 3.1 统一底座 core

| 类/函数                          | 说明                  |
| -------------------------------- | --------------------- |
| `get_settings()`                 | 获取全局配置单例      |
| `get_logger()`                   | 获取全局 logger       |
| `PIIDetector.detect(text)`       | 检测文本中的 PII 类型 |
| `PIIDetector.mask(text)`         | 对 PII 进行脱敏       |
| `InjectionDetector.detect(text)` | 检测提示词注入        |
| `OutputReviewer.review(text)`    | 输出内容审核          |
| `VersionManager`                 | 版本管理              |
| `DegradationManager.execute()`   | 降级管理统一入口      |
| `get_registry()`                 | 获取模块注册中心      |

### 3.2 需求诊断器 diagnosis

| 类/函数                                      | 说明         |
| -------------------------------------------- | ------------ |
| `AIFeasibilityChecklist.evaluate(scores)`    | 五维评估     |
| `AIFeasibilityChecklist.quick_evaluate(...)` | 快速评估     |
| `DiagnosisReportGenerator.generate(...)`     | 生成诊断报告 |
| `DiagnosisReportGenerator.save_report(...)`  | 保存报告     |

### 3.3 数据准备器 data_prep

| 类/函数                                   | 说明             |
| ----------------------------------------- | ---------------- |
| `DataPrepPipeline.run(...)`               | 完整数据准备管道 |
| `DataCleaner.clean(...)`                  | 数据清洗         |
| `DataQualityEvaluator.evaluate(data)`     | 数据质量评估     |
| `EvalSetBuilder.build(data, num_samples)` | 构建评测集       |
| `deduplicate(data, similarity_threshold)` | 字符级去重       |
| `semantic_deduplicate(data, similarity_threshold)` | 语义去重 |

### 3.4 原型组装器 prototype_assembler

| 类/函数                                             | 说明            |
| --------------------------------------------------- | --------------- |
| `PrototypeAssembler.create(template_name)`          | 创建 Agent 原型 |
| `PrototypeAssembler.run(template_name, user_input)` | 创建并运行      |
| `Agent.run(user_input)`                             | 执行 Agent      |
| `Agent.save_state(path)`                            | 保存状态        |
| `Agent.load_state(path)`                            | 加载状态        |
| `ShortTermMemory.add(role, content)`                | 添加短期记忆    |
| `ShortTermMemory.get_all() / get_last_n(n) / clear()` | 读取/清空短期记忆 |
| `LongTermMemory.set(key, value)`                    | 设置长期记忆    |
| `LongTermMemory.get(key) / get_relevant(query)`     | 读取长期记忆    |
| `ContextBuilder.build(...)`                         | 构建上下文      |

### 3.5 五步裁剪引擎 cropper

| 类/函数                                | 说明         |
| -------------------------------------- | ------------ |
| `crop_for_customer(constraints)`       | 生成裁剪方案 |
| `FiveStepCropper.execute(constraints)` | 执行五步裁剪 |
| `CropPlan.to_dict()`                   | 方案转为字典 |
| `CropPlan.save(path)`                  | 保存方案     |

### 3.6 部署加固器 deploy_hardener

| 类/函数                                 | 说明                  |
| --------------------------------------- | --------------------- |
| `DeployHardenerPipeline.run(...)`       | 部署加固管道          |
| `Dockerizer.generate_dockerfile(...)`   | 生成 Dockerfile       |
| `ComposeGenerator.generate(...)`        | 生成 Compose 文件     |
| `BaremetalGenerator.generate(...)`      | 生成 systemd 服务文件 |
| `DegradationPreset.get_default_chain()` | 获取降级链            |

### 3.7 监控开箱器 monitor

| 类/函数                                        | 说明         |
| ---------------------------------------------- | ------------ |
| `MetricsCollector.record_request(...)`         | 记录请求指标 |
| `MetricsCollector.get_metrics()`               | 获取指标汇总 |
| `AlertManager.check_all(metrics)`              | 检查告警     |
| `DashboardGenerator.generate(metrics, alerts)` | 生成看板数据 |

> `MetricsCollector.record_request(success, latency_ms, input_tokens=0, output_tokens=0, model="unknown", hour=None)`：v1.2.0 起 token 按 input/output 拆分，`tokens=` 单参数已废弃。

### 3.8 数据飞轮器 data_flywheel

| 类/函数                                     | 说明             |
| ------------------------------------------- | ---------------- |
| `DataFlywheelPipeline.record_feedback(...)` | 记录反馈         |
| `DataFlywheelPipeline.update_eval_set(...)` | 更新评测集       |
| `DataFlywheelPipeline.export_assets(...)`   | 导出资产         |
| `FeedbackCollector.add_feedback(...)`       | 添加反馈到标注池 |
| `EvalSetUpdater.update(...)`                | 评测集更新       |
| `AssetExporter.export(...)`                 | 资产导出         |

---
