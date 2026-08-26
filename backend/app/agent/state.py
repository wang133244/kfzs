from typing import Literal, Optional, TypedDict


class ToolResult(TypedDict):
    # 工具统一返回结构，ok=False 表示调用失败且 error 为原因
    name: str
    arguments: dict
    ok: bool
    data: Optional[dict]
    error: Optional[str]


class AgentState(TypedDict):
    # LangGraph 状态机契约：字段与说明书 5.4 保持一致
    # 对话历史与用户标识
    messages: list[dict]
    user_id: str
    # 意图识别与从消息中提取的信息
    intent: Literal[
        "order",
        "product",
        "refund",
        "shipment",
        "inventory",
        "complaint",
        "smalltalk",
        "unknown",
    ]
    order_id: Optional[str]
    product_query: Optional[str]
    # 工具调用结果与知识库检索依据，供 Grounding 门禁和 LLM 引用
    tool_results: list[ToolResult]
    retrieved_chunks: list[str]
    citations: list[str]
    # 转人工相关状态
    needs_human: bool
    human_task_id: Optional[str]
    # 回复内容与迭代控制（超过 max_iterations 强制转人工）
    final_response: str
    iteration: int
    max_iterations: int
    # Grounding 门禁结果：None 表示尚未校验
    grounding_passed: Optional[bool]
    # 槽位抽取结果与路由决策
    slots: dict[str, str]
    missing_slots: list[str]
    action: str
    next_step: str
    reason_code: str
    # 会话记忆上下文
    session_id: Optional[str]
    memory_context: dict
    resolved_query: str
    # 售后预览
    after_sales_preview_id: Optional[str]
    # 引用详情（含 score、source_type）
    citations_detail: list[dict]
    # 安全校验
    safety_blocked: bool
    # RAG 归一化相关性分数（0-1），低于阈值时草稿转人工审核
    relevance_score: float
    # 客服回复附带的商品卡片（标题、价格、真实链接）
    product_cards: list[dict]
    # WS 流式推送开关：True 时 final_answer 跳过同步 LLM 润色，由 chat_ws 逐 token 推送
    stream_final: bool
