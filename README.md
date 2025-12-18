# SkyFrame
SkyFrame is a single-service Python Flask MVP that delivers a TikTok-style vertical feed for astronomical images. It pairs a secure, production-ready backend (Flask app factory, PostgreSQL, SQLAlchemy, Alembic, Flask-Login/WTF, Argon2, Flask-Limiter) with a Bootstrap 5 + vanilla JS + PWA frontend (scroll snap, sticky nav, service worker) and local asset handling (uploads, thumbnails, avatars).

## Highlights

- **Security by default**: CSP + HSTS + cookie hardening + CSRF on every state-changing request + rate limits on auth/actions + Argon2 password hashing + validated payloads and uploads (MIME, extension, re-encoded with Pillow, UUID filenames).
- **Structured app factory**: Blueprints for `auth`, `main`, and `api`, shared extensions (`SQLAlchemy`, `Login`, `CSRF`, `Limiter`, `Migrate`), environment-aware config classes, and Alembic migrations for schema versioning.
- **TikTok-style UX**: Full-viewport feed cards with CSS scroll snapping, skeleton actions, vertical action rail (likes, favorites, follow, download, comments), infinite JSON feed, comment bottom sheet, sticky bottom navigation, mobile-first design, and PWA install flow + offline fallback.
- **Uploads & media**: Local `uploads/` storage with thumbnails, avatars (Gravatar + upload), download endpoint (with safe headers and optional thumbnails), and ready hooks to swap in S3/MinIO later.
- **Search & filtering**: Search page filters by observer, object, category, datetime range, and free-text notes/tags, updating via familiar Bootstrap forms.
- **API surface**: Cursor-paginated feed, like/unlike, favorite/unfavorite, follow/unfollow, comments CRUD, secure downloads (headers sanitized), rate limits, and CSRF protection even for JSON endpoints.

## Getting started

1. **Install dependencies**
   ```bash
   python -m pip install -r requirements.txt
   ```

2. **Configure secrets**
   - Copy `instance/.env` or create your own (see `[CONFIGURATION](#configuration)` below).
   - Ensure `SECRET_KEY` and `DATABASE_URL` are set. `DATABASE_URL` must point to PostgreSQL (e.g. `postgresql+psycopg2://user:pass@localhost/skyframe`).

3. **Initialize the database**
   ```bash
   flask db upgrade
   ```
   The Alembic configuration in `alembic.ini` reads the same `SQLALCHEMY_DATABASE_URI` that your Flask config uses.

4. **Run the development server**
   ```bash
   flask run
   ```
   Or for production-style launches:
   ```bash
   gunicorn wsgi:app
   ```

5. **Visit the app**
   - Register, log in, upload an image (with metadata), enjoy the infinite TikTok-like feed, like/favorite/follow/comment, search, and install it as a PWA. The service worker caches assets + an offline page.

## Project layout

```
.
├── alembic.ini
├── migrations/          # Alembic env + schema versions
├── requirements.txt
├── wsgi.py              # Entry point for WSGI servers
├── config.py            # Config classes (dev/prod) + security defaults
├── skyframe/            # Flask package
│   ├── __init__.py      # App factory + security headers
│   ├── extensions.py    # Shared Flask extensions
│   ├── models.py
│   ├── forms.py
│   ├── storage.py       # Image/avatar processing helpers
│   ├── main/            # Blueprint with feed/upload/profile/search routes
│   ├── auth/            # Login/register/logout
│   └── api/             # JSON feed + action endpoints
├── templates/           # Jinja2 views (base, feed, auth, profile, upload, search)
├── static/
│   ├── css/
│   ├── js/
│   ├── icons/
│   └── offline.html     # Offline fallback for service worker
└── uploads/             # Local storage for images/avatars (created automatically)
```

## Configuration

- The default config loads `instance/.env`. Update it with `SECRET_KEY` and `DATABASE_URL`.
- Production config enforces secure cookies, HSTS, CSP, and other headers; development mode relaxes secure cookies for local testing.
- Adjust `FEED_PAGE_SIZE`, `MAX_CONTENT_LENGTH`, or storage paths directly in `config.py` before deploying.

## Deployment notes

- Use `gunicorn wsgi:app` (or a similar WSGI server) with an HTTPS fronting proxy.
- Ensure `uploads/` is writable by the process and persists between deployments. For scaling, swap `storage.process_image_upload` to upload to S3/MinIO; `Config` exposes `UPLOAD_PATH`, `IMAGE_SUBDIR`, and `THUMB_SUBDIR` for this extension point.
- Keep the `.env` secrets out of source control; use environment-specific config management.
- The service worker caches static assets but not dynamic API responses—clear caches when deploying new assets.

## Security checklist

- All forms use Flask-WTF CSRF protection, and JSON actions validate `X-CSRFToken`.
- Password policy enforces length, uppercase/lowercase, digits, and special characters; Argon2 hashes everything.
- Query sets rely on SQLAlchemy ORM only, with indexed search fields (`category`, `object_name`, `observer_name`, `observed_at`, `created_at`).
- Strict headers: CSP with nonces, HSTS, X-Content-Type-Options, Referrer/Permissions/Frame policies, SameSite & Secure cookies.
- Uploads are validated by extension/mimetype, re-encoded with Pillow, stored with UUID names, and thumbnails auto-generated to mitigate polyglot attacks.

## Running Alembic

```bash
alembic upgrade head       # Apply migrations
alembic revision --autogenerate -m "desc"
alembic downgrade -1
```

Alembic uses the Flask app context (`create_app`) inside `migrations/env.py`, so it shares the same config/metadata.

## Next steps

1. Wire in email confirmations/notifications if needed for social features.
2. Swap local storage for S3/MinIO by implementing a storage backend that still returns `file_path`/`thumb_path`.
3. Add analytics dashboards or admin tools for moderation.
