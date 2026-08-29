"""项目结束生成可复用资产清单"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from core.logging.logger import get_logger

logger = get_logger()


class AssetExporter:
    """资产导出器"""

    def export(
        self,
        project_id: str,
        assets: List[Dict[str, Any]],
        output_path: str,
        project_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成可复用资产清单

        参数:
            project_id: 项目标识
            assets: 资产列表，每项包含 type/name/path
            output_path: 输出 JSON 文件路径
            project_summary: 项目总结（可选）
        """
        asset_list = []
        for idx, asset in enumerate(assets):
            asset_list.append({
                "id": f"ASSET-{idx+1:03d}",
                "type": asset.get("type", "component"),   # component/template/doc/config
                "name": asset["name"],
                "path": asset.get("path", ""),
                "description": asset.get("description", ""),
                "reusable": asset.get("reusable", True),
            })

        export_data = {
            "project_id": project_id,
            "exported_at": datetime.now().isoformat(),
            "summary": project_summary or "",
            "assets": asset_list,
            "total_assets": len(asset_list),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        logger.info(f"资产清单已导出: {output_path}，共 {len(asset_list)} 项")
        return export_data

    def generate_default_assets(self, project_id: str) -> List[Dict[str, Any]]:
        """根据当前项目结构生成默认资产清单（示例）"""
        return [
            {"type": "config", "name": "数据清洗配置", "path": "data_prep/cleaning/default_rules.yaml", "description": "通用数据清洗规则"},
            {"type": "template", "name": "知识问答Agent模板", "path": "prototype_assembler/templates/qa_agent.py", "description": "RAG问答场景模板"},
            {"type": "component", "name": "PII脱敏组件", "path": "core/security/pii.py", "description": "通用PII检测与脱敏"},
            {"type": "doc", "name": "部署文档", "path": "docs/deployment.md", "description": "部署加固器使用说明"},
            {"type": "config", "name": "降级预案", "path": "deploy_hardener/degradation.yaml", "description": "三级降级链配置"},
        ]