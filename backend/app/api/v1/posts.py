"""Post and feed API routes."""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_current_user
from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.post import FeedResponse, PostCreate, PostResponse
from backend.app.services.post_service import PostService

router = APIRouter(tags=["posts"])


@router.post("/posts", response_model=PostResponse, status_code=201)
def create_post(
    payload: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return PostService(db).create_post(current_user.id, payload)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/me/posts", response_model=list[PostResponse])
def get_my_posts(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return PostService(db).get_user_posts(
            current_user.id, limit=limit, offset=offset
        )
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/users/{username}/posts", response_model=list[PostResponse])
def get_user_posts_by_username(
    username: str,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        from backend.app.services.profile_service import ProfileService
        profile = ProfileService(db).get_profile_by_username(
            username, viewer_id=current_user.id
        )
        if (
            profile.visibility == "connections"
            and profile.user_id != current_user.id
            and not profile.is_connected
        ):
            return []
        return PostService(db).get_user_posts(
            profile.user_id, limit=limit, offset=offset, viewer_id=current_user.id
        )
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        PostService(db).delete_post(post_id, current_user.id)
        return {"status": "deleted"}
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/feed", response_model=FeedResponse)
def get_feed(
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return PostService(db).get_feed(
            current_user.id, limit=limit, cursor=cursor
        )
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/feed/trending", response_model=list[PostResponse])
def get_trending_feed(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return PostService(db).get_trending_feed(current_user.id, limit=limit)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )
