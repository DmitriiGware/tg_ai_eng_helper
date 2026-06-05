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

        if "roadmap_review_index" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN roadmap_review_index INTEGER DEFAULT 0"
            )

        if "last_result" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN last_result VARCHAR DEFAULT ''"
            )

        if "streak_count" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN streak_count INTEGER DEFAULT 0"
            )

        if "streak_last_date" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN streak_last_date VARCHAR DEFAULT ''"
            )

        if "daily_goal_date" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN daily_goal_date VARCHAR DEFAULT ''"
            )

        if "daily_goal_errors_closed" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN daily_goal_errors_closed INTEGER DEFAULT 0"
            )

        if "daily_goal_topics_done" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN daily_goal_topics_done INTEGER DEFAULT 0"
            )

        if "roadmap_topics_completed_total" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN roadmap_topics_completed_total INTEGER DEFAULT 0"
            )

        if "practice_sessions_completed" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN practice_sessions_completed INTEGER DEFAULT 0"
            )

        if "mistake_training_sessions_completed" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN mistake_training_sessions_completed INTEGER DEFAULT 0"
            )

        if "chat_sessions_completed" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN chat_sessions_completed INTEGER DEFAULT 0"
            )

        if "ai_explanations_completed" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN ai_explanations_completed INTEGER DEFAULT 0"
            )

        if "ai_summaries_completed" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN ai_summaries_completed INTEGER DEFAULT 0"
            )

        if "ai_quizzes_completed" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN ai_quizzes_completed INTEGER DEFAULT 0"
            )

        if "vocab_review_checked_count" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN vocab_review_checked_count INTEGER DEFAULT 0"
            )

        if "vocab_review_correct_count" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN vocab_review_correct_count INTEGER DEFAULT 0"
            )

        if "words_per_day" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN words_per_day INTEGER"
            )

        if "last_vocab_sent_date" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN last_vocab_sent_date VARCHAR DEFAULT ''"
            )

        if "last_vocab_review_sent_date" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN last_vocab_review_sent_date VARCHAR DEFAULT ''"
            )

        if "last_mistake_sent_date" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN last_mistake_sent_date VARCHAR DEFAULT ''"
            )

        if "irregular_verbs_enabled" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN irregular_verbs_enabled INTEGER DEFAULT 0"
            )

        if "last_irregular_verbs_sent_date" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN last_irregular_verbs_sent_date VARCHAR DEFAULT ''"
            )

        if "timezone_offset" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN timezone_offset VARCHAR DEFAULT '+03:00'"
            )

        if "vocab_hour" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN vocab_hour INTEGER DEFAULT 10"
            )

        if "mistake_hour" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN mistake_hour INTEGER DEFAULT 18"
            )

        if "irregular_verbs_hour" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN irregular_verbs_hour INTEGER DEFAULT 19"
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
