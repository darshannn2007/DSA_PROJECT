"""PostLike and PostComment ORM models."""
import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Index
from backend.app.db.database import Base


class PostLike(Base):
    __tablename__ = "post_likes"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))


class PostComment(Base):
    __tablename__ = "post_comments"
    __table_args__ = (
        Index("ix_comments_post_created", "post_id", "created_at"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_comment_id = Column(Integer, ForeignKey("post_comments.id", ondelete="CASCADE"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    deleted_at = Column(DateTime, nullable=True)
