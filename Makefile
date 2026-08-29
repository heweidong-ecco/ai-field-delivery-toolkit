.PHONY: up down logs ps check install init-db test clean

## 启动基础设施
up:
	docker compose up -d

## 停止基础设施
down:
	docker compose down

## 查看日志
logs:
	docker compose logs -f

## 查看服务状态
ps:
	docker compose ps

## 检查环境健康
check:
	@echo "=== 检查 PostgreSQL ==="
	@docker exec toolkit-postgres pg_isready -U toolkit
	@echo "=== 检查 Redis ==="
	@docker exec toolkit-redis redis-cli ping
	@echo "=== 检查 ChromaDB ==="
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/heartbeat
	@echo ""
	@echo "=== 全部服务健康 ==="

## 安装 Python 依赖
install:
	pip install -r requirements.txt

## 初始化数据库
init-db:
	python -m core.db.init_db

## 运行测试
test:
	pytest tests/ -v

## 清理缓存
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache


## 运行示例
### 统一底座示例
example-core:
	python examples/core_example.py
### 数据准备器示例
example-data-prep:
	python examples/data_prep_example.py
### 原型组装器示例
example-prototype:
	python examples/prototype_example.py
###五步裁剪引擎示例
example-cropper:
	python examples/cropper_example.py
### 部署加固器示例
example-deploy:
	python examples/deploy_example.py
### 需求诊断器示例
example-diagnosis:
	python examples/diagnosis_example.py
### 监控开箱器示例
example-monitor:
	python examples/monitor_example.py
### 运行数据飞轮器示例
example-flywheel:
	python examples/data_flywheel_example.py

## 运行测试
test:
	pytest tests/ -v

## 运行测试并生成覆盖率报告
test-cov:
	pytest tests/ --cov=. --cov-report=html