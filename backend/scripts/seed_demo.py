"""Load demo data: LNMIIT departments, sample faculty with profiles, collaborations and requests.

For development and demos only. Every demo account's email starts with "demo." so it can't
collide with (or email) a real person, and `--remove` deletes exactly what this script made.

Usage (from backend/, venv active):
    python -m scripts.seed_demo            # create (safe to run again: existing demo data is kept)
    python -m scripts.seed_demo --remove   # delete all demo accounts and their data

All demo accounts share one password: DEMO_PASSWORD below (or set the DEMO_PASSWORD env var).
Never run this against a production database.
"""
import argparse
import os
import sys
from datetime import date, datetime, timedelta

from sqlalchemy import delete, func, or_, select

from app.database import SessionLocal
from app.models import (
    Collaboration,
    CollaborationRequest,
    Department,
    ExpertiseKeyword,
    FacultyProfile,
    Notification,
    NotificationType,
    Project,
    ProjectStatus,
    Publication,
    RequestStatus,
    ResearchInterest,
    User,
    UserRole,
    UserStatus,
)
from app.security.hashing import hash_password
from app.services.collaboration import ordered_pair

DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "DemoPass2026")  # demo accounts only
DEMO_PREFIX = "demo."
DOMAIN = "lnmiit.ac.in"

# The real departments are kept by --remove (profiles may come to depend on them)
DEPARTMENTS = {
    "CSE": "Computer Science and Engineering",
    "CCE": "Communication and Computer Engineering",
    "ECE": "Electronics and Communication Engineering",
    "MME": "Mechanical-Mechatronics Engineering",
    "AIDS": "Artificial Intelligence and Data Science",
}

# (key, full name, designation, dept, expertise, interests, publications, projects)
# Names and work are fictional.
FACULTY = [
    ("ananya.iyer", "Dr. Ananya Iyer", "Associate Professor", "CSE",
     ["Machine Learning", "Natural Language Processing"], ["Explainable AI", "Medical Imaging"],
     [("Interpretable Transformers for Clinical Notes", "ACL Findings", 2024),
      ("Low-Resource NER for Indian Languages", "LREC", 2022)],
     [("Explainable triage assistant", ProjectStatus.ongoing, date(2024, 7, 1), None)]),
    ("rohan.mehta", "Dr. Rohan Mehta", "Assistant Professor", "CSE",
     ["Distributed Systems", "Cloud Computing"], ["Edge Computing", "Blockchain"],
     [("Consistency Trade-offs in Edge Caches", "IEEE ICDCS", 2023)],
     [("Campus edge cloud testbed", ProjectStatus.ongoing, date(2025, 1, 15), None)]),
    ("kavita.sharma", "Prof. Kavita Sharma", "Professor", "CSE",
     ["Computer Vision", "Deep Learning"], ["Medical Imaging", "Remote Sensing"],
     [("Self-Supervised Segmentation of Retinal Scans", "MICCAI", 2023),
      ("Crop Health from Multispectral Imagery", "IEEE TGRS", 2021)],
     [("Retinal disease screening", ProjectStatus.past, date(2020, 8, 1), date(2023, 6, 30))]),
    ("arjun.nair", "Dr. Arjun Nair", "Assistant Professor", "CCE",
     ["Wireless Networks", "Internet of Things"], ["Edge Computing", "Smart Cities"],
     [("Energy-Aware Routing for LoRa Meshes", "IEEE IoT Journal", 2024)],
     [("Smart campus sensor network", ProjectStatus.ongoing, date(2024, 2, 1), None)]),
    ("sneha.kulkarni", "Dr. Sneha Kulkarni", "Associate Professor", "CCE",
     ["Network Security", "Cryptography"], ["Blockchain", "Privacy-Preserving ML"],
     [("Lightweight Authentication for IoT Gateways", "ACM AsiaCCS", 2023)],
     []),
    ("vikram.singh", "Prof. Vikram Singh", "Professor", "ECE",
     ["VLSI Design", "Embedded Systems"], ["Edge AI", "Hardware Security"],
     [("A 28nm Accelerator for Sparse CNNs", "IEEE JSSC", 2022)],
     [("Low-power AI accelerator chip", ProjectStatus.ongoing, date(2023, 9, 1), None)]),
    ("meera.joshi", "Dr. Meera Joshi", "Assistant Professor", "ECE",
     ["Signal Processing", "Medical Imaging"], ["Deep Learning", "Wearable Devices"],
     [("Denoising ECG with Learned Wavelets", "IEEE TBME", 2024)],
     [("Wearable ECG monitor", ProjectStatus.ongoing, date(2024, 1, 10), None)]),
    ("rahul.verma", "Dr. Rahul Verma", "Associate Professor", "ECE",
     ["Antenna Design", "RF Engineering"], ["5G Systems", "Wireless Networks"],
     [("Compact MIMO Antennas for Sub-6 GHz", "IEEE AWPL", 2023)],
     []),
    ("pooja.agarwal", "Dr. Pooja Agarwal", "Assistant Professor", "MME",
     ["Robotics", "Control Systems"], ["Reinforcement Learning", "Human-Robot Interaction"],
     [("Adaptive Control of Soft Grippers", "IEEE RA-L", 2024)],
     [("Assistive robotic arm", ProjectStatus.ongoing, date(2024, 8, 1), None)]),
    ("sanjay.rao", "Prof. Sanjay Rao", "Professor", "MME",
     ["Additive Manufacturing", "Materials Engineering"], ["Biomedical Devices", "Smart Materials"],
     [("Lattice Structures for Orthopaedic Implants", "Additive Manufacturing", 2022)],
     [("3D-printed implant prototypes", ProjectStatus.past, date(2019, 7, 1), date(2022, 12, 31))]),
    ("nisha.patel", "Dr. Nisha Patel", "Assistant Professor", "MME",
     ["Mechatronics", "Embedded Systems"], ["Robotics", "Internet of Things"],
     [], []),
    ("aditya.bansal", "Dr. Aditya Bansal", "Associate Professor", "AIDS",
     ["Data Science", "Machine Learning"], ["Recommender Systems", "Explainable AI"],
     [("Fairness Audits for Course Recommenders", "ACM RecSys", 2023)],
     [("Learning analytics platform", ProjectStatus.ongoing, date(2025, 3, 1), None)]),
    ("priya.menon", "Dr. Priya Menon", "Assistant Professor", "AIDS",
     ["Reinforcement Learning", "Optimization"], ["Robotics", "Smart Cities"],
     [("Sample-Efficient RL for Traffic Signals", "AAMAS", 2024)],
     []),
    ("karan.malhotra", "Dr. Karan Malhotra", "Visiting Faculty", "AIDS",
     ["Natural Language Processing", "Large Language Models"], ["Machine Learning", "Education Technology"],
     [], []),
]

# Accepted collaborations, pending requests and a declined one, so dashboards and reports have data
ACCEPTED = [
    ("ananya.iyer", "kavita.sharma", "Medical imaging + NLP for radiology reports?"),
    ("arjun.nair", "rohan.mehta", None),
    ("meera.joshi", "kavita.sharma", "Would love to combine ECG and retinal work."),
    ("pooja.agarwal", "priya.menon", "RL for our assistive arm?"),
    ("vikram.singh", "nisha.patel", None),
]
PENDING = [
    ("aditya.bansal", "ananya.iyer", "Explainability for recommenders - shall we write a proposal together?"),
    ("sneha.kulkarni", "arjun.nair", "Securing the smart campus network."),
    ("karan.malhotra", "aditya.bansal", None),
]
DECLINED = [("rahul.verma", "sanjay.rao", "Antennas for implant telemetry?")]

# Staff accounts for trying the oversight roles
STAFF = [
    ("research.office", "Research Office (Demo)", UserRole.research_admin, None),
    ("hod.cse", "HOD CSE (Demo)", UserRole.dept_mgmt, "CSE"),
]


def email_for(key: str) -> str:
    return f"{DEMO_PREFIX}{key}@{DOMAIN}"


def get_or_create_departments(db) -> dict[str, int]:
    ids = {}
    for code, name in DEPARTMENTS.items():
        dept = db.scalar(select(Department).where(func.lower(Department.name) == name.lower()))
        if dept is None:
            dept = Department(name=name, institute="LNMIIT")
            db.add(dept)
            db.flush()
        ids[code] = dept.id
    return ids


def seed() -> None:
    with SessionLocal() as db:
        dept = get_or_create_departments(db)
        pw = hash_password(DEMO_PASSWORD)
        users: dict[str, int] = {}
        created = 0

        for key, name, desig, d, exp, intr, pubs, projs in FACULTY:
            existing = db.scalar(select(User).where(User.email == email_for(key)))
            if existing:
                users[key] = existing.id
                continue
            u = User(email=email_for(key), full_name=name, hashed_password=pw, role=UserRole.faculty, status=UserStatus.active)
            db.add(u)
            db.flush()
            users[key] = u.id
            db.add(FacultyProfile(
                user_id=u.id, full_name=name, designation=desig, department_id=dept[d],
                bio=f"{desig} in {DEPARTMENTS[d]}. (Demo profile.)",
                expertise_keywords=[ExpertiseKeyword(keyword=k) for k in exp],
                research_interests=[ResearchInterest(topic=t) for t in intr],
                publications=[Publication(title=t, venue=v, year=y) for t, v, y in pubs],
                projects=[Project(title=t, status=s, start_date=sd, end_date=ed,
                                  description="Demo project.") for t, s, sd, ed in projs],
            ))
            created += 1

        for key, name, role, d in STAFF:
            if db.scalar(select(User.id).where(User.email == email_for(key))) is None:
                db.add(User(email=email_for(key), full_name=name, hashed_password=pw, role=role,
                            status=UserStatus.active, department_id=dept[d] if d else None))
                created += 1
        db.flush()

        # Requests: only add ones that don't exist yet, so re-running doesn't duplicate
        def add_request(a, b, message, status, days_ago):
            s, r = users[a], users[b]
            if db.scalar(select(CollaborationRequest.id).where(
                    CollaborationRequest.sender_id == s, CollaborationRequest.recipient_id == r)):
                return None
            when = datetime.utcnow() - timedelta(days=days_ago)
            req = CollaborationRequest(sender_id=s, recipient_id=r, message=message, status=status, sent_at=when,
                                       responded_at=None if status == RequestStatus.pending else when + timedelta(days=1))
            db.add(req)
            db.flush()
            return req

        sender_name = {k: n for k, n, *_ in FACULTY}
        # Spread accepted collaborations over recent months so the activity chart has a shape
        for i, (a, b, msg) in enumerate(ACCEPTED):
            req = add_request(a, b, msg, RequestStatus.accepted, days_ago=20 + i * 35)
            if req:
                x, y = ordered_pair(users[a], users[b])
                db.add(Collaboration(request_id=req.id, faculty_a=x, faculty_b=y, created_at=req.responded_at))
                db.add(Notification(recipient_id=users[a], type=NotificationType.request_accepted, request_id=req.id,
                                    message=f"{sender_name[b]} accepted your collaboration request.",
                                    is_read=True, created_at=req.responded_at))
        for i, (a, b, msg) in enumerate(PENDING):
            req = add_request(a, b, msg, RequestStatus.pending, days_ago=1 + i)
            if req:
                db.add(Notification(recipient_id=users[b], type=NotificationType.request_received, request_id=req.id,
                                    message=f"{sender_name[a]} sent you a collaboration request.", created_at=req.sent_at))
        for a, b, msg in DECLINED:
            req = add_request(a, b, msg, RequestStatus.declined, days_ago=40)
            if req:
                db.add(Notification(recipient_id=users[a], type=NotificationType.request_declined, request_id=req.id,
                                    message=f"{sender_name[b]} declined your collaboration request.",
                                    created_at=req.responded_at))

        db.commit()
        print(f"Demo data ready: {len(DEPARTMENTS)} departments, {created} new accounts "
              f"({len(FACULTY)} faculty + {len(STAFF)} staff in total).")
        print(f"Log in with any demo.*@{DOMAIN} account. The shared demo password is in scripts/seed_demo.py "
              "(DEMO_PASSWORD), unless you set the DEMO_PASSWORD env var.")


def remove() -> None:
    with SessionLocal() as db:
        ids = list(db.scalars(select(User.id).where(User.email.like(f"{DEMO_PREFIX}%@{DOMAIN}"))))
        if not ids:
            print("No demo data found.")
            return
        db.execute(delete(Notification).where(Notification.recipient_id.in_(ids)))
        db.execute(delete(Collaboration).where(or_(Collaboration.faculty_a.in_(ids), Collaboration.faculty_b.in_(ids))))
        db.execute(delete(CollaborationRequest).where(
            or_(CollaborationRequest.sender_id.in_(ids), CollaborationRequest.recipient_id.in_(ids))))
        for p in db.scalars(select(FacultyProfile).where(FacultyProfile.user_id.in_(ids))):
            db.delete(p)  # ORM delete cascades keywords, publications, projects
        db.flush()
        db.execute(delete(User).where(User.id.in_(ids)))
        db.commit()
        print(f"Removed {len(ids)} demo accounts and their data. Departments were kept.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--remove", action="store_true", help="delete all demo accounts and their data")
    args = parser.parse_args()
    remove() if args.remove else seed()
    sys.exit(0)
