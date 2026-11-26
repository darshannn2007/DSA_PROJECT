"""End-to-end API, security, DSA integration, and page tests (v1.3)."""
import io
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from PIL import Image


def _make_png_bytes(width: int = 16, height: int = 16) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(37, 99, 235)).save(buf, format="PNG")
    return buf.getvalue()


def _csrf(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("csrf_token", "")
    return {"X-CSRF-Token": token} if token else {}


@pytest.fixture()
def app_client(monkeypatch):
    tmp_dir = tempfile.mkdtemp()
    db_file = os.path.join(tmp_dir, "test_campusconnect.db")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("EXPOSE_RESET_TOKEN_FOR_TESTS", "true")

    from backend.app.core.security import rate_limiter
    rate_limiter.reset()

    from backend.app.main import app

    with TestClient(app) as client:
        yield app, client


def test_health_ready_and_pages(app_client):
    _, client = app_client
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}

    for page in [
        "/", "/login", "/register", "/home", "/feed", "/connections",
        "/requests", "/discover", "/groups", "/search", "/my-profile",
        "/notifications", "/settings", "/help", "/terms", "/privacy",
        "/profile", "/profile/alice",
    ]:
        rp = client.get(page)
        assert rp.status_code == 200, f"Page {page} failed"

    assert client.get("/static/css/styles.css").status_code == 200
    assert client.get("/static/js/app.js").status_code == 200


def test_production_config_fails_closed(monkeypatch):
    from backend.app.core.config import Settings

    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "dev-secret-change-me-in-production")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    with pytest.raises(RuntimeError):
        Settings().validate_production_settings()


def test_full_social_and_security_workflow(app_client, monkeypatch):
    app, _ = app_client
    c_alice = TestClient(app)
    c_bob = TestClient(app)
    c_charlie = TestClient(app)

    # Password policy checks: missing special, uppercase, digit, or space must fail 422
    for bad_pw in ["password123", "Password123", "password@1", "PASSWORD@1", "Pass@ 123"]:
        bad_r = c_alice.post("/api/v1/auth/register", json={
            "username": "baduser", "password": bad_pw
        })
        assert bad_r.status_code == 422, f"Expected 422 for weak password {bad_pw!r}"

    # Register (auto-sets session + csrf cookies)
    r = c_alice.post("/api/v1/auth/register", json={
        "username": "alice", "password": "Password@123", "email": "alice@uni.edu"
    })
    assert r.status_code == 201
    assert c_alice.get("/api/v1/auth/me").status_code == 200

    # Verify password is saved as Argon2id hash in SQLite, never plaintext
    from backend.app.db.database import SessionLocal
    from backend.app.models.user import User as UserModel
    with SessionLocal() as db_check:
        u_row = db_check.query(UserModel).filter(UserModel.username == "alice").first()
        assert u_row is not None
        assert u_row.password_hash.startswith("$argon2id$")
        assert "Password@123" not in u_row.password_hash

    # CSRF check: missing header on state-changing request must fail 403
    assert c_alice.patch("/api/v1/me/profile", json={"bio": "no csrf"}).status_code == 403

    # PG year > 2 must fail 422
    assert c_alice.patch("/api/v1/me/profile", headers=_csrf(c_alice), json={
        "degree_level": "PG", "year": 3
    }).status_code == 422

    # Profile update + UG/PG + visibility
    r = c_alice.patch("/api/v1/me/profile", headers=_csrf(c_alice), json={
        "display_name": "Alice Smith",
        "programme": "B.Tech CSAI",
        "degree_level": "UG",
        "year": 2,
        "bio": "Loves algorithms",
        "skills": ["Python", "DSA"],
        "visibility": "connections",
    })
    assert r.status_code == 200
    assert r.json()["skills"] == ["DSA", "Python"]
    assert r.json()["degree_level"] == "UG"

    # Register bob & charlie
    bob_id = c_bob.post("/api/v1/auth/register", json={
        "username": "bob", "password": "Password@123"
    }).json()["id"]
    c_charlie.post("/api/v1/auth/register", json={
        "username": "charlie", "password": "Password@123"
    })

    # Trie search
    r = c_alice.get("/api/v1/users/search?q=bo")
    assert r.status_code == 200
    assert r.json()["count"] == 1
    assert r.json()["users"][0]["username"] == "bob"

    # Connection requests + duplicate/reverse guard
    req1_id = c_alice.post(
        "/api/v1/connections/requests",
        headers=_csrf(c_alice),
        json={"receiver_id": bob_id, "username": "bob"},
    ).json()["id"]
    assert c_bob.post(
        "/api/v1/connections/requests",
        headers=_csrf(c_bob),
        json={"username": "alice"},
    ).status_code == 409

    notifs = c_bob.get("/api/v1/notifications").json()
    assert notifs["unread_count"] == 1
    assert c_bob.post(
        f"/api/v1/notifications/{notifs['notifications'][0]['id']}/read",
        headers=_csrf(c_bob),
    ).status_code == 200

    assert c_bob.post(
        f"/api/v1/connections/requests/{req1_id}/accept",
        headers=_csrf(c_bob),
    ).status_code == 200

    req2_id = c_bob.post(
        "/api/v1/connections/requests",
        headers=_csrf(c_bob),
        json={"username": "charlie"},
    ).json()["id"]
    assert c_charlie.post(
        f"/api/v1/connections/requests/{req2_id}/accept",
        headers=_csrf(c_charlie),
    ).status_code == 200

    # Graph: mutuals, shortest path, Jaccard suggestions
    assert c_alice.get("/api/v1/users/charlie/mutual").json()["count"] == 1
    path = c_alice.get("/api/v1/users/charlie/path").json()
    assert path["hop_count"] == 2
    assert path["degree_label"] == "2nd degree"
    assert [u["username"] for u in path["path"]] == ["alice", "bob", "charlie"]
    assert c_alice.get("/api/v1/me/suggestions").json()[0]["user"]["username"] == "charlie"

    # Posts, Likes, Comments, Replies, UndoStack, Trending Feed
    p1 = c_alice.post("/api/v1/posts", headers=_csrf(c_alice), json={"body": "Hello from Alice!"}).json()
    p2 = c_bob.post("/api/v1/posts", headers=_csrf(c_bob), json={"body": "Hello from Bob!"}).json()

    assert c_alice.post(f"/api/v1/posts/{p2['id']}/like", headers=_csrf(c_alice)).json()["liked"] is True
    c1 = c_alice.post(f"/api/v1/posts/{p2['id']}/comments", headers=_csrf(c_alice), json={"body": "Nice!"}).json()
    assert c_bob.post(f"/api/v1/posts/{p2['id']}/comments", headers=_csrf(c_bob), json={
        "body": "Thanks!", "parent_comment_id": c1["id"]
    }).status_code == 201

    # Soft-delete p1 -> UndoStack restores it!
    assert c_alice.delete(f"/api/v1/posts/{p1['id']}", headers=_csrf(c_alice)).status_code == 200
    assert c_alice.post("/api/v1/me/undo", headers=_csrf(c_alice)).status_code == 200
    assert len(c_alice.get("/api/v1/me/posts").json()) == 1

    # Profile posts endpoint: visible to connected bob, hidden to unconnected charlie (connections-only)
    assert len(c_bob.get("/api/v1/users/alice/posts").json()) == 1
    assert c_charlie.get("/api/v1/users/alice/posts").json() == []

    # Connect charlie -> alice for trending test
    req_ac = c_alice.post("/api/v1/connections/requests", headers=_csrf(c_alice), json={"username": "charlie"}).json()["id"]
    assert c_charlie.post(f"/api/v1/connections/requests/{req_ac}/accept", headers=_csrf(c_charlie)).status_code == 200
    assert c_charlie.post(f"/api/v1/posts/{p2['id']}/like", headers=_csrf(c_charlie)).status_code == 200
    assert c_alice.get("/api/v1/feed/trending").json()[0]["id"] == p2["id"]

    # Groups: request-to-join approval, group posts, private group isolation
    g_req = c_bob.post("/api/v1/groups", headers=_csrf(c_bob), json={
        "name": "Private Study", "description": "Restricted", "visibility": "campus", "membership_policy": "request"
    }).json()
    assert c_alice.post(f"/api/v1/groups/{g_req['id']}/join", headers=_csrf(c_alice)).json()["my_status"] == "pending"
    alice_id = c_alice.get("/api/v1/auth/me").json()["id"]
    assert c_bob.post(
        f"/api/v1/groups/{g_req['id']}/join-requests/{alice_id}/approve",
        headers=_csrf(c_bob),
    ).status_code == 200
    assert c_alice.post(
        f"/api/v1/groups/{g_req['id']}/posts",
        headers=_csrf(c_alice),
        json={"body": "Group note"},
    ).status_code == 201
    assert len(c_alice.get(f"/api/v1/groups/{g_req['id']}/feed").json()) == 1
    assert c_charlie.post(
        f"/api/v1/groups/{g_req['id']}/posts",
        headers=_csrf(c_charlie),
        json={"body": "Not a member"},
    ).status_code == 403

    # Media Upload (Pillow PNG ok, SVG rejected, connections-only IDOR blocked for non-connection)
    c_dave = TestClient(app)
    c_dave.post("/api/v1/auth/register", json={"username": "dave", "password": "Password@123"})

    up_ok = c_alice.post(
        "/api/v1/me/avatar",
        headers=_csrf(c_alice),
        files={"file": ("a.png", _make_png_bytes(), "image/png")},
    )
    assert up_ok.status_code == 200
    avatar_url = up_ok.json()["avatar_url"]
    assert c_alice.get(avatar_url).status_code == 200
    assert c_bob.get(avatar_url).status_code == 200
    assert c_dave.get(avatar_url).status_code == 403  # Alice's profile visibility is 'connections'
    assert c_alice.delete("/api/v1/me/avatar", headers=_csrf(c_alice)).status_code == 200

    up_bad = c_alice.post(
        "/api/v1/me/avatar",
        headers=_csrf(c_alice),
        files={"file": ("x.svg", b"<svg></svg>", "image/svg+xml")},
    )
    assert up_bad.status_code == 422

    # Authenticated Change Password + Session Rotation + Preferences + Consent
    assert c_alice.post("/api/v1/me/password", headers=_csrf(c_alice), json={
        "current_password": "Password@123", "new_password": "UpdatedPass@123"
    }).status_code == 200
    assert len(c_alice.get("/api/v1/me/sessions").json()) == 1

    assert c_alice.patch("/api/v1/me/preferences", headers=_csrf(c_alice), json={
        "theme": "dark", "reduced_motion": True
    }).json()["theme"] == "dark"
    assert c_alice.post("/api/v1/me/consent", headers=_csrf(c_alice), json={
        "policy_version": "1.3", "analytics_allowed": False
    }).status_code == 201

    # Password Reset: non-disclosure in non-test ENV, disclosure only in test ENV
    monkeypatch.setenv("ENV", "development")
    assert "reset_token" not in c_alice.post("/api/v1/auth/password-reset/request", json={"username": "alice"}).json()
    monkeypatch.setenv("ENV", "test")

    reset_req = c_alice.post("/api/v1/auth/password-reset/request", json={"username": "alice"}).json()
    assert "reset_token" in reset_req
    assert c_alice.post("/api/v1/auth/password-reset/confirm", json={
        "token": reset_req["reset_token"], "new_password": "FinalPassword@123"
    }).status_code == 200
    # Session invalidated on password reset
    assert c_alice.get("/api/v1/auth/me").status_code == 401
    assert c_alice.post("/api/v1/auth/login", json={
        "username": "alice", "password": "FinalPassword@123"
    }).status_code == 200

    # Account Delete
    assert c_dave.delete("/api/v1/me/account", headers=_csrf(c_dave)).status_code == 200
    assert c_dave.get("/api/v1/auth/me").status_code == 401
