"""Block, report, admin moderation, export, and account deletion routes."""
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_current_user
from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.moderation import ReportCreate, ReportResolve, ReportResponse
from backend.app.services.moderation_service import ModerationService

router = APIRouter(tags=["moderation"])


@router.post("/users/{username}/block")
def block_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        ModerationService(db).block_user(current_user.id, username)
        return {"status": "blocked"}
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.delete("/users/{username}/block")
def unblock_user(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        ModerationService(db).unblock_user(current_user.id, username)
        return {"status": "unblocked"}
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/reports", response_model=ReportResponse, status_code=201)
def create_report(
    payload: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ModerationService(db).create_report(current_user.id, payload)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/admin/reports", response_model=list[ReportResponse])
def list_reports(
    status: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ModerationService(db).list_reports(current_user, status=status)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/admin/reports/{report_id}/resolve", response_model=ReportResponse)
def resolve_report(
    report_id: int,
    payload: ReportResolve,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ModerationService(db).resolve_report(current_user, report_id, payload)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/me/export")
def export_my_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ModerationService(db).export_user_data(current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.delete("/me/account")
def delete_my_account(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        ModerationService(db).delete_account(current_user.id)
        response.delete_cookie(key="session_token", path="/")
        return {"status": "deleted"}
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )
