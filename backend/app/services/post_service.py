"""Post and feed service."""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from backend.app.core.errors import ForbiddenError, NotFoundError, ValidationError
from backend.app.dsa.feed import FeedMerger
from backend.app.dsa.trending import compute_trending_posts
from backend.app.repositories.connection_repo import ConnectionRepository
from backend.app.repositories.interaction_repo import InteractionRepository
from backend.app.repositories.moderation_repo import ModerationRepository
from backend.app.repositories.post_repo import PostRepository
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.post import FeedResponse, PostCreate, PostResponse
from backend.app.services.profile_service import ProfileService


def _media_url(filename: str | None) -> str | None:
    return f"/api/v1/media/{filename}" if filename else None


class PostService:
    def __init__(self, db: Session):
        self.db = db
        self.post_repo = PostRepository(db)
        self.connection_repo = ConnectionRepository(db)
        self.user_repo = UserRepository(db)
        self.profile_service = ProfileService(db)
        self.interaction_repo = InteractionRepository(db)
        self.mod_repo = ModerationRepository(db)

    def _enrich_posts(
        self, post_dicts: list[dict], viewer_id: int
    ) -> list[PostResponse]:
        if not post_dicts:
            return []
        post_ids = [p["id"] for p in post_dicts]
        author_summaries = self.profile_service.get_multiple_summaries(
            list({p["author_id"] for p in post_dicts})
        )
        likes_map = self.interaction_repo.get_likes_for_posts(post_ids)
        comments_map = self.interaction_repo.get_comment_authors_for_posts(post_ids)

        responses: list[PostResponse] = []
        for p in post_dicts:
            if p["author_id"] not in author_summaries:
                continue
            pid = p["id"]
            like_users = likes_map.get(pid, set())
            responses.append(
                PostResponse(
                    id=pid,
                    author=author_summaries[p["author_id"]],
                    body=p["body"],
                    image_url=_media_url(p.get("image_filename")),
                    like_count=len(like_users),
                    comment_count=len(comments_map.get(pid, [])),
                    liked_by_me=viewer_id in like_users,
                    trending_score=p.get("trending_score"),
                    trending_reason=p.get("trending_reason"),
                    created_at=p["created_at"],
                    updated_at=p.get("updated_at"),
                )
            )
        return responses

    def create_post(self, user_id: int, data: PostCreate) -> PostResponse:
        post = self.post_repo.create(author_id=user_id, body=data.body)
        author = self.profile_service.get_profile_summary(user_id)
        return PostResponse(
            id=post.id,
            author=author,
            body=post.body,
            image_url=_media_url(post.image_filename),
            like_count=0,
            comment_count=0,
            liked_by_me=False,
            created_at=post.created_at,
            updated_at=post.updated_at,
        )

    def delete_post(self, post_id: int, user_id: int) -> None:
        from backend.app.services.undo_service import UndoService
        post = self.post_repo.get_by_id(post_id)
        if post is None:
            raise NotFoundError("Post not found")
        if post.author_id != user_id:
            raise ForbiddenError("You can only delete your own posts")
        self.post_repo.delete(post)
        UndoService(self.db).record_post_delete(user_id, post_id)

    def get_user_posts(
        self, user_id: int, limit: int = 20, offset: int = 0, viewer_id: int | None = None
    ) -> list[PostResponse]:
        user = self.user_repo.get_by_id(user_id)
        if user is None or user.status != "active":
            raise NotFoundError("User not found")
        posts = self.post_repo.get_user_posts(user_id, limit=limit, offset=offset)
        dicts = [self.post_repo._to_dict(p) for p in posts]
        return self._enrich_posts(dicts, viewer_id=viewer_id or user_id)

    def get_feed(
        self, user_id: int, limit: int = 20, cursor: str | None = None
    ) -> FeedResponse:
        blocked_ids = self.mod_repo.get_blocked_ids_for_user(user_id)
        connected_ids = [
            other_id
            for other_id, _ in self.connection_repo.get_user_connections(user_id)
            if other_id not in blocked_ids
        ]
        author_ids = list({user_id, *connected_ids})

        after_cursor = None
        if cursor:
            after_cursor = FeedMerger.parse_cursor(cursor)
            if after_cursor is None:
                raise ValidationError("Invalid feed cursor")

        per_author_limit = max(limit * 2, 50)
        streams = self.post_repo.get_multi_author_streams(
            author_ids, per_author_limit=per_author_limit
        )
        merged = FeedMerger.merge_feeds(
            streams, limit=limit + 1, after_cursor=after_cursor
        )

        has_more = len(merged) > limit
        page_posts = merged[:limit]
        next_cursor = (
            FeedMerger.make_cursor(page_posts[-1])
            if has_more and page_posts
            else None
        )

        return FeedResponse(
            posts=self._enrich_posts(page_posts, viewer_id=user_id),
            next_cursor=next_cursor,
        )

    def get_trending_feed(self, user_id: int, limit: int = 20) -> list[PostResponse]:
        blocked_ids = self.mod_repo.get_blocked_ids_for_user(user_id)
        connected_ids = {
            other_id
            for other_id, _ in self.connection_repo.get_user_connections(user_id)
            if other_id not in blocked_ids
        }
        if not connected_ids:
            return []

        streams = self.post_repo.get_multi_author_streams(
            list(connected_ids), per_author_limit=50
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        candidate_posts: list[dict] = []
        for posts in streams.values():
            for p in posts:
                if p["created_at"] >= cutoff:
                    candidate_posts.append(p)

        if not candidate_posts:
            return []

        post_ids = [p["id"] for p in candidate_posts]
        likes_map = self.interaction_repo.get_likes_for_posts(post_ids)
        comments_map = self.interaction_repo.get_comment_authors_for_posts(post_ids)

        ranked = compute_trending_posts(
            posts=candidate_posts,
            likes_by_post=likes_map,
            comments_by_post=comments_map,
            viewer_connections=connected_ids,
            limit=limit,
        )
        return self._enrich_posts(ranked, viewer_id=user_id)
