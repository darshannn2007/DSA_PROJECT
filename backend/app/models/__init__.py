"""Import all models so they register with Base.metadata."""
from backend.app.models.user import User
from backend.app.models.profile import Profile
from backend.app.models.skill import Skill, UserSkill
from backend.app.models.connection import Connection, ConnectionRequest
from backend.app.models.post import Post
from backend.app.models.session import UserSession
from backend.app.models.notification import Notification
from backend.app.models.interaction import PostLike, PostComment
from backend.app.models.group import Group, GroupMember, GroupPost
from backend.app.models.moderation import UserBlock, Report, PasswordResetToken
from backend.app.models.extras import (
    UndoActionRecord,
    UserPreference,
    ConsentRecord,
    SignupAttribution,
)

__all__ = [
    "User", "Profile", "Skill", "UserSkill",
    "Connection", "ConnectionRequest", "Post",
    "UserSession", "Notification",
    "PostLike", "PostComment",
    "Group", "GroupMember", "GroupPost",
    "UserBlock", "Report", "PasswordResetToken",
    "UndoActionRecord", "UserPreference", "ConsentRecord", "SignupAttribution",
]
