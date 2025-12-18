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
from sqlalchemy import func, or_
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError
from werkzeug.utils import secure_filename

from ..config import Config
from ..extensions import db, limiter
from ..forms import CATEGORY_CHOICES as FORM_CATEGORY_CHOICES
from ..models import Comment, Favorite, Follow, Image, Like, User
from ..share_storage import create_share_token
from ..storage import winjupos_label_from_metadata
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


def _prioritized_filter(liked_ids: set[int], following_ids: set[int]):
    conditions = []
    if liked_ids:
        conditions.append(Image.id.in_(liked_ids))
    if following_ids:
        conditions.append(Image.user_id.in_(following_ids))
    if not conditions:
        return None
    return or_(*conditions)



def _extract_tags(notes: str | None) -> list[str]:
    if not notes:
        return []
    return re.findall(r"#([A-Za-z0-9_\-]+)", notes)


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

    cursor_point = None
    cursor_image_id = None
    if cursor and cursor != "random":
        try:
            timestamp, image_id = cursor.split("_")
            cursor_point = datetime.fromisoformat(timestamp)
            cursor_image_id = int(image_id)
        except ValueError:
            return jsonify({"error": "invalid cursor"}), 400

    prioritized_filter = _prioritized_filter(liked_ids, following_ids)
    images: list[Image] = []
    seen_ids = set()
    next_cursor = None

    if cursor != "random" and prioritized_filter is not None:
        query = Image.query.filter(prioritized_filter)
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
        prioritized_entries = ordered[:per_page]
        has_more_prioritized = len(ordered) > per_page
        for image in prioritized_entries:
            images.append(image)
            seen_ids.add(image.id)
        if prioritized_entries:
            cursor_target = prioritized_entries[-1]
            next_cursor = f"{cursor_target.created_at.isoformat()}_{cursor_target.id}"
            if not has_more_prioritized:
                next_cursor = "random"
        else:
            next_cursor = "random"

    remaining = per_page - len(images)
    if remaining > 0:
        random_query = Image.query
        if liked_ids:
            random_query = random_query.filter(~Image.id.in_(liked_ids))
        if following_ids:
            random_query = random_query.filter(~Image.user_id.in_(following_ids))
        if seen_ids:
            random_query = random_query.filter(~Image.id.in_(seen_ids))
        random_entries = random_query.order_by(func.random()).limit(remaining).all()
        for image in random_entries:
            images.append(image)
            seen_ids.add(image.id)
        if not next_cursor:
            next_cursor = "random"

    if not images:
        next_cursor = ""

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
