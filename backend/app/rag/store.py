# 向量库（Chroma）封装：构建嵌入函数与客户端，负责知识库写入（默认导入）与向量检索
import hashlib
import math
import os
import re
import threading
from pathlib import Path
from typing import Any
import numpy as np

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("POSTHOG_DISABLED", "1")

import chromadb
from chromadb.utils import embedding_functions

from ..config import settings
from .loaders import load_knowledge_markdown

_lock = threading.Lock()
_client: Any = None
_collection: Any = None
_knowledge_chunks: list[dict] | None = None


def invalidate_knowledge_cache() -> None:
    # Markdown 或在售商品变更后清空分块缓存，下次检索重新加载
    global _knowledge_chunks
    _knowledge_chunks = None


# 离线嵌入实现：把词哈希到固定维度向量并归一化，全程不依赖网络与模型文件
class HashEmbeddingFunction:
    # 纯本地哈希嵌入，网络不可用时保证 Chroma 仍可写入和检索
    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    # 对文本分词后按哈希映射到 dim 维向量，再做 L2 归一化便于余弦检索
    def __call__(self, input: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in input:
            vector = [0.0] * self.dim
            for token in re.findall(r"[\w\u4e00-\u9fff]+", text.lower()):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).hexdigest()
                index = int(digest, 16) % self.dim
                vector[index] += 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        # 返回 1D ndarray 列表：HttpClient 遍历调用 .tolist()，PersistentClient 做 == [] 检查均兼容
        return [np.array(v, dtype=np.float32) for v in vectors]

    # 嵌入函数标识名，便于 Chroma 识别该嵌入函数
    def name(self) -> str:
        return "hash-offline"


# 双通道嵌入：优先 ONNX 语义模型，任何异常都自动回退到哈希嵌入，保证服务可用
class SafeEmbeddingFunction:
    """Try ONNX MiniLM first, then fall back to an offline hash embedding."""

    def __init__(self) -> None:
        # 优先使用 chromadb 自带 ONNXMiniLM_L6_V2，加载失败时使用哈希回退
        self._onnx = None
        self._hash = HashEmbeddingFunction()
        try:
            self._onnx = embedding_functions.ONNXMiniLM_L6_V2()
        except Exception:
            self._onnx = None

    # 优先用 ONNX 向量化，失败即回退哈希，避免单点故障中断检索
    def __call__(self, input: list[str]) -> list[list[float]]:
        if self._onnx is not None:
            try:
                return self._onnx(input)
            except Exception:
                self._onnx = None
        result = self._hash(input)
        # 统一为 list[ndarray]：ONNX 返回 2D ndarray 时拆成逐行 1D 数组
        if isinstance(result, np.ndarray):
            result = [row for row in result]
        return result

    def name(self) -> str:
        return "onnx-with-hash-fallback"


# 按配置选择嵌入函数：openai 用远程兼容 API，其余场景用本地双通道实现
def _build_embedding_function() -> Any:
    # openai 模式走 OpenAI 兼容 API，onnx 模式走 SafeEmbeddingFunction
    if settings.embedding_provider.lower() == "openai":
        kwargs: dict = {
            "api_key": settings.embedding_api_key,
            "model_name": settings.embedding_model,
        }
        if settings.embedding_base_url:
            kwargs["api_base"] = settings.embedding_base_url
        return embedding_functions.OpenAIEmbeddingFunction(**kwargs)
    return SafeEmbeddingFunction()


# 全局单例客户端：优先连接远程 Chroma 服务，否则使用本地持久化目录
def get_client() -> Any:
    # 配置 CHROMA_URL 时连接独立 Chroma 服务，否则使用本地持久化目录
    global _client
    if _client is not None:
        return _client
    if settings.chroma_is_remote:
        from urllib.parse import urlparse

        parsed = urlparse(settings.chroma_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8000
        _client = chromadb.HttpClient(host=host, port=port, ssl=parsed.scheme == "https")
    else:
        persist_dir = Path(settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(persist_dir))
    return _client


# 用内置知识库填充空 collection，保证首次检索即有结果
def _load_defaults(collection: Any) -> None:
    # collection 为空时自动导入内置知识库
    base_dir = Path(__file__).resolve().parents[1] / "data" / "knowledge"
    chunks = load_knowledge_markdown(base_dir)
    if not chunks:
        return
    # 过滤只有标题的碎片，避免“# 商品名”这种空块进入知识库
    chunks = [chunk for chunk in chunks if len(chunk["text"].strip()) >= 20]
    # 以"文件名-序号"作为唯一 id，source 存入 metadata 便于结果溯源
    collection.add(
        ids=[f"{chunk['source']}-{index}" for index, chunk in enumerate(chunks)],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[{"source": chunk["source"]} for chunk in chunks],
    )


def _load_knowledge_chunks() -> list[dict]:
    # 缓存知识库分块，供混合召回时做全文关键词匹配
    global _knowledge_chunks
    if _knowledge_chunks is None:
        base_dir = Path(__file__).resolve().parents[1] / "data" / "knowledge"
        chunks = [
            chunk
            for chunk in load_knowledge_markdown(base_dir)
            if len(chunk["text"].strip()) >= 20
        ]
        try:
            from ..core.product_knowledge import live_catalog_chunks
            from ..data import showcase

            seen = {chunk["text"] for chunk in chunks}
            for extra in live_catalog_chunks(list(showcase.PRODUCTS)):
                if extra["text"] not in seen:
                    chunks.append(extra)
                    seen.add(extra["text"])
        except Exception:
            pass
        _knowledge_chunks = chunks
    return _knowledge_chunks


def keyword_score(query: str, text: str) -> int:
    # 按 2-4 字 n-gram 计算字面相关度，供混合召回与结果排序使用
    normalized_query = re.sub(r"\s+", "", query.lower())
    normalized_text = re.sub(r"\s+", "", text.lower())
    if not normalized_query:
        return 0
    score = 0
    for size in (2, 3, 4):
        ngrams = {
            normalized_query[index : index + size]
            for index in range(len(normalized_query) - size + 1)
        }
        score += sum(1 for ngram in ngrams if ngram in normalized_text)
    # 问价格时优先命中包含售价/优惠价的商品块，避免被同分其他小节挤掉
    if any(term in query for term in ("价格", "多少钱", "售价")) and any(
        term in text for term in ("售价", "价格", "优惠价")
    ):
        score += 20
    if any(term in query for term in ("有什么", "推荐", "哪些")) and any(
        term in text for term in ("在售", "售价", "推荐")
    ):
        score += 15
    return score


# 获取全局共享 collection：线程安全地完成创建与默认知识导入
def get_collection(rebuild: bool = False) -> Any:
    # rebuild=True 时清空并重建内置知识库，保证 Markdown 更新后重启即生效
    global _collection
    with _lock:
        if _collection is not None and not rebuild:
            return _collection
        if rebuild:
            invalidate_knowledge_cache()
        client = get_client()
        try:
            client.delete_collection("doudian_kb")
        except Exception:
            # 首次启动时 collection 尚不存在，忽略删除错误
            pass
        collection = client.get_or_create_collection(
            name="doudian_kb",
            embedding_function=_build_embedding_function(),
        )
        _load_defaults(collection)
        _collection = collection
    return _collection


# 知识检索入口：向量化 query 并返回 top_k 条结果，附带来源供引用
async def search_knowledge(query: str, top_k: int = 5) -> list[dict]:
    # 混合召回：向量结果与关键词命中合并后按字面相关度排序，修正详细知识库下的串题
    return await search_knowledge_with_distances(query, top_k)


# 带向量距离的检索：返回每条结果附带 Chroma 距离，供相关性评分使用
async def search_knowledge_with_distances(query: str, top_k: int = 5) -> list[dict]:
    collection = get_collection()
    result = collection.query(query_texts=[query], n_results=top_k)
    documents = (result.get("documents") or [[]])[0] or []
    metadatas = (result.get("metadatas") or [[]])[0] or []
    distances = (result.get("distances") or [[]])[0] or []
    candidates: dict[str, dict] = {}
    for text, metadata, distance in zip(documents, metadatas, distances):
        candidates[text] = {
            "text": text,
            "source": metadata.get("source", "unknown"),
            "distance": float(distance),
        }
    for chunk in _load_knowledge_chunks():
        if keyword_score(query, chunk["text"]) > 0:
            # 关键词命中的候选不来自向量检索，distance 设为 None
            candidates.setdefault(chunk["text"], {**chunk, "distance": None})
    return sorted(
        candidates.values(),
        key=lambda item: keyword_score(query, item["text"]),
        reverse=True,
    )[:top_k]
