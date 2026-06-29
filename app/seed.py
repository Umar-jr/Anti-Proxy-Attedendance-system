from werkzeug.security import generate_password_hash
from app import db
from app.models import User


def ensure_default_admin():
    """Create a default admin user if none exists."""
    existing = User.query.filter_by(role="ADMIN").first()
    if existing:
        return

    admin = User(
        full_name="System Administrator",
        email="admin@uni.edu",
        password_hash=generate_password_hash("Admin123!"),
        role="ADMIN",
        matric_no=None,
    )
    db.session.add(admin)
    db.session.commit()
