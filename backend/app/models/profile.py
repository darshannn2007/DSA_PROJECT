"""Profile ORM model."""
import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.db.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    display_name = Column(String(100), nullable=False, default="")
    programme = Column(String(100), nullable=False, default="")
    degree_level = Column(String(10), nullable=False, default="UG")
    year = Column(Integer, nullable=False, default=1)
    bio = Column(Text, nullable=False, default="")
    visibility = Column(String(20), nullable=False, default="campus")
    avatar_filename = Column(String(255), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    user = relationship("User", backref="profile", uselist=False)
