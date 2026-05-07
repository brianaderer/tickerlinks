from flask import Flask
from config import Config
from app.extensions import db, migrate, celery_init_app


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    celery_init_app(app)

    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    from app.cli import seed_command, process_backlog_command, backfill_prices_command
    app.cli.add_command(seed_command)
    app.cli.add_command(process_backlog_command)
    app.cli.add_command(backfill_prices_command)

    return app
