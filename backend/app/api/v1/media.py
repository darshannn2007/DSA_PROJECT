"""Secure media upload and authorized serving routes (Pillow decode/re-encode, EXIF strip)."""
import io
import os
import secrets
from pathlib import Path
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_current_user
from backend.app.core.errors import ForbiddenError, NotFoundError, ValidationError
from backend.app.db.database import get_db
from backend.app.models.post import Post
from backend.app.models.profile import Profile
from backend.app.models.user import User
from backend.app.repositories.connection_repo import ConnectionRepository
from backend.app.repositories.moderation_repo import ModerationRepository
from backend.app.repositories.post_repo import PostRepository
from backend.app.repositories.profile_repo import ProfileRepository

router = APIRouter(tags=["media"])

UPLOAD_DIR = Path("data/uploads")
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_DIMENSION = 4096
MAX_PIXELS = 16_000_000
ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

# Guard against decompression bombs
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def _decode_and_reencode_image(raw_bytes: bytes) -> tuple[bytes, str]:
    """Decode with Pillow, validate dimensions/format, strip EXIF, and re-encode."""
    if not raw_bytes:
        raise ValidationError("Empty upload")
    if len(raw_bytes) > MAX_IMAGE_BYTES:
        raise ValidationError("Image exceeds 5 MB limit")

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            fmt = (img.format or "").upper()
            if fmt not in ALLOWED_FORMATS:
                raise ValidationError("Only JPEG, PNG, and WebP images are allowed")
            w, h = img.size
            if w <= 0 or h <= 0 or w > MAX_DIMENSION or h > MAX_DIMENSION or (w * h) > MAX_PIXELS:
                raise ValidationError("Image dimensions exceed allowed limits")

            # Re-encode from pixel data to strip EXIF/location metadata & polyglot payloads
            clean_mode = "RGBA" if fmt in ("PNG", "WEBP") and img.mode in ("RGBA", "LA", "PA") else "RGB"
            converted = img.convert(clean_mode)
            out = io.BytesIO()
            converted.save(out, format=fmt)
            return out.getvalue(), ALLOWED_FORMATS[fmt]
    except ValidationError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        raise ValidationError("Invalid or corrupted image file")


async def _save_validated_image(file: UploadFile) -> str:
    data = await file.read(MAX_IMAGE_BYTES + 1)
    clean_bytes, ext = _decode_and_reencode_image(data)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"{secrets.token_hex(16)}{ext}"
    (UPLOAD_DIR / filename).write_bytes(clean_bytes)
    return filename


def _delete_file_quietly(filename: str | None) -> None:
    if not filename:
        return
    safe_name = Path(filename).name
    target = UPLOAD_DIR / safe_name
    if target.is_file():
        try:
            target.unlink()
        except OSError:
            pass


@router.post("/me/avatar")
@router.post("/me/profile/photo")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        profile_repo = ProfileRepository(db)
        existing = profile_repo.get_by_user_id(current_user.id)
        old_filename = existing.avatar_filename if existing else None
        filename = await _save_validated_image(file)
        profile_repo.update(current_user.id, avatar_filename=filename)
        if old_filename and old_filename != filename:
            _delete_file_quietly(old_filename)
        return {"avatar_url": f"/api/v1/media/{filename}"}
    except ValidationError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.delete("/me/avatar")
@router.delete("/me/profile/photo")
def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile_repo = ProfileRepository(db)
    profile = profile_repo.get_by_user_id(current_user.id)
    if profile and profile.avatar_filename:
        old = profile.avatar_filename
        profile.avatar_filename = None
        db.commit()
        _delete_file_quietly(old)
    return {"status": "deleted"}


@router.post("/posts/{post_id}/image")
@router.post("/posts/{post_id}/media")
async def upload_post_image(
    post_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        post_repo = PostRepository(db)
        post = post_repo.get_by_id(post_id)
        if post is None:
            raise NotFoundError("Post not found")
        if post.author_id != current_user.id:
            raise ForbiddenError("You can only attach images to your own posts")
        old_filename = post.image_filename
        filename = await _save_validated_image(file)
        post_repo.set_image(post, filename)
        if old_filename and old_filename != filename:
            _delete_file_quietly(old_filename)
        return {"image_url": f"/api/v1/media/{filename}"}
    except (ValidationError, NotFoundError, ForbiddenError) as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/media/{filename}")
def get_media(
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Prevent path traversal
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        return JSONResponse(
            status_code=400,
            content={"code": "validation_error", "message": "Invalid filename"},
        )
    target = UPLOAD_DIR / safe_name
    if not target.is_file():
        return JSONResponse(
            status_code=404,
            content={"code": "not_found", "message": "Media not found"},
        )

    # Re-check authorization against owning profile or post
    mod_repo = ModerationRepository(db)
    conn_repo = ConnectionRepository(db)
    blocked = mod_repo.get_blocked_ids_for_user(current_user.id)

    profile = db.query(Profile).filter(Profile.avatar_filename == safe_name).first()
    if profile is not None:
        if profile.user_id != current_user.id:
            if profile.user_id in blocked:
                return JSONResponse(status_code=403, content={"code": "forbidden", "message": "Access denied"})
            if profile.visibility == "connections" and conn_repo.get_connection(current_user.id, profile.user_id) is None:
                return JSONResponse(status_code=403, content={"code": "forbidden", "message": "Access denied"})
        return FileResponse(str(target))

    post = db.query(Post).filter(Post.image_filename == safe_name, Post.deleted_at.is_(None)).first()
    if post is not None:
        if post.author_id != current_user.id:
            if post.author_id in blocked:
                return JSONResponse(status_code=403, content={"code": "forbidden", "message": "Access denied"})
            if post.visibility == "connections" and conn_repo.get_connection(current_user.id, post.author_id) is None:
                return JSONResponse(status_code=403, content={"code": "forbidden", "message": "Access denied"})
        return FileResponse(str(target))

    return JSONResponse(status_code=404, content={"code": "not_found", "message": "Media not found"})
