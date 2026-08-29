import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
项目档案示例：以项目为中心保存完整过程记录

运行方式：
    python examples/projects_example.py
"""

from core.logging.logger import get_logger

logger = get_logger()


if __name__ == "__main__":
    logger.info("=== 项目档案示例 ===")

    from projects.archive import add_event, create_project, get_project, list_projects

    proj = create_project("制造客户-设备预测", customer="制造客户")
    pid = proj["project_id"]
    logger.info(f"项目已创建: {pid}")

    add_event(pid, "meeting", "需求沟通会", detail="确认核心痛点是设备停机预测")
    add_event(pid, "diagnosis", "完成需求诊断", detail="多 Agent 对抗评审 + 人工确认", ref="run-xxx")
    add_event(pid, "iteration", "第一轮迭代", detail="接入传感器数据")
    add_event(pid, "issue", "现场问题：数据权限未开", detail="等待客户 IT 授权")

    detail = get_project(pid)
    logger.info(f"项目时间线共 {len(detail['events'])} 条过程记录")
    for ev in detail["events"]:
        logger.info(f"  [{ev['type']}] {ev['title']}")

    logger.info(f"最近项目: {[p['name'] for p in list_projects()]}")
