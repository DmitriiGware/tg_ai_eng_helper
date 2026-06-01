from sqlalchemy import Column, Integer, String
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
