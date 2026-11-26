"""Repository for PostLike and PostComment."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.models.interaction import PostLike, PostComment


class InteractionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_like(self, user_id: int, post_id: int) -> PostLike | None:
        return (
            self.db.query(PostLike)
            .filter(PostLike.user_id == user_id, PostLike.post_id == post_id)
            .first()
        )

    def add_like(self, user_id: int, post_id: int) -> PostLike:
        like = PostLike(user_id=user_id, post_id=post_id)
        self.db.add(like)
        self.db.commit()
        return like

    def remove_like(self, like: PostLike) -> None:
        self.db.delete(like)
        self.db.commit()

    def get_likes_for_posts(self, post_ids: list[int]) -> dict[int, set[int]]:
        if not post_ids:
            return {}
        rows = (
            self.db.query(PostLike.post_id, PostLike.user_id)
            .filter(PostLike.post_id.in_(post_ids))
            .all()
        )
        result: dict[int, set[int]] = {pid: set() for pid in post_ids}
        for pid, uid in rows:
            result[pid].add(uid)
        return result

    def count_likes(self, post_id: int) -> int:
        return self.db.query(PostLike).filter(PostLike.post_id == post_id).count()

    def create_comment(
        self,
        post_id: int,
        author_id: int,
        body: str,
        parent_comment_id: int | None = None,
    ) -> PostComment:
        comment = PostComment(
            post_id=post_id,
            author_id=author_id,
            body=body,
            parent_comment_id=parent_comment_id,
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def get_comment_by_id(self, comment_id: int) -> PostComment | None:
        return (
            self.db.query(PostComment)
            .filter(PostComment.id == comment_id, PostComment.deleted_at.is_(None))
            .first()
        )

    def soft_delete_comment(self, comment: PostComment) -> None:
        comment.deleted_at = datetime.now(timezone.utc)
        self.db.commit()

    def get_comments_for_post(self, post_id: int) -> list[PostComment]:
        return (
            self.db.query(PostComment)
            .filter(PostComment.post_id == post_id, PostComment.deleted_at.is_(None))
            .order_by(PostComment.created_at.asc(), PostComment.id.asc())
            .all()
        )

    def get_comment_authors_for_posts(self, post_ids: list[int]) -> dict[int, list[int]]:
        if not post_ids:
            return {}
        rows = (
            self.db.query(PostComment.post_id, PostComment.author_id)
            .filter(PostComment.post_id.in_(post_ids), PostComment.deleted_at.is_(None))
            .all()
        )
        result: dict[int, list[int]] = {pid: [] for pid in post_ids}
        for pid, aid in rows:
            result[pid].append(aid)
        return result
