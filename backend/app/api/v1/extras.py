"""Routes for UndoStack, user preferences, and privacy consent."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_current_user
from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.models.extras import ConsentRecord, UserPreference
from backend.app.models.user import User
from backend.app.services.undo_service import UndoService

router = APIRouter(tags=["account-extras"])


class PreferencesUpdate(BaseModel):
    theme: str | None = None
    reduced_motion: bool | None = None

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str | None) -> str | None:
        if v is not None and v not in ("system", "light", "dark"):
            raise ValueError("Theme must be system, light, or dark")
        return v


class ConsentCreate(BaseModel):
    policy_version: str = "1.3"
    analytics_allowed: bool = False


@router.post("/me/undo")
def undo_latest_action(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return UndoService(db).undo_latest(current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/me/preferences")
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if pref is None:
        return {"theme": "system", "reduced_motion": False}
    return {"theme": pref.theme, "reduced_motion": pref.reduced_motion}


@router.patch("/me/preferences")
def update_preferences(
    payload: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if pref is None:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)
    if payload.theme is not None:
        pref.theme = payload.theme
    if payload.reduced_motion is not None:
        pref.reduced_motion = payload.reduced_motion
    pref.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"theme": pref.theme, "reduced_motion": pref.reduced_motion}


@router.post("/me/consent", status_code=201)
def record_consent(
    payload: ConsentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rec = ConsentRecord(
        user_id=current_user.id,
        policy_version=payload.policy_version[:20],
        analytics_allowed=payload.analytics_allowed,
    )
    db.add(rec)
    db.commit()
    return {
        "policy_version": rec.policy_version,
        "essential": True,
        "analytics_allowed": rec.analytics_allowed,
        "recorded_at": rec.recorded_at,
    }
