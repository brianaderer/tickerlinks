import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://stocklynx:stocklynx@db:5432/stocklynx"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

    WATCHLIST_PATH = os.environ.get("WATCHLIST_PATH", "/app/watchlist.yaml")

    MARKET_FETCH_PERIOD = "1d"
    MARKET_FETCH_INTERVAL = "1h"
