"""Post ORM model."""
import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from backend.app.db.database import Base


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_author_created", "author_id", "created_at"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body = Column(Text, nullable=False)
    image_filename = Column(String(255), nullable=True)
    visibility = Column(String(20), nullable=False, default="connections")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    deleted_at = Column(DateTime, nullable=True)
