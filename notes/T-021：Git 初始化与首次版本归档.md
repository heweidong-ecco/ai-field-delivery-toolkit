# T-021：Git 初始化与首次版本归档

> 日期：2026-08-29
> 类型：项目决策 / 里程碑记录
> 关联：T-001（创建项目仓库与目录结构）、T-007（版本管理规范）、CHANGELOG.md、README.md

## 背景

项目自建仓以来一直**未纳入版本控制**（`git init` 前无 .git）。经 12 轮迭代（诊断 v2.x → 数据作战流 v3.0 → 集成工作台 v4.0 → RAG v5.0 → 资产复用闭环 v6.0 → 项目作战台 v7.0 → 原型模板做实 v8.0 → 标注人工工作台 v9.0 → 门禁硬化 v10.0 → 真实试运行 v11.0 → 文档同步 v12.0 → Web 重设计 v13.0），在 v1.14.0 里程碑把全量成果一次性纳入版本控制并推送 GitHub。

## 里程碑状态（首次提交时）

- **版本**：v1.14.0（README / CHANGELOG / pyproject / core/__init__ 已对齐，消除版本双轨）
- **测试**：`pytest tests/` **163 passed**
- **规模**：231 文件 / 28,264 行
- **模块**：诊断、裁剪、数据作战流（dataprep）、原型（4 模板真调 LLM）、部署、监控、飞轮、项目作战台、字段映射、功能说明（manifest/guide）、资产库；底座 core/ + cases/projects/mapping/annotation/kb/retrieval/assets/dataprep

## Git 前全面检查（已逐项完成）

| 检查项 | 结果 |
| ---- | ---- |
| 敏感信息 | `DEEPSEEK_API_KEY` 值仅在 .env（已忽略）；全仓无 sk- 真实密钥，231 文件 0 泄漏 |
| 临时产物 | tmp/(933M)、venv/、logs/、__pycache__、.pytest_cache、.DS_Store、diagnosis_report.json 全部忽略 |
| .gitignore | 修复：`notes/`（决策记录 T-xxx）误忽略 → 移除，23 份决策记录纳入提交 |
| 版本 | pyproject/core 1.2.0 → 1.14.0（对齐 README） |
| LICENSE | 新增 MIT（Copyright heweidong） |
| 行业清单 | `各行业AI需求列表.md` → `docs/行业AI需求列表.md`（去 emoji + 加说明头） |

## Git 历史

```
afb258d chore: 初始化 ai-field-delivery-toolkit v1.14.0
```

- 远端：https://github.com/heweidong-ecco/ai-field-delivery-toolkit.git（公开）
- 分支：main（已跟踪 origin/main）
- 认证：macOS osxkeychain（`git config --global credential.helper osxkeychain`），用户名 heweidong-ecco
- 提交身份：heweidong-ecco <823683018@qq.com>
- 备注：首次推送遇一次瞬时连接超时，重试成功

## 后续约定

- 新迭代一律**先提交再继续**（建议一次迭代一个 commit，信息按 CHANGELOG 版本号）
- 产物/临时文件继续走 .gitignore（tmp/ 不入库）
- 版本号变更同步：pyproject / core/__init__ / README「当前版本」 / CHANGELOG 四处对齐
