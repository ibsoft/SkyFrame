import os
import secrets
from pathlib import Path

from flask import Flask, g, request

from .api import bp as api_bp
from .auth import bp as auth_bp
from .config import Config, DevelopmentConfig, ProductionConfig
from .extensions import csrf_protect, db, limiter, login_manager, migrate
from .main import bp as main_bp
from .models import User

PROJECT_ROOT = Path(__file__).resolve().parent.parent


configurations = {
    "production": ProductionConfig,
    "development": DevelopmentConfig,
    "default": DevelopmentConfig,
}


def create_app(config_name: str | None = None):
    config_name = config_name or os.getenv("FLASK_ENV", "default")
    app = Flask(
        __name__,
        static_folder=str(PROJECT_ROOT / "static"),
        template_folder=str(PROJECT_ROOT / "templates"),
        instance_relative_config=True,
    )
    app.config.from_object(configurations.get(config_name, ProductionConfig))
    Config.init_app(app)

    app.config.setdefault("JSON_SORT_KEYS", False)
    login_manager.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    csrf_protect.init_app(app)
    limiter.init_app(app)

    @login_manager.user_loader
    def _load_user(user_id):
        return User.query.get(int(user_id))

    @app.before_request
    def set_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.after_request
    def set_security_headers(response):
        nonce = getattr(g, "csp_nonce", "")
        csp = (
            f"default-src 'self'; "
            f"script-src {Config.CSP_SCRIPT_SRC} 'nonce-{nonce}'; "
            f"style-src {Config.CSP_STYLE_SRC} 'nonce-{nonce}'; "
            f"img-src {Config.CSP_IMG_SRC}; "
            f"font-src {Config.CSP_FONT_SRC}; "
            f"connect-src {Config.CSP_CONNECT_SRC}; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
        )
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer-when-downgrade")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cross-Origin-Embedder-Policy", "require-corp")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("X-DNS-Prefetch-Control", "off")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    Path(app.config["UPLOAD_PATH"]).mkdir(parents=True, exist_ok=True)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)

    return app
