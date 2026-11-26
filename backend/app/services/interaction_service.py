"""Service for post likes and comments/replies."""
from sqlalchemy.orm import Session

from backend.app.core.errors import ForbiddenError, NotFoundError, ValidationError
from backend.app.repositories.connection_repo import ConnectionRepository
from backend.app.repositories.interaction_repo import InteractionRepository
from backend.app.repositories.moderation_repo import ModerationRepository
from backend.app.repositories.post_repo import PostRepository
from backend.app.schemas.interaction import (
    CommentCreate,
    CommentResponse,
    LikeToggleResponse,
)
from backend.app.services.notification_service import NotificationService
from backend.app.services.profile_service import ProfileService


class InteractionService:
    def __init__(self, db: Session):
        self.db = db
        self.interaction_repo = InteractionRepository(db)
        self.post_repo = PostRepository(db)
        self.connection_repo = ConnectionRepository(db)
        self.mod_repo = ModerationRepository(db)
        self.profile_service = ProfileService(db)
        self.notification_service = NotificationService(db)

    def _ensure_can_view_post(self, user_id: int, post_id: int):
        post = self.post_repo.get_by_id(post_id)
        if post is None:
            raise NotFoundError("Post not found")
        blocked = self.mod_repo.get_blocked_ids_for_user(user_id)
        if post.author_id in blocked:
            raise ForbiddenError("Cannot interact with this post")
        if post.author_id != user_id and post.visibility == "connections":
            if self.connection_repo.get_connection(user_id, post.author_id) is None:
                raise ForbiddenError("Only connections can interact with this post")
        return post

    def toggle_like(self, user_id: int, post_id: int) -> LikeToggleResponse:
        post = self._ensure_can_view_post(user_id, post_id)
        existing = self.interaction_repo.get_like(user_id, post_id)
        if existing is not None:
            self.interaction_repo.remove_like(existing)
            liked = False
        else:
            self.interaction_repo.add_like(user_id, post_id)
            liked = True
            if post.author_id != user_id:
                self.notification_service.create_notification(
                    recipient_id=post.author_id,
                    actor_id=user_id,
                    type="post_like",
                    entity_type="post",
                    entity_id=post.id,
                )
        count = self.interaction_repo.count_likes(post_id)
        return LikeToggleResponse(post_id=post_id, liked=liked, like_count=count)

    def add_comment(
        self, user_id: int, post_id: int, data: CommentCreate
    ) -> CommentResponse:
        post = self._ensure_can_view_post(user_id, post_id)
        parent = None
        if data.parent_comment_id is not None:
            parent = self.interaction_repo.get_comment_by_id(data.parent_comment_id)
            if parent is None or parent.post_id != post_id:
                raise NotFoundError("Parent comment not found on this post")
            if parent.parent_comment_id is not None:
                raise ValidationError("Replies can only target top-level comments")

        comment = self.interaction_repo.create_comment(
            post_id=post_id,
            author_id=user_id,
            body=data.body,
            parent_comment_id=data.parent_comment_id,
        )

        # Notify post author or parent comment author
        if parent is not None and parent.author_id != user_id:
            self.notification_service.create_notification(
                recipient_id=parent.author_id,
                actor_id=user_id,
                type="comment_reply",
                entity_type="post",
                entity_id=post.id,
            )
        elif post.author_id != user_id:
            self.notification_service.create_notification(
                recipient_id=post.author_id,
                actor_id=user_id,
                type="post_comment",
                entity_type="post",
                entity_id=post.id,
            )

        author = self.profile_service.get_profile_summary(user_id)
        return CommentResponse(
            id=comment.id,
            post_id=comment.post_id,
            author=author,
            parent_comment_id=comment.parent_comment_id,
            body=comment.body,
            created_at=comment.created_at,
            replies=[],
        )

    def list_comments(self, user_id: int, post_id: int) -> list[CommentResponse]:
        self._ensure_can_view_post(user_id, post_id)
        blocked = self.mod_repo.get_blocked_ids_for_user(user_id)
        raw = [
            c
            for c in self.interaction_repo.get_comments_for_post(post_id)
            if c.author_id not in blocked
        ]
        if not raw:
            return []

        summaries = self.profile_service.get_multiple_summaries(
            [c.author_id for c in raw]
        )
        top_level: list[CommentResponse] = []
        by_id: dict[int, CommentResponse] = {}

        for c in raw:
            if c.author_id not in summaries:
                continue
            item = CommentResponse(
                id=c.id,
                post_id=c.post_id,
                author=summaries[c.author_id],
                parent_comment_id=c.parent_comment_id,
                body=c.body,
                created_at=c.created_at,
                replies=[],
            )
            by_id[c.id] = item
            if c.parent_comment_id is None:
                top_level.append(item)

        for c in raw:
            if c.parent_comment_id is not None and c.parent_comment_id in by_id and c.id in by_id:
                by_id[c.parent_comment_id].replies.append(by_id[c.id])

        return top_level

    def delete_comment(self, user_id: int, comment_id: int) -> None:
        comment = self.interaction_repo.get_comment_by_id(comment_id)
        if comment is None:
            raise NotFoundError("Comment not found")
        if comment.author_id != user_id:
            raise ForbiddenError("You can only delete your own comments")
        self.interaction_repo.soft_delete_comment(comment)
