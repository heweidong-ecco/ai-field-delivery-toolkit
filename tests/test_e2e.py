"""端到端集成测试：覆盖全流程"""

import json
import os

import pytest


class TestEndToEnd:
    """端到端测试"""

    def test_full_flow(self, tmp_path):
        """模拟 FDE 从诊断到飞轮的完整流程"""
        # 1. 诊断
        from diagnosis.checklist import AIFeasibilityChecklist
        checklist = AIFeasibilityChecklist()
        feasibility = checklist.quick_evaluate(4, 3, 4, 5, 2)
        assert feasibility["total_score"] >= 15

        # 2. 裁剪
        from cropper.constraints import (
            CustomerConstraints, HardwareConstraints, EnvironmentConstraints,
            DataConstraints, UserConstraints, ComplianceConstraints,
        )
        from cropper.engine import crop_for_customer
        constraints = CustomerConstraints(
            customer_id="e2e-customer",
            budget=100000,
            hardware=HardwareConstraints(gpu=None),
            environment=EnvironmentConstraints(docker=True),
            data=DataConstraints(total_records=10000, quality="medium"),
            users=UserConstraints(total_users=50),
            compliance=ComplianceConstraints(),
            timeline_weeks=2,
        )
        plan = crop_for_customer(constraints)
        assert "data_prep" in plan.enabled_modules
        assert "prototype_assembler" in plan.enabled_modules

        # 3. 数据准备
        from data_prep.pipeline import DataPrepPipeline
        # 创建 CSV（30 条语义各异的内容，语义去重后应全部保留）
        import csv
        csv_path = tmp_path / "e2e.csv"
        docs = [
            "基于内部知识库搭建智能问答系统",
            "自动对客户工单进行多级分类",
            "从租赁合同中抽取关键条款",
            "对生产设备故障日志做根因分析",
            "将非结构化简历解析为结构化字段",
            "销售话术复盘并生成改进建议",
            "质检报告中的异常数据清洗",
            "对客服对话进行情感分析",
            "跨系统数据一致性自动校验",
            "政策文件要点提取与摘要生成",
            "投标文档自动比对关键差异",
            "用户评论主题聚类分析",
            "电商商品描述自动生成",
            "医疗报告关键指标抽取",
            "财务报表科目异常检测",
            "招聘岗位与简历匹配打分",
            "论文参考文献格式化转换",
            "会议纪要自动生成行动项",
            "代码仓库缺陷标题规范化",
            "城市交通拥堵热点分析",
            "供应链库存周转预测",
            "舆情事件关联网络构建",
            "教学课件知识点自动切片",
            "保险理赔材料完整性检查",
            "安防监控异常事件检测",
            "银行流水交易对手方识别",
            "科研文献实验方法对比",
            "客服话术合规性审查",
            "多语言产品说明翻译校对",
            "供应链缺货风险预警",
        ]
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["content"])
            writer.writeheader()
            for doc in docs:
                writer.writerow({"content": doc})

        pipeline = DataPrepPipeline()
        prep_result = pipeline.run(
            source_type="csv",
            source_path=str(csv_path),
            output_dir=str(tmp_path / "prep_output"),
            eval_samples=10,
        )
        assert prep_result["cleaned_count"] > 0
        assert prep_result["eval_set_count"] == 10

        # 4. 原型运行
        from prototype_assembler.assembler import PrototypeAssembler
        assembler = PrototypeAssembler()
        agent_result = assembler.run("knowledge_qa", "什么是RAG？")
        assert isinstance(agent_result, str)

        # 5. 部署配置
        from deploy_hardener.pipeline import DeployHardenerPipeline
        deploy_pipeline = DeployHardenerPipeline()
        deploy_result = deploy_pipeline.run(
            project_dir=str(tmp_path),
            output_dir=str(tmp_path / "deploy_output"),
            mode="docker-compose",
        )
        assert deploy_result["mode"] == "docker-compose"

        # 6. 监控指标
        from monitor.metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_request(success=True, latency_ms=100, input_tokens=100, output_tokens=50)
        metrics = collector.get_metrics()
        assert metrics["total_requests"] == 1

        # 7. 数据飞轮
        from data_flywheel.pipeline import DataFlywheelPipeline
        flywheel = DataFlywheelPipeline()
        flywheel.record_feedback(
            request_id="e2e-001",
            user_input="问题",
            model_output="回答",
            feedback_type="dislike",
        )
        assert len(flywheel.feedback_collector.get_pool()) == 1

        # 8. 资产导出
        asset_result = flywheel.export_assets(
            project_id="e2e-project",
            output_path=str(tmp_path / "assets.json"),
        )
        assert asset_result["total_assets"] > 0