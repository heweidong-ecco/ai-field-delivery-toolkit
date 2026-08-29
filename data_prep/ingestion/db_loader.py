"""数据库数据接入（PostgreSQL）"""

from typing import List, Dict, Any

from data_prep.ingestion.base import DataIngestor


class DBLoader(DataIngestor):
    """从数据库查询数据"""

    def ingest(self, db_connection: str, query: str = "SELECT * FROM records LIMIT 1000") -> Dict[str, Any]:
        # query 参数允许传入自定义 SQL
        # MVP 简化：假设连接串是 SQLAlchemy 格式，执行一个固定查询
        # 实际项目需要传入表名或查询语句
        import asyncio
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        async def _fetch():
            engine = create_async_engine(db_connection)
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT * FROM records LIMIT 1000"))
                rows = result.fetchall()
                columns = result.keys()
                records = []
                for row in rows:
                    content = " ".join(str(row[i]) for i in range(len(row)))
                    metadata = {columns[i]: str(row[i]) for i in range(len(row))}
                    records.append({"content": content, "metadata": metadata})
            await engine.dispose()
            return records

        records = asyncio.run(_fetch())
        return {"data": records}