import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / "instance" / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'instance' / 'skyframe.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 7
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_CHECK_DEFAULT = True
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024  # 12MB uploads max
    UPLOAD_PATH = PROJECT_ROOT / "uploads"
    IMAGE_SUBDIR = "images"
    THUMB_SUBDIR = "thumbs"
    AVATAR_SUBDIR = "avatars"
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    IMAGE_PROCESS_SIZE = (1920, 1920)
    THUMB_SIZE = (640, 640)
    AVATAR_SIZE = (400, 400)
    FEED_PAGE_SIZE = 6
    PREFERRED_URL_SCHEME = "https"
    CACHE_TYPE = "simple"
    REPORT_EMAIL = None
    CSP_FRAME_SRC = "'self'"
    CSP_IMG_SRC = "'self' data:"
    CSP_FONT_SRC = "'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://fonts.gstatic.com"
    CSP_STYLE_SRC = "'self' https://cdn.jsdelivr.net https://fonts.googleapis.com"
    CSP_SCRIPT_SRC = "'self' https://cdn.jsdelivr.net"
    SHARE_PATH = PROJECT_ROOT / "instance" / "shares"
    ARCHIVE_SUBDIR = "archives"

    @classmethod
    def init_app(cls, app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    PREFERRED_URL_SCHEME = "http"


class ProductionConfig(Config):
    DEBUG = False
    HSTS_SECONDS = 31536000
    HSTS_INCLUDE_SUBDOMAINS = True
    HSTS_PRELOAD = True
