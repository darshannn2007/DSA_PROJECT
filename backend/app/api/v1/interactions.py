"""Post like and comment API routes."""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_current_user
from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.interaction import (
    CommentCreate,
    CommentResponse,
    LikeToggleResponse,
)
from backend.app.services.interaction_service import InteractionService

router = APIRouter(tags=["interactions"])


@router.post("/posts/{post_id}/like", response_model=LikeToggleResponse)
def toggle_post_like(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return InteractionService(db).toggle_like(current_user.id, post_id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/posts/{post_id}/comments", response_model=list[CommentResponse])
def list_post_comments(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return InteractionService(db).list_comments(current_user.id, post_id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=201)
def add_post_comment(
    post_id: int,
    payload: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return InteractionService(db).add_comment(current_user.id, post_id, payload)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        InteractionService(db).delete_comment(current_user.id, comment_id)
        return {"status": "deleted"}
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )
