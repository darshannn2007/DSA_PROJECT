"""Connection and ConnectionRequest ORM models."""
import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint
from backend.app.db.database import Base


class Connection(Base):
    __tablename__ = "connections"
    __table_args__ = (
        CheckConstraint("user_low_id < user_high_id", name="ck_canonical_order"),
    )
    user_low_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    user_high_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))


class ConnectionRequest(Base):
    __tablename__ = "connection_requests"
    __table_args__ = (
        CheckConstraint("sender_id != receiver_id", name="ck_no_self_request"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
