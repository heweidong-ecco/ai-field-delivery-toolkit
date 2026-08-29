## 建议提交前执行的操作序列

bash

# 1. 清理所有临时文件
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
rm -rf .pytest_cache logs
mkdir -p logs && touch logs/.gitkeep
# 2. 运行测试
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
make test
# 3. 检查 Git 状态
git status
# 4. 确认 .env 未被跟踪
git status --ignored | grep .env || echo ".env 未被跟踪"
# 5. 添加所有文件
git add .
# 6. 再次检查暂存区
git status
# 7. 提交
git commit -m "feat: AI 项目现场交付工具包 v1.2.0 完整发布"

---

## 总结

| 类别         | 操作                                                              |
| ------------ | ----------------------------------------------------------------- |
| **必须删除** | 运行时产物、虚拟环境、日志、临时 JSON、缓存                       |
| **必须修改** | `models.py` Float 类型、`pipeline.py` 清洗参数、版本号、TODO 注释 |
| **必须增加** | `requirements-dev.txt`、`.gitignore` 补充规则、README 版本        |
| **建议检查** | PDF 依赖、测试通过、脚本权限、`.env` 忽略                         |

完成上述操作后，即可安全提交 Git。如果还有任何文件不确定是否应该提交，可以运行 `git status --ignored` 查看完整状态，或者将输出发给我，我帮你做最后甄别。