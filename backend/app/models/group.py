"""Group and GroupMember ORM models."""
import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from backend.app.db.database import Base


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False, default="")
    visibility = Column(String(20), nullable=False, default="campus")  # campus | private
    membership_policy = Column(String(20), nullable=False, default="open")  # open | request | invite
    created_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))


class GroupMember(Base):
    __tablename__ = "group_members"
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role = Column(String(20), nullable=False, default="member")  # owner | moderator | member
    status = Column(String(20), nullable=False, default="active")  # active | pending
    joined_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))


class GroupPost(Base):
    __tablename__ = "group_posts"
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
