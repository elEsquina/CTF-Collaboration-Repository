from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator
from .database import Base

def utcnow():
    return datetime.now(timezone.utc)

class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True
    def process_bind_param(self, value, dialect):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value else None
    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value else None

class Challenge(Base):
    __tablename__ = 'challenges'
    __table_args__ = {'sqlite_autoincrement': True}
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    flag: Mapped[str] = mapped_column(String(4096))
    category: Mapped[str] = mapped_column(String(40), index=True)
    requires_docker: Mapped[bool] = mapped_column(Boolean)
    folder_path: Mapped[str] = mapped_column(String(300))
    original_filename: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
