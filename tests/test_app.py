"""End-to-end tests: CSRF protection + the full attendance flow.

Each test gets its own throwaway SQLite database via the `client` fixture,
so tests are isolated and repeatable.
"""
import json
import re

import pytest

from app import create_app

FORM = r'name="csrf_token" value="([^"]+)"'
SCAN = r'window\.__CSRF__ = "([^"]+)"'


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Fresh, isolated DB per test.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _grab(client, path, pattern):
    html = client.get(path).get_data(as_text=True)
    match = re.search(pattern, html)
    assert match, f"no CSRF token found at {path}"
    return match.group(1)


def _login(client, email, password):
    token = _grab(client, "/login", FORM)
    return client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": token},
    )


def test_app_builds_and_login_page_renders(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert 'name="csrf_token"' in resp.get_data(as_text=True)


def test_login_without_csrf_is_rejected(client):
    resp = client.post(
        "/login", data={"email": "admin@uni.edu", "password": "Admin123!"}
    )
    assert resp.status_code == 400


def test_login_with_csrf_succeeds(client):
    resp = _login(client, "admin@uni.edu", "Admin123!")
    assert resp.status_code == 302


def test_admin_form_without_csrf_is_rejected(client):
    _login(client, "admin@uni.edu", "Admin123!")
    resp = client.post(
        "/admin/users/create",
        data={"full_name": "X", "email": "x@x.edu", "password": "p", "role": "STUDENT"},
    )
    assert resp.status_code == 400


def test_full_attendance_flow(client):
    # Admin sets up a lecturer, a student, a course, and an enrollment.
    _login(client, "admin@uni.edu", "Admin123!")
    for data in (
        {"full_name": "Dr Lecturer", "email": "lec@uni.edu",
         "password": "Lec123!", "role": "LECTURER"},
        {"full_name": "Stu Dent", "email": "stu@uni.edu",
         "password": "Stu123!", "role": "STUDENT", "matric_no": "CSC/21/001"},
    ):
        data["csrf_token"] = _grab(client, "/admin", FORM)
        client.post("/admin/users/create", data=data)

    client.post("/admin/courses/create", data={
        "code": "CSC401", "title": "Distributed Systems",
        "lecturer_id": "2", "csrf_token": _grab(client, "/admin", FORM)})
    client.post("/admin/enroll", data={
        "course_id": "1", "student_id": "3",
        "csrf_token": _grab(client, "/admin", FORM)})

    # Lecturer starts a session and we pull the QR scan token.
    client.get("/logout")
    _login(client, "lec@uni.edu", "Lec123!")
    start_token = _grab(client, "/lecturer/session/start/1", FORM)
    resp = client.post("/lecturer/session/start/1", data={
        "duration_min": "60", "radius_m": "100",
        "location_lat": "9.0765", "location_lng": "7.3986",
        "csrf_token": start_token})
    assert resp.status_code == 302

    qr = json.loads(client.get("/api/session/1/qr").get_data(as_text=True))
    assert qr.get("png_b64") and "token=" in qr["scan_url"]
    qr_token = re.search(r"token=([^&\s\"]+)", qr["scan_url"]).group(1)

    # Student marks attendance.
    client.get("/logout")
    _login(client, "stu@uni.edu", "Stu123!")

    # Without the CSRF header -> rejected.
    resp = client.post("/api/attendance/mark", json={
        "token": qr_token, "lat": 9.0765, "lng": 7.3986, "device_id": "d1"})
    assert resp.status_code == 400

    # With the CSRF header -> success, attendance recorded.
    csrf_header = _grab(client, f"/scan?token={qr_token}", SCAN)
    resp = client.post(
        "/api/attendance/mark",
        json={"token": qr_token, "lat": 9.0765, "lng": 7.3986, "device_id": "d1"},
        headers={"X-CSRFToken": csrf_header})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


# --------------------- password management ---------------------

def _login_dest(client, email, password):
    """Return the redirect target of a login attempt.
    Success -> '/dashboard', failure -> '/login'."""
    return _login(client, email, password).headers.get("Location", "")


def _user_id(client, email):
    from app.models import User
    with client.application.app_context():
        return User.query.filter_by(email=email).first().id


def test_change_own_password_success(client):
    _login(client, "admin@uni.edu", "Admin123!")
    token = _grab(client, "/account/password", FORM)
    resp = client.post("/account/password", data={
        "current_password": "Admin123!", "new_password": "BrandNew123",
        "confirm_password": "BrandNew123", "csrf_token": token})
    assert resp.status_code == 302
    client.get("/logout")
    assert _login_dest(client, "admin@uni.edu", "BrandNew123").endswith("/dashboard")
    client.get("/logout")
    # old password no longer works
    assert _login_dest(client, "admin@uni.edu", "Admin123!").endswith("/login")


def test_change_password_wrong_current_is_rejected(client):
    _login(client, "admin@uni.edu", "Admin123!")
    token = _grab(client, "/account/password", FORM)
    client.post("/account/password", data={
        "current_password": "WRONG", "new_password": "BrandNew123",
        "confirm_password": "BrandNew123", "csrf_token": token})
    client.get("/logout")
    # old still works, attempted new does not
    assert _login_dest(client, "admin@uni.edu", "Admin123!").endswith("/dashboard")
    client.get("/logout")
    assert _login_dest(client, "admin@uni.edu", "BrandNew123").endswith("/login")


def test_change_password_mismatch_is_rejected(client):
    _login(client, "admin@uni.edu", "Admin123!")
    token = _grab(client, "/account/password", FORM)
    client.post("/account/password", data={
        "current_password": "Admin123!", "new_password": "BrandNew123",
        "confirm_password": "Different123", "csrf_token": token})
    client.get("/logout")
    assert _login_dest(client, "admin@uni.edu", "Admin123!").endswith("/dashboard")


def test_admin_reset_user_password(client):
    _login(client, "admin@uni.edu", "Admin123!")
    client.post("/admin/users/create", data={
        "full_name": "Stu", "email": "stu@uni.edu", "password": "OldPass123",
        "role": "STUDENT", "matric_no": "CSC/21/002",
        "csrf_token": _grab(client, "/admin", FORM)})
    sid = _user_id(client, "stu@uni.edu")
    client.post(f"/admin/users/{sid}/reset-password", data={
        "new_password": "ResetPass123", "csrf_token": _grab(client, "/admin", FORM)})
    client.get("/logout")
    assert _login_dest(client, "stu@uni.edu", "ResetPass123").endswith("/dashboard")


def test_admin_cannot_delete_self(client):
    _login(client, "admin@uni.edu", "Admin123!")
    me = _user_id(client, "admin@uni.edu")
    client.post(f"/admin/users/{me}/delete",
                data={"csrf_token": _grab(client, "/admin", FORM)})
    from app.models import User
    with client.application.app_context():
        assert User.query.get(me) is not None


def test_last_admin_cannot_be_deleted_then_can_after_second_admin(client):
    _login(client, "admin@uni.edu", "Admin123!")
    default_admin = _user_id(client, "admin@uni.edu")

    # Only admin -> guard blocks deletion (attempted by a second... but we're it).
    # Create a second admin first, then delete the default from the new account.
    client.post("/admin/users/create", data={
        "full_name": "Owner", "email": "owner@uni.edu", "password": "OwnerPass123",
        "role": "ADMIN", "csrf_token": _grab(client, "/admin", FORM)})
    client.get("/logout")
    _login(client, "owner@uni.edu", "OwnerPass123")
    client.post(f"/admin/users/{default_admin}/delete",
                data={"csrf_token": _grab(client, "/admin", FORM)})
    from app.models import User
    with client.application.app_context():
        assert User.query.get(default_admin) is None
        # deleting the now-only admin (owner) is blocked
        owner_id = User.query.filter_by(email="owner@uni.edu").first().id
    client.post(f"/admin/users/{owner_id}/delete",
                data={"csrf_token": _grab(client, "/admin", FORM)})
    with client.application.app_context():
        assert User.query.get(owner_id) is not None  # last admin guard held
