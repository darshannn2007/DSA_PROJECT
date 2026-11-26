# CampusHive

A university student social networking platform built with **FastAPI**, **SQLite**, **vanilla HTML/CSS/JS**, and pure-Python **Data Structures & Algorithms** (`backend/app/dsa/`).

## Tech Stack

- **Backend:** FastAPI, Uvicorn, SQLAlchemy, SQLite (`PRAGMA foreign_keys=ON`), Pydantic v2, Argon2id (`argon2-cffi`)
- **Frontend:** Vanilla HTML5, CSS3 (with light/dark theme toggle), and JavaScript (safe DOM rendering with `textContent`)
- **DSA Engine (Pure Python):**
  - **Social Graph (`backend/app/dsa/graph.py`):** Adjacency list (`dict[int, set[int]]`), BFS shortest path (`collections.deque`), hop count & degree labels, and mutual connections via set intersection (`&`).
  - **Recommendations (`backend/app/dsa/recommendations.py`):** Two-hop "People You May Know" discovery ranked by Jaccard similarity coefficient with deterministic tie-breaking.
  - **Prefix Search (`backend/app/dsa/trie.py`):** Unicode-normalized (NFKC + casefold) Trie for O(L) prefix lookup on usernames and display names.
  - **Feed Merging (`backend/app/dsa/feed.py`):** K-way merge of per-author post streams using `heapq` (`O(K log C)`) with opaque cursor pagination.
  - **Queues & Stacks (`backend/app/dsa/queue.py`, `backend/app/dsa/stack.py`):** Per-user FIFO `deque` notification queue and bounded LIFO undo stack.

## Setup & Run

```powershell
# Install dependencies
pip install -r requirements.txt

# Start the server
python -m uvicorn backend.app.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000` in your browser.

> **Note (Windows Application Control):** `backend/app/main.py` and `backend/app/db/database.py` automatically set `DISABLE_SQLALCHEMY_CEXT_RUNTIME=1` so SQLAlchemy runs cleanly in pure-Python mode if Cython `.pyd` extensions are restricted by Windows policy.

## Running Tests

```powershell
pytest backend/tests
```

## Key API Endpoints (`/api/v1`)

- **Auth:** `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- **Profile:** `GET /me/profile`, `PATCH /me/profile`, `GET /users/{username}`
- **Search:** `GET /users/search?q=...`
- **Connections & Graph:** `POST /connections/requests`, `GET /connections/requests/incoming`, `GET /connections/requests/outgoing`, `POST /connections/requests/{id}/accept`, `POST /connections/requests/{id}/reject`, `DELETE /connections/requests/{id}`, `GET /connections`, `DELETE /connections/{user_id}`, `GET /users/{username}/mutual`, `GET /users/{username}/path`, `GET /me/suggestions`
- **Posts & Feed:** `POST /posts`, `GET /me/posts`, `DELETE /posts/{id}`, `GET /feed`
- **Notifications:** `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all`
