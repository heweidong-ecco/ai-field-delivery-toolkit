# AI 项目现场交付工具包

## 当前版本
v1.14.0

## 项目简介
AI 项目现场交付工具包是一个面向 FDE（Forward Deployed Engineer，前线部署工程师）的模块化武器箱，覆盖从需求诊断到数据飞轮的完整 AI 项目交付流程。

### 产品定位
- **用户**：FDE、解决方案工程师、内部 AI 交付团队
- **场景**：客户现场部署、POC 验证、快速复制已验证方案
- **价值**：现场 2 周内完成从需求诊断到生产部署，无需从零搭建基础设施
- 
### 核心原则
- **模块独立**：每个模块是独立插件，可单独启用
- **底座共享**：统一配置、安全、日志、版本管理
- **安全内建**：PII 脱敏、注入拦截、输出审核默认开启
- **本地优先**：无外部依赖，数据不出客户网络

## 目录结构

ai-field-delivery-toolkit/  
├── core/ # 统一底座  
│ ├── config/ # 配置中心  
│ ├── security/ # 安全基座  
│ ├── logging/ # 日志系统  
│ ├── version/ # 版本管理  
│ └── degradation/ # 降级管理  
├── diagnosis/ # ① 需求诊断器  
├── data_prep/ # ② 数据准备器  
├── dataprep/ # 数据作战流（项目级数据准备流水线：断点续接 + 产物沉淀复用）  
├── prototype_assembler/ # ③ 原型组装器  
├── deploy_hardener/ # ④ 部署加固器  
├── monitor/ # ⑤ 监控开箱器  
├── data_flywheel/ # ⑥ 数据飞轮器  
├── cropper/ # 五步裁剪引擎  
├── cases/ # 案例/交付物层（可打印 HTML/PDF、案例检索）  
├── projects/ # 项目档案（完整过程记录 + 作战台聚合 warroom.py）  
├── mapping/ # 字段映射工作台（集成工作流：导入真实样例 + 实跑校验 + 人工修正迭代 + 适配器导出）  
├── annotation/ # 数据标注与评测集管理  
├── kb/ # 知识库构建（分块/质检）  
├── retrieval/ # RAG 检索问答（分块 → 向量化 ChromaDB → 检索 → 带引用问答）  
├── assets/ # 可复用资产注册表（项目越多、工具越强：注册/检索/建议/一键接入）  
├── templates/ # 场景模板  
├── docs/ # 文档  
├── refactor/ # 重构归档（需求诊断 / FDE 全局决策过程与方案）  
├── tests/ # 测试  
├── logs/ # 日志（Git 忽略）  
├── docker-compose.yml # 一键启动开发环境  
├── requirements.txt # Python 依赖  
├── Makefile # 常用命令  
├── .env.example # 环境变量模板  
├── .gitignore # Git 忽略规则  
└── README.md # 本文档


## 模块说明
| 模块                | 职责                                   | 开发状态 |
| ------------------- | -------------------------------------- | -------- |
| core                | 统一底座：配置、安全、日志、版本、降级 | ✅ 已完成 |
| diagnosis           | 需求诊断器：AI 适用性判断、需求评估    | ✅ 已完成 |
| data_prep           | 数据准备器：清洗、标注、评测集构建     | ✅ 已完成 |
| dataprep            | 数据作战流：项目级数据准备流水线（断点续接 + 产物沉淀复用） | ✅ 已完成 |
| prototype_assembler | 原型组装器：Agent 技术栈 + 场景模板    | ✅ 已完成 |
| deploy_hardener     | 部署加固器：Docker 化、降级、发布      | ✅ 已完成 |
| monitor             | 监控开箱器：看板、告警、真实 LLM 用量/成本 | ✅ 已完成   |
| data_flywheel       | 数据飞轮器：反馈回流、评测集更新       | ✅ 已完成   |
| cropper             | 五步裁剪引擎：客户约束 → 裁剪方案（可从诊断带入） | ✅ 已完成 |
| cases               | 案例/交付物层：诊断定稿 → 可打印 HTML/PDF、案例检索 | ✅ 已完成 |
| projects            | 项目作战台：完整过程记录（时间线）+ 全部产物聚合（warroom） | ✅ 已完成   |
| mapping             | 字段映射工作台：LLM 初判 + 导入真实样例 + 实跑校验 + 修正迭代 + 适配器导出 + 断点 | ✅ 已完成 |
| annotation          | 人工双人标注工作台（标注员 A/B 分别标 → 逐行一致性 → 分歧改判 → 评测集；可从数据作战流 cleaned_data 建任务） | ✅ 已完成   |
| kb                  | 知识库构建：分块 + 质检                | ✅ 已完成   |
| retrieval           | RAG 检索问答：分块 → 向量化(ChromaDB) → 检索 → 带引用问答 | ✅ 已完成 |
| assets              | 可复用资产注册表：dataprep 沉淀/mapping 导出/诊断定稿 → 自动入库；新任务自动带出 + 一键接入 | ✅ 已完成 |

## 快速开始

### 环境要求
- Python 3.11+
- Docker & Docker Compose
- 至少 8GB 内存

### 启动步骤
```bash
# 1. 克隆仓库
git clone <仓库地址>
cd ai-field-delivery-toolkit
# 2. 创建本地环境变量
cp .env.example .env
# 编辑 .env，填写你的 API Key
# 3. 安装 Python 依赖
pip install -r requirements.txt
# 4. 启动基础设施
docker compose up -d
# 5. 验证环境
make check
# 6. 初始化数据库
python -m core.db.init_db
```

## 开发规范

- 分支管理：main / develop / feature/xxx / fix/xxx
    
- 提交格式：类型: 简述（feat / fix / docs / test / refactor）
    
- 所有合并必须通过 PR 和代码审查
    
- 单元测试覆盖率 ≥80%
    
## 技术栈

| 组件       | 技术选型                  |
| ---------- | ------------------------- |
| 语言       | Python 3.11               |
| Web 框架   | FastAPI                   |
| 数据库     | PostgreSQL 16             |
| 缓存       | Redis 7                   |
| 向量数据库 | ChromaDB                  |
| LLM 客户端 | openai 库（兼容多家 API） |
| 部署       | Docker Compose            |
| Agent 框架 | 自研薄封装                |

## 文档

- [开发流程规范](https://docs/development-process.md)
    
- [安全基线](https://docs/security-baseline.md)
    
- [配置规范](https://docs/config-spec.md)
    
- [版本管理规范](https://docs/version-spec.md)

## 功能模块状态
| 模块         | 状态     | 说明                                                          |
| ------------ | -------- | ------------------------------------------------------------- |
| 统一底座     | ✅ 已完成 | 配置、安全、日志、版本、降级、模块注册、数据库                |
| 数据准备器   | ✅ 已完成 | 接入、评估、清洗（含语义去重）、评测集构建                    |
| 数据作战流   | ✅ 已完成 | 项目级数据准备流水线：上传 csv/json → 导入/清洗/质量 → 标注 → 评测集 → 知识库；以 run_id 断点续接（刷新不丢）；产物真实落盘 + 沉淀为可复用资产（案例检索可搜到）；任务挂项目档案；知识库步骤完成后自动索引（ChromaDB）→ RAG 就绪 |
| 原型组装器   | ✅ 已完成 | Agent Harness、4 种循环、记忆、工具、上下文、结构化输出、流式；4 个模板（知识问答 / 信息抽取 / 多步推理 / 反思型）全部真调 DeepSeek（core/llm.py）；知识问答支持带 kb_run_id 走 RAG 检索问答（回答带引用分块）；LLM 调用失败时诚实降级（返回错误说明，不装成功） |
| 五步裁剪引擎 | ✅ 已完成 | 7 类约束 + 网络带宽 + 合规等级；支持从诊断结论带入             |
| 部署加固器   | ✅ 已完成 | Docker 化、降级预案、Compose、裸机、环境检查                  |
| 需求诊断器   | ✅ 已完成 | 多 Agent 对抗评审（Generator/Critic/Reviewer）+ 技术 5 维 + 非技术全景可行性 + 商务提案（投入/里程碑/责任清单/试点退出/替代方案，供洽谈）+ 版本化交付 + 客户反馈闭环 |
| 监控开箱器   | ✅ 已完成 | 基础指标 + 真实 LLM 用量/成本（计费打点自动喂）+ 告警 + 看板   |
| 数据飞轮器   | ✅ 已完成 | 反馈回流、评测集更新、资产导出                                |
| 案例/交付物层 | ✅ 已完成 | 诊断定稿 → 可打印 HTML/PDF、结构化案例存档、案例检索          |
| 项目档案     | ✅ 已完成 | 以项目为中心的过程记录（诊断/会议/现场问题/迭代/交付物时间线） |
| 项目作战台   | ✅ 已完成 | 以项目为中心，打开一个项目全部产物真实拉齐：诊断 / 数据作战流 / 映射 / 交付物 / 资产 / RAG 索引 / 工作流进度 / 时间线；`GET /api/v1/projects/{pid}/warroom` 聚合；⑧ tab 升级为作战台；诊断 finalize 把 project_id 落盘 run 档案；带上下文跳转（跳 ③/⑨ 预填项目/客户、跳 ①/③/⑨ 续做指定 run）；workflow 按项目过滤（不再被其它项目产物撑高） |
| 质量门禁     | ✅ 已完成 | 门禁硬化（v1.11.0）：`core/workflow.py::gate_check(stage, project_id)` 基于真实档案判定关键质量点（诊断须人工确认 / 数据须真实质量评估 / 文档包须人工确认）；`/prototype/run` 传 project_id 数据未达标 → 403（force 强制通道诚实记录 gate_override）、`/cropper/from-diagnosis` 未确认 → 400、`/cases/create-doc-package` 无确认 → 400；`GET /workflow/gate` 供前端展示门禁状态；warroom 显示「门禁未过：reason」 |
| 字段映射工作台 | ✅ 已完成 | 集成工作流：LLM 初判映射 + 导入真实样例 CSV + 实跑校验（逐字段 pass/warn/fail + 理由 + 成功率/无失败率）+ 人工修正迭代重跑 + 导出适配器 + 断点续接 + 挂项目档案 |
| 数据标注管理 | ✅ 已完成 | 人工双人标注工作台：每样本两列（标注员 A/B）分别存标签、逐行一致性（未标/仅A/仅B/一致/分歧）、分歧可改判到一致、构建评测集；可从数据作战流 cleaned_data 建任务（source 诚实标注）、list_tasks 按 mtime 倒序；数据作战流「标注」步骤为规则自动打标（流水线便利），人工工作台是真实标注表面 |
| 知识库构建   | ✅ 已完成 | 长文本分块 + 质检（RAG 最小件）                               |
| RAG 检索问答 | ✅ 已完成 | 知识库分块 → 向量化(ChromaDB) → 检索 → 问答（带引用分块）；数据作战流 knowledge_base 步骤自动索引，④ 原型可选知识库做检索问答 |
| 资产复用闭环 | ✅ 已完成 | 可复用资产注册表（tmp/web/assets/registry.json）：dataprep 沉淀（评测集/知识库分块/清洗规则/质量报告）、mapping 导出（字段映射配置）、诊断定稿（诊断方案）自动入库；新任务（诊断/mapping/dataprep 创建）响应自动带出相关资产（规则评分 + reason）；一键接入 adopt：映射配置预填新映射 run、数据资产复制到目标 dataprep run 的 products 并挂项目 asset_reuse 事件；⑪ 资产库 tab 检索/筛选/详情/一键接入 |

## 测试

```bash
make test          # 运行全部测试
make test-cov      # 生成覆盖率报告
```

## 发布与回滚

```bash
./scripts/release.sh 1.2.0    # 发布
./scripts/rollback.sh 1.2.0   # 回滚
```

## 使用示例

所有示例位于 `examples/` 目录，每个模块一个可运行的示例脚本。

| 模块         | 示例文件                        | 说明                   |
| ------------ | ------------------------------- | ---------------------- |
| 统一底座     | `examples/core_example.py`      | 配置、安全、注册、版本 |
| 数据准备器   | `examples/data_prep_example.py` | 接入→评估→清洗→评测集  |
| 原型组装器   | `examples/prototype_example.py` | 创建 Agent 原型并运行（4 模板真调 DeepSeek） |
| 五步裁剪引擎 | `examples/cropper_example.py`   | 客户约束 → 裁剪方案    |
| 部署加固器   | `examples/deploy_example.py`    | Docker 化 + 降级预案   |
| 需求诊断器   | `examples/diagnosis_example.py` | AI 适用性评估 + 报告   |
| 监控开箱器   | `examples/monitor_example.py`   | 指标收集 + 告警 + 看板 |
| 数据飞轮     | `examples/data_flywheel_example.py`   | 数据飞轮器：反馈回流、评测集更新、资产沉淀" |
| 数据标注管理 | `examples/annotation_example.py`      | 人工双人标注 → 一致性 → 评测集构建 |
| 案例/交付物层 | `examples/cases_example.py`          | 诊断定稿 → 可打印 HTML/PDF 交付物 + 案例存档/检索 |
| 知识库构建   | `examples/kb_example.py`              | 长文本分块 + 质检（RAG 最小件） |
| 字段映射工作台 | `examples/mapping_example.py`        | LLM 初判映射 + 导入真实样例 + 实跑校验 + 导出适配器 |
| 项目档案     | `examples/projects_example.py`        | 项目时间线 + 工作流进度（作战台聚合见 pilot） |
| 真实试运行   | `examples/pilot_example.py`           | 全工具链在真实制造业客户项目上端到端跑通（诊断→数据→原型+RAG→映射→部署→作战台→交付物包），产出客户交付物包；`--stub` 打桩可复现、默认真调 DeepSeek |

> `retrieval` / `assets` 无独立示例：见 `examples/pilot_example.py` 全链路（含 RAG 检索问答与资产注册/一键接入），或 `--stub` 打桩复现。
运行示例：

```bash
# 激活环境
source venv/bin/activate

# 运行某个模块的示例
python examples/cropper_example.py

# 真实试运行（打桩模式，秒级可复现；去掉 --stub 则真调 DeepSeek）
python examples/pilot_example.py --stub
```

## 真实案例

> v1.12.0 起，用一套真实制造业客户项目把全工具链完整跑通，沉淀为「可复现的真实案例」，产出可发给客户的交付物包。

**客户**：某汽车零部件制造厂（制造业 · 设备预测性维护）
**行业**：汽车零部件制造
**数据**：`examples/data/manufacturing_sensors.csv`（42 行：注塑/CNC 加工/冲压/空压/装配产线，温度/压力/振动/转速/电流，含时间戳与状态）+ `examples/data/retail_inventory.csv`（32 行零售库存，固定数据集提交仓库，非教学场景）
**走完的模块**：需求诊断（多 Agent + 人工确认）→ 数据作战流（清洗/质量/标注/评测集/知识库分块 + 自动索引）→ 原型 + RAG（knowledge_qa，数据门禁放行）→ 字段映射（导入真实样例 + 实跑校验 + 适配器导出）→ 部署配置（docker-compose + 降级预案）→ 项目作战台（warroom 全分区聚合）→ 项目文档包（confirmed 放行）
**产物**：客户交付物包 `tmp/web/pilot/某汽车零部件制造厂/`（客户项目总览.md + 诊断交付物.html + 项目文档包.html + warroom.json）
**复现方法**：

```bash
# 打桩模式（可复现、CI 用、秒级）
python examples/pilot_example.py --stub

# 真调 DeepSeek（仓库 .env 有 DEEPSEEK_API_KEY，约 2-4 分钟，≈12 次 LLM 调用）
python examples/pilot_example.py --pilot-dir /tmp/pilot_real
```

诚实标注：报告 `llm_mode` 字段区分 `real`（真调 DeepSeek）与 `stub`（全打桩）；每次运行新建 run_id 不覆盖旧产物。