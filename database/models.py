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
