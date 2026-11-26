"""Synthetic Indian university dataset seed script for CampusConnect."""
import os

os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

from PIL import Image, ImageDraw

from backend.app.core.security import hash_password
from backend.app.db.database import Base, SessionLocal, engine
import backend.app.models  # noqa: F401
from backend.app.repositories.connection_repo import ConnectionRepository
from backend.app.repositories.group_repo import GroupRepository
from backend.app.repositories.interaction_repo import InteractionRepository
from backend.app.repositories.notification_repo import NotificationRepository
from backend.app.repositories.post_repo import PostRepository
from backend.app.repositories.profile_repo import ProfileRepository
from backend.app.repositories.user_repo import UserRepository


def _generate_post_image(filename: str, title: str, subtitle: str, bg_rgb: tuple[int, int, int]) -> str:
    os.makedirs("data/uploads", exist_ok=True)
    path = os.path.join("data/uploads", filename)
    img = Image.new("RGB", (800, 420), color=bg_rgb)
    draw = ImageDraw.Draw(img)
    # Draw clean decorative card frame and text
    draw.rectangle([28, 28, 772, 392], outline=(255, 255, 255), width=3)
    draw.rectangle([48, 54, 180, 90], fill=(255, 255, 255))
    draw.text((62, 64), "CAMPUSHIVE", fill=bg_rgb)
    draw.text((48, 140), title, fill=(255, 255, 255))
    draw.text((48, 185), subtitle, fill=(252, 231, 243))
    img.save(path, format="PNG")
    return filename


def seed():
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user_repo = UserRepository(db)
        profile_repo = ProfileRepository(db)
        conn_repo = ConnectionRepository(db)
        post_repo = PostRepository(db)
        inter_repo = InteractionRepository(db)
        notif_repo = NotificationRepository(db)
        group_repo = GroupRepository(db)

        # Remove admin user if present from earlier seed
        existing_admin = user_repo.get_by_username("admin")
        if existing_admin is not None:
            from backend.app.models.user import User
            db.query(User).filter(User.id == existing_admin.id).delete()
            db.commit()

        users_spec = [
            ("aarav", "Aarav Sharma", "B.Tech CSAI", "UG", 2, ["Python", "DSA", "FastAPI"], "student"),
            ("ananya", "Ananya Iyer", "B.Tech EECS", "UG", 2, ["C++", "DSA", "Embedded"], "student"),
            ("rohan", "Rohan Verma", "M.Tech CSAI", "PG", 1, ["Python", "ML", "FastAPI"], "student"),
            ("priya", "Priya Nair", "B.Tech EVE", "UG", 3, ["VLSI", "Python", "Math"], "student"),
            ("kabir", "Kabir Malhotra", "B.Tech CSAI", "UG", 4, ["Distributed Systems", "Go", "DSA"], "student"),
            ("sneha", "Sneha Kulkarni", "M.Tech AI", "PG", 2, ["Deep Learning", "PyTorch", "Python"], "student"),
            ("vikram", "Vikram Reddy", "B.Tech EECS", "UG", 1, ["Robotics", "C++", "ROS"], "student"),
            ("meera", "Meera Krishnan", "B.Tech CSAI", "UG", 3, ["UI/UX", "JavaScript", "HTML/CSS"], "student"),
            ("arjun", "Arjun Patel", "M.Tech Data Science", "PG", 1, ["SQL", "Python", "Statistics"], "student"),
            ("diya", "Diya Deshmukh", "B.Tech EVE", "UG", 2, ["Signal Processing", "MATLAB", "Python"], "student"),
        ]

        created = {}
        pw_hash = hash_password("Password@123")
        for uname, dname, prog, deg, yr, skills, role in users_spec:
            u = user_repo.get_by_username(uname)
            if u is None:
                u = user_repo.create_user(
                    username=uname,
                    password_hash=pw_hash,
                    email=f"{uname}@campus.edu.in",
                    role=role,
                )
                profile_repo.update(
                    u.id,
                    display_name=dname,
                    programme=prog,
                    degree_level=deg,
                    year=yr,
                    bio=f"{dname} — {deg} {prog} (Year {yr})",
                )
                profile_repo.set_skills(u.id, skills)
            created[uname] = u

        # Ensure every user has at least 1 accepted connection (including arjun)
        accepted_pairs = [
            ("aarav", "ananya"),
            ("aarav", "priya"),
            ("ananya", "rohan"),
            ("priya", "rohan"),
            ("rohan", "kabir"),
            ("kabir", "sneha"),
            ("ananya", "meera"),
            ("meera", "vikram"),
            ("priya", "diya"),
            ("arjun", "rohan"),
        ]
        for a, b in accepted_pairs:
            if conn_repo.get_connection(created[a].id, created[b].id) is None:
                req = conn_repo.create_request(created[a].id, created[b].id)
                conn_repo.accept_request(req)

        # Pending directed connection request (vikram -> aarav)
        if conn_repo.get_any_pending_between(created["vikram"].id, created["aarav"].id) is None:
            pending_req = conn_repo.create_request(created["vikram"].id, created["aarav"].id)
            notif_repo.create(
                recipient_id=created["aarav"].id,
                actor_id=created["vikram"].id,
                type="connection_request",
                entity_type="connection_request",
                entity_id=pending_req.id,
            )

        # Connect Darshan (if present) -> aarav so Darshan has 1st, 2nd, and 3rd degree connections
        darshan = user_repo.get_by_username("Darshan")
        if darshan is not None and conn_repo.get_connection(darshan.id, created["aarav"].id) is None:
            req = conn_repo.create_request(darshan.id, created["aarav"].id)
            conn_repo.accept_request(req)

        # Generate sample post images with Pillow
        img_energy = _generate_post_image(
            "seed_energy_monitor.png",
            "Smart Campus Energy Monitor",
            "IoT Sensor Node + FastAPI Real-Time Dashboard",
            (190, 24, 93),
        )
        img_dsa = _generate_post_image(
            "seed_dsa_graph.png",
            "CampusHive Graph & DSA Engine",
            "Adjacency List | BFS Shortest Path | Jaccard | Trie | Heap",
            (157, 23, 77),
        )
        img_study = _generate_post_image(
            "seed_study_session.png",
            "Weekend Algorithms Study Session",
            "Graph Traversals, Heap K-Way Merge & Complexity",
            (131, 24, 67),
        )
        img_portal = _generate_post_image(
            "seed_club_portal.png",
            "Accessible Student Club Portal",
            "Light Pink & Near-Black Theme | Keyboard Navigation",
            (219, 39, 119),
        )

        # Posts + likes + comments + replies (only if not already seeded)
        if not post_repo.get_user_posts(created["aarav"].id, limit=1):
            p1 = post_repo.create(
                created["ananya"].id,
                "Looking for teammates for the Smart Campus Energy Monitor hardware + FastAPI dashboard!",
                visibility="campus",
                image_filename=img_energy,
            )
            p2 = post_repo.create(
                created["aarav"].id,
                "Just finished implementing BFS shortest path, Jaccard recommendations, and Trie prefix search in pure Python.",
                visibility="campus",
                image_filename=img_dsa,
            )
            p3 = post_repo.create(
                created["rohan"].id,
                "Hosting a weekend study session on Graph Algorithms and Heap-based K-Way Merging.",
                visibility="campus",
                image_filename=img_study,
            )
            p4 = post_repo.create(
                created["meera"].id,
                "Redesigned our student club portal with accessible keyboard navigation and dark mode.",
                visibility="campus",
                image_filename=img_portal,
            )

            inter_repo.add_like(created["aarav"].id, p1.id)
            inter_repo.add_like(created["rohan"].id, p1.id)
            inter_repo.add_like(created["priya"].id, p3.id)
            inter_repo.add_like(created["ananya"].id, p3.id)

            c1 = inter_repo.create_comment(p1.id, created["aarav"].id, "Count me in for the FastAPI backend!")
            inter_repo.create_comment(p1.id, created["ananya"].id, "Awesome! Let's sync after the 4 PM lab.", parent_comment_id=c1.id)
            inter_repo.create_comment(p3.id, created["priya"].id, "Will you cover Dijkstra and BFS complexity too?")
        else:
            # Attach images to existing seeded posts that don't have one yet
            img_by_user = {
                created["ananya"].id: img_energy,
                created["aarav"].id: img_dsa,
                created["rohan"].id: img_study,
                created["meera"].id: img_portal,
            }
            for uid, fname in img_by_user.items():
                for p in post_repo.get_user_posts(uid, limit=5):
                    if not p.image_filename:
                        p.image_filename = fname
                        p.visibility = "campus"
            db.commit()

        # Campus Groups (only if not already seeded)
        existing_group_names = {g.name for g in group_repo.list_all()}
        if "DSA & Competitive Coding Circle" not in existing_group_names:
            g1 = group_repo.create_group(
                name="DSA & Competitive Coding Circle",
                description="Weekly algorithms, graph theory, and placement prep.",
                visibility="campus",
                membership_policy="open",
                creator_id=created["ananya"].id,
            )
            group_repo.add_member(g1.id, created["rohan"].id)
            group_repo.add_member(g1.id, created["kabir"].id)
            group_repo.add_member(g1.id, created["priya"].id)

        if "AI & Systems Research Lab" not in existing_group_names:
            g2 = group_repo.create_group(
                name="AI & Systems Research Lab",
                description="Paper reading group for ML, PyTorch, and distributed systems.",
                visibility="campus",
                membership_policy="request",
                creator_id=created["sneha"].id,
            )
            group_repo.add_member(g2.id, created["rohan"].id)
            group_repo.add_member(g2.id, created["kabir"].id)

        print("Seeded 11 synthetic Indian users (password: Password@123), graph edges, posts, and 2 groups.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
