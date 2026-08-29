# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

`ai-field-delivery-toolkit` 是面向 FDE（前线部署工程师）的模块化交付工具包，覆盖 AI 项目从需求诊断到数据飞轮的完整现场交付流程。Python 3.11，纯库代码（无核心模块强依赖数据库/外部 API），本地优先、可离线运行。

模块均为独立目录 + 薄管道入口类，通过统一底座 `core/` 共享配置、日志与安全能力。中文注释/docstring 是仓库惯例；业务标识符保持英文。

## 常用命令

```bash
# 激活环境（仓库内已有 venv/）
source venv/bin/activate

# 一键初始化（检查 Python/Docker → 生成 .env → 装依赖 → 启动基础设施）
./scripts/setup.sh

# 基础设施（PostgreSQL / Redis / ChromaDB，docker compose 启动）
make up          # docker compose up -d
make check       # 健康检查（pg_isready / redis ping / chroma heartbeat）
make down        # 停止
make init-db     # python -m core.db.init_db（建表，需先 up）

# 运行 API + FDE 操作台（FastAPI，端口来自 settings.api_port=8100）
# 浏览器打开 http://localhost:8100/ 使用网页版操作台（11 个标签页 ①-⑪）
python -m core.main

# 测试
make test                  # pytest tests/ -v
make test-cov              # pytest tests/ --cov=. --cov-report=html
pytest tests/test_cropper.py                      # 单个文件
pytest tests/test_cropper.py::TestCropPlan::test_x  # 单个用例
pytest tests/ -k "cost"     # 按名称过滤

# 示例（每个模块一个，examples/*_example.py）
make example-cropper       # 等价于 python examples/cropper_example.py
# 可用：example-core / example-data-prep / example-prototype / example-cropper
#      example-deploy / example-diagnosis / example-monitor / example-flywheel

# 发布与回滚
./scripts/release.sh 1.2.0     # 先跑测试 → 构建镜像 → 打标签 → 记录回滚版本
./scripts/rollback.sh 1.2.0

make clean       # 清理 __pycache__ / .pytest_cache
```

## 架构

### 统一底座 `core/`（所有模块的共享层）

模块**不直接读环境变量、不自己初始化日志**，统一经底座访问：

- `core/config/settings.py` — `get_settings()` 单例（pydantic-settings，读 `.env`）。配置优先级：环境变量 > `config.yaml` > 内置默认值。API Key 等敏感配置只走环境变量。
- `core/logging/logger.py` — `get_logger()` 单例（loguru，控制台 + 按天滚动文件）。
- `core/security/` — PII 检测/脱敏（`PIIDetector`）、提示词注入拦截（`InjectionDetector`）、输出审核（`OutputReviewer`，占位）。设计意图是所有模块 IO 自动经过，目前需显式调用。
- `core/degradation/manager.py` — `DegradationManager.execute()`，AI 调用统一降级路径：正常 → 缓存 → 规则 → 人工 → 拒绝。设计约定"所有 AI 调用必须经过"，但当前代码未强制。
- `core/registry.py` — `get_registry()` 模块注册中心单例（FastAPI 启动时注册各模块）。
- `core/db/` — SQLAlchemy 2.0 异步（asyncpg），8 张表定义在 `models.py`（projects / data_versions / eval_sets / prototype_runs / deployments / feedbacks / crop_plans / assets）。`init_db.py` 建表。
- `core/main.py` — FastAPI 入口，`create_app()` + `/health` + 注册接口；`python -m core.main` 启动。
- `core/api.py` — FDE 操作台 REST 端点（包装全部模块，返回原始 JSON）；`web/` — 操作台前端（零构建静态页，11 个标签页 ①-⑪）。产物写入 `tmp/web/`，经 `/artifacts/...` 下载。

**跨模块 API 契约与统一错误码的设计期权威在 `docs/统一底座架构设计.md`**；目录结构以 README 目录树为准；实际端点全量以 `docs/api.md` 为准。

### 六个功能模块 + 裁剪引擎

每个模块一个入口类，用法与示例脚本一一对应（`examples/`）：

| 模块 | 入口 | 说明 |
| ---- | ---- | ---- |
| `diagnosis/` | `AIFeasibilityChecklist.evaluate()/quick_evaluate()` | 五维 AI 适用性评分（1-5 分/维，总分决定结论），`DiagnosisReportGenerator` 出报告 |
| `data_prep/` | `DataPrepPipeline.run(source_type, source_path, output_dir, eval_samples)` | 接入（csv/json/pdf/db）→ 质量评估 → 清洗 → 评测集。清洗含字符级去重 + 语义去重（ChromaDB `DefaultEmbeddingFunction`，首次调用需联网下载模型），扫描版 PDF 会被标记跳过 |
| `prototype_assembler/` | `PrototypeAssembler.create(template_name)` → `Agent.run(input)` | 4 种模板（`knowledge_qa` / `information_extraction` / `multi_step_reasoning` / `reflexion`），每种由 harness + loop + memory + tools + context 组装 |
| `deploy_hardener/` | `DeployHardenerPipeline.run(mode="docker-compose"\|"bare-metal")` | 生成降级预案 `degradation.yaml` + Dockerfile/compose 或 systemd 单元；`pre_deploy_check.sh` 做环境变量预检 |
| `monitor/` | `MetricsCollector` + `AlertManager` + `DashboardGenerator` | 全内存指标（含 token/成本追踪、按小时分桶）、3 条默认告警规则、看板 JSON |
| `data_flywheel/` | `DataFlywheelPipeline.record_feedback()/update_eval_set()/export_assets()` | 反馈 → JSON 标注池 → 评测集更新 → 复用资产导出 |
| `cropper/` | `crop_for_customer(CustomerConstraints)` → `CropPlan` | **跨模块决策引擎**：按客户约束（预算/硬件/环境/数据/用户/合规）五步裁剪出 `enabled_modules` / `deleted_modules` / `simplifications` / `timeline_suggestion` |

### 跨模块数据流

```
diagnosis（该不该上 AI）→ cropper（砍哪些模块/简化）→ data_prep（数据）→
prototype_assembler（Agent 原型）→ deploy_hardener（部署）→ monitor（运行指标）
                        └──────────── data_flywheel（反馈回流，闭环回到数据/评测）──────────┘
```

`cropper/five_steps.py` 中的 `ALL_MODULES` 是全工具包模块清单，裁剪结果直接决定客户启用哪些模块。

### 关键约定与模式

- **全局单例模式**：每个共享对象用模块级 `_x = None` + `get_x()`（如 `get_settings` / `get_logger` / `get_registry`）。
- **LLM 调用默认真调（注入式可覆盖）**：原型 4 模板默认真调 DeepSeek（`core/llm.py`），诊断多 Agent / 映射初判与校验 / RAG 问答均真调；未配置 key 时诊断/映射有规则兜底、原型/检索诚实报错。注入式（给 `Agent` 注入 `llm_call` / `plan_generator` / `step_executor` / `answer_generator` 函数，v1.2.0 起支持）仍可用作覆盖。`prototype_assembler/loops/react.py` 的 `_call_llm` 默认回退为 `"finish: 已完成任务"`（未注入时）。
- **持久化**：多数模块状态在内存或 JSON 文件（如 `annotation_pool.json`、`crop_plan.json`），数据库仅底座层提供；这些产物文件在 `.gitignore` 中。
- **示例即文档**：新增/改动模块行为时，同步更新 `examples/<module>_example.py` 与 README 模块状态表。
- 测试用 `conftest.py` 保证项目根在 `sys.path`；e2e 测试（`tests/test_e2e.py`）串起诊断→裁剪→数据→原型→部署→监控→飞轮全流程，是理解各模块协作的最佳入口。

## 当前状态

- 测试套件 163 个用例全部通过（`pytest tests/`）。
- 语义去重（`data_prep/cleaning/semantic_dedup.py`）基于 ChromaDB `DefaultEmbeddingFunction`（all-MiniLM-L6-v2），**首次调用会联网下载约 79MB 模型**，模型缓存于 `~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/`；内网隔离/受限网络的部署机需预置该模型，否则调用会长时间阻塞（`DataPrepPipeline` 默认启用语义去重）。
- `requirements.txt` 固定了 `numpy<2`（chromadb 0.5.0 导入时引用 `np.float_`，numpy 2.x 已移除）。
- 已修复的独立 bug：`monitor/metrics.py` 缺失 `Optional` 导入、`deploy_hardener/pipeline.py` 重复 `run()` 及未初始化生成器、`data_prep/quality/evaluator.py` 缺失 `QualityReport` 导入、字符去重误删（`dedup.py` 精确去重改为基于原始文本）、`anomaly.py` 乱码判定误杀中文、`pdf_loader.py` 非 PDF 文件回退纯文本、`EvalSetBuilder` 空桶配额浪费、`test_e2e.py` 过时 `tokens=` 参数。

## 文档

- `docs/统一底座架构设计.md` — 权威架构、错误码表、API 契约、五步裁剪设计、数据库设计
- `docs/development-process.md` — 分支/提交/审查/覆盖率规范
- `docs/config-spec.md` / `docs/version-spec.md` / `docs/security-baseline.md` / `docs/api.md`
- `notes/` — 项目决策记录（T-xxx），`CHANGELOG.md` 按模块记录每个版本变更
