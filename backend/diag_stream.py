import asyncio

from app.agent.graph import run_agent
from app.agent.llm import generate_chat_response_stream
from app.config import settings


async def main() -> None:
    print(f"PROVIDER={settings.llm_provider} BASE={settings.llm_base_url} MODEL={settings.llm_model}", flush=True)
    state = await run_agent([{"role": "user", "content": "你好"}], "1", None, stream_final=True)
    print(
        f"INTENT={state.get('intent')} STREAM={state.get('stream_final')} "
        f"NEEDS={state.get('needs_human')} DRAFT={state.get('final_response', '')[:40]!r}",
        flush=True,
    )
    print("GEN_BEGIN", flush=True)
    n = 0
    collected = ""
    async for piece in generate_chat_response_stream(state):
        n += 1
        collected += piece
        if n <= 5:
            print(f"  PIECE {n}: {piece[:12]!r}", flush=True)
    print(f"GEN_END pieces={n} collected={collected[:50]!r}", flush=True)


asyncio.run(main())
print("DIAG_DONE", flush=True)
