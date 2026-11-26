"""User search API routes."""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_current_user
from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.search import SearchResult
from backend.app.services.search_service import SearchService

router = APIRouter(tags=["search"])


@router.get("/users/search", response_model=SearchResult)
def search_users(
    q: str = Query(""),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return SearchService(db).search_users(
            query=q, limit=limit, viewer_id=current_user.id
        )
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )
