from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 全局应用与安全配置
    app_name: str = "doudian-agent"
    env: str = "development"
    secret_key: str = "please-change-me-to-a-long-random-string"
    jwt_expire_minutes: int = 480
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        alias="CORS_ORIGINS",
    )

    database_url: str = "sqlite+aiosqlite:///./doudian.db"
    redis_url: str = "redis://localhost:6379/0"
    chroma_persist_dir: str = "./chroma_data"
    chroma_url: str = ""

    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.2

    embedding_provider: str = "onnx"
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str = ""
    embedding_base_url: str = ""

    doudian_provider: str = "mock"
    doudian_app_key: str = ""
    doudian_app_secret: str = ""
    doudian_access_token: str = ""
    doudian_refresh_token: str = ""
    doudian_base_url: str = "https://openapi-fxg.jinritemai.com"

    # 低相关性回复审核阈值：RAG 检索相关性低于该值时草稿转人工审核
    relevance_threshold: float = 0.1

    admin_username: str = "admin"
    admin_password: str = "Admin@123456"
    staff_username: str = "staff"
    staff_password: str = "Staff@123456"
    customer_username: str = "customer"
    customer_password: str = "Customer@123"

    wechat_appid: str = "wxcecff699667444d5"
    wechat_secret: str = ""
    initial_wallet: float = 2000.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def cors_origins(self) -> list[str]:
        # 兼容逗号分隔的环境变量，返回允许跨域的源列表
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def jwt_secret(self) -> str:
        return self.secret_key

    @model_validator(mode="after")
    def _validate_production_secret_key(self) -> "Settings":
        # 生产环境必须通过环境变量设置强密钥，防止使用默认值签发 JWT
        if self.env == "production" and (
            not self.secret_key or self.secret_key == "please-change-me-to-a-long-random-string"
        ):
            raise ValueError(
                "SECRET_KEY 未设置或仍为默认值，生产环境必须配置强随机密钥，"
                "例如：python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def chroma_is_remote(self) -> bool:
        # 配置 CHROMA_URL 时使用独立 Chroma 服务，否则使用本地持久化目录
        return bool(self.chroma_url)


@lru_cache
def get_settings() -> Settings:
    # 进程内缓存配置，避免每次读取环境变量
    return Settings()


settings = get_settings()
