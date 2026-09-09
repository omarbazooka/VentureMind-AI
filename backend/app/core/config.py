from typing import Any
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str

    # SecretStr to avoid leaking API keys in logs.
    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    firecrawl_api_key: SecretStr | None = None

    # Browser/API integration. Keep origins explicit; never use a credentialed wildcard.
    cors_origins: str = "http://localhost:3000"

    # Supabase Auth Configuration
    supabase_url: str | None = None
    supabase_jwt_secret: SecretStr | None = None
    supabase_jwt_audience: str = "authenticated"
    enable_dev_auth_bypass: bool = False

    turn_understanding_model: str = "gemini-3.1-flash-lite"
    market_research_model: str = "gemini-3.5-flash-lite"
    competitor_intelligence_model: str = "gemini-3.5-flash-lite"
    customer_intelligence_model: str = "gemini-3.5-flash-lite"
    business_strategy_model: str = "gemini-3.5-flash-lite"
    finance_assumption_model: str = "gemini-3.5-flash-lite"
    risk_analysis_model: str = "gemini-3.5-flash-lite"

    # Fallback models used if requests/quota run out for primary models
    llm_fallback_models: list[str] | str = [
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash-lite",
    ]

    @field_validator("llm_fallback_models", mode="after")
    @classmethod
    def _parse_llm_fallback_models(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v_strip = v.strip()
            if v_strip.startswith("[") and v_strip.endswith("]"):
                import json
                try:
                    return json.loads(v_strip)
                except Exception:
                    pass
            return [m.strip() for m in v_strip.split(",") if m.strip()]
        return list(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
