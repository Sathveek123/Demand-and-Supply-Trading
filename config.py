import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_IDS: str = "7168024869,1191689637"
    TELEGRAM_PROXY: str = os.getenv("TELEGRAM_PROXY", "")
    TELEGRAM_BASE_URL: str = os.getenv("TELEGRAM_BASE_URL", "https://api.telegram.org/bot")
    TELEGRAM_WEBHOOK_URL: str = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    
    # LLM Provider Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    USE_LLM_FORMATTER: bool = os.getenv("USE_LLM_FORMATTER", "True").lower() == "true"
    
    # Trading Strategy Settings
    DEFAULT_ASSETS: list[str] = ["BTC/USDT", "ETH/USDT", "XAUUSD", "EURUSD"]
    SL_BUFFER_PIPS: float = 3.0  # Buffer pips/points beyond OB wick
    
    # Server Settings
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
