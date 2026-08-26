# 云托管会注入 PORT；未注入时默认 80，与控制台默认监听端口一致
import os

import uvicorn


def main() -> None:
    port = int(os.getenv("PORT", "80"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
