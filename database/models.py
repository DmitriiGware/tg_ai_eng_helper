from sqlalchemy import Column, Integer, String, Text
from database.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key = True)
    telegram_id = Column(Integer, unique = True)
    name = Column(String)
    birthday = Column(String)
    frequency = Column(String)
    level = Column(String, default="A1")
    current_topic_index = Column(Integer, default=0)
    roadmap_review_index = Column(Integer, default=0)
    last_result = Column(String, default="")
    words_per_day = Column(Integer, nullable=True)
    last_vocab_sent_date = Column(String, default="")
    last_mistake_sent_date = Column(String, default="")
    irregular_verbs_enabled = Column(Integer, default=0)
    last_irregular_verbs_sent_date = Column(String, default="")
    timezone_offset = Column(String, default="+03:00")
    vocab_hour = Column(Integer, default=10)
    mistake_hour = Column(Integer, default=18)
    irregular_verbs_hour = Column(Integer, default=19)
    premium_until = Column(String, default="")
    ai_requests_date = Column(String, default="")
    ai_requests_count = Column(Integer, default=0)
    pending_yookassa_payment_id = Column(String, default="")
    pending_yookassa_payment_url = Column(String, default="")
    last_telegram_payment_charge_id = Column(String, default="")


class VocabWord(Base):
    __tablename__ = "vocab_words"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, index=True)
    level = Column(String)
    word = Column(String, index=True)
    translation = Column(String)
    example = Column(String)
    example_translation = Column(String)
    sent_date = Column(String)


class IrregularVerbHistory(Base):
    __tablename__ = "irregular_verb_history"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, index=True)
    base_form = Column(String, index=True)
    sent_date = Column(String)


class RoadmapLessonCache(Base):
    __tablename__ = "roadmap_lesson_cache"

    id = Column(Integer, primary_key=True)
    cache_key = Column(String, unique=True, index=True)
    level = Column(String, index=True)
    topic = Column(String, index=True)
    lesson_type = Column(String, default="topic")
    simplify = Column(Integer, default=0)
    content = Column(Text)
    created_at = Column(String, default="")
    last_used_at = Column(String, default="")
    use_count = Column(Integer, default=0)


class UserMistake(Base):
    __tablename__ = "user_mistakes"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, index=True)
    level = Column(String, index=True)
    source = Column(String, default="")
    topic = Column(String, index=True)
    question = Column(Text)
    options = Column(Text, default="")
    correct_answer = Column(Text, default="")
    explanation = Column(Text, default="")
    status = Column(String, default="active")
    seen_count = Column(Integer, default=0)
    correct_streak = Column(Integer, default=0)
    created_at = Column(String, default="")
    last_seen_at = Column(String, default="")
