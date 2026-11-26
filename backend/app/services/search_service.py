"""User search service backed by Trie prefix index."""
from sqlalchemy.orm import Session

from backend.app.dsa.trie import Trie
from backend.app.repositories.moderation_repo import ModerationRepository
from backend.app.repositories.profile_repo import ProfileRepository
from backend.app.schemas.search import SearchResult
from backend.app.services.profile_service import ProfileService


class SearchService:
    def __init__(self, db: Session):
        self.db = db
        self.profile_repo = ProfileRepository(db)
        self.profile_service = ProfileService(db)
        self.mod_repo = ModerationRepository(db)

    def search_users(
        self, query: str, limit: int = 10, viewer_id: int | None = None
    ) -> SearchResult:
        clean_query = query.strip()
        if not clean_query:
            return SearchResult(users=[], query=query, count=0)

        blocked_ids = (
            self.mod_repo.get_blocked_ids_for_user(viewer_id)
            if viewer_id is not None
            else set()
        )
        username_map = self.profile_repo.get_username_map()
        display_name_map = self.profile_repo.get_display_name_map()

        entries: list[tuple[str, int]] = []
        for uid, username in username_map.items():
            if uid not in blocked_ids:
                entries.append((username, uid))

        for uid, display_name in display_name_map.items():
            if uid not in username_map or uid in blocked_ids or not display_name:
                continue
            entries.append((display_name, uid))
            for token in display_name.split():
                if token:
                    entries.append((token, uid))

        trie = Trie()
        trie.rebuild(entries)

        matched_ids = trie.search_prefix(clean_query, limit=limit)
        summaries = self.profile_service.get_multiple_summaries(matched_ids)
        users = sorted(
            (summaries[uid] for uid in matched_ids if uid in summaries),
            key=lambda s: (s.username.lower(), s.user_id),
        )
        return SearchResult(users=users, query=query, count=len(users))
