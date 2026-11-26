"""Group, join-request approval, group-post, and community discovery routes."""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_current_user
from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.group import (
    GroupCreate,
    GroupResponse,
    GroupSuggestionResponse,
)
from backend.app.schemas.post import PostCreate, PostResponse
from backend.app.services.group_service import GroupService

router = APIRouter(tags=["groups"])


@router.get("/groups/suggestions", response_model=list[GroupSuggestionResponse])
def get_group_suggestions(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GroupService(db).get_suggestions(current_user.id, limit=limit)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/groups", response_model=list[GroupResponse])
def list_groups(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GroupService(db).list_groups(current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/groups", response_model=GroupResponse, status_code=201)
def create_group(
    payload: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GroupService(db).create_group(current_user.id, payload)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/groups/{group_id}", response_model=GroupResponse)
def get_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GroupService(db).get_group(current_user.id, group_id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/groups/{group_id}/join", response_model=GroupResponse)
def join_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GroupService(db).join_group(current_user.id, group_id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.delete("/groups/{group_id}/leave")
def leave_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        GroupService(db).leave_group(current_user.id, group_id)
        return {"status": "left"}
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/groups/{group_id}/join-requests")
def list_group_join_requests(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GroupService(db).list_pending_requests(current_user.id, group_id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/groups/{group_id}/join-requests/{target_user_id}/approve")
def approve_group_join_request(
    group_id: int,
    target_user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GroupService(db).review_join_request(
            current_user.id, group_id, target_user_id, approve=True
        )
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/groups/{group_id}/join-requests/{target_user_id}/reject")
def reject_group_join_request(
    group_id: int,
    target_user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GroupService(db).review_join_request(
            current_user.id, group_id, target_user_id, approve=False
        )
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/groups/{group_id}/posts", response_model=PostResponse, status_code=201)
def create_group_post(
    group_id: int,
    payload: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GroupService(db).create_group_post(current_user.id, group_id, payload)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/groups/{group_id}/feed", response_model=list[PostResponse])
def get_group_feed(
    group_id: int,
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return GroupService(db).get_group_feed(current_user.id, group_id, limit=limit)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )
