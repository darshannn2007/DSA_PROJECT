"""Profile API routes."""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_current_user, get_optional_user
from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.profile import ProfileResponse, ProfileUpdate
from backend.app.services.profile_service import ProfileService

router = APIRouter(tags=["profile"])


@router.get("/me/profile", response_model=ProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ProfileService(db).get_profile(
            current_user.id, viewer_id=current_user.id
        )
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.patch("/me/profile", response_model=ProfileResponse)
def update_my_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ProfileService(db).update_profile(current_user.id, payload)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/users/{username}", response_model=ProfileResponse)
def get_user_profile(
    username: str,
    viewer: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    try:
        viewer_id = viewer.id if viewer is not None else None
        return ProfileService(db).get_profile_by_username(
            username, viewer_id=viewer_id
        )
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )
