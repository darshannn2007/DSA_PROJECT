"""Profile service."""
from sqlalchemy.orm import Session

from backend.app.core.errors import ForbiddenError, NotFoundError
from backend.app.models.profile import Profile
from backend.app.models.user import User
from backend.app.repositories.connection_repo import ConnectionRepository
from backend.app.repositories.moderation_repo import ModerationRepository
from backend.app.repositories.profile_repo import ProfileRepository
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.profile import ProfileResponse, ProfileSummary, ProfileUpdate


def _media_url(filename: str | None) -> str | None:
    return f"/api/v1/media/{filename}" if filename else None


class ProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.profile_repo = ProfileRepository(db)
        self.connection_repo = ConnectionRepository(db)
        self.mod_repo = ModerationRepository(db)

    def get_profile(
        self, user_id: int, viewer_id: int | None = None
    ) -> ProfileResponse:
        user = self.user_repo.get_by_id(user_id)
        if user is None or user.status != "active":
            raise NotFoundError("User not found")

        profile = self.profile_repo.get_by_user_id(user_id)
        if profile is None:
            raise NotFoundError("Profile not found")

        skills = self.profile_repo.get_skills(user_id)
        is_blocked = False
        if viewer_id is None:
            is_connected, connection_status = False, None
        else:
            is_blocked = self.mod_repo.get_block(viewer_id, user_id) is not None
            if viewer_id != user_id and user_id in self.mod_repo.get_blocked_ids_for_user(viewer_id):
                if not is_blocked:
                    raise ForbiddenError("Profile is unavailable")
            is_connected, connection_status = (
                self.connection_repo.get_connection_status(viewer_id, user_id)
            )

        # Enforce connections-only profile visibility
        if (
            profile.visibility == "connections"
            and viewer_id != user_id
            and not is_connected
        ):
            return ProfileResponse(
                user_id=user.id,
                username=user.username,
                display_name=profile.display_name,
                programme="",
                degree_level=profile.degree_level,
                year=profile.year,
                bio="This profile is visible to connections only.",
                skills=[],
                visibility=profile.visibility,
                avatar_url=_media_url(profile.avatar_filename),
                is_connected=is_connected,
                connection_status=connection_status,
                is_blocked=is_blocked,
            )

        return ProfileResponse(
            user_id=user.id,
            username=user.username,
            display_name=profile.display_name,
            programme=profile.programme,
            degree_level=profile.degree_level,
            year=profile.year,
            bio=profile.bio,
            skills=skills,
            visibility=profile.visibility,
            avatar_url=_media_url(profile.avatar_filename),
            is_connected=is_connected,
            connection_status=connection_status,
            is_blocked=is_blocked,
        )

    def get_profile_by_username(
        self, username: str, viewer_id: int | None = None
    ) -> ProfileResponse:
        user = self.user_repo.get_by_username(username)
        if user is None or user.status != "active":
            raise NotFoundError("User not found")
        return self.get_profile(user.id, viewer_id=viewer_id)

    def update_profile(self, user_id: int, data: ProfileUpdate) -> ProfileResponse:
        user = self.user_repo.get_by_id(user_id)
        if user is None or user.status != "active":
            raise NotFoundError("User not found")

        profile = self.profile_repo.get_by_user_id(user_id)
        if profile is None:
            raise NotFoundError("Profile not found")

        new_level = data.degree_level or profile.degree_level
        new_year = data.year
        if new_year is None and new_level == "PG" and profile.year > 2:
            new_year = 2

        self.profile_repo.update(
            user_id,
            display_name=data.display_name,
            programme=data.programme,
            degree_level=data.degree_level,
            year=new_year,
            bio=data.bio,
            visibility=data.visibility,
        )
        if data.skills is not None:
            self.profile_repo.set_skills(user_id, data.skills)

        return self.get_profile(user_id, viewer_id=user_id)

    def get_profile_summary(self, user_id: int) -> ProfileSummary:
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        profile = self.profile_repo.get_by_user_id(user_id)
        return ProfileSummary(
            user_id=user.id,
            username=user.username,
            display_name=profile.display_name if profile else user.username,
            programme=profile.programme if profile else "",
            degree_level=profile.degree_level if profile else "UG",
            year=profile.year if profile else 1,
            avatar_url=_media_url(profile.avatar_filename) if profile else None,
        )

    def get_multiple_summaries(
        self, user_ids: list[int]
    ) -> dict[int, ProfileSummary]:
        if not user_ids:
            return {}
        unique_ids = list(set(user_ids))
        rows = (
            self.db.query(User, Profile)
            .outerjoin(Profile, Profile.user_id == User.id)
            .filter(User.id.in_(unique_ids))
            .all()
        )
        summaries: dict[int, ProfileSummary] = {}
        for user, profile in rows:
            summaries[user.id] = ProfileSummary(
                user_id=user.id,
                username=user.username,
                display_name=profile.display_name if profile else user.username,
                programme=profile.programme if profile else "",
                degree_level=profile.degree_level if profile else "UG",
                year=profile.year if profile else 1,
                avatar_url=_media_url(profile.avatar_filename) if profile else None,
            )
        return summaries
