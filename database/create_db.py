from database.db import engine
from database.models import Base

Base.metadata.create_all(bind=engine)

print("База данных создана ✅")