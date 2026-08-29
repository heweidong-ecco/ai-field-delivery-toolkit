# 二、Git 提交前完整行业标准清单
以下清单适用于开源项目和企业内部项目的首次提交或版本发布，覆盖代码、文档、测试、配置、安全、忽略规则等方面。
## 1. 核心文件完整性
| 检查项                             | 是否必须 | 说明                                                   |
| ---------------------------------- | -------- | ------------------------------------------------------ |
| `README.md`                        | 必须     | 项目简介、快速开始、功能列表、版本、目录结构、贡献指南 |
| `LICENSE`                          | 必须     | 开源项目必须，内部项目可选                             |
| `.gitignore`                       | 必须     | 排除虚拟环境、缓存、日志、敏感文件                     |
| `requirements.txt`                 | 必须     | 运行依赖完整且可安装                                   |
| `requirements-dev.txt`             | 必须     | 开发/测试依赖与运行依赖分离                            |
| `pyproject.toml` 或 `setup.py`     | 必须     | 项目元数据、构建配置                                   |
| `Makefile` 或等效脚本              | 建议     | 常用命令（安装、测试、清理、运行）                     |
| `docker-compose.yml` 或 Dockerfile | 条件必须 | 如项目需要容器化部署                                   |
| `CHANGELOG.md`                     | 建议     | 记录版本变更历史                                       |
| `CONTRIBUTING.md`                  | 建议     | 贡献指南，开源项目必须                                 |
| `CODE_OF_CONDUCT.md`               | 建议     | 行为准则，开源项目建议                                 |
## 2. 代码质量
| 检查项                       | 是否必须 | 说明                             |
| ---------------------------- | -------- | -------------------------------- |
| 无未使用的 import            | 必须     | 代码整洁                         |
| 无硬编码密钥/密码            | 必须     | 安全基线                         |
| 无调试 print 语句            | 必须     | 生产代码中移除                   |
| 无 TODO/FIXME 未经说明的占位 | 必须     | 占位需有 TODO 注释并说明后续计划 |
| 代码风格一致                 | 必须     | 遵循 PEP 8，可配置 linter        |
| 类型注解                     | 建议     | 提高可读性和可维护性             |
| 错误处理完善                 | 必须     | 不出现未捕获异常导致崩溃         |
| 日志使用统一                 | 必须     | 统一日志框架，不直接使用 print   |
## 3. 测试
| 检查项                 | 是否必须 | 说明                       |
| ---------------------- | -------- | -------------------------- |
| 单元测试覆盖核心模块   | 必须     | 覆盖率 ≥80%                |
| 集成测试               | 必须     | 端到端流程测试             |
| 测试可运行             | 必须     | 新成员运行测试命令后能通过 |
| 测试不依赖外部服务     | 建议     | 使用 mock 或 fixture       |
| 测试数据不包含敏感信息 | 必须     | 脱敏                       |
| CI 配置                | 建议     | 自动化测试跑通             |
## 4. 文档
| 检查项      | 是否必须 | 说明                   |
| ----------- | -------- | ---------------------- |
| README 完整 | 必须     | 含快速开始、功能、版本 |
| API 文档    | 条件必须 | 如提供 API，需有文档   |
| 使用指南    | 必须     | 各模块用法             |
| 部署文档    | 必须     | 部署步骤和配置说明     |
| 回滚预案    | 必须     | 生产项目必须           |
| 发布说明    | 必须     | 当前版本发布内容和变更 |
| 示例可运行  | 必须     | 示例脚本可直接运行     |
## 5. 配置与安全
| 检查项               | 是否必须 | 说明                              |
| -------------------- | -------- | --------------------------------- |
| `.env.example` 存在  | 必须     | 提供环境变量模板                  |
| `.env` 未被提交      | 必须     | 确认 `.gitignore` 生效            |
| 密钥未硬编码         | 必须     | 使用环境变量                      |
| 数据库连接信息未暴露 | 必须     | 使用配置或环境变量                |
| 镜像安全扫描通过     | 条件必须 | 容器化项目                        |
| 依赖无已知高危漏洞   | 必须     | 运行安全扫描工具                  |
| 权限最小化           | 必须     | Docker 非 root 用户、文件权限最小 |
## 6. Git 忽略规则
确认 `.gitignore` 包含以下内容：
```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
venv/
.venv/
*.egg-info/
dist/
build/
# 测试与覆盖
.pytest_cache/
.coverage
htmlcov/
# 日志
logs/
*.log
# IDE
.vscode/
.idea/
*.swp
*.swo
# 系统
.DS_Store
Thumbs.db
# 环境变量
.env
# 运行时产物
annotation_pool.json
eval_set*.json
dashboard.json
crop_plan.json
diagnosis_report.json
project_assets.json
cleaned_data.json
quality_report.json
cleaning_stats.json
.release_prev_version
```
## 7. 构建与运行

| 检查项             | 是否必须 | 说明                    |
| ------------------ | -------- | ----------------------- |
| 一键启动环境可运行 | 必须     | 新成员能快速跑通        |
| Docker 构建成功    | 条件必须 | 如提供 Docker 部署      |
| 服务健康检查通过   | 必须     | 启动后 /health 返回正常 |
| 依赖安装成功       | 必须     | 全新环境安装无报错      |

## 8. 版本控制

| 检查项       | 是否必须 | 说明                           |
| ------------ | -------- | ------------------------------ |
| 版本号更新   | 必须     | 代码、README、CHANGELOG 一致   |
| 提交信息规范 | 必须     | 使用 Conventional Commits 格式 |
| 分支规范     | 必须     | 不在 main 直接开发             |
| 标签         | 建议     | 发布版本打 tag（如 `v1.2.0`）  |

---

## 提交前执行命令清单

```bash

# 1. 清理所有临时文件
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
rm -rf .pytest_cache logs
mkdir -p logs && touch logs/.gitkeep
# 2. 安装依赖
pip install -r requirements.txt -r requirements-dev.txt
# 3. 运行测试
make test
# 4. 检查代码风格（如配置了 linter）
flake8 . || echo "未配置 flake8"
# 5. 检查安全
pip-audit || echo "未配置 pip-audit"
# 6. 检查 Git 状态
git status
git status --ignored | grep .env || echo ".env 未被跟踪"
# 7. 检查暂存文件
git add .
git status
# 8. 提交
git commit -m "feat: AI 项目现场交付工具包 v1.2.0 完整发布"
git tag v1.2.0
```
---

# 总结

| 类别        | 具体行动                                                     |
| ----------- | ------------------------------------------------------------ |
| README 更新 | 必须：更新版本号、模块状态、测试说明、发布回滚、示例         |
| 必须删除    | 临时 JSON、缓存、日志、虚拟环境                              |
| 必须增加    | `requirements-dev.txt`、`CHANGELOG.md`、`.gitignore` 补充    |
| 必须修改    | `models.py` Float、`pipeline.py` 清洗参数、TODO 注释、版本号 |
| 建议检查    | PDF 依赖、测试通过、脚本权限、`.env` 忽略                    |