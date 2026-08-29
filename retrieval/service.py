"""RAG 检索模块：知识库分块 → 向量化(ChromaDB) → 检索 → 问答(带引用)

打通「数据作战流知识库产物 → 索引 → 检索 → 带引用问答」闭环（原型阶段核心假设验证）。
- index_knowledge(kb_run_id, chunks)   把分块写入 ChromaDB collection kb_<run_id>（真实向量化）
- retrieve(kb_run_id, query, top_k)    向量检索 top_k 相关分块（真实 ChromaDB 最近邻）
- rag_answer(kb_run_id, query, llm_call)  检索 → 组装 prompt → 调 core/llm → {answer, sources}
- list_indexed()                       列出已索引的知识库（前端「选择知识库」下拉）

档案：tmp/web/retrieval/<kb_run_id>/archive.json（collection 名、块数、索引时间）。
ChromaDB 持久化目录：tmp/web/retrieval/chroma（已 gitignore）。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from core.logging.logger import get_logger

logger = get_logger()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RETRIEVAL_ROOT = PROJECT_ROOT / "tmp" / "web" / "retrieval"
CHROMA_DIR = RETRIEVAL_ROOT / "chroma"
COLLECTION_PREFIX = "kb_"

_client_instance = None


def _client():
    """ChromaDB PersistentClient 单例（懒加载，禁用匿名遥测）"""
    global _client_instance
    if _client_instance is None:
        import chromadb
        from chromadb.config import Settings
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client_instance = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client_instance


def _get_ef(embedding_function=None):
    """嵌入函数：未指定时用 ChromaDB 默认嵌入（本机已缓存 ONNX MiniLM，离线可用）。

    注意：macOS 上 onnxruntime 的 CoreMLExecutionProvider 对批量输入偶发崩溃，
    这里强制用 CPUExecutionProvider 保证批量分块索引稳定。
    """
    if embedding_function is not None:
        return embedding_function
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
    return ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])


def collection_name(kb_run_id: str) -> str:
    return f"{COLLECTION_PREFIX}{kb_run_id}"


# ---------- 档案 ----------


def _write_archive(kb_run_id: str, payload: dict) -> None:
    d = RETRIEVAL_ROOT / kb_run_id
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "archive.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _load_archive(kb_run_id: str) -> Optional[dict]:
    p = RETRIEVAL_ROOT / kb_run_id / "archive.json"
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def get_archive(kb_run_id: str) -> Optional[dict]:
    """读取某知识库索引档案（collection 名 / 块数 / 索引时间），未索引返回 None"""
    return _load_archive(kb_run_id)


def list_indexed() -> list:
    """列出已索引的知识库（按索引时间倒序），供前端「选择知识库」"""
    if not RETRIEVAL_ROOT.exists():
        return []
    out = []
    for d in RETRIEVAL_ROOT.iterdir():
        if d.is_dir():
            a = _load_archive(d.name)
            if a:
                out.append(a)
    out.sort(key=lambda x: x.get("indexed_at", ""), reverse=True)
    return out


# ---------- 1. 索引 ----------


def index_knowledge(kb_run_id: str, chunks: list, embedding_function=None, min_chunk_len: int = 20) -> dict:
    """把分块写入 ChromaDB collection kb_<run_id>（真实向量化），返回 {collection, chunk_count}

    过滤过短分块（<min_chunk_len，与 kb.quality_check 的 too_short 阈值一致）：
    过短文本的嵌入向量高度泛化，会让检索排序失真（如 4 字块「防尘罩。」排到最前）。
    """
    chunks = [str(c).strip() for c in (chunks or []) if c and str(c).strip()]
    chunks = [c for c in chunks if len(c) >= min_chunk_len]
    if not chunks:
        raise ValueError(f"没有可索引的分块（全部过短，min_chunk_len={min_chunk_len}）")
    ef = _get_ef(embedding_function)
    client = _client()
    name = collection_name(kb_run_id)
    col = client.get_or_create_collection(
        name,
        metadata={"hnsw:space": "cosine"},
        embedding_function=ef,
    )
    # 幂等重建：先清掉该知识库旧分块，再整体写入（重新索引覆盖旧数据）
    try:
        col.delete(where={"source": kb_run_id})
    except Exception:
        pass
    ids = [f"{kb_run_id}:{i}" for i in range(len(chunks))]
    metadatas = [{"source": kb_run_id, "chunk_id": i} for i in range(len(chunks))]
    col.upsert(ids=ids, documents=chunks, metadatas=metadatas)

    now = datetime.now().isoformat()
    _write_archive(kb_run_id, {
        "kb_run_id": kb_run_id,
        "collection": name,
        "chunk_count": len(chunks),
        "indexed_at": now,
    })
    logger.info(f"知识库索引完成 kb_run_id={kb_run_id} collection={name} chunks={len(chunks)}")
    return {"collection": name, "chunk_count": len(chunks)}


# ---------- 2. 检索 ----------


def retrieve(kb_run_id: str, query: str, top_k: int = 5, embedding_function=None) -> list:
    """向量检索 top_k 相关分块，返回 [{chunk, score, distance, source}]（score 越高越相关）"""
    if not query or not str(query).strip():
        raise ValueError("检索 query 不能为空")
    ef = _get_ef(embedding_function)
    client = _client()
    name = collection_name(kb_run_id)
    try:
        col = client.get_collection(name, embedding_function=ef)
    except Exception:
        raise FileNotFoundError(f"知识库未索引或不存在: {kb_run_id}（请先执行索引）")
    if col.count() == 0:
        return []

    res = col.query(
        query_texts=[query],
        n_results=max(1, int(top_k)),
        include=["documents", "metadatas", "distances"],
    )
    docs = (res.get("documents") or [[]])[0] or []
    metas = (res.get("metadatas") or [[]])[0] or []
    dists = (res.get("distances") or [[]])[0] or []

    out = []
    for i, doc in enumerate(docs):
        d = float(dists[i]) if i < len(dists) else 0.0
        m = metas[i] if i < len(metas) else {}
        out.append({
            "chunk": doc,
            "score": round(1.0 - d, 4),   # 余弦相似度（越高越相关）
            "distance": round(d, 4),
            "source": m.get("source", kb_run_id),
        })
    return out


# ---------- 3. RAG 问答（带引用） ----------


def _default_llm_call(system: str, user: str) -> str:
    from core.llm import chat
    return chat(system=system, user=user, temperature=0.3)


RAG_SYSTEM = (
    "你是一个基于知识库的问答助手。根据提供的知识库分块内容回答用户问题。\n"
    "规则：\n"
    "1. 优先使用知识库内容回答；\n"
    "2. 如果知识库内容不足以回答问题，明确回答“我不知道”或“知识库中未找到相关信息”，不要编造；\n"
    "3. 回答末尾标注你所引用的分块编号，格式如 [1][2]；\n"
    "4. 回答简洁准确，只回答用户问题。"
)


def rag_answer(kb_run_id: str, query: str, llm_call: Optional[Callable] = None,
               top_k: int = 5, embedding_function=None) -> dict:
    """检索 top_k → 组装 prompt → 调 LLM → {answer, sources:[{chunk 前100字, score}]}"""
    hits = retrieve(kb_run_id, query, top_k=top_k, embedding_function=embedding_function)
    if not hits:
        return {"answer": "知识库中没有可检索的内容，无法回答。", "sources": []}

    ctx_blocks = "\n".join(f"[{i + 1}] {h['chunk']}" for i, h in enumerate(hits))
    user = f"知识库分块内容：\n{ctx_blocks}\n\n用户问题：{query}"

    caller = llm_call or _default_llm_call
    answer = caller(RAG_SYSTEM, user)

    sources = [
        {"chunk": h["chunk"][:100], "score": h["score"], "source": h["source"]}
        for h in hits
    ]
    return {"answer": answer, "sources": sources}
