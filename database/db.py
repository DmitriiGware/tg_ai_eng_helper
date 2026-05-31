from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DB_PATH = Path(__file__).resolve().parent.parent / "bot.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(DATABASE_URL,echo=False)
SessionLocal = sessionmaker(bind = engine)

Base = declarative_base()


def ensure_user_progress_columns():
    with engine.begin() as conn:
        columns = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(users)")
        }

        if not columns:
            return

        if "current_topic_index" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN current_topic_index INTEGER DEFAULT 0"
            )

        if "last_result" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN last_result VARCHAR DEFAULT ''"
            )

        if "words_per_day" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN words_per_day INTEGER"
            )

        if "last_vocab_sent_date" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN last_vocab_sent_date VARCHAR DEFAULT ''"
            )

        if "premium_until" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN premium_until VARCHAR DEFAULT ''"
            )

        if "ai_requests_date" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN ai_requests_date VARCHAR DEFAULT ''"
            )

        if "ai_requests_count" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN ai_requests_count INTEGER DEFAULT 0"
            )

        if "pending_yookassa_payment_id" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN pending_yookassa_payment_id VARCHAR DEFAULT ''"
            )

        if "pending_yookassa_payment_url" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN pending_yookassa_payment_url VARCHAR DEFAULT ''"
            )

        if "last_telegram_payment_charge_id" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN last_telegram_payment_charge_id VARCHAR DEFAULT ''"
            )
