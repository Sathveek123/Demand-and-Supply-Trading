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
    # XAUUSD dropped from auto-scan: evaluate.py's walk-forward out-of-sample test
    # (trained on first 70% of ~60d history, validated on the untouched last 30%)
    # showed negative expectancy for gold and a +13R/44% win rate/8.8 rating improvement
    # for BTC+ETH+EURUSD without it. Still reachable manually via /debug XAUUSD or the
    # GOLD button if you want to keep an eye on it.
    DEFAULT_ASSETS: list[str] = ["BTC/USDT", "ETH/USDT", "EURUSD"]
    SL_BUFFER_PIPS: float = 3.0  # Buffer pips/points beyond OB wick
    
    # Server Settings
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    # Public URL of this app — used by the keep-alive self-pinger.
    # Set RENDER_EXTERNAL_URL in Render env vars (it's auto-set by Render).
    # Falls back to the known Render deployment URL.
    RENDER_EXTERNAL_URL: str = os.getenv(
        "RENDER_EXTERNAL_URL",
        "https://demand-and-supply-trading.onrender.com"
    )

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
