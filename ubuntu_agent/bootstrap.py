"""Trusted, versioned-by-migration local room, persona and category bootstrap."""

from sqlite3 import Connection

from .models import utc_now

PRINCIPAL_ID = "local-user"
ROOMS = {
    "public_research": ("Public Research", "public"),
    "operations": ("Operations", "internal"),
    "academic": ("Academic", "sensitive"),
    "projects": ("Projects", "sensitive"),
    "opportunities": ("Opportunities", "internal"),
    "personal_vault": ("Personal Vault", "restricted"),
    "health": ("Health", "restricted"),
}
PERSONAS = {
    "task_deadline_manager": ("Task & Deadline Manager", "Manage scoped tasks and reminders", "task_manager"),
    "exam_study_coach": ("Exam & Study Coach", "Manage study tasks and approved notes", "study_coach"),
    "ai_ml_researcher": ("AI/ML Researcher", "Work in assigned project scope", "researcher"),
    "desktop_operator": ("Desktop Operator", "Read active job and approval scope", "desktop_operator"),
}
CATEGORIES = (
    "Academics", "Projects", "Hackathons & Competitions", "AI/ML Research",
    "Robotics", "Quantum Computing", "Opportunities", "Personal / Admin", "Waiting / Follow-up",
)


def seed_trusted_state(connection: Connection) -> None:
    now = utc_now()
    for room_id, (name, sensitivity) in ROOMS.items():
        connection.execute("INSERT OR IGNORE INTO rooms VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (room_id, name, sensitivity, "local", "user_managed", now, now))
    for persona_id, (name, purpose, profile) in PERSONAS.items():
        connection.execute("INSERT OR IGNORE INTO personas VALUES (?, ?, ?, ?, 1, ?, ?)",
                           (persona_id, name, purpose, profile, now, now))
    for order, name in enumerate(CATEGORIES):
        category_id = name.lower().replace("&", "and").replace("/", "-").replace(" ", "_")
        connection.execute("INSERT OR IGNORE INTO categories VALUES (?, ?, ?, 1, ?, ?)",
                           (category_id, name, order, now, now))
