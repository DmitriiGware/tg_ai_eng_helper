import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def resolve_database_url() -> str:
    direct_url = (os.getenv("DATABASE_URL") or "").strip()
    if direct_url:
        return direct_url

    raw_path = (os.getenv("DATABASE_PATH") or "").strip()
    db_path = Path(raw_path) if raw_path else PROJECT_ROOT / "bot.db"
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"


DATABASE_URL = resolve_database_url()

engine = create_engine(DATABASE_URL, echo=False)
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

        if "weekly_stats_key" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN weekly_stats_key VARCHAR DEFAULT ''"
            )

        if "weekly_roadmap_topics_done" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN weekly_roadmap_topics_done INTEGER DEFAULT 0"
            )

        if "weekly_practice_sessions" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN weekly_practice_sessions INTEGER DEFAULT 0"
            )

        if "weekly_mistake_training_sessions" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN weekly_mistake_training_sessions INTEGER DEFAULT 0"
            )

        if "weekly_chat_sessions" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN weekly_chat_sessions INTEGER DEFAULT 0"
            )

        if "weekly_ai_explanations" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN weekly_ai_explanations INTEGER DEFAULT 0"
            )

        if "weekly_ai_summaries" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN weekly_ai_summaries INTEGER DEFAULT 0"
            )

        if "weekly_ai_quizzes" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN weekly_ai_quizzes INTEGER DEFAULT 0"
            )

        if "weekly_vocab_review_checked" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN weekly_vocab_review_checked INTEGER DEFAULT 0"
            )

        if "weekly_vocab_review_correct" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN weekly_vocab_review_correct INTEGER DEFAULT 0"
            )

        if "last_weekly_report_sent_date" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN last_weekly_report_sent_date VARCHAR DEFAULT ''"
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

        if "last_yookassa_payment_id" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN last_yookassa_payment_id VARCHAR DEFAULT ''"
            )

        if "last_telegram_payment_charge_id" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN last_telegram_payment_charge_id VARCHAR DEFAULT ''"
            )
