"""Service for Groups, join-request approvals, group posts, and community suggestions."""
from sqlalchemy.orm import Session

from backend.app.core.errors import ConflictError, ForbiddenError, NotFoundError
from backend.app.dsa.graph import build_adjacency_list
from backend.app.dsa.groups import suggest_groups
from backend.app.models.group import GroupMember, GroupPost
from backend.app.models.post import Post
from backend.app.repositories.connection_repo import ConnectionRepository
from backend.app.repositories.group_repo import GroupRepository
from backend.app.repositories.moderation_repo import ModerationRepository
from backend.app.repositories.post_repo import PostRepository
from backend.app.repositories.profile_repo import ProfileRepository
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.group import GroupCreate, GroupResponse, GroupSuggestionResponse
from backend.app.schemas.post import PostCreate, PostResponse
from backend.app.services.post_service import PostService
from backend.app.services.profile_service import ProfileService


class GroupService:
    def __init__(self, db: Session):
        self.db = db
        self.group_repo = GroupRepository(db)
        self.user_repo = UserRepository(db)
        self.connection_repo = ConnectionRepository(db)
        self.profile_repo = ProfileRepository(db)
        self.mod_repo = ModerationRepository(db)
        self.post_repo = PostRepository(db)
        self.profile_service = ProfileService(db)
        self.post_service = PostService(db)

    def _to_response(self, g, m: GroupMember | None, member_count: int) -> GroupResponse:
        return GroupResponse(
            id=g.id,
            name=g.name,
            description=g.description,
            visibility=g.visibility,
            membership_policy=g.membership_policy,
            created_by=g.created_by,
            member_count=member_count,
            my_role=m.role if m else None,
            my_status=m.status if m else None,
            created_at=g.created_at,
        )

    def create_group(self, user_id: int, data: GroupCreate) -> GroupResponse:
        group = self.group_repo.create_group(
            name=data.name,
            description=data.description,
            visibility=data.visibility,
            membership_policy=data.membership_policy,
            creator_id=user_id,
        )
        m = self.group_repo.get_membership(group.id, user_id)
        return self._to_response(group, m, member_count=1)

    def get_group(self, user_id: int, group_id: int) -> GroupResponse:
        group = self.group_repo.get_by_id(group_id)
        if group is None:
            raise NotFoundError("Group not found")
        m = self.group_repo.get_membership(group_id, user_id)
        if group.visibility == "private" and (m is None or m.status != "active"):
            raise ForbiddenError("Private group access denied")
        member_count = len(self.group_repo.get_active_member_ids(group_id))
        return self._to_response(group, m, member_count)

    def list_groups(self, user_id: int) -> list[GroupResponse]:
        all_groups = self.group_repo.list_all()
        memberships = self.group_repo.get_user_memberships(user_id)
        member_sets = self.group_repo.get_all_active_memberships()
        results: list[GroupResponse] = []
        for g in all_groups:
            m = memberships.get(g.id)
            if g.visibility == "private" and (m is None or m.status != "active"):
                continue
            results.append(self._to_response(g, m, len(member_sets.get(g.id, set()))))
        return results

    def join_group(self, user_id: int, group_id: int) -> GroupResponse:
        group = self.group_repo.get_by_id(group_id)
        if group is None:
            raise NotFoundError("Group not found")
        if group.visibility == "private" or group.membership_policy == "invite":
            raise ForbiddenError("This group is invite-only")
        existing = self.group_repo.get_membership(group_id, user_id)
        if existing is not None:
            raise ConflictError("Already a member or request pending")

        status = "active" if group.membership_policy == "open" else "pending"
        m = self.group_repo.add_member(group_id, user_id, role="member", status=status)
        member_count = len(self.group_repo.get_active_member_ids(group_id))
        return self._to_response(group, m, member_count)

    def leave_group(self, user_id: int, group_id: int) -> None:
        m = self.group_repo.get_membership(group_id, user_id)
        if m is None:
            raise NotFoundError("Membership not found")
        if m.role == "owner":
            raise ForbiddenError("Group owner cannot leave the group")
        self.group_repo.remove_member(m)

    def _require_manager(self, group_id: int, user_id: int) -> None:
        m = self.group_repo.get_membership(group_id, user_id)
        if m is None or m.status != "active" or m.role not in ("owner", "moderator"):
            raise ForbiddenError("Owner or moderator role required")

    def list_pending_requests(self, actor_id: int, group_id: int) -> list[dict]:
        group = self.group_repo.get_by_id(group_id)
        if group is None:
            raise NotFoundError("Group not found")
        self._require_manager(group_id, actor_id)
        pending = (
            self.db.query(GroupMember)
            .filter(GroupMember.group_id == group_id, GroupMember.status == "pending")
            .all()
        )
        summaries = self.profile_service.get_multiple_summaries([p.user_id for p in pending])
        return [
            {"user": summaries[p.user_id], "requested_at": p.joined_at}
            for p in pending
            if p.user_id in summaries
        ]

    def review_join_request(
        self, actor_id: int, group_id: int, target_user_id: int, approve: bool
    ) -> dict:
        group = self.group_repo.get_by_id(group_id)
        if group is None:
            raise NotFoundError("Group not found")
        self._require_manager(group_id, actor_id)
        m = self.group_repo.get_membership(group_id, target_user_id)
        if m is None or m.status != "pending":
            raise NotFoundError("Pending join request not found")
        if approve:
            m.status = "active"
            self.db.commit()
            return {"status": "approved", "user_id": target_user_id}
        self.group_repo.remove_member(m)
        return {"status": "rejected", "user_id": target_user_id}

    def create_group_post(
        self, user_id: int, group_id: int, data: PostCreate
    ) -> PostResponse:
        group = self.group_repo.get_by_id(group_id)
        if group is None:
            raise NotFoundError("Group not found")
        m = self.group_repo.get_membership(group_id, user_id)
        if m is None or m.status != "active":
            raise ForbiddenError("Only active group members can post")

        post = self.post_repo.create(
            author_id=user_id, body=data.body, visibility="group"
        )
        gp = GroupPost(group_id=group_id, post_id=post.id, author_id=user_id)
        self.db.add(gp)
        self.db.commit()
        author = self.profile_service.get_profile_summary(user_id)
        return PostResponse(
            id=post.id,
            author=author,
            body=post.body,
            created_at=post.created_at,
            updated_at=post.updated_at,
        )

    def get_group_feed(
        self, user_id: int, group_id: int, limit: int = 20
    ) -> list[PostResponse]:
        group = self.group_repo.get_by_id(group_id)
        if group is None:
            raise NotFoundError("Group not found")
        m = self.group_repo.get_membership(group_id, user_id)
        if group.visibility == "private" and (m is None or m.status != "active"):
            raise ForbiddenError("Private group feed requires active membership")

        blocked = self.mod_repo.get_blocked_ids_for_user(user_id)
        rows = (
            self.db.query(Post)
            .join(GroupPost, GroupPost.post_id == Post.id)
            .filter(GroupPost.group_id == group_id, Post.deleted_at.is_(None))
            .order_by(Post.created_at.desc(), Post.id.desc())
            .limit(limit)
            .all()
        )
        dicts = [
            self.post_repo._to_dict(p) for p in rows if p.author_id not in blocked
        ]
        return self.post_service._enrich_posts(dicts, viewer_id=user_id)

    def get_suggestions(
        self, user_id: int, limit: int = 10
    ) -> list[GroupSuggestionResponse]:
        active_ids = self.user_repo.get_all_active_ids()
        edges = self.connection_repo.get_all_accepted_edges()
        adj = build_adjacency_list(active_ids, edges)

        blocked_ids = self.mod_repo.get_blocked_ids_for_user(user_id)
        viewer_skills = set(self.profile_repo.get_skills(user_id))

        all_groups = self.group_repo.list_all()
        member_sets = self.group_repo.get_all_active_memberships()

        all_member_ids: set[int] = set()
        for uids in member_sets.values():
            all_member_ids.update(uids)

        member_skills_map = {
            uid: set(self.profile_repo.get_skills(uid)) for uid in all_member_ids
        }

        group_dicts = [
            {
                "id": g.id,
                "name": g.name,
                "description": g.description,
                "visibility": g.visibility,
                "membership_policy": g.membership_policy,
                "member_ids": member_sets.get(g.id, set()),
            }
            for g in all_groups
        ]

        recs = suggest_groups(
            adj=adj,
            viewer_id=user_id,
            viewer_skills=viewer_skills,
            groups=group_dicts,
            member_skills_map=member_skills_map,
            blocked_ids=blocked_ids,
            inactive_ids=set(),
            limit=limit,
        )
        return [GroupSuggestionResponse(**r) for r in recs]
