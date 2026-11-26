"""Post repository."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.models.post import Post


class PostRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _ensure_utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def _to_dict(self, post: Post) -> dict:
        return {
            "id": post.id,
            "author_id": post.author_id,
            "body": post.body,
            "image_filename": post.image_filename,
            "visibility": post.visibility,
            "created_at": self._ensure_utc(post.created_at),
            "updated_at": self._ensure_utc(post.updated_at),
        }

    def create(
        self,
        author_id: int,
        body: str,
        visibility: str = "connections",
        image_filename: str | None = None,
    ) -> Post:
        post = Post(
            author_id=author_id,
            body=body,
            image_filename=image_filename,
            visibility=visibility,
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def set_image(self, post: Post, image_filename: str | None) -> Post:
        post.image_filename = image_filename
        post.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(post)
        return post

    def get_by_id(self, post_id: int) -> Post | None:
        return (
            self.db.query(Post)
            .filter(Post.id == post_id, Post.deleted_at.is_(None))
            .first()
        )

    def delete(self, post: Post) -> None:
        post.deleted_at = datetime.now(timezone.utc)
        self.db.commit()

    def get_user_posts(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> list[Post]:
        return (
            self.db.query(Post)
            .filter(Post.author_id == user_id, Post.deleted_at.is_(None))
            .order_by(Post.created_at.desc(), Post.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_author_stream(self, author_id: int, limit: int = 50) -> list[dict]:
        posts = self.get_user_posts(author_id, limit=limit, offset=0)
        return [self._to_dict(p) for p in posts]

    def get_multi_author_streams(
        self, author_ids: list[int], per_author_limit: int = 50
    ) -> dict[int, list[dict]]:
        """Fetch bounded newest-first post streams per author for Python heap merge."""
        if not author_ids:
            return {}
        streams: dict[int, list[dict]] = {}
        for aid in author_ids:
            posts = self.get_user_posts(aid, limit=per_author_limit, offset=0)
            streams[aid] = [self._to_dict(p) for p in posts]
        return streams
