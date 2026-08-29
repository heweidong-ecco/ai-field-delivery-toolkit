<div align="center">

# AI 项目现场交付工具包

**FDE 前线部署工程师的模块化交付武器箱 —— 从需求诊断到数据飞轮的完整 AI 项目交付闭环**

[![版本](https://img.shields.io/badge/version-1.14.0-blue)](CHANGELOG.md)
[![测试](https://img.shields.io/badge/tests-163%20passed-brightgreen)](tests/)
[![许可证](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue)](pyproject.toml)
[![接口](https://img.shields.io/badge/API-FastAPI-009688)](docs/api.md)

**简体中文** · [English](./README.en.md)

</div>

---

## 一句话

把 **FDE（Forward Deployed Engineer）** 现场交付 AI 项目的脏活累活 —— 需求诊断、数据准备、原型验证、集成映射、部署、监控、资产沉淀 —— 全部接住，且**本地优先、可离线运行、数据不出客户网络**。

**北极星**：不是省时间，是把事做好（质量 + 口碑）。省时间是「系统沉淀能力 + 复利资产」换来的副产品。

---

## 亮点特性

| 能力 | 说明 |
| ---- | ---- |
| 🎯 **需求诊断（多 Agent 对抗）** | Generator 打分 → Critic 盲审 → 人工复核 → Reviewer 再评分 → 强制确认定稿；五维 AI 适用性 + 非技术全景可行性 + **商务提案**（投入/里程碑/责任清单/试点退出/替代方案） |
| 🔄 **数据作战流** | 项目级 6 步流水线（导入→清洗→质量→标注→评测集→知识库），**run_id 断点续接**（刷新/重连不丢），每步产物真实落盘 |
| 🔗 **字段映射工作台** | 导入真实样例 CSV → 映射**实跑校验**（逐字段 pass/warn/fail + 理由 + 成功率）→ 人工修正迭代 → 导出适配器，全程断点续接 |
| 🧠 **原型 + RAG** | 4 个 Agent 模板**全部真调 DeepSeek**（知识问答/信息抽取/多步推理/反思型）；知识问答走 RAG（ChromaDB 向量化 → 检索 → **带引用回答**，答不出就说不知道） |
| 🗂 **项目作战台** | 以项目为中心，打开一个项目**全部产物真实拉齐**：诊断/数据/映射/交付物/资产/RAG/工作流进度/时间线，一键跳转续做 |
| ♻️ **资产复用闭环** | 每次交付沉淀的可复用资产（评测集/清洗规则/映射配置/知识库分块）自动入库，下次交付**自动带出 + 一键接入** —— 项目越多、工具越强 |
| 🛡 **质量门禁硬化** | 「数据未达标不进原型」「发客户前必须人工确认」从展示变成**真阻断**（403/400 + 可解释 reason），同时保留诚实的人工强制通道 |
| 🏷 **界面** | 11 个标签页的 FDE 操作台（Ant Design Pro 企业风格），零构建、纯 HTML/CSS/JS、离线可用 |

> 细节以 [docs/api.md](docs/api.md)（接口全量）与 [docs/统一底座架构设计.md](docs/统一底座架构设计.md)（设计期权威）为准。

---

## 界面截图

**需求诊断**

![需求诊断](docs/screenshots/home.png)

**数据作战流**

![数据作战流](docs/screenshots/dataprep.png)

**项目作战台**

![项目作战台](docs/screenshots/warroom.png)

**资产库**

![资产库](docs/screenshots/assets.png)

---

## 架构

```
统一底座 core/（配置 · 日志 · 安全 · 降级 · 注册 · 数据库）
        │  模块不直接读环境变量/不自己初始化日志，全部经底座
        ▼
diagnosis（该不该上 AI）→ cropper（砍哪些模块）→ dataprep（数据作战流）
→ prototype（Agent 原型 + RAG）→ deploy（部署配置）→ monitor（运行指标）
                        └── data_flywheel / assets（反馈回流 + 资产复利，闭环）──┘
```

**六步 SOP**：需求诊断 → 数据作战流（硬门禁：数据未达标不进原型）→ 现场原型 → 部署集成（发客户前人工确认）→ 交付沉淀（文档包 + 案例归档）→ 资产复用闭环。

---

## 快速开始

### 环境要求
- Python 3.11+　·　Docker & Docker Compose　·　≥8GB 内存

### 启动（5 步）

```bash
# 1. 克隆并进入
git clone https://github.com/heweidong-ecco/ai-field-delivery-toolkit.git
cd ai-field-delivery-toolkit

# 2. 环境变量（填 DEEPSEEK_API_KEY 等）
cp .env.example .env

# 3. 安装依赖（仓库内已有 venv/ 则跳过）
pip install -r requirements.txt

# 4. 一键初始化（检查 Python/Docker → 生成 .env → 装依赖 → 启动基础设施）
./scripts/setup.sh

# 5. 启动操作台，浏览器打开 http://localhost:8100/
python -m core.main
```

> 基础设施（PostgreSQL / Redis / ChromaDB）用 `make up` 启动、`make check` 健康检查。数据库建表 `make init-db`。

### 没有 LLM Key 也能跑？

可以。诊断/映射有**规则兜底**，原型/检索会**诚实报错**；所有示例支持 `--stub` 打桩（确定性、离线、秒级）。详见 [FAQ](#faq)。

---

## 功能模块

| 模块 | 职责 | 状态 |
| ---- | ---- | ---- |
| `core/` | 统一底座：配置、日志、安全（PII/注入/审核）、降级、注册、数据库 | ✅ |
| `diagnosis/` | 需求诊断：多 Agent 对抗 + 版本循环 + 客户反馈 + 商务提案 | ✅ |
| `cropper/` | 五步裁剪：客户约束 → 启用/删除模块 + 排期；可从诊断带入 | ✅ |
| `data_prep/` + `dataprep/` | 数据接入/清洗/评测集 + **数据作战流**（6 步断点续接流水线） | ✅ |
| `prototype_assembler/` | 原型组装：4 模板真调 DeepSeek，知识问答走 RAG | ✅ |
| `deploy_hardener/` | 部署加固：Docker 化 + 降级预案 + 环境预检 | ✅ |
| `monitor/` | 监控：指标/告警/看板 + **真实 LLM 用量/成本**（计费打点） | ✅ |
| `data_flywheel/` | 数据飞轮：反馈 → 标注池 → 评测集更新 → 资产导出 | ✅ |
| `cases/` | 案例/交付物层：可打印 HTML/PDF + 结构化存档 + 检索 | ✅ |
| `projects/` | 项目作战台：过程记录 + **warroom 全产物聚合** + 门禁 | ✅ |
| `mapping/` | 字段映射工作台：真实样例实跑校验 → 适配器导出 | ✅ |
| `annotation/` | 人工双人标注工作台：A/B 一致性 → 分歧改判 → 评测集 | ✅ |
| `kb/` + `retrieval/` | 知识库分块/质检 + RAG 检索问答（带引用） | ✅ |
| `assets/` | 可复用资产注册表：自动入库 + 自动带出 + 一键接入 | ✅ |

---

## 使用示例

每个模块一个可运行示例（`python examples/xxx_example.py`）：

| 模块 | 示例 |
| ---- | ---- |
| 需求诊断 | `examples/diagnosis_example.py` |
| 数据准备 / 数据作战流 | `examples/data_prep_example.py` |
| 原型（4 模板真调 LLM） | `examples/prototype_example.py` |
| 五步裁剪 | `examples/cropper_example.py` |
| 部署 / 监控 / 飞轮 | `deploy_example.py` / `monitor_example.py` / `data_flywheel_example.py` |
| 案例交付物 | `examples/cases_example.py` |
| 知识库 / 字段映射 / 项目 | `kb_example.py` / `mapping_example.py` / `projects_example.py` |
| 人工标注 | `examples/annotation_example.py` |
| **全链路真实试运行** | `examples/pilot_example.py --stub`（打桩秒级复现；去 `--stub` 真调 DeepSeek） |

---

## 真实案例

> v1.12.0 起沉淀的「可复现真实案例」——全工具链在真实制造业客户项目上端到端跑通，产出**可发给客户的交付物包**。

**某汽车零部件制造厂 · 设备预测性维护**（制造业）：需求诊断 → 数据作战流（清洗/质量/标注/评测集/知识库分块 + 自动索引）→ 原型 + RAG → 字段映射（实跑校验）→ 部署配置 → 项目作战台 → 项目文档包。

```bash
python examples/pilot_example.py --stub      # 打桩，秒级可复现
python examples/pilot_example.py             # 真调 DeepSeek（约 2-4 分钟）
```

产物：`tmp/web/pilot/<客户>/`（客户项目总览 + 诊断交付物 HTML + 项目文档包 HTML + warroom 快照）。诚实标注 `llm_mode`：`real`（真调）/ `stub`（打桩）。

---

## 技术栈

| 组件 | 选型 |
| ---- | ---- |
| 语言 | Python 3.11 |
| Web 框架 | FastAPI（零构建前端，原生 HTML/CSS/JS） |
| 数据库 | PostgreSQL 16 · Redis 7 · ChromaDB（向量） |
| LLM 客户端 | 自研统一 `core/llm.py`（DeepSeek/OpenAI 兼容，计费打点喂监控） |
| Agent 框架 | 自研薄封装（harness / loop / memory / tools / context） |
| 部署 | Docker Compose / systemd |

---

## FAQ

**Q1：这个工具和直接用 LangChain / DeepSeek API 有什么区别？**
直接调 API 解决的是「单个 AI 能力」；本工具解决的是 **FDE 现场交付一整条链**：需求该不该上 AI（诊断）、数据怎么准备好（作战流）、字段怎么映射（工作台）、部署怎么配（加固）、跑完怎么监控、沉淀怎么复用。单点能力都有替代，**把交付链打通 + 资产复利**才是护城河。

**Q2：数据会出客户网络吗？**
不会。工具**本地优先、可离线运行**，数据落本地 `tmp/`，向量存本机 ChromaDB。唯一需要联网的是：首次调用 LLM（DeepSeek API）与语义去重首次下载嵌入模型（约 79MB，可预置到 `~/.cache/chroma/onnx_models/`）。

**Q3：没有 DEEPSEEK_API_KEY 能跑吗？**
能。诊断/映射有**规则兜底**（不调 LLM 也能出结果）；原型/检索会**诚实报错**（提示配 Key），绝不装成功。所有示例 `--stub` 打桩可完整离线复现。

**Q4：11 个标签页太多，从哪开始？**
按交付流程：① 需求诊断 → ③ 数据作战流 → ④ 原型 → ⑨ 字段映射 → ⑧ 项目作战台（看全部产物）。⑩ 功能说明是内置使用指南（含动态建议），⑪ 资产库看沉淀成果。

**Q5：断点续接是什么意思？**
诊断/数据作战流/映射任务都有 `run_id` 档案。现场做到一半关电脑，下次从「历史」恢复，进度/产物/已跑步骤都在，**刷新不丢**。

**Q6：测试怎么跑？**
```bash
source venv/bin/activate
make test        # pytest tests/（163 用例）
make test-cov    # 覆盖率报告
```

**Q7：如何贡献 / 二次开发？**
欢迎提 Issue / PR。约定：中文注释、业务标识符英文、schema 只增不改、旧用例零改动、新功能同步示例 + README 模块表 + CHANGELOG。迭代记录见 `refactor/` 与 `notes/`。

**Q8：许可证？**
[MIT](LICENSE)。可商用、可修改、可再分发，保留版权声明即可。

**Q9：监控面板显示的是「本工具」的 LLM 成本，不是客户系统的监控？**
是的，目前定位是**交付工具自身的用量/成本看板**（真实计费打点）。客户系统运行监控不在当前范围（设计决策 Q12：不复刻 Grafana）。

---

## 文档

- [API 接口全量](docs/api.md) · [统一底座架构设计（设计期权威）](docs/统一底座架构设计.md)
- [开发流程](docs/development-process.md) · [安全基线](docs/security-baseline.md) · [配置规范](docs/config-spec.md) · [版本规范](docs/version-spec.md)
- [使用指南](docs/usage-guide.md)
- 决策记录：`notes/`（T-001…T-021） · 迭代归档：`refactor/`

## 版本 / 发布

版本同步四处：`pyproject.toml` / `core/__init__.py` / README「当前版本」/ `CHANGELOG.md`。

```bash
./scripts/release.sh 1.15.0   # 测试 → 构建镜像 → 打标签 → 记录回滚版本
./scripts/rollback.sh 1.15.0  # 回滚
```

## 许可证

[MIT](LICENSE) © 2026 heweidong
