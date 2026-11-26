"""Connection and graph API routes."""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_current_user
from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.connection import (
    ConnectionRequestResponse,
    ConnectionResponse,
    MutualConnectionsResponse,
    PathResponse,
    SuggestionResponse,
)
from backend.app.services.connection_service import ConnectionService

router = APIRouter(tags=["connections"])


# --- Connection Request Endpoints (match frontend JS) ---

class ConnectionRequestCreate(BaseModel):
    receiver_id: int | None = None
    username: str | None = None


@router.post(
    "/connections/requests",
    response_model=ConnectionRequestResponse,
    status_code=201,
)
def send_connection_request_body(
    payload: ConnectionRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a connection request. Body: {receiver_id: int} or {username: str}."""
    try:
        from backend.app.repositories.user_repo import UserRepository
        receiver_id = payload.receiver_id
        if receiver_id is None and payload.username:
            user_repo = UserRepository(db)
            target = user_repo.get_by_username(payload.username)
            if target:
                receiver_id = target.id
        if receiver_id is None:
            return JSONResponse(
                status_code=422,
                content={"code": "validation_error", "message": "receiver_id or username required"},
            )
        return ConnectionService(db).send_request(current_user.id, int(receiver_id))
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post(
    "/users/{user_id}/requests",
    response_model=ConnectionRequestResponse,
    status_code=201,
)
def send_connection_request(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).send_request(current_user.id, user_id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/connections/requests/incoming")
def get_incoming_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).get_incoming_requests(current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/connections/requests/outgoing")
def get_outgoing_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).get_outgoing_requests(current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/me/requests")
def get_my_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        service = ConnectionService(db)
        return {
            "incoming": service.get_incoming_requests(current_user.id),
            "outgoing": service.get_outgoing_requests(current_user.id),
        }
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/connections/requests/{request_id}/accept", response_model=ConnectionResponse)
def accept_connection_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).accept_request(request_id, current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/connections/requests/{request_id}/reject", response_model=ConnectionRequestResponse)
def reject_connection_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).reject_request(request_id, current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/connections/requests/{request_id}/cancel", response_model=ConnectionRequestResponse)
def cancel_connection_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).cancel_request(request_id, current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.delete("/connections/requests/{request_id}")
def delete_connection_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).cancel_request(request_id, current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


# --- Also keep legacy /requests/{id} routes ---

@router.post("/requests/{request_id}/accept", response_model=ConnectionResponse)
def accept_request_legacy(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).accept_request(request_id, current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/requests/{request_id}/reject", response_model=ConnectionRequestResponse)
def reject_request_legacy(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).reject_request(request_id, current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/requests/{request_id}/cancel", response_model=ConnectionRequestResponse)
def cancel_request_legacy(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).cancel_request(request_id, current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


# --- Connection Management ---

@router.delete("/connections/{user_id}")
def remove_connection(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        ConnectionService(db).remove_connection(current_user.id, user_id)
        return {"status": "removed"}
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/connections", response_model=list[ConnectionResponse])
def get_my_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).get_connections(current_user.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/users/{user_id}/connections", response_model=list[ConnectionResponse])
def get_user_connections(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).get_connections(user_id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


# --- Graph: Mutual Connections, Path, Suggestions ---

@router.get("/users/{username}/mutual")
def get_mutual_connections_by_username(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        from backend.app.repositories.user_repo import UserRepository
        user_repo = UserRepository(db)
        target = user_repo.get_by_username(username)
        if target is None:
            # Try as numeric ID
            try:
                target_id = int(username)
            except ValueError:
                return JSONResponse(
                    status_code=404,
                    content={"code": "not_found", "message": "User not found"},
                )
            else:
                return ConnectionService(db).get_mutual_connections(current_user.id, target_id)
        return ConnectionService(db).get_mutual_connections(current_user.id, target.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get(
    "/users/{user_id}/mutual-connections",
    response_model=MutualConnectionsResponse,
)
def get_mutual_connections(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).get_mutual_connections(current_user.id, user_id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/users/{username}/path")
def get_connection_path_by_username(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        from backend.app.repositories.user_repo import UserRepository
        user_repo = UserRepository(db)
        target = user_repo.get_by_username(username)
        if target is None:
            try:
                target_id = int(username)
            except ValueError:
                return JSONResponse(
                    status_code=404,
                    content={"code": "not_found", "message": "User not found"},
                )
            else:
                return ConnectionService(db).get_path(current_user.id, target_id)
        return ConnectionService(db).get_path(current_user.id, target.id)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/me/suggestions", response_model=list[SuggestionResponse])
def get_suggestions(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return ConnectionService(db).get_suggestions(current_user.id, limit=limit)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )
