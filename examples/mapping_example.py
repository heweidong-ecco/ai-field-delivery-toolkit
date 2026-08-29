import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
字段映射工作台示例

运行方式：
    python examples/mapping_example.py

流程：LLM 初判映射 → 人工调整 → 导出适配器配置（run_id 断点可续接）
说明：需要已配置 DEEPSEEK_API_KEY（LLM 初判会调真实模型）。
"""

from core.logging.logger import get_logger

logger = get_logger()


if __name__ == "__main__":
    logger.info("=== 字段映射工作台示例 ===")

    from mapping.service import create_mapping, export_mapping, get_mapping, update_mapping

    source = [
        {"name": "customer_name", "sample": "张三"},
        {"name": "customer_phone", "sample": "13812345678"},
        {"name": "full_address", "sample": "北京市朝阳区XX路1号"},
    ]
    target = [
        {"name": "name", "sample": "张三"},
        {"name": "phone", "sample": "13812345678"},
        {"name": "address", "sample": "北京市朝阳区XX路1号"},
    ]

    m = create_mapping("客户信息同步", source, target)
    run_id = m["run_id"]
    logger.info(f"映射任务已创建 run_id={run_id}，LLM 初判 {len(m['mappings'])} 条：")
    for mp in m["mappings"]:
        logger.info(f"  {mp['target']} <- {mp['source']} [{mp['rule']}] {mp.get('confidence','')}")

    # 人工调整（例如把 phone 的来源改为 full_address 的拆分，此处演示保留 LLM 初判）
    adjusted = [dict(x) for x in m["mappings"]]
    update_mapping(run_id, adjusted)
    logger.info("人工调整已保存（断点可续接，get_mapping 可恢复）")

    exp = export_mapping(run_id)
    logger.info(f"适配器已导出: {exp['config_path']} / {exp['adapter_path']}")
    logger.info("--- adapter.py ---")
    print(exp["adapter_code"])
