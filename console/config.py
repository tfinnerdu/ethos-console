import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    ETHOS_API_KEY = os.environ.get("ETHOS_API_KEY", "")
    ETHOS_GRAPHQL_API_KEY = os.environ.get("ETHOS_GRAPHQL_API_KEY", "")
    ETHOS_BASE_URL = os.environ.get("ETHOS_BASE_URL", "https://integrate.elluciancloud.com")
    CONDUCTOR_API_KEY = os.environ.get("CONDUCTOR_API_KEY", "")
    CONDUCTOR_URL = os.environ.get("CONDUCTOR_URL", "")
    UNIDATA_CONN_STR = os.environ.get("UNIDATA_CONN_STR", "")
    COLLEAGUE_WEB_API_URL = os.environ.get("COLLEAGUE_WEB_API_URL", "")
    COLLEAGUE_WEB_API_USER = os.environ.get("COLLEAGUE_WEB_API_USER", "")
    COLLEAGUE_WEB_API_PASS = os.environ.get("COLLEAGUE_WEB_API_PASS", "")
    UNIDATA_HOST = os.environ.get("UNIDATA_HOST", "")
    UNIDATA_PORT = int(os.environ.get("UNIDATA_PORT", "31438"))
    UNIDATA_USER = os.environ.get("UNIDATA_USER", "")
    UNIDATA_PASSWORD = os.environ.get("UNIDATA_PASSWORD", "")
    UNIDATA_ACCOUNT = os.environ.get("UNIDATA_ACCOUNT", "")
    CONSOLE_KEY = os.environ.get("CONSOLE_KEY", "")
    BUS_POLL_INTERVAL = int(os.environ.get("BUS_POLL_INTERVAL", "2"))
    SILENCE_THRESHOLD_MINUTES = int(os.environ.get("SILENCE_THRESHOLD_MINUTES", "30"))
    ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "")
    ALERT_ERROR_THRESHOLD = int(os.environ.get("ALERT_ERROR_THRESHOLD", "10"))
    CONSOLE_MOCK_MODE = os.environ.get("CONSOLE_MOCK_MODE", "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    ETHOS_ENVIRONMENTS = [
        {
            "name": os.environ.get(f"ETHOS_ENV_{i}_NAME", ""),
            "url": os.environ.get(f"ETHOS_ENV_{i}_URL", "https://integrate.elluciancloud.com"),
            "key": os.environ.get(f"ETHOS_ENV_{i}_KEY", ""),
        }
        for i in range(1, 6)
        if os.environ.get(f"ETHOS_ENV_{i}_NAME") and os.environ.get(f"ETHOS_ENV_{i}_KEY")
    ]
    DEFAULT_ENV = os.environ.get("DEFAULT_ENV", "").strip()

    _db_url = os.environ.get("DATABASE_URL", "")
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url or "sqlite:///ethos_console.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    DEBUG = True
    ENV = "development"

class ProductionConfig(Config):
    DEBUG = False
    ENV = "production"

config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
