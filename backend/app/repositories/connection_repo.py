"""Connection and connection request repository."""
from datetime import datetime, timezone
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from backend.app.models.connection import Connection, ConnectionRequest


class ConnectionRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _canonical_pair(user_a: int, user_b: int) -> tuple[int, int]:
        return (user_a, user_b) if user_a < user_b else (user_b, user_a)

    def get_all_accepted_edges(self) -> list[tuple[int, int]]:
        rows = self.db.query(Connection.user_low_id, Connection.user_high_id).all()
        return [(low, high) for low, high in rows]

    def get_connection(self, user_a: int, user_b: int) -> Connection | None:
        low, high = self._canonical_pair(user_a, user_b)
        return (
            self.db.query(Connection)
            .filter(
                Connection.user_low_id == low,
                Connection.user_high_id == high,
            )
            .first()
        )

    def create_request(self, sender_id: int, receiver_id: int) -> ConnectionRequest:
        req = ConnectionRequest(
            sender_id=sender_id,
            receiver_id=receiver_id,
            status="pending",
        )
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)
        return req

    def get_pending_request(
        self, sender_id: int, receiver_id: int
    ) -> ConnectionRequest | None:
        return (
            self.db.query(ConnectionRequest)
            .filter(
                ConnectionRequest.sender_id == sender_id,
                ConnectionRequest.receiver_id == receiver_id,
                ConnectionRequest.status == "pending",
            )
            .first()
        )

    def get_any_pending_between(
        self, user_a: int, user_b: int
    ) -> ConnectionRequest | None:
        return (
            self.db.query(ConnectionRequest)
            .filter(
                ConnectionRequest.status == "pending",
                or_(
                    and_(
                        ConnectionRequest.sender_id == user_a,
                        ConnectionRequest.receiver_id == user_b,
                    ),
                    and_(
                        ConnectionRequest.sender_id == user_b,
                        ConnectionRequest.receiver_id == user_a,
                    ),
                ),
            )
            .first()
        )

    def get_request_by_id(self, request_id: int) -> ConnectionRequest | None:
        return (
            self.db.query(ConnectionRequest)
            .filter(ConnectionRequest.id == request_id)
            .first()
        )

    def accept_request(self, request: ConnectionRequest) -> Connection:
        request.status = "accepted"
        request.updated_at = datetime.now(timezone.utc)

        existing = self.get_connection(request.sender_id, request.receiver_id)
        if existing is None:
            low, high = self._canonical_pair(request.sender_id, request.receiver_id)
            conn = Connection(user_low_id=low, user_high_id=high)
            self.db.add(conn)
        else:
            conn = existing

        self.db.commit()
        self.db.refresh(conn)
        return conn

    def reject_request(self, request: ConnectionRequest) -> ConnectionRequest:
        request.status = "rejected"
        request.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(request)
        return request

    def cancel_request(self, request: ConnectionRequest) -> ConnectionRequest:
        request.status = "cancelled"
        request.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(request)
        return request

    def remove_connection(self, user_a: int, user_b: int) -> bool:
        conn = self.get_connection(user_a, user_b)
        if conn is None:
            return False
        self.db.delete(conn)
        self.db.commit()
        return True

    def get_user_connections(self, user_id: int) -> list[tuple[int, datetime]]:
        rows = (
            self.db.query(Connection)
            .filter(
                or_(
                    Connection.user_low_id == user_id,
                    Connection.user_high_id == user_id,
                )
            )
            .order_by(Connection.created_at.desc())
            .all()
        )
        result: list[tuple[int, datetime]] = []
        for conn in rows:
            other_id = (
                conn.user_high_id if conn.user_low_id == user_id else conn.user_low_id
            )
            result.append((other_id, conn.created_at))
        return result

    def get_incoming_requests(self, user_id: int) -> list[ConnectionRequest]:
        return (
            self.db.query(ConnectionRequest)
            .filter(
                ConnectionRequest.receiver_id == user_id,
                ConnectionRequest.status == "pending",
            )
            .order_by(ConnectionRequest.created_at.desc())
            .all()
        )

    def get_outgoing_requests(self, user_id: int) -> list[ConnectionRequest]:
        return (
            self.db.query(ConnectionRequest)
            .filter(
                ConnectionRequest.sender_id == user_id,
                ConnectionRequest.status == "pending",
            )
            .order_by(ConnectionRequest.created_at.desc())
            .all()
        )

    def get_pending_pairs(self, user_id: int) -> set[tuple[int, int]]:
        rows = (
            self.db.query(ConnectionRequest.sender_id, ConnectionRequest.receiver_id)
            .filter(
                ConnectionRequest.status == "pending",
                or_(
                    ConnectionRequest.sender_id == user_id,
                    ConnectionRequest.receiver_id == user_id,
                ),
            )
            .all()
        )
        return {(sender_id, receiver_id) for sender_id, receiver_id in rows}

    def get_connection_status(
        self, viewer_id: int, target_id: int
    ) -> tuple[bool, str | None]:
        if viewer_id == target_id:
            return (False, "self")
        if self.get_connection(viewer_id, target_id) is not None:
            return (True, "connected")
        pending = self.get_any_pending_between(viewer_id, target_id)
        if pending is not None:
            if pending.sender_id == viewer_id:
                return (False, "pending_sent")
            return (False, "pending_received")
        return (False, None)
