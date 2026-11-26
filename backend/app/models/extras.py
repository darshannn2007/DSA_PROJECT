"""UndoActionRecord, UserPreference, ConsentRecord, and SignupAttribution ORM models."""
import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from backend.app.db.database import Base


class UndoActionRecord(Base):
    __tablename__ = "undo_actions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(40), nullable=False)  # e.g. restore_post
    target_type = Column(String(40), nullable=False)  # e.g. post
    target_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)


class UserPreference(Base):
    __tablename__ = "user_preferences"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    theme = Column(String(20), nullable=False, default="system")  # system | light | dark
    reduced_motion = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))


class ConsentRecord(Base):
    __tablename__ = "consent_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_version = Column(String(20), nullable=False, default="1.3")
    analytics_allowed = Column(Boolean, nullable=False, default=False)
    recorded_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))


class SignupAttribution(Base):
    __tablename__ = "signup_attribution"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    utm_source = Column(String(64), nullable=True)
    utm_medium = Column(String(64), nullable=True)
    utm_campaign = Column(String(64), nullable=True)
    utm_content = Column(String(64), nullable=True)
    consent_version = Column(String(20), nullable=False, default="1.3")
    captured_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
