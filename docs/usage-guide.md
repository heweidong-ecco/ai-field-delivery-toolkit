# AI 项目现场交付工具包 - 使用教程

面向 FDE（Forward Deployed Engineer，前线部署工程师）的模块化交付工具箱。覆盖 AI 项目从**需求诊断 → 方案裁剪 → 数据准备 → 原型组装 → 部署加固 → 运行监控 → 数据飞轮**的完整现场交付流程。

## 1. 功能总览

| 模块 | 目录 | 功能 |
| ---- | ---- | ---- |
| 统一底座 | `core/` | 配置中心、安全基座、日志、版本管理、降级管理、模块注册、数据库、FastAPI 入口、**统一 LLM 客户端（计费打点）** |
| 需求诊断器 | `diagnosis/` | **多 Agent 对抗评审**（Generator/Critic/Reviewer 盲审）+ 人工复核 + AI 再评分 + 非技术全景可行性 + 商务提案 + 版本化交付 + 客户反馈闭环 |
| 五步裁剪引擎 | `cropper/` | 按客户约束裁剪「哪些模块该上、怎么简化」；**支持从诊断结论带入** |
| 数据准备器 | `data_prep/` | 接入 → 质量评估 → 清洗 → 评测集；**数据作战流见 dataprep 模块** |
| 数据作战流 | `dataprep/` | 项目级 6 步数据流水线（导入→清洗→质量→标注→评测集→知识库）+ **run_id 断点续接** + 每步产物落盘 + **沉淀可复用资产** + 知识库自动索引 RAG 就绪 |
| 原型组装器 | `prototype_assembler/` | Agent 模板、ReAct 循环、记忆、工具；**4 个模板全部真调 DeepSeek**（知识问答支持 RAG） |
| 部署加固器 | `deploy_hardener/` | Docker 化 / 裸机 systemd + 降级预案 + 部署前环境检查 |
| 监控开箱器 | `monitor/` | 指标收集 + **真实 LLM 用量/成本（计费打点自动喂）** + 告警 + 看板 |
| 数据飞轮器 | `data_flywheel/` | 反馈回流 → 评测集更新 → 复用资产导出 |
| 案例/交付物层 | `cases/` | 诊断定稿 → **可打印 HTML/PDF 交付物** + 结构化案例存档 + 案例检索 + 项目文档包 |
| 项目档案/作战台 | `projects/` | 以项目为中心的过程记录（时间线）+ **作战台 warroom**（诊断/数据/映射/交付物/资产/RAG 全产物聚合 + 一键跳转续做） |
| 字段映射工作台 | `mapping/` | **LLM 初判** + 导入真实样例 + **实跑校验（逐字段 pass/warn/fail）** + 人工修正迭代 + 导出适配器 + 断点续接 |
| 数据标注管理 | `annotation/` | **人工双人标注工作台**（标注员 A/B → 逐行一致性 → 分歧改判 → 评测集） |
| 知识库构建 | `kb/` | 长文本分块 + 质检（RAG 最小件） |
| RAG 检索问答 | `retrieval/` | 知识库分块 → 向量化(ChromaDB) → 检索 → **带引用问答** |
| 可复用资产库 | `assets/` | 可复用资产注册表：诊断/数据作战流/映射**自动入库** + 检索/建议 + **一键接入 adopt**（项目越多、工具越强） |

**核心原则**：模块独立可单独使用；所有模块通过统一底座共享配置/日志/安全；本地优先、无外部依赖（语义去重除外，见 6.1）。

## 2. 环境准备

### 2.1 依赖要求

- Python 3.11+
- Docker & Docker Compose（用于 PostgreSQL / Redis / ChromaDB 基础设施，可选）
- 至少 8GB 内存

### 2.2 一键初始化（推荐）

```bash
./scripts/setup.sh
# 自动完成：检查 Python/Docker → 生成 .env → 安装依赖 → 启动基础设施
```

### 2.3 手动初始化

```bash
# 1. 创建虚拟环境并激活
python3.11 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env：填入 DEEPSEEK_API_KEY 等（原型 4 个模板真调 DeepSeek，Key 用于原型运行，见 6.2）

# 4. 启动基础设施（PostgreSQL / Redis / ChromaDB）
docker compose up -d

# 5. 验证环境健康
make check

# 6. 初始化数据库（建表）
make init-db
```

> 绝大多数模块（诊断、裁剪、原型、监控、飞轮、部署配置生成）**不需要**数据库和外部服务即可运行，纯本地调用。只有 `core/db` 和 FastAPI 入口依赖数据库。

## 3. 运行测试、示例与 API

### 3.1 测试

```bash
make test                  # 全部测试
make test-cov              # 生成覆盖率报告（htmlcov/）
pytest tests/test_cropper.py -q                       # 单文件
pytest tests/test_cropper.py::TestCropPlan::test_x   # 单个用例
```

### 3.2 示例脚本

每个模块在 `examples/` 有一个可运行示例：

```bash
source venv/bin/activate
python examples/core_example.py          # 统一底座
python examples/diagnosis_example.py     # 需求诊断
python examples/cropper_example.py       # 五步裁剪
python examples/data_prep_example.py     # 数据准备
python examples/prototype_example.py     # 原型组装
python examples/deploy_example.py        # 部署加固
python examples/monitor_example.py       # 监控
python examples/data_flywheel_example.py # 数据飞轮
```

也可以用 Makefile 快捷命令：`make example-core example-cropper ...`

### 3.3 启动 API（FastAPI 底座）

```bash
python -m core.main
# FastAPI 启动在 http://localhost:8100（端口来自 settings.api_port）
# GET  /health                      → 健康状态 + 已注册模块
# POST /api/v1/registry/register    → 手动注册模块
```

> 各模块既可作 **Python 库** 调用，也可通过 **FDE 操作台**在网页上使用：`python -m core.main` 启动后访问 `http://localhost:8100/`（11 个标签页 ①-⑪ 对应全部模块），端点与用法见 `docs/api.md`。

## 4. 各模块使用指南

### 4.1 统一底座 `core/`

所有模块的公共依赖。**统一入口，不要在模块里直接读环境变量或自建日志**。

```python
from core.config.settings import get_settings      # 全局配置（pydantic-settings，读 .env）
from core.logging.logger import get_logger         # 全局日志（loguru）
from core.security.pii import PIIDetector          # PII 检测与脱敏
from core.security.injection import InjectionDetector  # 提示词注入拦截
from core.registry import get_registry             # 模块注册中心
from core.version.manager import VersionManager    # 版本管理
from core.degradation.manager import DegradationManager  # AI 调用降级

logger = get_logger()
settings = get_settings()
print(settings.postgres_host, settings.default_model)

# PII 脱敏
text = "我的手机号是13812345678，邮箱是test@example.com"
print(PIIDetector.detect(text))   # ['phone', 'email']
print(PIIDetector.mask(text))     # 手机号/邮箱被打码

# 模块注册
registry = get_registry()
registry.register("data_prep", dependencies=["core"], config_keys=["cleaning_intensity"])

# 降级管理：所有 AI 调用走统一降级链（正常 → 缓存 → 规则 → 人工 → 拒绝）
manager = DegradationManager()
result = manager.execute(model_call=..., cache_get=..., rule_fallback=...)
```

配置来源优先级：**环境变量 > config.yaml > 内置默认值**。敏感配置（API Key、密码）只走 `.env`。

### 4.2 需求诊断器 `diagnosis/`

判断一个客户场景**适不适合上 AI**。五个维度各 1-5 分，总分 5-25：

- 生成性、推理复杂度、不确定性容忍度、数据可得性、实时性要求（实时性要求越低分越适合 AI）
- 总分 ≥20 强烈推荐；15-19 推荐但需谨慎；10-14 一般；<10 不推荐

```python
from diagnosis.checklist import AIFeasibilityChecklist
from diagnosis.report import DiagnosisReportGenerator

checklist = AIFeasibilityChecklist()
result = checklist.quick_evaluate(
    generation=4, reasoning=3, uncertainty=4, data=5, real_time=2,
)
print(result["total_score"], result["conclusion"], result["suggestion"])

# 生成诊断报告（含下一步建议）
report_gen = DiagnosisReportGenerator()
report = report_gen.generate(
    customer_name="研发团队",
    requirement_summary="基于内部文档的智能问答",
    feasibility_result=result,
    interview_notes="访谈 5 人，主要痛点是文档查找慢",
    decision_maker="研发负责人",
)
report_gen.save_report(report, "diagnosis_report.json")
```

**AI 中立评估**：操作台（`http://localhost:8100/#tab-diagnosis`）支持直接输入客户需求，由 LLM（默认 DeepSeek）按**可自定义的严格中立提示词**打分，输出各维度理由 + 总结（实现见 `diagnosis/ai_scorer.py`，API 为 `POST /api/v1/diagnosis/ai`）。未配置 `DEEPSEEK_API_KEY` 或模型调用失败时，自动降级为规则关键词评估并在结果中标注。

### 4.3 五步裁剪引擎 `cropper/`

根据客户约束，五步裁剪（质疑 → 删除 → 简化 → 加速 → 自动化），输出「启用哪些模块、删掉哪些、怎么简化、排期建议」。

```python
from cropper.constraints import (
    CustomerConstraints, HardwareConstraints, EnvironmentConstraints,
    DataConstraints, UserConstraints, ComplianceConstraints,
)
from cropper.engine import crop_for_customer

constraints = CustomerConstraints(
    customer_id="customer-001",
    budget=200000,
    hardware=HardwareConstraints(cpu="8核", memory_gb=32, gpu=None, storage_gb=500),
    environment=EnvironmentConstraints(
        os="ubuntu-22.04", docker=True,
        network="intranet-isolated", external_access=False, network_bandwidth_mbps=20,
    ),
    data=DataConstraints(total_records=300000, daily_new=500, formats=["csv", "json"], quality="dirty"),
    users=UserConstraints(total_users=100, concurrent_peak=20),
    compliance=ComplianceConstraints(data_residency="on-premise", pii_sensitive=True, compliance_level="standard"),
    timeline_weeks=2,
)

plan = crop_for_customer(constraints)
print("启用:", plan.enabled_modules)
print("删除:", plan.deleted_modules)
print("简化:", plan.simplifications)
print("排期:", plan.timeline_suggestion)
plan.save("crop_plan.json")
```

关键规则示例：无 GPU 只保留 ReAct 循环；预算 <3 万直接删 monitor/flywheel/deploy；内网隔离时外部 API 需本地替代；带宽 <50Mbps 时监控/飞轮降级为批量。

### 4.4 数据准备器 `data_prep/`

一站式：**接入 → 质量评估 → 清洗 → 评测集构建**，结果写入 `output_dir`。

支持的数据源：`csv` / `json` / `pdf`（扫描版自动标记跳过）/ `db`（PostgreSQL）。

```python
from data_prep.pipeline import DataPrepPipeline

pipeline = DataPrepPipeline()
result = pipeline.run(
    source_type="csv",          # csv / json / pdf / db
    source_path="data/raw.csv",
    output_dir="output/prep",
    eval_samples=100,           # 评测集样本数
    db_connection=None,         # source_type="db" 时传入连接串
)
print(result["raw_count"], result["cleaned_count"], result["eval_set_count"])
```

清洗流水线（`data_prep/cleaning/`）默认执行：字符级去重 → **语义去重**（ChromaDB MiniLM 模型，阈值 0.85，见 6.1）→ 归一化 → 异常过滤（短/超长/乱码）→ PII 脱敏。

产物文件：`cleaned_data.json` / `eval_set.json` / `quality_report.json` / `cleaning_stats.json`。

### 4.5 原型组装器 `prototype_assembler/`

按模板组装一个可运行的 Agent 原型（harness + 循环 + 记忆 + 工具 + 上下文）。

```python
from prototype_assembler.assembler import PrototypeAssembler

assembler = PrototypeAssembler()
print(list(assembler.TEMPLATE_MAP.keys()))
# ['knowledge_qa', 'information_extraction', 'multi_step_reasoning', 'reflexion']

agent = assembler.create("knowledge_qa")
result = agent.run("什么是RAG？")
print(result)
```

> ✅ **四个模板默认真调 DeepSeek**（v8.0 起）：`knowledge_qa` / `information_extraction` / `multi_step_reasoning` / `reflexion` 的 `create_*_agent()` 均已注入真实 LLM 调用（内部 `from core.llm import chat`）。自定义注入依然可用——给 Agent 注入函数可覆盖/替换默认实现：

```python
agent = assembler.create("knowledge_qa")

def my_llm(agent, context, user_input):
    # 在这里调用你的模型 API，返回形如 "finish: 回答" 的字符串
    return "finish: 你的回答"

agent.llm_call = my_llm   # ReAct 用
# Plan-Execute 循环还可注入 plan_generator / step_executor / answer_generator
result = agent.run("什么是RAG？")
```

### 4.6 部署加固器 `deploy_hardener/`

为项目生成部署配置和降级预案。两种模式：`docker-compose` / `bare-metal`。

```python
from deploy_hardener.pipeline import DeployHardenerPipeline

pipeline = DeployHardenerPipeline()

# Docker Compose 模式：生成 docker-compose.yml + Dockerfile + degradation.yaml
result = pipeline.run(project_dir=".", output_dir="output/deploy", mode="docker-compose")
print(result["compose_file"], result["dockerfile"], result["degradation_config"])

# 裸机模式：生成 systemd 服务文件
result2 = pipeline.run(project_dir=".", output_dir="output/deploy_bare", mode="bare-metal")
print(result2["systemd_service"])
```

如果项目目录下存在 `deploy_hardener/pre_deploy_check.sh`，管道会先做**环境变量预检**（`POSTGRES_*`、`REDIS_URL` 等缺失即报错）。也可手动运行：

```bash
bash deploy_hardener/pre_deploy_check.sh
```

### 4.7 监控开箱器 `monitor/`

收集运行指标（内存存储）、按规则告警、生成看板数据。

```python
from monitor.metrics import MetricsCollector
from monitor.alerts import AlertManager
from monitor.dashboard import DashboardGenerator

collector = MetricsCollector()
collector.record_request(success=True, latency_ms=120, input_tokens=350, output_tokens=150, model="deepseek-chat")
collector.record_request(success=False, latency_ms=3500, input_tokens=0, output_tokens=0, model="deepseek-chat")
collector.record_degradation()

metrics = collector.get_metrics()
print(metrics["total_requests"], metrics["success_rate"], metrics["p99_latency_ms"], metrics["total_cost"])

alert_mgr = AlertManager()                     # 默认 3 条规则：错误率 / P99 延迟 / 降级
triggered = alert_mgr.check_all(metrics)

dashboard = DashboardGenerator().generate(metrics, triggered)
DashboardGenerator().save_dashboard(dashboard, "dashboard.json")
```

`MODEL_PRICES` 在 `monitor/metrics.py` 中维护（元/百万 token），可据实调整以估算成本。

### 4.8 数据飞轮器 `data_flywheel/`

把线上反馈回流成评测集与可复用资产，形成闭环。

```python
from data_flywheel.pipeline import DataFlywheelPipeline

pipeline = DataFlywheelPipeline(storage_path="annotation_pool.json")

# 1. 记录反馈（dislike / audit_fail / low_confidence）
pipeline.record_feedback(
    request_id="req-001",
    user_input="什么是RAG？",
    model_output="RAG是检索增强生成。",
    feedback_type="dislike",
    note="回答过于简单",
)
pipeline.feedback_collector.save("annotation_pool.json")

# 2. 用标注池更新评测集（eval_set.json 来自数据准备器）
update = pipeline.update_eval_set(eval_set_path="eval_set.json", num_samples=20, output_path="eval_set_updated.json")
print(update["added_count"], update["total_count"])

# 3. 导出可复用资产
assets = [
    {"type": "component", "name": "PII脱敏组件", "path": "core/security/pii.py", "description": "通用PII检测与脱敏"},
]
asset_result = pipeline.export_assets(project_id="project-001", assets=assets, output_path="project_assets.json")
print(asset_result["total_assets"])
```

## 5. 端到端工作流

一次典型的 FDE 交付，各模块串起来：

```python
# 1. 诊断：这个需求适不适合 AI？
from diagnosis.checklist import AIFeasibilityChecklist
feasibility = AIFeasibilityChecklist().quick_evaluate(4, 3, 4, 5, 2)

# 2. 裁剪：客户约束下该上哪些模块、怎么简化？
from cropper.constraints import CustomerConstraints
from cropper.engine import crop_for_customer
plan = crop_for_customer(CustomerConstraints(customer_id="e2e-customer", budget=100000))

# 3. 数据准备
from data_prep.pipeline import DataPrepPipeline
prep = DataPrepPipeline().run(source_type="csv", source_path="data.csv", output_dir="output/prep", eval_samples=100)

# 4. 原型组装
from prototype_assembler.assembler import PrototypeAssembler
agent_result = PrototypeAssembler().run("knowledge_qa", "什么是RAG？")

# 5. 部署加固
from deploy_hardener.pipeline import DeployHardenerPipeline
deploy = DeployHardenerPipeline().run(project_dir=".", output_dir="output/deploy", mode="docker-compose")

# 6. 监控
from monitor.metrics import MetricsCollector
collector = MetricsCollector()
collector.record_request(success=True, latency_ms=100, input_tokens=50, output_tokens=50)
print(collector.get_metrics()["success_rate"])

# 7. 数据飞轮：反馈回流 → 评测集 → 资产
from data_flywheel.pipeline import DataFlywheelPipeline
flywheel = DataFlywheelPipeline()
flywheel.record_feedback(request_id="req-1", user_input="问题", model_output="回答", feedback_type="dislike")
flywheel.export_assets(project_id="pilot-001", output_path="assets.json")
```

完整可运行版本见 `tests/test_e2e.py::test_full_flow`。

> **v11 真实试运行（推荐先看）**：`examples/pilot_example.py` 把全工具链在真实制造业客户项目上端到端跑通——需求诊断（多 Agent + 人工确认）→ 数据作战流 6 步（断点续接 + 知识库自动索引）→ 原型 + RAG（过数据门禁）→ 字段映射（导入真实样例 + 实跑校验 + 适配器导出）→ 部署配置 → 项目作战台（warroom）→ 项目文档包 → 资产沉淀。`python examples/pilot_example.py --stub` 打桩秒级复现、默认真调 DeepSeek（约 12 次调用）。

## 6. 常见问题

### 6.1 语义去重需要模型

`data_prep` 的语义去重使用 ChromaDB 的 `DefaultEmbeddingFunction`（all-MiniLM-L6-v2，约 79MB）。**首次调用会联网下载**，缓存到 `~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/`。

- 内网隔离/受限网络的部署机：需预先拷贝该缓存目录，或保证能联网。
- 安装时 `requirements.txt` 已固定 `numpy<2`（chromadb 0.5.0 在 numpy 2 下无法导入）。

### 6.2 LLM 调用（原型 4 模板真调 DeepSeek）

原型组装器 4 个模板（知识问答 / 信息抽取 / 多步推理 / 反思型）的 `create_*_agent()` 均已注入真实 LLM 调用（`core/llm.py::chat`，DeepSeek）。因此运行原型前需在 `.env` 配置 `DEEPSEEK_API_KEY`（`deepseek_api_key`）。未配置或调用失败时，模板**诚实降级**：返回错误说明（如「…未能完成（LLM 调用失败：未配置 DEEPSEEK_API_KEY）…」），不伪装成功。**诊断多 Agent / 映射初判与校验 / RAG 问答 / 原型 4 模板均真调 DeepSeek（`core/llm.py`）；未配置 key 时诊断/映射有规则兜底，原型/检索诚实报错。**

### 6.3 配置

- 修改 `.env` 后重启进程生效；配置字段见 `env.example`。
- 服务端口：`API_PORT`（默认 8100）；日志：`LOG_LEVEL` / `LOG_DIR`。

### 6.4 产物文件

各模块会往当前目录写入 JSON 产物（`crop_plan.json`、`dashboard.json`、`eval_set*.json`、`annotation_pool.json`、`output/` 等），这些已在 `.gitignore` 中，不会污染仓库。

### 6.5 版本与发布

```bash
./scripts/release.sh 1.2.0   # 跑测试 → 构建镜像 → 打标签 → 记录回滚版本
./scripts/rollback.sh 1.2.0  # 回滚
```

版本规范见 `docs/version-spec.md`，架构与错误码见 `docs/统一底座架构设计.md`。
