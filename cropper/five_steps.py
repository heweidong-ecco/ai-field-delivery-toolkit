"""五步执行逻辑：质疑→删除→简化→加速→自动化（v1.2.0）"""

from typing import List, Dict, Any

from core.logging.logger import get_logger

from cropper.constraints import CustomerConstraints

logger = get_logger()

# 工具包全部模块清单（MVP）
ALL_MODULES = [
    "diagnosis",              # 需求诊断器
    "data_prep",              # 数据准备器
    "prototype_assembler",    # 原型组装器
    "deploy_hardener",        # 部署加固器
    "monitor",                # 监控开箱器
    "data_flywheel",          # 数据飞轮器
]


class FiveStepCropper:
    """五步裁剪器（v1.2.0）"""

    def execute(self, constraints: CustomerConstraints) -> Dict[str, Any]:
        """执行五步裁剪，返回完整方案"""
        logger.info(f"开始五步裁剪，客户: {constraints.customer_id}")

        # 第一步：质疑每一项需求
        necessity = self._step_question(constraints)

        # 第二步：删除所有能删除的
        deleted = self._step_delete(constraints, necessity)

        # 第三步：简化与优化保留模块
        simplifications = self._step_simplify(constraints, deleted)

        # 第四步：加速周转时间
        timeline = self._step_accelerate(constraints)

        # 第五步：自动化
        automations = self._step_automate(constraints)

        # 汇总
        enabled = [m for m in ALL_MODULES if m not in deleted]
        plan = {
            "customer_id": constraints.customer_id,
            "enabled_modules": enabled,
            "deleted_modules": deleted,
            "simplifications": simplifications,
            "automations": automations,
            "timeline_suggestion": timeline,
            "five_step_records": {
                "questioned": necessity,
                "deleted_reasons": self._get_deletion_reasons(constraints),
            },
        }
        logger.info(f"裁剪完成：启用={enabled}, 删除={deleted}")
        return plan

    def _step_question(self, constraints: CustomerConstraints) -> Dict[str, Any]:
        """第一步：质疑每一项需求

        核心是区分“真实必须”和“假设必须”。
        """
        questioned = {}

        # 硬件约束
        if not constraints.hardware.gpu:
            questioned["prototype_assembler:multi_agent"] = "无 GPU，多 Agent 协作可删除"
            questioned["prototype_assembler:complex_loop"] = "无 GPU，仅保留 ReAct 循环"

        # 预算约束
        if constraints.budget < 50000:
            questioned["monitor:full_tracing"] = "预算低，全链路追踪可删除"
            questioned["data_flywheel:auto_update"] = "预算低，自动数据飞轮可删除"

        # 环境约束
        if not constraints.environment.docker:
            questioned["deploy_hardener:docker"] = "客户不支持 Docker，需简化或更换部署方式"

        # 合规约束
        if constraints.compliance.data_residency == "on-premise":
            questioned["all:external_api"] = "数据驻留要求本地，外部 API 需配置本地替代"

        # v1.2.0 新增规则
        if constraints.environment.network_bandwidth_mbps < 50:
            questioned["data_flywheel:auto_pipeline"] = "网络带宽低，数据回流宜用批量而非实时"
            questioned["monitor:real_time"] = "网络带宽低，实时监控可降级为定时上报"

        if constraints.compliance.compliance_level == "critical":
            questioned["all:external_dependency"] = "合规等级 critical，所有外部依赖需审计"
            questioned["prototype_assembler:cloud_api"] = "合规等级 critical，建议本地模型"
        elif constraints.compliance.compliance_level == "strict":
            questioned["monitor:cloud_tracing"] = "合规等级 strict，全链路追踪建议本地化"

        return questioned

    def _step_delete(self, constraints: CustomerConstraints, necessity: Dict) -> List[str]:
        """第二步：删除所有能删除的模块"""
        deleted = []

        # 预算极低
        if constraints.budget < 30000:
            deleted.extend(["monitor", "data_flywheel", "deploy_hardener"])

        # 数据量极小
        if constraints.data.total_records < 1000:
            deleted.append("data_flywheel")

        # 用户极少
        if constraints.users.total_users < 5:
            if "monitor" not in deleted:
                deleted.append("monitor")

        # v1.2.0 新增规则
        if constraints.compliance.compliance_level == "critical" and not constraints.hardware.gpu:
            deleted.append("prototype_assembler")   # 完全本地化 + 无 GPU，MVP 暂不支持

        # 去重
        deleted = list(set(deleted))
        return deleted

    def _step_simplify(self, constraints: CustomerConstraints, deleted: List[str]) -> Dict[str, Any]:
        """第三步：简化与优化保留模块"""
        simplifications = {}

        # 部署加固器简化
        if "deploy_hardener" not in deleted:
            if not constraints.environment.docker:
                simplifications["deploy_hardener"] = {"mode": "bare-metal"}
            else:
                simplifications["deploy_hardener"] = {"mode": "docker-compose"}

        # 原型组装器简化
        if "prototype_assembler" not in deleted:
            if not constraints.hardware.gpu:
                simplifications["prototype_assembler"] = {
                    "agent_loop": "react-only",
                    "model_source": "local-cpu",
                }
            else:
                simplifications["prototype_assembler"] = {
                    "agent_loop": "react",
                    "model_source": "cloud-api",
                }

        # 数据准备器简化
        if "data_prep" not in deleted:
            if constraints.data.quality == "dirty":
                simplifications["data_prep"] = {"cleaning_intensity": "high"}
            elif constraints.data.quality == "medium":
                simplifications["data_prep"] = {"cleaning_intensity": "medium"}
            else:
                simplifications["data_prep"] = {"cleaning_intensity": "low"}

        # v1.2.0 新增规则
        if constraints.environment.network_bandwidth_mbps < 50:
            if "monitor" not in deleted:
                simplifications["monitor"] = {"report_frequency": "batch"}
            if "data_flywheel" not in deleted:
                simplifications["data_flywheel"] = {"mode": "batch"}

        if constraints.compliance.compliance_level == "strict":
            if "prototype_assembler" not in deleted:
                simplifications["prototype_assembler"]["model_source"] = "local-or-vetted-api"

        return simplifications

    def _step_accelerate(self, constraints: CustomerConstraints) -> Dict[str, Any]:
        """第四步：加速周转时间，给出时间线建议"""
        weeks = constraints.timeline_weeks
        if weeks >= 4:
            data_prep_days = 8
            prototype_days = 3
            deploy_days = 3
        elif weeks >= 2:
            data_prep_days = 5
            prototype_days = 2
            deploy_days = 2
        else:
            data_prep_days = 3
            prototype_days = 1
            deploy_days = 1

        return {
            "data_prep": f"{data_prep_days} days",
            "prototype": f"{prototype_days} days",
            "deploy": f"{deploy_days} days",
            "total_days": data_prep_days + prototype_days + deploy_days,
        }

    def _step_automate(self, constraints: CustomerConstraints) -> List[str]:
        """第五步：自动化建议"""
        automations = []

        if constraints.data.daily_new > 0 and constraints.budget >= 50000:
            automations.append("data_flywheel:auto_feedback_pipeline")
        if constraints.users.total_users >= 100:
            automations.append("monitor:auto_alerting")
        if constraints.environment.docker and constraints.hardware.gpu:
            automations.append("deploy_hardener:auto_scaling")

        # v1.2.0 新增规则
        if constraints.environment.network_bandwidth_mbps >= 200:
            automations.append("monitor:real_time_dashboard")
        if constraints.compliance.compliance_level == "standard":
            automations.append("data_flywheel:auto_eval_update")

        return automations

    def _get_deletion_reasons(self, constraints: CustomerConstraints) -> Dict[str, str]:
        """生成删除原因"""
        reasons = {}
        if constraints.budget < 30000:
            reasons["monitor"] = "预算极低，监控简化为本地日志"
            reasons["data_flywheel"] = "预算极低，数据飞轮后置"
            reasons["deploy_hardener"] = "预算极低，使用裸机脚本而非容器"
        if constraints.data.total_records < 1000:
            reasons["data_flywheel"] = "数据量极小，无需持续回流"
        if constraints.users.total_users < 5:
            reasons["monitor"] = "用户极少，基础告警即可"
        if constraints.compliance.compliance_level == "critical" and not constraints.hardware.gpu:
            reasons["prototype_assembler"] = "合规等级 critical + 无 GPU，需完全本地化方案"
        return reasons