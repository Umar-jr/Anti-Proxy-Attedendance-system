import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "main.login"
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    # Hosting platforms (Render, Fly.io, etc.) put the app behind a reverse
    # proxy that terminates HTTPS. ProxyFix makes Flask trust the forwarded
    # scheme/host so QR scan URLs come out as https://... not http://...
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # SECRET_KEY signs session cookies AND the short-lived QR tokens.
    # Production MUST set a real value (render.yaml generates one automatically).
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "dev-only-insecure-key-change-me"
    )

    # Database selection:
    #   - If DATABASE_URL is set (e.g. Postgres in production), use it.
    #   - Otherwise fall back to a local SQLite file for development.
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        # Some hosts hand out the legacy "postgres://" scheme; SQLAlchemy
        # needs "postgresql://".
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    else:
        base_dir = os.path.abspath(os.path.dirname(__file__))
        db_dir = os.path.join(base_dir, "database")
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, "attendance.db")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.routes import main
    app.register_blueprint(main)

    with app.app_context():
        from app.models import User  # noqa: F401  (ensures model is registered)
        db.create_all()

        # Seed default admin if none exists
        from app.seed import ensure_default_admin
        ensure_default_admin()

    return app
