from datetime import datetime
from flask_login import UserMixin
from app import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # ADMIN, LECTURER, STUDENT
    matric_no = db.Column(db.String(50), unique=True, nullable=True)
    last_device_id = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Enrollment(db.Model):
    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("course_id", "student_id", name="uq_course_student"),
    )


class LectureSession(db.Model):
    __tablename__ = "lecture_sessions"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    starts_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="ACTIVE")  # ACTIVE / ENDED

    location_lat = db.Column(db.Float, nullable=False)
    location_lng = db.Column(db.Float, nullable=False)
    radius_m = db.Column(db.Integer, default=60)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("lecture_sessions.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    marked_at = db.Column(db.DateTime, default=datetime.utcnow)
    student_lat = db.Column(db.Float, nullable=False)
    student_lng = db.Column(db.Float, nullable=False)
    distance_m = db.Column(db.Float, nullable=False)

    device_id = db.Column(db.String(120), nullable=True)
    flagged = db.Column(db.Integer, default=0)  # 1 if device mismatch or suspicious

    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id", name="uq_session_student"),
    )
