"""Connection and social graph service."""
from sqlalchemy.orm import Session

from backend.app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from backend.app.dsa.graph import (
    build_adjacency_list,
    build_ordered_adjacency,
    degree_label,
    hop_count,
    mutual_connections,
    shortest_path,
)
from backend.app.dsa.recommendations import get_recommendations
from backend.app.repositories.connection_repo import ConnectionRepository
from backend.app.repositories.moderation_repo import ModerationRepository
from backend.app.repositories.profile_repo import ProfileRepository
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.connection import (
    ConnectionRequestResponse,
    ConnectionResponse,
    MutualConnectionsResponse,
    PathResponse,
    SuggestionResponse,
)
from backend.app.services.notification_service import NotificationService
from backend.app.services.profile_service import ProfileService


class ConnectionService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.connection_repo = ConnectionRepository(db)
        self.profile_repo = ProfileRepository(db)
        self.profile_service = ProfileService(db)
        self.notification_service = NotificationService(db)
        self.mod_repo = ModerationRepository(db)

    def _build_graph(self) -> dict[int, set[int]]:
        user_ids = self.user_repo.get_all_active_ids()
        edges = self.connection_repo.get_all_accepted_edges()
        return build_adjacency_list(user_ids, edges)

    def _ensure_active_user(self, user_id: int) -> None:
        user = self.user_repo.get_by_id(user_id)
        if user is None or user.status != "active":
            raise NotFoundError("User not found")

    def _request_to_response(self, req) -> ConnectionRequestResponse:
        summaries = self.profile_service.get_multiple_summaries(
            [req.sender_id, req.receiver_id]
        )
        return ConnectionRequestResponse(
            id=req.id,
            sender=summaries[req.sender_id],
            receiver=summaries[req.receiver_id],
            status=req.status,
            created_at=req.created_at,
        )

    def send_request(
        self, sender_id: int, receiver_id: int
    ) -> ConnectionRequestResponse:
        if sender_id == receiver_id:
            raise ValidationError("Cannot send connection request to yourself")
        self._ensure_active_user(receiver_id)
        if receiver_id in self.mod_repo.get_blocked_ids_for_user(sender_id):
            raise ForbiddenError("Cannot send connection request to this user")

        if self.connection_repo.get_connection(sender_id, receiver_id) is not None:
            raise ConflictError("Users are already connected")
        if (
            self.connection_repo.get_any_pending_between(sender_id, receiver_id)
            is not None
        ):
            raise ConflictError("A pending connection request already exists")

        req = self.connection_repo.create_request(sender_id, receiver_id)
        self.notification_service.create_notification(
            recipient_id=receiver_id,
            actor_id=sender_id,
            type="connection_request",
            entity_type="connection_request",
            entity_id=req.id,
        )
        return self._request_to_response(req)

    def accept_request(
        self, request_id: int, user_id: int
    ) -> ConnectionResponse:
        req = self.connection_repo.get_request_by_id(request_id)
        if req is None:
            raise NotFoundError("Connection request not found")
        if req.receiver_id != user_id:
            raise ForbiddenError("Only the recipient can accept this request")
        if req.status != "pending":
            raise ConflictError("Connection request is no longer pending")

        conn = self.connection_repo.accept_request(req)
        self.notification_service.create_notification(
            recipient_id=req.sender_id,
            actor_id=user_id,
            type="connection_accepted",
            entity_type="connection_request",
            entity_id=req.id,
        )
        sender_summary = self.profile_service.get_profile_summary(req.sender_id)
        return ConnectionResponse(
            user=sender_summary,
            connected_since=conn.created_at,
        )

    def reject_request(
        self, request_id: int, user_id: int
    ) -> ConnectionRequestResponse:
        req = self.connection_repo.get_request_by_id(request_id)
        if req is None:
            raise NotFoundError("Connection request not found")
        if req.receiver_id != user_id:
            raise ForbiddenError("Only the recipient can reject this request")
        if req.status != "pending":
            raise ConflictError("Connection request is no longer pending")

        updated = self.connection_repo.reject_request(req)
        return self._request_to_response(updated)

    def cancel_request(
        self, request_id: int, user_id: int
    ) -> ConnectionRequestResponse:
        req = self.connection_repo.get_request_by_id(request_id)
        if req is None:
            raise NotFoundError("Connection request not found")
        if req.sender_id != user_id:
            raise ForbiddenError("Only the sender can cancel this request")
        if req.status != "pending":
            raise ConflictError("Connection request is no longer pending")

        updated = self.connection_repo.cancel_request(req)
        return self._request_to_response(updated)

    def remove_connection(self, user_id: int, other_user_id: int) -> None:
        if user_id == other_user_id:
            raise ValidationError("Cannot remove connection with yourself")
        removed = self.connection_repo.remove_connection(user_id, other_user_id)
        if not removed:
            raise NotFoundError("Connection not found")

    def get_connections(self, user_id: int) -> list[ConnectionResponse]:
        self._ensure_active_user(user_id)
        conns = self.connection_repo.get_user_connections(user_id)
        summaries = self.profile_service.get_multiple_summaries(
            [other_id for other_id, _ in conns]
        )
        return [
            ConnectionResponse(user=summaries[other_id], connected_since=created_at)
            for other_id, created_at in conns
            if other_id in summaries
        ]

    def get_mutual_connections(
        self, user_id: int, other_user_id: int
    ) -> MutualConnectionsResponse:
        self._ensure_active_user(user_id)
        self._ensure_active_user(other_user_id)
        adj = self._build_graph()
        mutual_ids = sorted(mutual_connections(adj, user_id, other_user_id))
        summaries = self.profile_service.get_multiple_summaries(mutual_ids)
        items = [summaries[uid] for uid in mutual_ids if uid in summaries]
        return MutualConnectionsResponse(
            user_id=user_id,
            other_user_id=other_user_id,
            mutual_connections=items,
            count=len(items),
        )

    def get_suggestions(
        self, user_id: int, limit: int = 10
    ) -> list[SuggestionResponse]:
        self._ensure_active_user(user_id)
        adj = self._build_graph()
        pending_pairs = self.connection_repo.get_pending_pairs(user_id)
        username_map = self.profile_repo.get_username_map()
        blocked_ids = self.mod_repo.get_blocked_ids_for_user(user_id)
        from backend.app.models.profile import Profile
        prog_rows = self.db.query(Profile.user_id, Profile.programme).all()
        programme_map = {uid: (prog or "") for uid, prog in prog_rows}
        skills_map = {uid: set(self.profile_repo.get_skills(uid)) for uid in adj}
        recs = get_recommendations(
            adj=adj,
            user_id=user_id,
            pending_pairs=pending_pairs,
            blocked_ids=blocked_ids,
            inactive_ids=set(),
            username_map=username_map,
            limit=limit,
            programme_map=programme_map,
            skills_map=skills_map,
        )
        summaries = self.profile_service.get_multiple_summaries(
            [r["user_id"] for r in recs]
        )
        return [
            SuggestionResponse(
                user=summaries[r["user_id"]],
                score=r["score"],
                mutual_count=r["mutual_count"],
                reason=r["reason"],
            )
            for r in recs
            if r["user_id"] in summaries
        ]

    def get_path(self, user_id: int, target_user_id: int) -> PathResponse:
        self._ensure_active_user(user_id)
        self._ensure_active_user(target_user_id)
        adj = self._build_graph()
        ordered_adj = build_ordered_adjacency(adj)
        path_ids = shortest_path(ordered_adj, user_id, target_user_id)
        if path_ids is None:
            return PathResponse(
                path=[],
                hop_count=-1,
                degree_label=degree_label(None),
            )
        hops = hop_count(path_ids)
        summaries = self.profile_service.get_multiple_summaries(path_ids)
        return PathResponse(
            path=[summaries[uid] for uid in path_ids if uid in summaries],
            hop_count=hops if hops is not None else -1,
            degree_label=degree_label(hops),
        )

    def get_incoming_requests(
        self, user_id: int
    ) -> list[ConnectionRequestResponse]:
        requests = self.connection_repo.get_incoming_requests(user_id)
        if not requests:
            return []
        user_ids = list({r.sender_id for r in requests} | {r.receiver_id for r in requests})
        summaries = self.profile_service.get_multiple_summaries(user_ids)
        return [
            ConnectionRequestResponse(
                id=r.id,
                sender=summaries[r.sender_id],
                receiver=summaries[r.receiver_id],
                status=r.status,
                created_at=r.created_at,
            )
            for r in requests
            if r.sender_id in summaries and r.receiver_id in summaries
        ]

    def get_outgoing_requests(
        self, user_id: int
    ) -> list[ConnectionRequestResponse]:
        requests = self.connection_repo.get_outgoing_requests(user_id)
        if not requests:
            return []
        user_ids = list({r.sender_id for r in requests} | {r.receiver_id for r in requests})
        summaries = self.profile_service.get_multiple_summaries(user_ids)
        return [
            ConnectionRequestResponse(
                id=r.id,
                sender=summaries[r.sender_id],
                receiver=summaries[r.receiver_id],
                status=r.status,
                created_at=r.created_at,
            )
            for r in requests
            if r.sender_id in summaries and r.receiver_id in summaries
        ]
