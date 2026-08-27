import pytest

from app.core.product_knowledge import build_product_knowledge_markdown
from app.data import showcase
from app.rag.store import get_collection, search_knowledge


@pytest.mark.asyncio
async def test_knowledge_base_loads_non_empty():
    collection = get_collection()
    assert collection.count() > 0


@pytest.mark.asyncio
async def test_search_returns_source():
    results = await search_knowledge("柱头灯 怎么安装")
    assert results
    assert "text" in results[0]
    assert results[0]["source"]


def test_product_knowledge_includes_live_catalog():
    markdown = build_product_knowledge_markdown(list(showcase.PRODUCTS))
    assert "店铺商品总览" in markdown
    assert "太阳能柱头灯" in markdown
    assert "售价 350 元" in markdown
    assert "户外壁灯" in markdown


def test_knowledge_texts_exclude_non_lighting_products():
    from pathlib import Path

    from app.core.product_knowledge import GENERIC_FAQ, build_product_knowledge_markdown

    markdown = build_product_knowledge_markdown(list(showcase.PRODUCTS))
    policies = (Path(__file__).resolve().parents[1] / "app" / "data" / "knowledge" / "policies.md").read_text(
        encoding="utf-8"
    )
    banned = ("耳机", "手环", "充电器", "音箱", "榨汁", "保温杯", "充电宝", "收纳架")
    for word in banned:
        assert word not in markdown
        assert word not in GENERIC_FAQ
        assert word not in policies


@pytest.mark.asyncio
async def test_search_product_price_hits_catalog():
    results = await search_knowledge("柱头灯多少钱")
    assert results
    joined = "\n".join(item["text"] for item in results)
    assert "售价" in joined
    assert "柱头灯" in joined


@pytest.mark.asyncio
async def test_hybrid_answer_mentions_product_price():
    from app.core.hybrid_rag import hybrid_search_with_answer

    answer, citations, relevance = await hybrid_search_with_answer("柱头灯多少钱")
    assert citations
    assert relevance >= 0.1
    assert "售价" in answer or "350" in answer or "元" in answer
    assert "知识库" not in answer


@pytest.mark.asyncio
async def test_hybrid_recommend_draft_strips_faq_markers():
    from app.core.hybrid_rag import hybrid_search_with_answer

    answer, citations, relevance = await hybrid_search_with_answer("给我推荐柱头灯")
    assert citations
    assert relevance >= 0.1
    assert "答：" not in answer
    assert "问：" not in answer


@pytest.mark.asyncio
async def test_hybrid_durability_uses_short_clerk_draft():
    from app.core.hybrid_rag import hybrid_search_with_answer

    answer, citations, relevance = await hybrid_search_with_answer("第一个耐用吗")
    assert citations
    assert relevance >= 0.1
    assert "售价" not in answer
    assert "P100" not in answer
    assert len(answer) < 80
    assert "防水" in answer or "户外" in answer


def test_hybrid_rag_module_does_not_bind_llm():
    from app.core import hybrid_rag

    assert not hasattr(hybrid_rag, "_llm_client")

