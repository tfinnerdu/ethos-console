import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    ETHOS_API_KEY = os.environ.get("ETHOS_API_KEY", "")
    ETHOS_BASE_URL = os.environ.get("ETHOS_BASE_URL", "https://integrate.elluciancloud.com")
    CONDUCTOR_API_KEY = os.environ.get("CONDUCTOR_API_KEY", "")
    CONDUCTOR_URL = os.environ.get("CONDUCTOR_URL", "")
    CNM_BASE_URL = os.environ.get("CNM_BASE_URL", "")
    CNM_API_KEY = os.environ.get("CNM_API_KEY", "")
    UNIDATA_CONN_STR = os.environ.get("UNIDATA_CONN_STR", "")
    UNIDATA_HOST = os.environ.get("UNIDATA_HOST", "")
    UNIDATA_PORT = int(os.environ.get("UNIDATA_PORT", "31438"))
    UNIDATA_USER = os.environ.get("UNIDATA_USER", "")
    UNIDATA_PASSWORD = os.environ.get("UNIDATA_PASSWORD", "")
    UNIDATA_ACCOUNT = os.environ.get("UNIDATA_ACCOUNT", "")
    CONSOLE_KEY = os.environ.get("CONSOLE_KEY", "")
    BUS_POLL_INTERVAL = int(os.environ.get("BUS_POLL_INTERVAL", "2"))
    SILENCE_THRESHOLD_MINUTES = int(os.environ.get("SILENCE_THRESHOLD_MINUTES", "30"))

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
