"""Configuration settings for multi-agent market research application."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # API Keys
    ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
    TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
    TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
    TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GROK_API_KEY = os.getenv("GROK_API_KEY", "")

    # LLM Configuration
    # Strip inline comments that Docker env_file doesn't handle
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").split("#")[0].strip()
    LLM_MODEL = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022").split("#")[0].strip()
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # Agent Configuration
    AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "30"))  # seconds
    AGENT_MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "2"))
    FUNDAMENTALS_LLM_ENABLED = os.getenv("FUNDAMENTALS_LLM_ENABLED", "true").lower() == "true"
    MACRO_AGENT_ENABLED = os.getenv("MACRO_AGENT_ENABLED", "true").lower() == "true"
    OPTIONS_AGENT_ENABLED = os.getenv("OPTIONS_AGENT_ENABLED", "true").lower() == "true"
    SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    SCHEDULER_MIN_INTERVAL = int(os.getenv("SCHEDULER_MIN_INTERVAL", "30"))
    CATALYST_SCHEDULER_ENABLED = os.getenv("CATALYST_SCHEDULER_ENABLED", "true").lower() == "true"
    CATALYST_SOURCE = os.getenv("CATALYST_SOURCE", "earnings").split("#")[0].strip().lower()
    CATALYST_PRE_DAYS = int(os.getenv("CATALYST_PRE_DAYS", "1"))
    CATALYST_POST_DAYS = int(os.getenv("CATALYST_POST_DAYS", "1"))
    CATALYST_SCAN_INTERVAL_MINUTES = int(os.getenv("CATALYST_SCAN_INTERVAL_MINUTES", "60"))
    PORTFOLIO_ACTIONS_ENABLED = os.getenv("PORTFOLIO_ACTIONS_ENABLED", "true").lower() == "true"
    MACRO_CATALYSTS_ENABLED = os.getenv("MACRO_CATALYSTS_ENABLED", "true").lower() == "true"
    MACRO_CATALYST_PRE_DAYS = int(os.getenv("MACRO_CATALYST_PRE_DAYS", "1"))
    MACRO_CATALYST_DAY_ENABLED = os.getenv("MACRO_CATALYST_DAY_ENABLED", "true").lower() == "true"
    MACRO_CATALYST_EVENT_TYPES = [
        event.strip().lower()
        for event in os.getenv("MACRO_CATALYST_EVENT_TYPES", "fomc,cpi,nfp").split(",")
        if event.strip()
    ]
    CALIBRATION_ENABLED = os.getenv("CALIBRATION_ENABLED", "true").lower() == "true"
    CALIBRATION_TIMEZONE = os.getenv("CALIBRATION_TIMEZONE", "America/New_York").split("#")[0].strip()
    CALIBRATION_CRON_HOUR = int(os.getenv("CALIBRATION_CRON_HOUR", "17"))
    CALIBRATION_CRON_MINUTE = int(os.getenv("CALIBRATION_CRON_MINUTE", "30"))
    ALERTS_ENABLED = os.getenv("ALERTS_ENABLED", "true").lower() == "true"
    PARALLEL_AGENTS = os.getenv("PARALLEL_AGENTS", "true").lower() == "true"

    # Database Configuration
    DATABASE_PATH = os.getenv("DATABASE_PATH", "market_research.db")

    # SEC EDGAR Configuration
    SEC_EDGAR_USER_AGENT = os.getenv("SEC_EDGAR_USER_AGENT", "MarketResearch/1.0 (research@example.com)")
    SEC_EDGAR_BASE_URL = "https://data.sec.gov/api/xbrl"

    # API Endpoints
    ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
    NEWS_API_BASE_URL = "https://newsapi.org/v2"
    TWITTER_API_BASE_URL = "https://api.twitter.com/2"

    # Data Sources Configuration
    YFINANCE_TIMEOUT = int(os.getenv("YFINANCE_TIMEOUT", "10"))
    NEWS_LOOKBACK_DAYS = int(os.getenv("NEWS_LOOKBACK_DAYS", "7"))
    MAX_NEWS_ARTICLES = int(os.getenv("MAX_NEWS_ARTICLES", "20"))
    TWITTER_MAX_RESULTS = int(os.getenv("TWITTER_MAX_RESULTS", "50"))
    TWITTER_MIN_ENGAGEMENT = int(os.getenv("TWITTER_MIN_ENGAGEMENT", "0"))

    # Technical Analysis Configuration
    RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
    MACD_FAST = int(os.getenv("MACD_FAST", "12"))
    MACD_SLOW = int(os.getenv("MACD_SLOW", "26"))
    MACD_SIGNAL = int(os.getenv("MACD_SIGNAL", "9"))
    BB_PERIOD = int(os.getenv("BB_PERIOD", "20"))
    BB_STD = int(os.getenv("BB_STD", "2"))

    # Sentiment Analysis Configuration
    SENTIMENT_FACTORS = {
        "earnings": {
            "weight": 0.30,
            "description": "Earnings beats or misses"
        },
        "guidance": {
            "weight": 0.40,
            "description": "Forward guidance changes"
        },
        "stock_reactions": {
            "weight": 0.20,
            "description": "Stock price reactions to news"
        },
        "strategic_news": {
            "weight": 0.10,
            "description": "Strategic announcements and initiatives"
        }
    }

    # Cache TTL (Time-To-Live) in seconds
    CACHE_TTL_PRICE = int(os.getenv("CACHE_TTL_PRICE", "300"))  # 5 minutes
    CACHE_TTL_NEWS = int(os.getenv("CACHE_TTL_NEWS", "3600"))  # 1 hour
    CACHE_TTL_FUNDAMENTALS = int(os.getenv("CACHE_TTL_FUNDAMENTALS", "86400"))  # 1 day

    # API Rate Limiting (general)
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # 1 hour

    # Alpha Vantage Rate Limiting
    AV_RATE_LIMIT_PER_MINUTE = int(os.getenv("AV_RATE_LIMIT_PER_MINUTE", "5"))
    AV_RATE_LIMIT_PER_DAY = int(os.getenv("AV_RATE_LIMIT_PER_DAY", "25"))

    # FastAPI Configuration
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    API_RELOAD = os.getenv("API_RELOAD", "true").lower() == "true"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    @classmethod
    def validate_config(cls) -> bool:
        """
        Validate that required configuration is present.

        Returns:
            True if configuration is valid, False otherwise
        """
        required_keys = []

        # Check LLM API key based on provider
        valid_providers = ("anthropic", "openai", "xai")
        if cls.LLM_PROVIDER not in valid_providers:
            print(f"ERROR: Invalid LLM_PROVIDER '{cls.LLM_PROVIDER}'. Must be one of: {', '.join(valid_providers)}")
            print("Hint: Docker env_file does not strip inline comments. Remove comments from .env values.")
            return False

        if cls.LLM_PROVIDER == "anthropic":
            if not cls.ANTHROPIC_API_KEY:
                required_keys.append("ANTHROPIC_API_KEY")
        elif cls.LLM_PROVIDER == "openai":
            if not cls.OPENAI_API_KEY:
                required_keys.append("OPENAI_API_KEY")
        elif cls.LLM_PROVIDER == "xai":
            if not cls.GROK_API_KEY:
                required_keys.append("GROK_API_KEY")

        # Warn about missing optional keys
        optional_keys = []
        if not cls.ALPHA_VANTAGE_API_KEY:
            optional_keys.append("ALPHA_VANTAGE_API_KEY")
        if not cls.NEWS_API_KEY:
            optional_keys.append("NEWS_API_KEY")

        if required_keys:
            print(f"ERROR: Missing required configuration: {', '.join(required_keys)}")
            return False

        if optional_keys:
            print(f"WARNING: Missing optional configuration: {', '.join(optional_keys)}")
            print("Some features may be limited without these API keys.")

        return True

    @classmethod
    def get_llm_config(cls) -> dict:
        """
        Get LLM configuration as a dictionary.

        Returns:
            Dict with LLM settings
        """
        config = {
            "provider": cls.LLM_PROVIDER,
            "model": cls.LLM_MODEL,
            "temperature": cls.LLM_TEMPERATURE,
            "max_tokens": cls.LLM_MAX_TOKENS,
        }

        if cls.LLM_PROVIDER == "anthropic":
            config["api_key"] = cls.ANTHROPIC_API_KEY
        elif cls.LLM_PROVIDER == "xai":
            config["api_key"] = cls.GROK_API_KEY
            config["base_url"] = "https://api.x.ai/v1"
        else:
            config["api_key"] = cls.OPENAI_API_KEY

        return config


# User agent strings for web scraping (rotating for anti-detection)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0"
]
