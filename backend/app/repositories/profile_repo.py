"""Profile and skills repository."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.models.profile import Profile
from backend.app.models.skill import Skill, UserSkill
from backend.app.models.user import User


class ProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: int) -> Profile | None:
        return self.db.query(Profile).filter(Profile.user_id == user_id).first()

    def update(self, user_id: int, **kwargs) -> Profile | None:
        profile = self.get_by_user_id(user_id)
        if profile is None:
            return None
        allowed_fields = {"display_name", "programme", "degree_level", "year", "bio", "visibility", "avatar_filename"}
        for key, value in kwargs.items():
            if key in allowed_fields and value is not None:
                setattr(profile, key, value)
        profile.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def set_skills(self, user_id: int, skill_names: list[str]) -> list[str]:
        self.db.query(UserSkill).filter(UserSkill.user_id == user_id).delete()

        seen: set[str] = set()
        result_names: list[str] = []
        for raw_name in skill_names:
            clean = raw_name.strip()
            if not clean:
                continue
            normalized = clean.lower()
            if normalized in seen:
                continue
            seen.add(normalized)

            skill = (
                self.db.query(Skill)
                .filter(Skill.name_normalized == normalized)
                .first()
            )
            if skill is None:
                skill = Skill(name=clean, name_normalized=normalized)
                self.db.add(skill)
                self.db.flush()

            self.db.add(UserSkill(user_id=user_id, skill_id=skill.id))
            result_names.append(skill.name)

        self.db.commit()
        return result_names

    def get_skills(self, user_id: int) -> list[str]:
        rows = (
            self.db.query(Skill.name)
            .join(UserSkill, UserSkill.skill_id == Skill.id)
            .filter(UserSkill.user_id == user_id)
            .order_by(Skill.name.asc())
            .all()
        )
        return [row[0] for row in rows]

    def get_username_map(self, user_ids: list[int] | None = None) -> dict[int, str]:
        query = self.db.query(User.id, User.username).filter(User.status == "active")
        if user_ids is not None:
            if not user_ids:
                return {}
            query = query.filter(User.id.in_(user_ids))
        return {uid: uname for uid, uname in query.all()}

    def get_display_name_map(self, user_ids: list[int] | None = None) -> dict[int, str]:
        query = (
            self.db.query(Profile.user_id, Profile.display_name)
            .join(User, User.id == Profile.user_id)
            .filter(User.status == "active")
        )
        if user_ids is not None:
            if not user_ids:
                return {}
            query = query.filter(Profile.user_id.in_(user_ids))
        return {uid: dname for uid, dname in query.all()}
