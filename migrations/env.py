import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context

from skyframe import create_app
from skyframe.extensions import db

config = context.config
ini_path = Path(config.config_file_name or "alembic.ini")
if not ini_path.exists():
    ini_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    config.config_file_name = str(ini_path)
fileConfig(ini_path)

app = create_app(os.getenv("FLASK_ENV", "default"))
with app.app_context():
    config.set_main_option("sqlalchemy.url", app.config["SQLALCHEMY_DATABASE_URI"])
    target_metadata = db.metadata

    def run_migrations_offline():
        url = config.get_main_option("sqlalchemy.url")
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()

    def run_migrations_online():
        connectable = db.engine
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()

    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
