import hashlib
from datetime import datetime
from pathlib import Path

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, or_

from ..extensions import db, limiter
from ..forms import CommentForm, ImageEditForm, ProfileForm, SearchForm, UploadForm
from ..models import Favorite, Follow, Image, Like, User
from ..share_storage import read_share_token
from ..storage import (
    process_image_upload,
    save_avatar_upload,
    winjupos_label_from_metadata,
)
from ..config import Config
import zipfile
from . import bp


@bp.before_app_request
def _load_nonce():
    from secrets import token_urlsafe

    request.csp_nonce = token_urlsafe(16)


def _prioritized_filter(liked_ids: set[int], following_ids: set[int]):
    conditions = []
    if liked_ids:
        conditions.append(Image.id.in_(liked_ids))
    if following_ids:
        conditions.append(Image.user_id.in_(following_ids))
    if not conditions:
        return None
    return or_(*conditions)


ARCHIVE_MAX_BYTES = 100 * 1024 * 1024


def _archive_root_dir(user: User) -> Path:
    base = Path(Config.UPLOAD_PATH) / Config.ARCHIVE_SUBDIR / user.username
    base.mkdir(parents=True, exist_ok=True)
    return base


def _archive_filename(user: User, part: int) -> str:
    return f"{user.username}-images-part-{part}.zip"


def _cleanup_archives(root: Path) -> None:
    for child in root.glob("*.zip"):
        try:
            child.unlink()
        except OSError:
            pass


def _build_user_archives(user: User) -> list[Path]:
    root = _archive_root_dir(user)
    _cleanup_archives(root)
    images = Image.query.filter_by(user_id=user.id).order_by(Image.created_at.asc()).all()
    if not images:
        return []
    archives: list[Path] = []
    current_zip: zipfile.ZipFile | None = None
    current_size = 0
    part = 1
    try:
        for image in images:
            file_path = Path(Config.UPLOAD_PATH) / image.file_path
            if not file_path.exists():
                continue
            file_size = file_path.stat().st_size
            if current_zip is None or (current_size + file_size > ARCHIVE_MAX_BYTES and current_size > 0):
                if current_zip:
                    current_zip.close()
                part_path = root / _archive_filename(user, part)
                current_zip = zipfile.ZipFile(part_path, "w", compression=zipfile.ZIP_DEFLATED)
                archives.append(part_path)
                part += 1
                current_size = 0
            current_zip.write(file_path, arcname=file_path.name)
            current_size += file_size
    finally:
        if current_zip:
            current_zip.close()
    return [path for path in archives if path.exists()]


def _list_user_archives(user: User) -> list[Path]:
    root = _archive_root_dir(user)
    return sorted(root.glob(f"{user.username}-images-part-*.zip"))


@bp.route("/")
def root():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    return redirect(url_for("main.feed"))


@bp.route("/feed")
def feed():
    form = SearchForm()
    comment_form = CommentForm()
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
    prioritized_filter = _prioritized_filter(liked_ids, following_ids)
    prioritized_images = []
    if prioritized_filter is not None:
        prioritized_images = (
            Image.query.filter(prioritized_filter)
            .order_by(Image.created_at.desc(), Image.id.desc())
            .limit(per_page)
            .all()
        )
    random_needed = max(per_page - len(prioritized_images), 0)
    random_images = []
    if random_needed > 0:
        random_query = Image.query
        if liked_ids:
            random_query = random_query.filter(~Image.id.in_(liked_ids))
        if following_ids:
            random_query = random_query.filter(~Image.user_id.in_(following_ids))
        random_images = random_query.order_by(func.random()).limit(random_needed).all()
    images = prioritized_images + random_images
    next_cursor = "random"
    if prioritized_images:
        cursor_target = prioritized_images[-1]
        next_cursor = f"{cursor_target.created_at.isoformat()}_{cursor_target.id}"
        if len(prioritized_images) < per_page:
            next_cursor = "random"
    elif not images:
        next_cursor = ""
    owned_ids: set[int] = set()
    if current_user.is_authenticated:
        owned_ids = {image.id for image in images if image.user_id == current_user.id}
    for img in images:
        img.download_name = f"{winjupos_label_from_metadata(img.object_name, img.observed_at, img.filter, img.uploader.username)}.jpg"
    return render_template(
        "feed.html",
        feed_images=images,
        search_form=form,
        comment_form=comment_form,
        csp_nonce=getattr(request, "csp_nonce", ""),
        liked=liked_ids,
        favorited=favorited_ids,
        following=following_ids,
        next_cursor=next_cursor,
        owned_ids=owned_ids,
    )


@bp.route("/saved")
@login_required
def saved():
    liked_ids = {row.image_id for row in current_user.likes.with_entities(Like.image_id).all()}
    favorited_ids = {
        row.image_id for row in current_user.favorites.with_entities(Favorite.image_id).all()
    }
    following_ids = {
        row.followed_id for row in current_user.following.with_entities(Follow.followed_id).all()
    }
    saved_images = (
        Image.query.join(Favorite, Favorite.image_id == Image.id)
        .filter(Favorite.user_id == current_user.id)
        .order_by(Image.created_at.desc(), Image.id.desc())
        .all()
    )
    owned_ids = {image.id for image in saved_images if image.user_id == current_user.id}
    for image in saved_images:
        image.download_name = f"{winjupos_label_from_metadata(image.object_name, image.observed_at, image.filter, image.uploader.username)}.jpg"
    return render_template(
        "saved.html",
        saved_images=saved_images,
        liked=liked_ids,
        favorited=favorited_ids,
        following=following_ids,
        owned_ids=owned_ids,
        csp_nonce=getattr(request, "csp_nonce", ""),
    )


@bp.route("/profile/archives", methods=["GET", "POST"])
@login_required
def profile_archives():
    if request.method == "POST":
        parts = _build_user_archives(current_user)
        if parts:
            flash("Archive ready! Download the pieces below.", "success")
        else:
            flash("You have no uploads to archive.", "warning")
        return redirect(url_for("main.profile_archives"))
    parts = [
        {"name": part.name, "size": part.stat().st_size}
        for part in _list_user_archives(current_user)
    ]
    return render_template(
        "profile_archives.html",
        parts=parts,
        csp_nonce=getattr(request, "csp_nonce", ""),
    )


@bp.route("/profile/archives/download/<path:filename>")
@login_required
def download_archive_part(filename):
    root = _archive_root_dir(current_user)
    safe_name = Path(filename).name
    target = root / safe_name
    if not target.exists():
        abort(404)
    return send_from_directory(str(root), safe_name, as_attachment=True)


@bp.route("/profile/archives/delete/<path:filename>", methods=["POST"])
@login_required
def delete_archive_part(filename):
    root = _archive_root_dir(current_user)
    safe_name = Path(filename).name
    target = root / safe_name
    if not target.exists():
        flash("Archive part missing.", "warning")
        return redirect(url_for("main.profile_archives"))
    try:
        target.unlink()
        flash("Archive part deleted.", "success")
    except OSError:
        flash("Unable to delete archive part.", "danger")
    return redirect(url_for("main.profile_archives"))


@bp.route("/share/<token>")
def shared_image(token):
    try:
        record = read_share_token(token)
    except FileNotFoundError:
        abort(404)
    image = Image.query.get_or_404(record["image_id"])
    owned = current_user.is_authenticated and current_user.id == image.user_id
    image.download_name = f"{winjupos_label_from_metadata(image.object_name, image.observed_at, image.filter, image.uploader.username)}.jpg"
    return render_template(
        "shared_image.html",
        image=image,
        owned=owned,
        share_url=url_for("main.shared_image", token=token, _external=True),
        share_image_url=url_for("main.shared_image_image", token=token, _external=True),
        share_download_url=url_for("main.shared_image_download", token=token, _external=True),
    )


@bp.route("/share/<token>/image")
def shared_image_image(token):
    try:
        record = read_share_token(token)
    except FileNotFoundError:
        abort(404)
    image = Image.query.get_or_404(record["image_id"])
    base_path = Path(Config.UPLOAD_PATH)
    file_path = base_path / image.file_path
    if not file_path.exists():
        abort(404)
    return send_from_directory(str(base_path), str(image.file_path))


@bp.route("/share/<token>/download")
def shared_image_download(token):
    try:
        record = read_share_token(token)
    except FileNotFoundError:
        abort(404)
    image = Image.query.get_or_404(record["image_id"])
    base_path = Path(Config.UPLOAD_PATH)
    file_path = base_path / image.file_path
    if not file_path.exists():
        abort(404)
    label = winjupos_label_from_metadata(
        image.object_name, image.observed_at, image.filter, image.uploader.username
    )
    safe_name = f"{label}.jpg"
    return send_from_directory(
        str(base_path),
        str(image.file_path),
        as_attachment=True,
        download_name=safe_name,
    )


@bp.route("/upload", methods=["GET", "POST"])
@login_required
@limiter.limit("6 per minute")
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        try:
            image_path, thumb_path = process_image_upload(form.file.data)
        except ValueError as exc:
            flash(str(exc), "danger")
        else:
            image = Image(
                user_id=current_user.id,
                file_path=image_path,
                thumb_path=thumb_path,
                category=form.category.data,
                object_name=form.object_name.data,
                observer_name=form.observer_name.data,
                observed_at=form.observed_at.data,
                location=form.location.data,
                filter=form.filter.data,
                telescope=form.telescope.data,
                camera=form.camera.data,
                notes=form.notes.data,
            )
            db.session.add(image)
            db.session.commit()
            flash("Astro frame uploaded successfully", "success")
            return redirect(url_for("main.feed"))
    return render_template("upload.html", form=form)


@bp.route("/images/<int:image_id>/edit", methods=["GET", "POST"])
@login_required
@limiter.limit("6 per minute")
def edit_image(image_id):
    image = Image.query.get_or_404(image_id)
    if image.user_id != current_user.id:
        flash("You can only edit your own uploads.", "danger")
        return redirect(url_for("main.feed"))

    form = ImageEditForm(obj=image)
    if request.method == "GET":
        form.observed_at.data = image.observed_at
    if form.validate_on_submit():
        image.category = form.category.data
        image.object_name = form.object_name.data
        image.observer_name = form.observer_name.data
        image.observed_at = form.observed_at.data
        image.location = form.location.data
        image.filter = form.filter.data
        image.telescope = form.telescope.data
        image.camera = form.camera.data
        image.notes = form.notes.data
        db.session.commit()
        flash("Frame details updated", "success")
        return redirect(url_for("main.feed"))

    return render_template(
        "edit_image.html",
        form=form,
        image=image,
        csp_nonce=getattr(request, "csp_nonce", ""),
    )


@bp.route("/profile")
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    gravatar_hash = hashlib.md5(current_user.email.strip().lower().encode()).hexdigest()
    return render_template("profile.html", profile_user=current_user, form=form, gravatar_hash=gravatar_hash)


@bp.route("/profile", methods=["POST"])
@login_required
@limiter.limit("4 per minute")
def update_profile():
    form = ProfileForm()
    if form.validate_on_submit():
        current_user.bio = form.bio.data
        current_user.avatar_type = form.avatar_type.data
        if (
            form.avatar_type.data == "upload"
            and form.avatar_upload.data
            and form.avatar_upload.data.filename
        ):
            avatar_path = save_avatar_upload(form.avatar_upload.data)
            current_user.avatar_path = avatar_path
        db.session.commit()
        flash("Profile updated", "success")
        return redirect(url_for("main.profile"))
    flash("Unable to update profile", "danger")
    gravatar_hash = hashlib.md5(current_user.email.strip().lower().encode()).hexdigest()
    return render_template(
        "profile.html", form=form, profile_user=current_user, gravatar_hash=gravatar_hash
    )


@bp.route("/search", methods=["GET", "POST"])
@login_required
def search():
    form = SearchForm()
    query = Image.query
    if form.validate_on_submit():
        if form.category.data:
            query = query.filter_by(category=form.category.data)
        if form.object_name.data:
            query = query.filter(Image.object_name.ilike(f"%{form.object_name.data}%"))
        if form.observer.data:
            query = query.filter(Image.observer_name.ilike(f"%{form.observer.data}%"))
        if form.date_from.data:
            query = query.filter(Image.observed_at >= form.date_from.data)
        if form.date_to.data:
            query = query.filter(Image.observed_at <= form.date_to.data)
        if form.query.data:
            query = query.filter(Image.notes.ilike(f"%{form.query.data}%"))
        images = query.order_by(Image.created_at.desc()).limit(20).all()
        return render_template("search.html", feed_images=images, form=form)
    return render_template("search.html", feed_images=[], form=form)


@bp.route("/uploads/<path:filename>")
@login_required
def uploads(filename):
    safe_root = Path(current_app.config["UPLOAD_PATH"])
    return send_from_directory(str(safe_root), filename)
