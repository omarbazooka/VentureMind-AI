from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str
    
    # SecretStr to don't leak the apis in logs 
    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    firecrawl_api_key: SecretStr | None = None

    turn_understanding_model: str = "gemini-3.1-flash-lite"
    market_research_model: str = "gemini-3.5-flash-lite"
    competitor_intelligence_model: str = "gemini-3.5-flash-lite"
    customer_intelligence_model: str = "gemini-3.5-flash-lite"
    business_strategy_model: str = "gemini-3.5-flash-lite"
    
    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding= "utf-8",
        extra="ignore",
    )

settings = Settings()
