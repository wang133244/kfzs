import os
import tempfile


_TMP_DIR = tempfile.mkdtemp(prefix="doudian_test_")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DIR}/test_doudian.db"  # 测试使用独立临时库，避免污染开发数据
os.environ["ENV"] = "test"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["DOUDIAN_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "onnx"
os.environ["CHROMA_PERSIST_DIR"] = os.path.join(_TMP_DIR, "chroma")
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    # 会话级初始化：建表 + 种子数据，测试结束后释放引擎
    from app.seed import init_db

    await init_db()
    yield
    from app.db import engine

    await engine.dispose()


@pytest.fixture(scope="session")
def api_client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        yield client
