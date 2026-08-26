import asyncio
import json

import httpx
import websockets

BASE = "http://localhost:8000"
WS = "ws://localhost:8000"


async def main() -> None:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE}/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123456"},
            timeout=10,
        )
        r.raise_for_status()
        token = r.json()["access_token"]
    print("LOGIN_OK", flush=True)

    uri = f"{WS}/api/v1/chat/ws?token={token}"
    async with websockets.connect(uri, max_size=None) as ws:
        await ws.send(json.dumps({"message": "你好", "session_id": None}))
        print("SENT 你好", flush=True)
        deltas = 0
        streamed = ""
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=45)
            except asyncio.TimeoutError:
                print(f"TIMEOUT deltas={deltas}", flush=True)
                break
            except websockets.ConnectionClosed as e:
                print(f"CLOSED {e}", flush=True)
                break
            data = json.loads(raw)
            t = data.get("type")
            if t == "final_delta":
                deltas += 1
                streamed += data.get("delta", "")
                if deltas <= 3:
                    print(f"  delta#{deltas}: {data.get('delta', '')[:12]!r}", flush=True)
            elif t == "final":
                print(f"FINAL deltas={deltas} resp={data.get('response', '')[:50]!r}", flush=True)
                print(f"STREAMED={streamed[:60]!r}", flush=True)
                break
            elif t == "error":
                print(f"ERROR {data.get('message')}", flush=True)
                break
            else:
                print(f"  EVT {t}", flush=True)


asyncio.run(main())
print("DONE", flush=True)
