import hashlib
import mimetypes
import re
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    current_app,
    jsonify,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required

from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError
from sqlalchemy import func
from werkzeug.utils import secure_filename

from ..config import Config
from ..feed import build_feed_selection, persist_seen_for_feed
from ..astro import planetary_coordinates
from ..extensions import csrf_protect, db, limiter
from ..forms import CATEGORY_CHOICES as FORM_CATEGORY_CHOICES
from ..models import Comment, Favorite, Follow, Image, Like, Motd, MotdSeen, User
from ..share_storage import create_share_token
from ..storage import perceptual_hashes_for_bytes, sha256_file, winjupos_label_from_metadata
from . import bp


CATEGORY_CHOICES = {name for name, _ in FORM_CATEGORY_CHOICES}
IMAGE_METADATA_SPEC = {
    "category": {"required": True, "max_length": 64, "choices": CATEGORY_CHOICES},
    "object_name": {"required": True, "max_length": 128},
    "observer_name": {"required": True, "max_length": 128},
    "location": {"required": False, "max_length": 128},
    "filter": {"required": False, "max_length": 64},
    "telescope": {"required": False, "max_length": 128},
    "camera": {"required": False, "max_length": 128},
    "notes": {"required": False, "max_length": 512},
}
ALLOWED_METADATA_KEYS = set(IMAGE_METADATA_SPEC.keys()) | {"observed_at"}


def _parse_iso_datetime(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw)


def json_csrf_protected(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            _require_json_csrf()
        except ValidationError:
            return jsonify({"error": "invalid csrf token"}), 400
        return view(*args, **kwargs)

    return wrapped


def _require_json_csrf():
    token = (
        request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
    )
    if not token:
        raise ValidationError("Missing CSRF token")
    validate_csrf(token)


def _extract_tags(notes: str | None) -> list[str]:
    if not notes:
        return []
    return re.findall(r"#([A-Za-z0-9_\-]+)", notes)


def _hamming_distance(left: str | None, right: str | None) -> int | None:
    if not left or not right:
        return None
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return None


def _serialize_image(
    image: Image,
    liked_ids: set[int],
    favorited_ids: set[int],
    following_ids: set[int],
    current_user_id: int | None,
) -> dict:
    return {
        "id": image.id,
        "category": image.category,
        "object_name": image.object_name,
        "observer_name": image.observer_name,
        "observed_at": image.observed_at.isoformat(),
        "location": image.location,
        "telescope": image.telescope,
        "camera": image.camera,
        "filter": image.filter,
        "notes": image.notes or "",
        "created_at": image.created_at.isoformat(),
        "uploader": image.uploader.username,
        "uploader_id": image.uploader.id,
        "owned_by_current_user": current_user_id is not None and image.user_id == current_user_id,
        "like_count": image.likes.count(),
        "favorite_count": image.favorites.count(),
        "comment_count": image.comments.count(),
        "liked": image.id in liked_ids,
        "favorited": image.id in favorited_ids,
        "following_uploader": image.uploader.id in following_ids,
        "thumb_url": url_for("api.download_image", image_id=image.id, thumb=1),
        "download_url": url_for("api.download_image", image_id=image.id),
        "download_name": f"{winjupos_label_from_metadata(image.object_name, image.observed_at, image.filter, image.uploader.username)}.jpg",
        "tags": _extract_tags(image.notes),
        "derotation_time": getattr(image, "derotation_time", None),
        "planetary_data": planetary_coordinates(
            image.observed_at,
            image.object_name,
            image.uploader.observatory_latitude,
            image.uploader.observatory_longitude,
        )
        if image.category == "Planets"
        else None,
        "seeing_rating": image.seeing_rating,
        "transparency_rating": image.transparency_rating,
        "bortle_rating": image.bortle_rating,
        "max_exposure_time": image.max_exposure_time,
        "allow_scientific_use": image.allow_scientific_use,
        "watermark_hash": image.watermark_hash,
    }


@bp.route("/images/<int:image_id>/share", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
@json_csrf_protected
def share_image(image_id):
    image = Image.query.get_or_404(image_id)
    if image.user_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403
    token = create_share_token(image)
    share_url = url_for("main.shared_image", token=token, _external=True)
    return jsonify({"share_url": share_url})


@bp.route("/images/<int:image_id>/verify", methods=["GET"])
def verify_image(image_id):
    image = Image.query.get_or_404(image_id)
    base_path = Path(Config.UPLOAD_PATH)
    file_path = base_path / image.file_path
    if not file_path.exists():
        return jsonify({"error": "image file missing"}), 404
    computed_hash = sha256_file(file_path)
    stored_hash = image.signature_sha256
    if not stored_hash:
        return jsonify(
            {
                "valid": False,
                "reason": "missing_signature",
                "computed_hash": computed_hash,
            }
        )
    return jsonify(
        {
            "valid": stored_hash == computed_hash,
            "stored_hash": stored_hash,
            "computed_hash": computed_hash,
            "image_id": image.id,
            "object_name": image.object_name,
            "observer_name": image.observer_name,
            "category": image.category,
            "observed_at": image.observed_at.isoformat() if image.observed_at else None,
            "uploader": image.uploader.username,
            "telescope": image.telescope,
            "camera": image.camera,
            "filter": image.filter,
            "location": image.location,
            "allow_scientific_use": image.allow_scientific_use,
        }
    )


@bp.route("/verify-file", methods=["POST"])
@csrf_protect.exempt
@limiter.limit("20 per minute")
def verify_file():
    if request.content_length and request.content_length > current_app.config["VERIFY_MAX_BYTES"]:
        return jsonify({"error": "file too large"}), 413
    file_storage = request.files.get("file")
    if not file_storage or not file_storage.filename:
        return jsonify({"error": "missing file"}), 400
    file_storage.stream.seek(0)
    data = file_storage.stream.read()
    file_storage.stream.seek(0)
    computed_hash = hashlib.sha256(data).hexdigest()
    try:
        phash_value, dhash_value = perceptual_hashes_for_bytes(data)
    except Exception:
        return jsonify({"error": "invalid image file"}), 400
    image = Image.query.filter_by(signature_sha256=computed_hash).first()
    current_app.logger.info(
        "Public verify-file request: matched=%s filename=%s",
        bool(image),
        file_storage.filename,
    )
    if not image:
        if not current_app.config.get("VERIFY_SIMILARITY_ENABLED", True):
            return jsonify(
                {
                    "valid": False,
                    "computed_hash": computed_hash,
                }
            ), 200
        candidates = (
            db.session.query(
                Image.id,
                Image.signature_phash,
                Image.signature_dhash,
                Image.object_name,
                Image.observer_name,
                Image.category,
                Image.observed_at,
                Image.telescope,
                Image.camera,
                Image.filter,
                Image.location,
                Image.allow_scientific_use,
                User.username,
            )
            .join(User, User.id == Image.user_id)
            .filter(Image.signature_phash.isnot(None), Image.signature_dhash.isnot(None))
            .all()
        )
        best = None
        best_score = None
        max_phash = current_app.config["VERIFY_PHASH_MAX_DISTANCE"]
        max_dhash = current_app.config["VERIFY_DHASH_MAX_DISTANCE"]
        for row in candidates:
            phash_dist = _hamming_distance(phash_value, row.signature_phash)
            dhash_dist = _hamming_distance(dhash_value, row.signature_dhash)
            if phash_dist is None or dhash_dist is None:
                continue
            if phash_dist <= max_phash and dhash_dist <= max_dhash:
                score = phash_dist + dhash_dist
                if best_score is None or score < best_score:
                    best_score = score
                    best = (row, phash_dist, dhash_dist)
        if not best:
            return jsonify(
                {
                    "valid": False,
                    "computed_hash": computed_hash,
                    "similar": False,
                    "phash": phash_value,
                    "dhash": dhash_value,
                }
            ), 200
        row, phash_dist, dhash_dist = best
        return jsonify(
            {
                "valid": False,
                "computed_hash": computed_hash,
                "similar": True,
                "phash_distance": phash_dist,
                "dhash_distance": dhash_dist,
                "image_id": row.id,
                "object_name": row.object_name,
                "observer_name": row.observer_name,
                "category": row.category,
                "observed_at": row.observed_at.isoformat() if row.observed_at else None,
                "uploader": row.username,
                "telescope": row.telescope,
                "camera": row.camera,
                "filter": row.filter,
                "location": row.location,
                "allow_scientific_use": row.allow_scientific_use,
            }
        ), 200
    return jsonify(
        {
            "valid": True,
            "computed_hash": computed_hash,
            "phash": phash_value,
            "dhash": dhash_value,
            "image_id": image.id,
            "object_name": image.object_name,
            "observer_name": image.observer_name,
            "category": image.category,
            "observed_at": image.observed_at.isoformat() if image.observed_at else None,
            "uploader": image.uploader.username,
            "telescope": image.telescope,
            "camera": image.camera,
            "filter": image.filter,
            "location": image.location,
            "allow_scientific_use": image.allow_scientific_use,
        }
    )


@bp.route("/notifications", methods=["GET"])
@login_required
def notifications():
    last_read = current_user.notifications_last_read_at or datetime.fromtimestamp(0)
    like_total = (
        db.session.query(func.count(Like.user_id))
        .join(Image, Like.image_id == Image.id)
        .filter(Image.user_id == current_user.id)
        .scalar()
        or 0
    )
    comment_total = (
        db.session.query(func.count(Comment.id))
        .join(Image, Comment.image_id == Image.id)
        .filter(Image.user_id == current_user.id)
        .scalar()
        or 0
    )
    like_unread = (
        db.session.query(func.count(Like.user_id))
        .join(Image, Like.image_id == Image.id)
        .filter(Image.user_id == current_user.id, Like.created_at > last_read)
        .scalar()
        or 0
    )
    comment_unread = (
        db.session.query(func.count(Comment.id))
        .join(Image, Comment.image_id == Image.id)
        .filter(Image.user_id == current_user.id, Comment.created_at > last_read)
        .scalar()
        or 0
    )
    likes = (
        db.session.query(Like, Image, User)
        .join(Image, Like.image_id == Image.id)
        .join(User, Like.user_id == User.id)
        .filter(Image.user_id == current_user.id, Like.created_at > last_read)
        .order_by(Like.created_at.desc())
        .limit(20)
        .all()
    )
    comments = (
        db.session.query(Comment, Image, User)
        .join(Image, Comment.image_id == Image.id)
        .join(User, Comment.user_id == User.id)
        .filter(Image.user_id == current_user.id, Comment.created_at > last_read)
        .order_by(Comment.created_at.desc())
        .limit(20)
        .all()
    )
    likes_payload = [
        {
            "image_id": image.id,
            "image_name": image.object_name,
            "thumb_url": url_for("api.download_image", image_id=image.id, thumb=1),
            "actor": user.username,
            "actor_avatar": user.avatar_url,
            "created_at": like.created_at.isoformat(),
            "link": url_for("main.feed", focus_image=image.id),
        }
        for like, image, user in likes
    ]
    comments_payload = [
        {
            "image_id": image.id,
            "image_name": image.object_name,
            "thumb_url": url_for("api.download_image", image_id=image.id, thumb=1),
            "actor": user.username,
            "actor_avatar": user.avatar_url,
            "body": comment.body,
            "created_at": comment.created_at.isoformat(),
            "link": url_for("main.feed", open_comment=image.id, focus_image=image.id),
        }
        for comment, image, user in comments
    ]
    return jsonify(
        {
            "like_total": like_total,
            "comment_total": comment_total,
            "like_unread": like_unread,
            "comment_unread": comment_unread,
            "likes": likes_payload,
            "comments": comments_payload,
        }
    )


@bp.route("/notifications/read", methods=["POST"])
@login_required
@json_csrf_protected
def notifications_read():
    current_user.notifications_last_read_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/notifications/read-item", methods=["POST"])
@login_required
@json_csrf_protected
def notifications_read_item():
    data = request.get_json(silent=True) or {}
    read_at = data.get("read_at")
    if not read_at:
        return jsonify({"error": "missing read_at"}), 400
    try:
        parsed = datetime.fromisoformat(read_at)
    except ValueError:
        return jsonify({"error": "invalid read_at"}), 400
    current = current_user.notifications_last_read_at
    if not current or parsed > current:
        current_user.notifications_last_read_at = parsed
        db.session.commit()
    return jsonify({"ok": True})


@bp.route("/motd/ack", methods=["POST"])
@login_required
@json_csrf_protected
def motd_ack():
    data = request.get_json(silent=True) or {}
    motd_id = data.get("motd_id")
    if not motd_id:
        return jsonify({"error": "missing motd id"}), 400
    motd = Motd.query.get(motd_id)
    if not motd:
        return jsonify({"error": "motd not found"}), 404
    existing = MotdSeen.query.filter_by(user_id=current_user.id, motd_id=motd.id).first()
    if not existing:
        db.session.add(MotdSeen(user_id=current_user.id, motd_id=motd.id))
        db.session.commit()
    return jsonify({"ok": True})


@bp.route("/feed", methods=["GET"])
def feed():
    cursor = request.args.get("cursor")
    per_page = current_app.config["FEED_PAGE_SIZE"]
    liked_ids: set[int] = set()
    favorited_ids: set[int] = set()
    following_ids: set[int] = set()
    if current_user.is_authenticated:
        liked_ids = {row.image_id for row in current_user.likes.with_entities(Like.image_id).all()}
        favorited_ids = {
            row.image_id for row in current_user.favorites.with_entities(Favorite.image_id).all()
        }
        following_ids = {
            row.followed_id for row in current_user.following.with_entities(Follow.followed_id).all()
        }

    selection = build_feed_selection(
        liked_ids=liked_ids,
        following_ids=following_ids,
        per_page=per_page,
        cursor=cursor,
        fresh_days=current_app.config["FEED_FRESH_DAYS"],
        prioritized_pct=current_app.config["FEED_PRIORITIZED_PCT"],
        candidate_multiplier=current_app.config["FEED_CANDIDATE_MULTIPLIER"],
        max_per_uploader=current_app.config["FEED_MAX_PER_UPLOADER"],
        max_consecutive=current_app.config["FEED_MAX_CONSECUTIVE_PER_UPLOADER"],
        seen_enabled=current_app.config["FEED_SEEN_ENABLED"],
        seen_user_id=getattr(current_user, "id", None),
        seen_retention_days=current_app.config["FEED_SEEN_RETENTION_DAYS"],
        seen_max_ids=current_app.config["FEED_SEEN_MAX_IDS"],
    )

    current_user_id = getattr(current_user, "id", None)
    payload = [
        _serialize_image(
            image, liked_ids, favorited_ids, following_ids, current_user_id=current_user_id
        )
        for image in selection.images
    ]
    persist_seen_for_feed(
        user_id=current_user_id,
        images=selection.images,
        retention_days=current_app.config["FEED_SEEN_RETENTION_DAYS"],
    )
    return jsonify({"images": payload, "next_cursor": selection.next_cursor}), 200


@bp.route("/my-feed", methods=["GET"])
@login_required
def my_feed():
    cursor = request.args.get("cursor")
    per_page = current_app.config["FEED_PAGE_SIZE"]
    liked_ids = {row.image_id for row in current_user.likes.with_entities(Like.image_id).all()}
    favorited_ids = {
        row.image_id for row in current_user.favorites.with_entities(Favorite.image_id).all()
    }
    following_ids = {
        row.followed_id for row in current_user.following.with_entities(Follow.followed_id).all()
    }

    cursor_point = None
    cursor_image_id = None
    if cursor:
        try:
            timestamp, image_id = cursor.split("_")
            cursor_point = datetime.fromisoformat(timestamp)
            cursor_image_id = int(image_id)
        except ValueError:
            return jsonify({"error": "invalid cursor"}), 400

    query = Image.query.filter_by(user_id=current_user.id)
    if cursor_point:
        query = query.filter(
            (Image.created_at < cursor_point)
            | ((Image.created_at == cursor_point) & (Image.id < cursor_image_id))
        )

    ordered = (
        query.order_by(Image.created_at.desc(), Image.id.desc())
        .limit(per_page + 1)
        .all()
    )
    images = ordered[:per_page]
    next_cursor = ""
    if len(ordered) > per_page and images:
        cursor_target = images[-1]
        next_cursor = f"{cursor_target.created_at.isoformat()}_{cursor_target.id}"

    payload = [
        _serialize_image(image, liked_ids, favorited_ids, following_ids, current_user_id=current_user.id)
        for image in images
    ]
    return jsonify({"images": payload, "next_cursor": next_cursor}), 200


@bp.route("/search", methods=["GET"])
@login_required
def search():
    per_page = current_app.config["FEED_PAGE_SIZE"]
    cursor = request.args.get("cursor")
    query = Image.query
    category = request.args.get("category")
    object_name = request.args.get("object_name")
    observer = request.args.get("observer")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    notes_query = request.args.get("query")
    if category:
        query = query.filter_by(category=category)
    if object_name:
        query = query.filter(Image.object_name.ilike(f"%{object_name}%"))
    if observer:
        query = query.filter(Image.observer_name.ilike(f"%{observer}%"))
    if date_from:
        try:
            query = query.filter(Image.observed_at >= datetime.fromisoformat(date_from))
        except ValueError:
            return jsonify({"error": "invalid date_from"}), 400
    if date_to:
        try:
            query = query.filter(Image.observed_at <= datetime.fromisoformat(date_to))
        except ValueError:
            return jsonify({"error": "invalid date_to"}), 400
    if notes_query:
        query = query.filter(Image.notes.ilike(f"%{notes_query}%"))

    cursor_point = None
    cursor_image_id = None
    if cursor:
        try:
            timestamp, image_id = cursor.split("_")
            cursor_point = datetime.fromisoformat(timestamp)
            cursor_image_id = int(image_id)
        except ValueError:
            return jsonify({"error": "invalid cursor"}), 400

    if cursor_point:
        query = query.filter(
            (Image.created_at < cursor_point)
            | ((Image.created_at == cursor_point) & (Image.id < cursor_image_id))
        )

    ordered = (
        query.order_by(Image.created_at.desc(), Image.id.desc())
        .limit(per_page + 1)
        .all()
    )
    images = ordered[:per_page]
    next_cursor = ""
    if len(ordered) > per_page and images:
        cursor_target = images[-1]
        next_cursor = f"{cursor_target.created_at.isoformat()}_{cursor_target.id}"

    liked_ids: set[int] = set()
    favorited_ids: set[int] = set()
    following_ids: set[int] = set()
    if current_user.is_authenticated:
        liked_ids = {row.image_id for row in current_user.likes.with_entities(Like.image_id).all()}
        favorited_ids = {
            row.image_id for row in current_user.favorites.with_entities(Favorite.image_id).all()
        }
        following_ids = {
            row.followed_id for row in current_user.following.with_entities(Follow.followed_id).all()
        }
    current_user_id = getattr(current_user, "id", None)
    payload = [
        _serialize_image(
            image, liked_ids, favorited_ids, following_ids, current_user_id=current_user_id
        )
        for image in images
    ]
    return jsonify({"images": payload, "next_cursor": next_cursor}), 200


@bp.route("/observers", methods=["GET"])
def observer_suggestions():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"observers": []})
    matches = (
        Image.query.with_entities(Image.observer_name)
        .filter(Image.observer_name.ilike(f"%{query}%"))
        .distinct()
        .order_by(Image.observer_name.asc())
        .limit(10)
        .all()
    )
    observers = [name for (name,) in matches if name]
    return jsonify({"observers": observers})


@bp.route("/images/<int:image_id>/like", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
@json_csrf_protected
def like_image(image_id):
    image = Image.query.get_or_404(image_id)
    if not Like.query.get((current_user.id, image.id)):
        db.session.add(Like(user_id=current_user.id, image_id=image.id))
        db.session.commit()
    return jsonify({"like_count": image.likes.count(), "liked": True})


@bp.route("/images/<int:image_id>/unlike", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
@json_csrf_protected
def unlike_image(image_id):
    image = Image.query.get_or_404(image_id)
    like = Like.query.get((current_user.id, image.id))
    if like:
        db.session.delete(like)
        db.session.commit()
    return jsonify({"like_count": image.likes.count(), "liked": False})


@bp.route("/images/<int:image_id>/favorite", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
@json_csrf_protected
def favorite_image(image_id):
    image = Image.query.get_or_404(image_id)
    if not Favorite.query.get((current_user.id, image.id)):
        db.session.add(Favorite(user_id=current_user.id, image_id=image.id))
        db.session.commit()
    return jsonify({"favorite_count": image.favorites.count(), "favorited": True})


@bp.route("/images/<int:image_id>/unfavorite", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
@json_csrf_protected
def unfavorite_image(image_id):
    image = Image.query.get_or_404(image_id)
    favorite = Favorite.query.get((current_user.id, image.id))
    if favorite:
        db.session.delete(favorite)
        db.session.commit()
    return jsonify({"favorite_count": image.favorites.count(), "favorited": False})


@bp.route("/users/<int:user_id>/follow", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
@json_csrf_protected
def follow_user(user_id):
    if user_id == current_user.id:
        return jsonify({"error": "cannot follow yourself"}), 400
    target = User.query.get_or_404(user_id)
    if not Follow.query.get((current_user.id, target.id)):
        db.session.add(Follow(follower_id=current_user.id, followed_id=target.id))
        db.session.commit()
    return jsonify({"following": True})


@bp.route("/users/<int:user_id>/unfollow", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
@json_csrf_protected
def unfollow_user(user_id):
    target = User.query.get_or_404(user_id)
    follow = Follow.query.get((current_user.id, target.id))
    if follow:
        db.session.delete(follow)
        db.session.commit()
    return jsonify({"following": False})


@bp.route("/images/<int:image_id>/comments", methods=["POST"])
@login_required
@limiter.limit("50 per minute")
@json_csrf_protected
def add_comment(image_id):
    payload = request.get_json(force=True, silent=True) or {}
    body = payload.get("body", "").strip()
    if not body or len(body) > 500:
        return jsonify({"error": "Invalid comment"}), 400
    image = Image.query.get_or_404(image_id)
    comment = Comment(image_id=image.id, user_id=current_user.id, body=body)
    db.session.add(comment)
    db.session.commit()
    return jsonify(
        {
            "id": comment.id,
            "body": comment.body,
            "created_at": comment.created_at.isoformat(),
            "user": current_user.username,
        }
    )


@bp.route("/images/<int:image_id>/comments", methods=["GET"])
@login_required
def list_comments(image_id):
    image = Image.query.get_or_404(image_id)
    comments = (
        Comment.query.filter_by(image_id=image.id)
        .order_by(Comment.created_at.asc())
        .limit(50)
        .all()
    )
    return jsonify(
        [
            {
                "id": comment.id,
                "body": comment.body,
                "created_at": comment.created_at.isoformat(),
                "user": comment.user.username,
            }
            for comment in comments
        ]
    )


@bp.route("/images/<int:image_id>/likes", methods=["GET"])
@login_required
def list_likes(image_id):
    image = Image.query.get_or_404(image_id)
    likes = (
        db.session.query(User, Like)
        .join(Like, Like.user_id == User.id)
        .filter(Like.image_id == image.id)
        .order_by(Like.created_at.desc())
        .all()
    )
    payload = [
        {"id": user.id, "username": user.username, "avatar_url": user.avatar_url}
        for user, _ in likes
    ]
    return jsonify({"likes": payload, "count": len(payload)}), 200


@bp.route("/images/<int:image_id>", methods=["PATCH"])
@login_required
@limiter.limit("12 per minute")
@json_csrf_protected
def update_image(image_id):
    image = Image.query.get_or_404(image_id)
    if image.user_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(force=True, silent=True) or {}
    if not payload:
        return jsonify({"error": "missing payload"}), 400

    unknown_fields = set(payload) - ALLOWED_METADATA_KEYS
    if unknown_fields:
        return jsonify({"error": f"unsupported fields: {', '.join(sorted(unknown_fields))}"}), 400

    changes = {}

    if "observed_at" in payload:
        observed_at_value = payload["observed_at"]
        if not observed_at_value:
            return jsonify({"error": "observed_at is required"}), 400
        if not isinstance(observed_at_value, str):
            return jsonify({"error": "observed_at must be a string"}), 400
        try:
            parsed = _parse_iso_datetime(observed_at_value)
        except ValueError:
            return jsonify({"error": "observed_at must be ISO 8601"}), 400
        if parsed != image.observed_at:
            image.observed_at = parsed
            changes["observed_at"] = parsed.isoformat()

    for field, spec in IMAGE_METADATA_SPEC.items():
        if field not in payload:
            continue
        raw_value = payload[field]
        if raw_value is None:
            setattr(image, field, None)
            changes[field] = None
            continue
        if not isinstance(raw_value, str):
            return jsonify({"error": f"{field} must be a string"}), 400
        value = raw_value.strip()
        if spec.get("required") and not value:
            return jsonify({"error": f"{field} cannot be empty"}), 400
        max_length = spec.get("max_length")
        if max_length and len(value) > max_length:
            return jsonify({"error": f"{field} must be {max_length} characters or fewer"}), 400
        choices = spec.get("choices")
        if choices and value not in choices:
            return jsonify({"error": f"{field} must be one of {', '.join(sorted(choices))}"}), 400
        if getattr(image, field) != value:
            setattr(image, field, value)
            changes[field] = value

    if not changes:
        return jsonify({"error": "no updates were provided"}), 400

    db.session.commit()
    return jsonify(
        {
            "id": image.id,
            "category": image.category,
            "object_name": image.object_name,
            "observer_name": image.observer_name,
            "observed_at": image.observed_at.isoformat(),
            "location": image.location,
            "filter": image.filter,
            "telescope": image.telescope,
            "camera": image.camera,
            "notes": image.notes,
        }
    ), 200


@bp.route("/images/<int:image_id>", methods=["DELETE"])
@login_required
@limiter.limit("6 per minute")
@json_csrf_protected
def delete_image(image_id):
    image = Image.query.get_or_404(image_id)
    if image.user_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403

    base_path = Path(Config.UPLOAD_PATH)
    for attr in ("file_path", "thumb_path"):
        target = base_path / getattr(image, attr)
        try:
            target.unlink()
        except FileNotFoundError:
            pass

    db.session.delete(image)
    db.session.commit()
    return jsonify({"deleted": True}), 200


@bp.route("/images/<int:image_id>/download", methods=["GET"])
def download_image(image_id):
    image = Image.query.get_or_404(image_id)
    base_path = Path(Config.UPLOAD_PATH)
    thumb_requested = request.args.get("thumb", "").lower() in {"1", "true", "yes"}
    if not thumb_requested and not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    target = image.thumb_path if thumb_requested else image.file_path
    file_path = base_path / target
    if not file_path.exists():
        return jsonify({"error": "file missing"}), 404
    mime_type, _ = mimetypes.guess_type(str(file_path))
    mime_type = mime_type or "application/octet-stream"
    label = winjupos_label_from_metadata(
        image.object_name, image.observed_at, image.filter, image.uploader.username
    )
    safe_name = f"{label}.jpg"
    return send_from_directory(
        directory=str(base_path),
        path=str(target),
        as_attachment=not thumb_requested,
        download_name=None if thumb_requested else safe_name,
        mimetype=mime_type,
    )
