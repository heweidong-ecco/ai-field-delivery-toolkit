"""五步裁剪引擎测试（v1.2.0）"""

import json
import os

from cropper.constraints import (
    CustomerConstraints,
    HardwareConstraints,
    EnvironmentConstraints,
    DataConstraints,
    UserConstraints,
    ComplianceConstraints,
)
from cropper.engine import crop_for_customer
from cropper.five_steps import FiveStepCropper


def make_constraints(**kwargs) -> CustomerConstraints:
    """构造测试用客户约束"""
    defaults = dict(
        customer_id="test-customer",
        budget=200000,
        hardware=HardwareConstraints(cpu="8核", memory_gb=32, gpu=None),
        environment=EnvironmentConstraints(docker=True, network="internet"),
        data=DataConstraints(total_records=300000, daily_new=500),
        users=UserConstraints(total_users=100),
        compliance=ComplianceConstraints(),
        timeline_weeks=2,
    )
    defaults.update(kwargs)
    return CustomerConstraints(**defaults)


class TestFiveStepCropper:
    """五步裁剪引擎基础测试"""

    def test_normal_plan(self):
        """正常预算和资源，核心模块应全部启用"""
        constraints = make_constraints()
        plan = crop_for_customer(constraints)
        assert "data_prep" in plan.enabled_modules
        assert "prototype_assembler" in plan.enabled_modules
        assert "diagnosis" in plan.enabled_modules

    def test_low_budget_deletes_modules(self):
        """预算极低时删除监控、数据飞轮、部署加固"""
        constraints = make_constraints(budget=20000)
        plan = crop_for_customer(constraints)
        assert "monitor" in plan.deleted_modules
        assert "data_flywheel" in plan.deleted_modules
        assert "deploy_hardener" in plan.deleted_modules

    def test_small_data_deletes_flywheel(self):
        """数据量极小时删除数据飞轮"""
        constraints = make_constraints(
            data=DataConstraints(total_records=500, daily_new=0)
        )
        plan = crop_for_customer(constraints)
        assert "data_flywheel" in plan.deleted_modules

    def test_few_users_deletes_monitor(self):
        """用户极少时删除监控"""
        constraints = make_constraints(
            users=UserConstraints(total_users=2, concurrent_peak=1)
        )
        plan = crop_for_customer(constraints)
        assert "monitor" in plan.deleted_modules

    def test_no_docker_simplifies_deploy(self):
        """不支持 Docker 时简化部署为裸机"""
        constraints = make_constraints(
            environment=EnvironmentConstraints(
                docker=False,
                network="intranet-isolated",
                external_access=False,
            )
        )
        plan = crop_for_customer(constraints)
        assert plan.simplifications["deploy_hardener"]["mode"] == "bare-metal"

    def test_no_gpu_simplifies_prototype(self):
        """无 GPU 时简化 Agent 循环和模型来源"""
        constraints = make_constraints(
            hardware=HardwareConstraints(cpu="8核", memory_gb=32, gpu=None)
        )
        plan = crop_for_customer(constraints)
        assert plan.simplifications["prototype_assembler"]["agent_loop"] == "react-only"
        assert plan.simplifications["prototype_assembler"]["model_source"] == "local-cpu"

    def test_dirty_data_high_cleaning(self):
        """脏数据时清洗强度为 high"""
        constraints = make_constraints(
            data=DataConstraints(total_records=100000, quality="dirty")
        )
        plan = crop_for_customer(constraints)
        assert plan.simplifications["data_prep"]["cleaning_intensity"] == "high"

    def test_plan_save_and_load(self, tmp_path):
        """裁剪方案保存和加载"""
        constraints = make_constraints()
        plan = crop_for_customer(constraints)
        path = str(tmp_path / "plan.json")
        plan.save(path)
        assert os.path.exists(path)

        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["customer_id"] == "test-customer"
        assert "data_prep" in loaded["enabled_modules"]


class TestFiveStepCropperV2:
    """五步裁剪引擎测试（v1.2.0 新增约束维度）"""

    def test_low_bandwidth_affects_monitor(self):
        """低网络带宽时监控改为批量上报"""
        constraints = make_constraints(
            environment=EnvironmentConstraints(
                docker=True,
                network="internet",
                network_bandwidth_mbps=20,
            )
        )
        plan = crop_for_customer(constraints)
        if "monitor" in plan.enabled_modules:
            assert plan.simplifications["monitor"]["report_frequency"] == "batch"

    def test_low_bandwidth_affects_flywheel(self):
        """低网络带宽时数据飞轮改为批量模式"""
        constraints = make_constraints(
            environment=EnvironmentConstraints(
                docker=True,
                network="internet",
                network_bandwidth_mbps=20,
            )
        )
        plan = crop_for_customer(constraints)
        if "data_flywheel" in plan.enabled_modules:
            assert plan.simplifications["data_flywheel"]["mode"] == "batch"

    def test_critical_compliance_affects_model(self):
        """合规等级 critical 时模型来源受限"""
        constraints = make_constraints(
            compliance=ComplianceConstraints(
                data_residency="on-premise",
                pii_sensitive=True,
                compliance_level="critical",
            )
        )
        plan = crop_for_customer(constraints)
        if "prototype_assembler" in plan.enabled_modules:
            assert plan.simplifications["prototype_assembler"]["model_source"] == "local-or-vetted-api"

    def test_critical_compliance_no_gpu_deletes_prototype(self):
        """合规等级 critical + 无 GPU 时删除原型组装器"""
        constraints = make_constraints(
            hardware=HardwareConstraints(cpu="8核", memory_gb=32, gpu=None),
            compliance=ComplianceConstraints(
                data_residency="on-premise",
                pii_sensitive=True,
                compliance_level="critical",
            ),
        )
        plan = crop_for_customer(constraints)
        assert "prototype_assembler" in plan.deleted_modules

    def test_high_bandwidth_automates_dashboard(self):
        """高网络带宽时自动开启实时看板"""
        constraints = make_constraints(
            environment=EnvironmentConstraints(
                docker=True,
                network="internet",
                network_bandwidth_mbps=500,
            )
        )
        plan = crop_for_customer(constraints)
        assert "monitor:real_time_dashboard" in plan.automations

    def test_standard_compliance_automates_eval_update(self):
        """标准合规等级时自动开启评测集更新"""
        constraints = make_constraints(
            compliance=ComplianceConstraints(
                data_residency="on-premise",
                pii_sensitive=True,
                compliance_level="standard",
            )
        )
        plan = crop_for_customer(constraints)
        assert "data_flywheel:auto_eval_update" in plan.automations

    def test_strict_compliance_no_automation(self):
        """严格合规等级时不自动开启数据飞轮"""
        constraints = make_constraints(
            compliance=ComplianceConstraints(
                data_residency="on-premise",
                pii_sensitive=True,
                compliance_level="strict",
            )
        )
        plan = crop_for_customer(constraints)
        assert "data_flywheel:auto_eval_update" not in plan.automations

    def test_question_records_new_dimensions(self):
        """质疑步骤应包含新维度的记录"""
        constraints = make_constraints(
            environment=EnvironmentConstraints(
                docker=True,
                network="internet",
                network_bandwidth_mbps=20,
            ),
            compliance=ComplianceConstraints(compliance_level="critical"),
        )
        cropper = FiveStepCropper()
        questioned = cropper._step_question(constraints)
        assert "data_flywheel:auto_pipeline" in questioned
        assert "all:external_dependency" in questioned


class TestCropperIntegration:
    """裁剪引擎与其他模块的集成测试"""

    def test_plan_is_json_serializable(self):
        """裁剪方案可 JSON 序列化"""
        constraints = make_constraints()
        plan = crop_for_customer(constraints)
        plan_dict = plan.to_dict()
        json.dumps(plan_dict)  # 不抛异常即通过

    def test_plan_contains_all_sections(self):
        """裁剪方案包含全部必要部分"""
        constraints = make_constraints()
        plan = crop_for_customer(constraints)
        plan_dict = plan.to_dict()
        assert "enabled_modules" in plan_dict
        assert "deleted_modules" in plan_dict
        assert "simplifications" in plan_dict
        assert "automations" in plan_dict
        assert "timeline_suggestion" in plan_dict

    def test_diagnosis_always_enabled(self):
        """诊断器始终启用"""
        constraints = make_constraints(budget=10000, data=DataConstraints(total_records=10))
        plan = crop_for_customer(constraints)
        assert "diagnosis" in plan.enabled_modules