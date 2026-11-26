"""Skill and UserSkill ORM models."""
import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from backend.app.db.database import Base


class Skill(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    name_normalized = Column(String(100), unique=True, nullable=False)


class UserSkill(Base):
    __tablename__ = "user_skills"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
