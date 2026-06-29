import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    # Local development only. In production the app is served by gunicorn,
    # which imports `app` above and never runs this block.
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(
        debug=debug,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5001")),
        use_reloader=debug,
    )
