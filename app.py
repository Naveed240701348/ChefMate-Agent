"""
ChefMate-Agent — Flask Application Entry Point
"""

import logging
from flask import Flask
from config import config
from routes.api import api_bp
from routes.pages import pages_bp

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    # Register blueprints
    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)

    return app


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=config.DEBUG)
