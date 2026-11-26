"""Security utilities: password hashing, session/CSRF tokens, and rate limiting."""
from collections import defaultdict, deque
import hashlib
import secrets
import threading
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from backend.app.core.errors import AppError

_ph = PasswordHasher()


class RateLimitError(AppError):
    def __init__(self, message: str = "Too many requests. Please try again later."):
        super().__init__(code="rate_limited", message=message, status_code=429)


def hash_password(password: str) -> str:
    """Hash password with Argon2id. Never stores plaintext."""
    return _ph.hash(password)


def validate_password_policy(password: str) -> str:
    """Enforce strong password rules: 8-128 chars, no spaces, 1 upper, 1 lower, 1 digit, 1 special."""
    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must be 8-128 characters")
    if any(ch.isspace() for ch in password):
        raise ValueError("Password must not contain spaces")
    if not any(ch.isupper() for ch in password):
        raise ValueError("Password must contain at least 1 uppercase letter")
    if not any(ch.islower() for ch in password):
        raise ValueError("Password must contain at least 1 lowercase letter")
    if not any(ch.isdigit() for ch in password):
        raise ValueError("Password must contain at least 1 digit")
    if not any(not ch.isalnum() and not ch.isspace() for ch in password):
        raise ValueError("Password must contain at least 1 special character")
    return password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext against Argon2id hash."""
    try:
        return _ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


def generate_session_token() -> str:
    """Generate a cryptographically random opaque token."""
    return secrets.token_urlsafe(32)


def generate_csrf_token() -> str:
    """Generate a cryptographically random CSRF token."""
    return secrets.token_urlsafe(24)


def hash_token(token: str) -> str:
    """SHA-256 hash of opaque token for database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding-window rate limiter keyed by (action, key)."""

    def __init__(self):
        self._buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, action: str, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        bucket_key = (action, key)
        with self._lock:
            q = self._buckets[bucket_key]
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= limit:
                raise RateLimitError()
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


rate_limiter = SlidingWindowRateLimiter()
