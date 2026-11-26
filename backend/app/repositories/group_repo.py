"""Repository for Groups and GroupMembers."""
from sqlalchemy.orm import Session

from backend.app.models.group import Group, GroupMember


class GroupRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_group(
        self,
        name: str,
        description: str,
        visibility: str,
        membership_policy: str,
        creator_id: int,
    ) -> Group:
        group = Group(
            name=name,
            description=description,
            visibility=visibility,
            membership_policy=membership_policy,
            created_by=creator_id,
        )
        self.db.add(group)
        self.db.flush()
        owner = GroupMember(
            group_id=group.id,
            user_id=creator_id,
            role="owner",
            status="active",
        )
        self.db.add(owner)
        self.db.commit()
        self.db.refresh(group)
        return group

    def get_by_id(self, group_id: int) -> Group | None:
        return self.db.query(Group).filter(Group.id == group_id).first()

    def list_all(self) -> list[Group]:
        return self.db.query(Group).order_by(Group.created_at.desc()).all()

    def get_membership(self, group_id: int, user_id: int) -> GroupMember | None:
        return (
            self.db.query(GroupMember)
            .filter(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
            .first()
        )

    def add_member(
        self,
        group_id: int,
        user_id: int,
        role: str = "member",
        status: str = "active",
    ) -> GroupMember:
        member = GroupMember(
            group_id=group_id,
            user_id=user_id,
            role=role,
            status=status,
        )
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        return member

    def remove_member(self, member: GroupMember) -> None:
        self.db.delete(member)
        self.db.commit()

    def get_active_member_ids(self, group_id: int) -> set[int]:
        rows = (
            self.db.query(GroupMember.user_id)
            .filter(GroupMember.group_id == group_id, GroupMember.status == "active")
            .all()
        )
        return {r[0] for r in rows}

    def get_all_active_memberships(self) -> dict[int, set[int]]:
        rows = (
            self.db.query(GroupMember.group_id, GroupMember.user_id)
            .filter(GroupMember.status == "active")
            .all()
        )
        res: dict[int, set[int]] = {}
        for gid, uid in rows:
            res.setdefault(gid, set()).add(uid)
        return res

    def get_user_memberships(self, user_id: int) -> dict[int, GroupMember]:
        rows = self.db.query(GroupMember).filter(GroupMember.user_id == user_id).all()
        return {m.group_id: m for m in rows}
