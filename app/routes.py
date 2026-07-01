import csv
from datetime import datetime, timedelta
from io import StringIO
import os

from flask import (
    current_app,
    Blueprint,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models import Attendance, Course, Enrollment, LectureSession, User
from app.utils import (
    BadSignature,
    SignatureExpired,
    haversine_m,
    make_session_token,
    qr_png_base64,
    sse_push,
    sse_stream_generator,
    verify_session_token,
)

main = Blueprint("main", __name__)


def role_required(*roles):
    def deco(fn):
        from functools import wraps

        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("main.login"))
            if current_user.role not in roles:
                flash("Access denied.", "danger")
                return redirect(url_for("main.landing"))
            return fn(*args, **kwargs)

        return wrapper

    return deco


@main.route("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html")


@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("main.login"))

        login_user(user)
        return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@main.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.landing"))


@main.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "ADMIN":
        return redirect(url_for("main.admin_dashboard"))
    if current_user.role == "LECTURER":
        return redirect(url_for("main.lecturer_dashboard"))
    return redirect(url_for("main.student_dashboard"))


# ---------------- ADMIN ----------------

@main.route("/admin")
@login_required
@role_required("ADMIN")
def admin_dashboard():
    users = User.query.order_by(User.created_at.desc()).all()
    courses = Course.query.order_by(Course.created_at.desc()).all()

    lecturers = User.query.filter_by(role="LECTURER").all()
    students = User.query.filter_by(role="STUDENT").all()

    enrollments = Enrollment.query.all()
    return render_template(
        "admin/dashboard.html",
        users=users,
        courses=courses,
        lecturers=lecturers,
        students=students,
        enrollments=enrollments,
    )


@main.route("/admin/users/create", methods=["POST"])
@login_required
@role_required("ADMIN")
def admin_create_user():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "").strip().upper()
    matric_no = request.form.get("matric_no", "").strip() or None

    if role not in {"ADMIN", "LECTURER", "STUDENT"}:
        flash("Invalid role.", "danger")
        return redirect(url_for("main.admin_dashboard"))

    if not full_name or not email or not password:
        flash("Please fill all required fields.", "danger")
        return redirect(url_for("main.admin_dashboard"))

    if User.query.filter_by(email=email).first():
        flash("Email already exists.", "danger")
        return redirect(url_for("main.admin_dashboard"))

    if matric_no and User.query.filter_by(matric_no=matric_no).first():
        flash("Matric number already exists.", "danger")
        return redirect(url_for("main.admin_dashboard"))

    user = User(
        full_name=full_name,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        matric_no=matric_no,
    )
    db.session.add(user)
    db.session.commit()

    flash("User created.", "success")
    return redirect(url_for("main.admin_dashboard"))


@main.route("/admin/courses/create", methods=["POST"])
@login_required
@role_required("ADMIN")
def admin_create_course():
    code = request.form.get("code", "").strip().upper()
    title = request.form.get("title", "").strip()
    lecturer_id = request.form.get("lecturer_id")

    if not code or not title or not lecturer_id:
        flash("Please fill all required fields.", "danger")
        return redirect(url_for("main.admin_dashboard"))

    if Course.query.filter_by(code=code).first():
        flash("Course code already exists.", "danger")
        return redirect(url_for("main.admin_dashboard"))

    course = Course(code=code, title=title, lecturer_id=int(lecturer_id))
    db.session.add(course)
    db.session.commit()

    flash("Course created.", "success")
    return redirect(url_for("main.admin_dashboard"))


@main.route("/admin/enroll", methods=["POST"])
@login_required
@role_required("ADMIN")
def admin_enroll_student():
    course_id = request.form.get("course_id")
    student_id = request.form.get("student_id")

    if not course_id or not student_id:
        flash("Select a course and student.", "danger")
        return redirect(url_for("main.admin_dashboard"))

    existing = Enrollment.query.filter_by(course_id=int(course_id), student_id=int(student_id)).first()
    if existing:
        flash("Student already enrolled in this course.", "warning")
        return redirect(url_for("main.admin_dashboard"))

    enr = Enrollment(course_id=int(course_id), student_id=int(student_id))
    db.session.add(enr)
    db.session.commit()

    flash("Student enrolled.", "success")
    return redirect(url_for("main.admin_dashboard"))


@main.route("/admin/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@role_required("ADMIN")
def admin_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get("new_password", "")
    if len(new_password) < 8:
        flash("Password must be at least 8 characters.", "danger")
        return redirect(url_for("main.admin_dashboard"))

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    flash(f"Password reset for {user.full_name}.", "success")
    return redirect(url_for("main.admin_dashboard"))


@main.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("ADMIN")
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)

    # Can't delete the account you're currently signed in as.
    if user.id == current_user.id:
        flash("You can't delete your own account while signed in.", "danger")
        return redirect(url_for("main.admin_dashboard"))

    # Never remove the last remaining admin — that would lock everyone out.
    if user.role == "ADMIN" and User.query.filter_by(role="ADMIN").count() <= 1:
        flash("Can't delete the last admin account.", "danger")
        return redirect(url_for("main.admin_dashboard"))

    # Lecturers own courses/sessions; deleting them would wipe other people's
    # data, so require those courses to be removed or reassigned first.
    if user.role == "LECTURER" and Course.query.filter_by(lecturer_id=user.id).first():
        flash(
            "This lecturer still has courses. Delete or reassign their courses first.",
            "warning",
        )
        return redirect(url_for("main.admin_dashboard"))

    # Clean up this user's own dependent rows (their attendance + enrollments).
    Attendance.query.filter_by(student_id=user.id).delete()
    Enrollment.query.filter_by(student_id=user.id).delete()

    name = user.full_name
    db.session.delete(user)
    db.session.commit()
    flash(f"Deleted user {name}.", "success")
    return redirect(url_for("main.admin_dashboard"))


# ---------------- ACCOUNT ----------------

@main.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if not check_password_hash(current_user.password_hash, current):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("main.change_password"))
        if len(new_password) < 8:
            flash("New password must be at least 8 characters.", "danger")
            return redirect(url_for("main.change_password"))
        if new_password != confirm:
            flash("New passwords do not match.", "danger")
            return redirect(url_for("main.change_password"))
        if check_password_hash(current_user.password_hash, new_password):
            flash("New password must be different from your current one.", "warning")
            return redirect(url_for("main.change_password"))

        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("Password updated successfully.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("account/password.html")


@main.route("/admin/reports")
@login_required
@role_required("ADMIN")
def admin_reports():
    sessions = LectureSession.query.order_by(LectureSession.starts_at.desc()).all()
    return render_template("admin/reports.html", sessions=sessions)


# ---------------- LECTURER ----------------

@main.route("/lecturer")
@login_required
@role_required("LECTURER")
def lecturer_dashboard():
    courses = Course.query.filter_by(lecturer_id=current_user.id).order_by(Course.created_at.desc()).all()
    sessions = LectureSession.query.filter_by(lecturer_id=current_user.id).order_by(LectureSession.starts_at.desc()).limit(15).all()
    return render_template("lecturer/dashboard.html", courses=courses, sessions=sessions)


@main.route("/lecturer/session/start/<int:course_id>", methods=["GET", "POST"])
@login_required
@role_required("LECTURER")
def lecturer_start_session(course_id):
    course = Course.query.get_or_404(course_id)
    if course.lecturer_id != current_user.id:
        flash("Access denied.", "danger")
        return redirect(url_for("main.lecturer_dashboard"))

    if request.method == "POST":
        duration_min = int(request.form.get("duration_min", "60"))
        radius_m = int(request.form.get("radius_m", "60"))
        lat = request.form.get("location_lat")
        lng = request.form.get("location_lng")

        try:
            lat = float(lat)
            lng = float(lng)
        except Exception:
            flash("Please provide valid location (lat/lng). Use 'Use my current location'.", "danger")
            return redirect(url_for("main.lecturer_start_session", course_id=course_id))

        now = datetime.utcnow()
        ends = now + timedelta(minutes=duration_min)

        session = LectureSession(
            course_id=course_id,
            lecturer_id=current_user.id,
            starts_at=now,
            ends_at=ends,
            status="ACTIVE",
            location_lat=lat,
            location_lng=lng,
            radius_m=radius_m,
        )
        db.session.add(session)
        db.session.commit()

        flash("Session started.", "success")
        return redirect(url_for("main.lecturer_session", session_id=session.id))

    return render_template("lecturer/start_session.html", course=course)


@main.route("/lecturer/session/<int:session_id>")
@login_required
@role_required("LECTURER")
def lecturer_session(session_id):
    session = LectureSession.query.get_or_404(session_id)
    if session.lecturer_id != current_user.id:
        flash("Access denied.", "danger")
        return redirect(url_for("main.lecturer_dashboard"))

    course = Course.query.get(session.course_id)
    attendance_rows = (
        db.session.query(Attendance, User)
        .join(User, User.id == Attendance.student_id)
        .filter(Attendance.session_id == session_id)
        .order_by(Attendance.marked_at.desc())
        .all()
    )

    return render_template(
        "lecturer/session.html",
        session=session,
        course=course,
        attendance_rows=attendance_rows,
    )


@main.route("/lecturer/session/<int:session_id>/end", methods=["POST"])
@login_required
@role_required("LECTURER")
def lecturer_end_session(session_id):
    session = LectureSession.query.get_or_404(session_id)
    if session.lecturer_id != current_user.id:
        flash("Access denied.", "danger")
        return redirect(url_for("main.lecturer_dashboard"))

    session.status = "ENDED"
    db.session.commit()
    flash("Session ended.", "success")
    return redirect(url_for("main.lecturer_session", session_id=session_id))


@main.route("/api/session/<int:session_id>/qr")
@login_required
@role_required("LECTURER")
def api_session_qr(session_id):
    session = LectureSession.query.get_or_404(session_id)
    if session.lecturer_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403

    # token expiry (seconds)
    ttl = 30
    token = make_session_token(current_app.config["SECRET_KEY"], session_id=session_id)

    base = os.getenv("BASE_URL")
    if base:
        scan_url = f"{base.rstrip('/')}{url_for('main.scan', token=token)}"
    else:
        scan_url = url_for("main.scan", token=token, _external=True)

    png_b64 = qr_png_base64(scan_url)

    return jsonify({"ttl": ttl, "scan_url": scan_url, "png_b64": png_b64})


@main.route("/lecturer/session/<int:session_id>/stream")
@login_required
@role_required("LECTURER")
def lecturer_session_stream(session_id):
    session = LectureSession.query.get_or_404(session_id)
    if session.lecturer_id != current_user.id:
        return "forbidden", 403

    return Response(sse_stream_generator(session_id), mimetype="text/event-stream")


@main.route("/lecturer/session/<int:session_id>/export.csv")
@login_required
@role_required("LECTURER")
def lecturer_export_csv(session_id):
    session = LectureSession.query.get_or_404(session_id)
    if session.lecturer_id != current_user.id:
        return "forbidden", 403

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student Name", "Email", "Matric No", "Marked At (UTC)", "Distance (m)", "Flagged"])

    rows = (
        db.session.query(Attendance, User)
        .join(User, User.id == Attendance.student_id)
        .filter(Attendance.session_id == session_id)
        .order_by(Attendance.marked_at.asc())
        .all()
    )

    for att, user in rows:
        writer.writerow([
            user.full_name,
            user.email,
            user.matric_no or "",
            att.marked_at.isoformat(sep=" ", timespec="seconds"),
            f"{att.distance_m:.2f}",
            "YES" if att.flagged else "NO",
        ])

    resp = Response(output.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = f"attachment; filename=session_{session_id}_attendance.csv"
    return resp


# ---------------- STUDENT ----------------

@main.route("/student")
@login_required
@role_required("STUDENT")
def student_dashboard():
    # Show courses the student is enrolled in
    enrolls = Enrollment.query.filter_by(student_id=current_user.id).all()
    course_ids = [e.course_id for e in enrolls]
    courses = Course.query.filter(Course.id.in_(course_ids)).all() if course_ids else []

    # Active sessions for enrolled courses
    now = datetime.utcnow()
    sessions = []
    if course_ids:
        sessions = (
            LectureSession.query
            .filter(LectureSession.course_id.in_(course_ids))
            .filter(LectureSession.status == "ACTIVE")
            .filter(LectureSession.ends_at > now)
            .order_by(LectureSession.starts_at.desc())
            .all()
        )

    # Existing attendance
    attended = Attendance.query.filter_by(student_id=current_user.id).all()
    attended_session_ids = {a.session_id for a in attended}

    return render_template(
        "student/dashboard.html",
        courses=courses,
        sessions=sessions,
        attended_session_ids=attended_session_ids,
    )


@main.route("/scan")
@login_required
@role_required("STUDENT")
def scan():
    token = request.args.get("token", "")
    # Validate token for quick feedback
    max_age = 35
    try:
        data = verify_session_token(current_app.config["SECRET_KEY"], token, max_age_seconds=max_age)
    except SignatureExpired:
        return render_template("student/scan.html", token=token, token_status="expired")
    except BadSignature:
        return render_template("student/scan.html", token=token, token_status="invalid")

    session_id = int(data["sid"])
    session = LectureSession.query.get(session_id)
    if not session or session.status != "ACTIVE" or session.ends_at <= datetime.utcnow():
        return render_template("student/scan.html", token=token, token_status="ended")

    course = Course.query.get(session.course_id)
    return render_template(
        "student/scan.html",
        token=token,
        token_status="ok",
        course=course,
        session=session,
    )


@main.route("/api/attendance/mark", methods=["POST"])
@login_required
@role_required("STUDENT")
def api_mark_attendance():
    body = request.get_json(force=True, silent=True) or {}
    token = body.get("token", "")
    lat = body.get("lat")
    lng = body.get("lng")
    device_id = body.get("device_id")

    if token == "" or lat is None or lng is None:
        return jsonify({"ok": False, "error": "Missing token or location."}), 400

    try:
        lat = float(lat)
        lng = float(lng)
    except Exception:
        return jsonify({"ok": False, "error": "Invalid location values."}), 400

    # Verify QR token
    max_age = 35
    try:
        data = verify_session_token(current_app.config["SECRET_KEY"], token, max_age_seconds=max_age)
    except SignatureExpired:
        return jsonify({"ok": False, "error": "QR code expired. Scan again."}), 400
    except BadSignature:
        return jsonify({"ok": False, "error": "Invalid QR token."}), 400

    session_id = int(data["sid"])
    session = LectureSession.query.get(session_id)
    if not session:
        return jsonify({"ok": False, "error": "Session not found."}), 404

    now = datetime.utcnow()
    if session.status != "ACTIVE" or session.ends_at <= now:
        return jsonify({"ok": False, "error": "Session is not active."}), 400

    # Check enrollment
    enrolled = Enrollment.query.filter_by(course_id=session.course_id, student_id=current_user.id).first()
    if not enrolled:
        return jsonify({"ok": False, "error": "You are not enrolled in this course."}), 403

    # Check distance
    distance = haversine_m(lat, lng, session.location_lat, session.location_lng)
    if distance > float(session.radius_m):
        return jsonify({
            "ok": False,
            "error": f"You are outside the allowed radius ({session.radius_m}m).",
            "distance_m": distance,
        }), 403

    # Prevent double marking
    existing = Attendance.query.filter_by(session_id=session_id, student_id=current_user.id).first()
    if existing:
        return jsonify({"ok": False, "error": "Attendance already marked for this session."}), 400

    # Anti-impersonation (light): device binding flag
    flagged = 0
    if device_id:
        if current_user.last_device_id and current_user.last_device_id != device_id:
            flagged = 1
        current_user.last_device_id = device_id

    att = Attendance(
        session_id=session_id,
        student_id=current_user.id,
        student_lat=lat,
        student_lng=lng,
        distance_m=float(distance),
        device_id=device_id,
        flagged=flagged,
    )

    db.session.add(att)
    db.session.commit()

    # Real-time update to lecturer
    sse_push(session_id, {
        "student": {
            "id": current_user.id,
            "name": current_user.full_name,
            "matric": current_user.matric_no,
        },
        "marked_at": att.marked_at.isoformat(),
        "distance_m": float(att.distance_m),
        "flagged": bool(att.flagged),
    })

    return jsonify({"ok": True, "distance_m": float(distance), "flagged": bool(flagged)})
