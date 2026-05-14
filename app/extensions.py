from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from celery import Celery
from celery.schedules import crontab

db = SQLAlchemy()
migrate = Migrate()

celery = Celery(__name__)


def celery_init_app(app):
    celery.conf.broker_url = app.config["CELERY_BROKER_URL"]
    celery.conf.result_backend = app.config["CELERY_RESULT_BACKEND"]
    celery.conf.include = [
        "app.tasks.fetch", "app.tasks.analyze", "app.tasks.backtest",
        "app.tasks.articles", "app.tasks.report", "app.tasks.trends",
        "app.tasks.maintenance", "app.tasks.tickerbets",
    ]
    celery.conf.task_default_queue = "celery"
    celery.conf.task_routes = {
        "app.tasks.maintenance.*": {"queue": "backfill"},
        "app.tasks.chat.*": {"queue": "user"},
        "app.tasks.analyze.run_company_prediction": {"queue": "user"},
        "app.tasks.tickerbets.train_tickerbets": {"queue": "backfill"},
    }
    celery.conf.beat_schedule = {
        "fetch-market-data": {
            "task": "app.tasks.fetch.fetch_market_data",
            "schedule": 900.0,  # every 15 minutes
        },
        "fetch-news": {
            "task": "app.tasks.fetch.fetch_news",
            "schedule": 900.0,  # every 15 minutes
        },
        "fetch-insider-trades": {
            "task": "app.tasks.fetch.fetch_insider_trades",
            "schedule": 21600.0,  # every 6 hours
        },
        "fetch-fundamentals": {
            "task": "app.tasks.fetch.fetch_fundamentals",
            "schedule": 86400.0,  # daily
        },
        "run-signal-analysis": {
            "task": "app.tasks.analyze.run_signal_analysis",
            "schedule": 900.0,  # every 15 minutes
        },
        "generate-report": {
            "task": "app.tasks.report.generate_report",
            "schedule": 900.0,  # every 15 minutes
        },
        "generate-trends": {
            "task": "app.tasks.trends.generate_trends",
            "schedule": 900.0,  # every 15 minutes
        },
        "check-backtest-windows": {
            "task": "app.tasks.backtest.check_backtest_windows",
            "schedule": 1800.0,  # every 30 minutes
        },
        "train-tickerbets-midnight": {
            "task": "app.tasks.tickerbets.train_tickerbets",
            "schedule": crontab(minute=0, hour=0),  # daily UTC midnight
        },
    }
    celery.conf.timezone = "UTC"

    class FlaskTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskTask
    return celery
