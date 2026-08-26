import math
import re
from typing import Any

from ..rag.store import _load_knowledge_chunks, keyword_score, search_knowledge_with_distances
from .ingestion import ingestion_service


def _query_terms(query: str) -> set[str]:
    """Extract English words and Chinese bigrams for lexical matching."""
    english = set(re.findall(r"[A-Za-z0-9]+", query.lower()))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", query))
    bigrams = {chinese[i:i + 2] for i in range(max(0, len(chinese) - 1))}
    if len(chinese) <= 2:
        bigrams.update(chinese)
    return {t for t in english | bigrams if t}


def _bm25_tokens(text: str) -> list[str]:
    english = re.findall(r"[a-z0-9]+", text.lower())
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    bigrams = [chinese[i:i + 2] for i in range(max(0, len(chinese) - 1))]
    return [t for t in [*english, *bigrams] if len(t) > 1]


def _bm25_score(query: str, candidates: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    """BM25 ranking over candidate documents."""
    query_terms = set(_bm25_tokens(query))
    if not query_terms or not candidates:
        return []
    tokenized = [(c, _bm25_tokens(c.get("text", ""))) for c in candidates]
    doc_count = len(tokenized)
    avg_len = sum(len(toks) for _, toks in tokenized) / max(doc_count, 1)
    df: dict[str, int] = {}
    for _, toks in tokenized:
        for term in set(toks):
            df[term] = df.get(term, 0) + 1
    k1, b = 1.2, 0.75
    scored: list[tuple[float, dict]] = []
    for cand, toks in tokenized:
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for term in query_terms:
            freq = tf.get(term, 0)
            if not freq:
                continue
            idf = math.log(1 + (doc_count - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
            norm = 1 - b + b * len(toks) / max(avg_len, 1)
            score += idf * (freq * (k1 + 1)) / (freq + k1 * norm)
        if score > 0:
            scored.append((score, cand))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit]]


def _rrf_fuse(vector_results: list[dict], bm25_results: list[dict], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion: combine vector and BM25 rankings."""
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    for rank, item in enumerate(vector_results, 1):
        key = item["text"]
        scores[key] = scores.get(key, 0) + 1 / (k + rank)
        items[key] = item
    for rank, item in enumerate(bm25_results, 1):
        key = item["text"]
        if key not in scores:
            scores[key] = 0
            items[key] = item
        scores[key] += 1 / (k + rank)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [{**items[key], "score": round(score, 6)} for key, score in ranked]


class CrossEncoderReranker:
    """Optional cross-encoder reranker with safe fallback to lexical scoring."""

    def __init__(self) -> None:
        self._model = None
        self._failed = False

    def rerank(self, query: str, items: list[dict], limit: int = 3) -> list[dict]:
        if not items or self._failed:
            return items[:limit]
        try:
            if self._model is None:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder("BAAI/bge-reranker-base", local_files_only=True, max_length=512)
            scores = self._model.predict(
                [(query, item.get("text", "")) for item in items], show_progress_bar=False
            )
            ranked = sorted(zip(scores, items), key=lambda x: float(x[0]), reverse=True)
            return [item for _, item in ranked[:limit]]
        except Exception:
            self._failed = True
            terms = _query_terms(query)
            scored = [
                (sum(1 for t in terms if t in item.get("text", "").lower()), item)
                for item in items
            ]
            scored.sort(key=lambda x: x[0], reverse=True)
            return [item for _, item in scored[:limit]]


reranker = CrossEncoderReranker()


def _relevance_from_distance(distance: float | None) -> float:
    """归一化相关性分数：Chroma L2 平方距离 → [0,1]，distance 为 None 时视为 0。"""
    if distance is None:
        return 0.0
    return max(0.0, 1.0 - float(distance) / 2.0)


def _combined_relevance(query: str, results: list[dict[str, Any]]) -> float:
    # 关键词命中的块没有向量距离，若只看 distance 会把商品问答误判成低相关去审核
    vector_rel = 0.0
    lexical = 0.0
    for item in results:
        if item.get("distance") is not None:
            vector_rel = max(vector_rel, _relevance_from_distance(item.get("distance")))
        ks = keyword_score(query, item.get("text", ""))
        if ks > 0:
            lexical = max(lexical, min(0.85, 0.4 + ks / 50.0))
    return max(vector_rel, lexical)


async def hybrid_search(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Hybrid retrieval: vector search + BM25 + RRF fusion + optional reranker."""
    vector_results = await search_knowledge_with_distances(query, top_k=30)
    all_chunks = _load_knowledge_chunks() + [
        {"text": c["content"], "source": c.get("document_id", "ingested")}
        for c in ingestion_service.ready_chunks()
    ]
    bm25_results = _bm25_score(query, all_chunks, limit=30)
    fused = _rrf_fuse(vector_results, bm25_results)
    if not fused:
        return []
    return reranker.rerank(query, fused, limit=top_k)


async def hybrid_search_with_answer(query: str, top_k: int = 3) -> tuple[str, list[dict], float]:
    """Retrieve evidence and generate an evidence-based answer."""
    results = await hybrid_search(query, top_k=top_k)
    if not results:
        return "暂时没有相关内容。", [], 0.0
    relevance_score = _combined_relevance(query, results)
    citations = [
        {"source": item.get("source", "unknown"), "text": item.get("text", ""), "score": item.get("score")}
        for item in results
    ]
    # 检索只抽证据，口语回复交给最后一轮润色，避免连打两次大模型
    terms = _query_terms(query)
    candidates: list[tuple[float, str]] = []
    for item in results:
        text = re.sub(r"\[\d+\]", "", item.get("text", "")).strip()
        for sentence in re.split(r"(?<=[。！？.!?])\s*|\n+", text):
            sentence = re.sub(r"^#{1,6}\s*", "", sentence).strip(" -")
            if len(sentence) >= 6:
                if sentence.startswith("问：") or sentence.endswith("？") or sentence.endswith("?"):
                    continue
                score = sum(1 for t in terms if t in sentence.lower())
                if any(word in query for word in ("多少钱", "价格", "售价")) and any(
                    word in sentence for word in ("售价", "价格", "元")
                ):
                    score += 3
                candidates.append((score, sentence))
    if not candidates:
        return "暂时没有相关内容。", citations, relevance_score
    selected: list[str] = []
    for _, sentence in sorted(candidates, key=lambda x: x[0], reverse=True):
        if sentence not in selected:
            selected.append(sentence[:240])
        if len(selected) == 3:
            break
    answer = " ".join(selected)
    return answer, citations, relevance_score
