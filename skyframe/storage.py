import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageOps
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .config import Config


def _ensure_dirs(*paths):
    for path in paths:
        os.makedirs(path, exist_ok=True)


def _allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower().strip(".")
    return ext in Config.ALLOWED_IMAGE_EXTENSIONS


def _winjupos_base(name: str | None) -> str:
    if not name:
        return "frame"
    cleaned = os.path.splitext(secure_filename(name.strip()))[0]
    cleaned = cleaned.replace(" ", "_")
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", cleaned)
    cleaned = cleaned or "frame"
    return cleaned[:64]


def process_image_upload(file_storage: FileStorage) -> tuple[str, str]:
    if not _allowed_file(file_storage.filename or ""):
        raise ValueError("Unsupported image format.")

    images_dir = Path(Config.UPLOAD_PATH) / Config.IMAGE_SUBDIR
    thumbs_dir = Path(Config.UPLOAD_PATH) / Config.THUMB_SUBDIR
    _ensure_dirs(images_dir, thumbs_dir)

    base = _winjupos_base(file_storage.filename)
    identifier = uuid.uuid4().hex[:6]
    img_filename = f"{base}-{identifier}.jpg"
    thumb_filename = f"{base}-{identifier}.jpg"

    img_path = images_dir / img_filename
    thumb_path = thumbs_dir / thumb_filename

    file_storage.stream.seek(0)
    image = Image.open(file_storage.stream)
    image = image.convert("RGB")
    image.thumbnail(Config.IMAGE_PROCESS_SIZE, Image.LANCZOS)
    image.save(img_path, "JPEG", quality=90, progressive=True)

    thumb = Image.open(img_path)
    thumb.thumbnail(Config.THUMB_SIZE, Image.LANCZOS)
    thumb.save(thumb_path, "JPEG", quality=80, progressive=True)

    return (
        str(img_path.relative_to(Config.UPLOAD_PATH)),
        str(thumb_path.relative_to(Config.UPLOAD_PATH)),
    )


def save_avatar_upload(file_storage: FileStorage) -> str:
    if not _allowed_file(file_storage.filename or ""):
        raise ValueError("Unsupported avatar format.")

    avatar_dir = Path(Config.UPLOAD_PATH) / Config.AVATAR_SUBDIR
    _ensure_dirs(avatar_dir)

    identifier = uuid.uuid4().hex
    avatar_filename = f"{identifier}.jpg"
    avatar_path = avatar_dir / avatar_filename

    file_storage.stream.seek(0)
    avatar = Image.open(file_storage.stream)
    avatar = avatar.convert("RGB")
    avatar = ImageOps.fit(avatar, Config.AVATAR_SIZE, Image.LANCZOS)
    avatar.save(avatar_path, "JPEG", quality=85, progressive=True)

    return str(avatar_path.relative_to(Config.UPLOAD_PATH))


def _sanitize_segment(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = secure_filename(value.strip())
    cleaned = cleaned.replace(" ", "_")
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", cleaned)
    return cleaned or None


def winjupos_label_from_path(path: str) -> str:
    stem = Path(path).stem
    match = re.match(r"^(.*?)(?:-[0-9a-f]{6})?$", stem, re.IGNORECASE)
    base = match.group(1) if match else stem
    return _winjupos_base(base)


def winjupos_label_from_metadata(
    object_name: str | None,
    observed_at: datetime | None,
    filter_value: str | None,
    uploader_name: str | None,
) -> str:
    timestamp = (
        observed_at.strftime("%Y-%m-%d_%H%M")
        if observed_at
        else datetime.utcnow().strftime("%Y-%m-%d_%H%M")
    )
    filter_seg = _sanitize_segment((filter_value or "RGB").upper()) or "RGB"
    observer_seg = _sanitize_segment(uploader_name) or "Observer"
    object_seg = _sanitize_segment(object_name) or "Object"
    parts = [timestamp, filter_seg, observer_seg, object_seg]
    base = "_".join(part for part in parts if part)
    return f"o{base}"
