import pytest

from app.agent.graph import run_agent
from app.agent.llm import classify_intent
from app.core.grounding import check_grounding
from app.db import async_session_factory
from app.models import HumanTask
from sqlalchemy import select


@pytest.mark.asyncio
async def test_order_intent_returns_order_info():
    state = await run_agent([{"role": "user", "content": "查一下订单 1001"}], "1")
    assert state["intent"] == "order"
    assert "1001" in state["final_response"]
    assert state["tool_results"][0]["ok"] is True


@pytest.mark.asyncio
async def test_refund_creates_human_task():
    state = await run_agent([{"role": "user", "content": "我要退款，订单 1002"}], "1")
    assert state["needs_human"] is True
    assert state["human_task_id"]
    async with async_session_factory() as session:
        task = await session.get(HumanTask, state["human_task_id"])
        assert task is not None
        assert task.task_type == "refund"
        assert task.status == "pending"


def test_grounding_rejects_unverified_fact():
    state = {
        "final_response": "该商品库存 888 件，请放心购买。",
        "tool_results": [],
        "retrieved_chunks": [],
        "citations": [],
    }
    result = check_grounding(state)
    assert result["ok"] is False
    assert result["reason"]


def test_grounding_passes_verified_fact():
    state = {
        "final_response": "SKU001 当前库存 12 件。",
        "tool_results": [
            {
                "name": "get_inventory",
                "arguments": {"sku_id": "SKU001"},
                "ok": True,
                "data": 12,
                "error": None,
            }
        ],
        "retrieved_chunks": [],
        "citations": [],
    }
    result = check_grounding(state)
    assert result["ok"] is True


def test_shop_prompt_sounds_like_human_clerk():
    from app.agent.llm import _llm_prompt

    messages = _llm_prompt(
        {
            "messages": [{"role": "user", "content": "第一个耐用吗"}],
            "intent": "product",
            "retrieved_chunks": ["太阳能柱头灯 售价 110 元，IP65 防水，不锈钢灯体。"],
            "product_cards": [
                {"title": "太阳能柱头灯户外庭院中式别墅围墙立柱灯自动开关智能光控新中式", "price": 110}
            ],
            "tool_results": [],
            "memory_context": {"recent_messages": [], "workflow_state": {"last_product_title": "太阳能柱头灯"}},
        }
    )
    system = messages[0]["content"]
    user = messages[1]["content"]
    assert "知识库" not in system
    assert "详情页" not in system
    assert "往好处说" in system
    assert "店员" in system or "口语" in system
    assert "不要复述全称" in system
    assert "第一款" in user or "1." in user


@pytest.mark.asyncio
async def test_final_answer_strips_markdown_and_knowledge_base_talk(monkeypatch):
    from app.agent import llm
    from app.agent.nodes import final_answer

    original_provider = llm.settings.llm_provider
    original_key = llm.settings.llm_api_key
    llm.settings.llm_provider = "deepseek"
    llm.settings.llm_api_key = "test-key"
    try:
        class FakeResponse:
            content = "根据知识库：这款**很耐用**，售价 110 元。建议您查看商品详情页了解材质。"

        monkeypatch.setattr(llm.ChatOpenAI, "invoke", lambda self, messages: FakeResponse())
        result = await final_answer(
            {
                "messages": [{"role": "user", "content": "耐用吗"}],
                "intent": "product",
                "needs_human": False,
                "final_response": "草稿 110",
                "citations": [],
                "tool_results": [],
                "retrieved_chunks": ["太阳能柱头灯 售价 110 元，IP65 防水"],
                "human_task_id": None,
            }
        )
        text = result["final_response"]
        assert "知识库" not in text
        assert "详情页" not in text
        assert "**" not in text
        assert "110" in text
    finally:
        llm.settings.llm_provider = original_provider
        llm.settings.llm_api_key = original_key


def test_mock_mode_does_not_call_network(monkeypatch):
    from app.agent import llm

    def fail_network(*args, **kwargs):
        raise AssertionError("mock mode should not call the network")

    monkeypatch.setattr(llm.ChatOpenAI, "invoke", fail_network)
    assert classify_intent("查一下订单 1001") == "order"
    assert classify_intent("我要退款") == "refund"


@pytest.mark.asyncio
async def test_deepseek_generation_uses_llm(monkeypatch):
    from app.agent import llm
    from app.agent.nodes import final_answer

    original_provider = llm.settings.llm_provider
    original_key = llm.settings.llm_api_key
    llm.settings.llm_provider = "deepseek"
    llm.settings.llm_api_key = "test-key"
    try:
        class FakeResponse:
            content = "订单 1001 已支付，商品为太阳能柱头灯。"

        def fake_invoke(self, messages):
            assert isinstance(messages, list)
            return FakeResponse()

        monkeypatch.setattr(llm.ChatOpenAI, "invoke", fake_invoke)
        state = {
            "messages": [{"role": "user", "content": "查一下订单 1001"}],
            "intent": "order",
            "needs_human": False,
            "final_response": "规则草稿",
            "citations": [],
            "tool_results": [
                {
                    "name": "get_order",
                    "arguments": {"order_id": "1001"},
                    "ok": True,
                    "data": {
                        "order_id": "1001",
                        "status": "paid",
                        "product": "太阳能柱头灯",
                        "amount": 350.0,
                        "customer": "张三",
                    },
                    "error": None,
                }
            ],
            "retrieved_chunks": [],
            "human_task_id": None,
        }
        result = await final_answer(state)
        assert "1001" in result["final_response"]
        assert "已支付" in result["final_response"]
    finally:
        llm.settings.llm_provider = original_provider
        llm.settings.llm_api_key = original_key


def test_product_cards_include_showcase_fields():
    from app.agent.nodes import _build_product_cards

    cards = _build_product_cards("柱头灯多少钱")
    assert cards
    card = cards[0]
    assert card["product_id"]
    assert card["title"]
    assert card["cover"]
    assert card["category"]
    assert "subtitle" in card
    assert "original_price" in card
    assert "cover_color" in card


@pytest.mark.asyncio
async def test_product_query_attaches_cards():
    state = await run_agent([{"role": "user", "content": "柱头灯多少钱"}], "1")
    cards = state.get("product_cards") or []
    assert cards
    assert cards[0]["cover"]
    assert cards[0]["product_id"]


def test_product_cards_match_recommendation_query():
    from app.agent.nodes import _build_product_cards

    cards = _build_product_cards("给我推荐一个壁灯")
    assert cards
    assert any("壁灯" in card["title"] or "壁灯" in card.get("category", "") for card in cards)


@pytest.mark.asyncio
async def test_wall_lamp_recommendation_answers_with_cards():
    state = await run_agent([{"role": "user", "content": "给我推荐一个壁灯"}], "1")
    assert not state.get("needs_human")
    assert "转人工" not in (state.get("final_response") or "")
    cards = state.get("product_cards") or []
    assert cards
    assert any("壁灯" in card["title"] or "壁灯" in card.get("category", "") for card in cards)
    assert all(card.get("cover") for card in cards)


OFFTOPIC_ASK = "抱歉小助手无法理解您的意思，是否需要转人工"


@pytest.mark.asyncio
async def test_offtopic_asks_before_handoff():
    state = await run_agent(
        [{"role": "user", "content": "今天天气怎么样"}],
        "1",
        "test-offtopic-ask",
    )
    assert state["intent"] == "unknown"
    assert state.get("needs_human") is False
    assert state.get("human_task_id") in (None, "")
    assert OFFTOPIC_ASK in (state.get("final_response") or "")
    async with async_session_factory() as session:
        tasks = (await session.scalars(select(HumanTask))).all()
        assert not any("天气" in (task.payload_json or "") for task in tasks)


@pytest.mark.asyncio
async def test_offtopic_yes_transfers_to_human():
    session_id = "test-offtopic-yes"
    first = await run_agent(
        [{"role": "user", "content": "今天天气怎么样"}],
        "1",
        session_id,
    )
    assert first.get("needs_human") is False
    second = await run_agent(
        [{"role": "user", "content": "是的"}],
        "1",
        session_id,
    )
    assert second.get("needs_human") is True
    assert second.get("human_task_id")
    assert "转接人工" in (second.get("final_response") or "") or "转人工" in (second.get("final_response") or "")


@pytest.mark.asyncio
async def test_offtopic_no_keeps_self_service():
    session_id = "test-offtopic-no"
    first = await run_agent(
        [{"role": "user", "content": "今天股票怎么样"}],
        "1",
        session_id,
    )
    assert first.get("needs_human") is False
    second = await run_agent(
        [{"role": "user", "content": "不用"}],
        "1",
        session_id,
    )
    assert second.get("needs_human") is False
    assert second.get("human_task_id") in (None, "")
    assert "转接人工" not in (second.get("final_response") or "")


@pytest.mark.asyncio
async def test_direct_handoff_keyword():
    state = await run_agent([{"role": "user", "content": "转人工"}], "1")
    assert state.get("needs_human") is True
    assert state.get("human_task_id")


@pytest.mark.asyncio
async def test_business_hours_from_knowledge():
    state = await run_agent([{"role": "user", "content": "你们几点营业"}], "1")
    assert not state.get("needs_human")
    assert "9:00" in (state.get("final_response") or "") or "22:00" in (state.get("final_response") or "")


@pytest.mark.asyncio
async def test_return_policy_answered_from_knowledge():
    state = await run_agent([{"role": "user", "content": "退货流程是什么"}], "1")
    assert state["intent"] == "product"
    assert not state.get("needs_human")
    assert "退" in (state.get("final_response") or "")


@pytest.mark.asyncio
async def test_offtopic_then_product_follows_latest_question():
    session_id = "test-offtopic-then-product"
    first = await run_agent(
        [{"role": "user", "content": "今天天气怎么样"}],
        "1",
        session_id,
    )
    assert first.get("needs_human") is False
    second = await run_agent(
        [{"role": "user", "content": "我想了解太阳能柱头灯户外防水现代简约LED庭院灯"}],
        "1",
        session_id,
    )
    assert second.get("needs_human") is False
    assert OFFTOPIC_ASK not in (second.get("final_response") or "")
    assert "转接人工" not in (second.get("final_response") or "")
    assert second["intent"] == "product"
    cards = second.get("product_cards") or []
    assert cards
    assert any("柱头灯" in card["title"] or "柱头灯" in card.get("category", "") for card in cards)


@pytest.mark.asyncio
async def test_followup_uses_last_product_memory():
    session_id = "test-memory-followup"
    first = await run_agent(
        [{"role": "user", "content": "给我推荐一个壁灯"}],
        "1",
        session_id,
    )
    assert first["intent"] == "product"
    assert first.get("product_cards")
    second = await run_agent(
        [{"role": "user", "content": "多少钱"}],
        "1",
        session_id,
    )
    assert second["intent"] == "product"
    assert not second.get("needs_human")
    cards = second.get("product_cards") or []
    assert cards
    assert any("壁灯" in card["title"] or "壁灯" in card.get("category", "") for card in cards)


@pytest.mark.asyncio
async def test_recall_last_product():
    session_id = "test-memory-recall"
    await run_agent(
        [{"role": "user", "content": "给我推荐一个壁灯"}],
        "1",
        session_id,
    )
    state = await run_agent(
        [{"role": "user", "content": "还记得吗"}],
        "1",
        session_id,
    )
    assert "壁灯" in (state.get("final_response") or "")
    assert not state.get("needs_human")


@pytest.mark.asyncio
async def test_order_followup_reuses_last_order_id():
    session_id = "test-memory-order"
    first = await run_agent(
        [{"role": "user", "content": "查一下订单 1001"}],
        "1",
        session_id,
    )
    assert first["intent"] == "order"
    second = await run_agent(
        [{"role": "user", "content": "怎么样了"}],
        "1",
        session_id,
    )
    assert second["intent"] == "order"
    assert "1001" in (second.get("final_response") or "")
