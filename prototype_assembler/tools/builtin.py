"""内置工具"""

from prototype_assembler.tools.registry import Tool, ToolRegistry


def _search_knowledge_base(args):
    """搜索知识库（示例）"""
    query = args.get("query", "")
    return f"知识库搜索结果：{query} 相关内容"


def _query_database(args):
    """查询数据库（示例）"""
    table = args.get("table", "unknown")
    return f"数据库表 {table} 查询结果"


def register_builtin_tools(registry: ToolRegistry):
    """注册内置工具"""
    registry.register(Tool(
        name="search_knowledge",
        description="搜索内部知识库",
        func=_search_knowledge_base,
    ))
    registry.register(Tool(
        name="query_db",
        description="查询数据库",
        func=_query_database,
        requires_permission=True,
    ))