import os
import re
import uuid
import hashlib
import math
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps, ImageDraw, ImageFont
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


def _build_watermark_payload(owner_name: str | None) -> tuple[str, str]:
    owner = owner_name.strip() if owner_name else "SkyFrame"
    owner = re.sub(r"[^A-Za-z0-9 _-]", "", owner) or "SkyFrame"
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    payload = f"{owner}|{timestamp}"
    signature = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return payload, signature


def _apply_invisible_watermark(image: Image.Image, text: str) -> Image.Image:
    watermark_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark_layer)
    try:
        font = ImageFont.load_default()
    except IOError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    padding = Config.WATERMARK_PADDING
    position = (max(image.width - text_width - padding, padding), max(image.height - text_height - padding, padding))
    draw.text(position, text, font=font, fill=(255, 255, 255, Config.WATERMARK_OPACITY))
    composited = Image.alpha_composite(image.convert("RGBA"), watermark_layer)
    return composited.convert("RGB")


def _image_to_grayscale(image: Image.Image, size: tuple[int, int]) -> list[list[float]]:
    resized = image.convert("L").resize(size, Image.LANCZOS)
    pixels = list(resized.getdata())
    width, height = resized.size
    return [pixels[row * width : (row + 1) * width] for row in range(height)]


def _dct_1d(values: list[float], cos_table: list[list[float]], alpha: list[float]) -> list[float]:
    size = len(values)
    output = [0.0] * size
    for k in range(size):
        total = 0.0
        cos_row = cos_table[k]
        for n in range(size):
            total += values[n] * cos_row[n]
        output[k] = total * alpha[k]
    return output


def _dct_2d(matrix: list[list[float]], cos_table: list[list[float]], alpha: list[float]) -> list[list[float]]:
    size = len(matrix)
    row_dct = [_dct_1d(row, cos_table, alpha) for row in matrix]
    result = [[0.0] * size for _ in range(size)]
    for col in range(size):
        column = [row_dct[row][col] for row in range(size)]
        column_dct = _dct_1d(column, cos_table, alpha)
        for row in range(size):
            result[row][col] = column_dct[row]
    return result


def _phash_from_image(image: Image.Image) -> str:
    size = 32
    small = _image_to_grayscale(image, (size, size))
    cos_table = [
        [math.cos((math.pi * (2 * n + 1) * k) / (2 * size)) for n in range(size)]
        for k in range(size)
    ]
    alpha = [math.sqrt(1 / size)] + [math.sqrt(2 / size)] * (size - 1)
    dct = _dct_2d(small, cos_table, alpha)
    block = [dct[row][col] for row in range(8) for col in range(8)]
    median_values = sorted(block[1:])
    median = median_values[len(median_values) // 2]
    hash_value = 0
    for value in block:
        hash_value = (hash_value << 1) | (1 if value > median else 0)
    return f"{hash_value:016x}"


def _dhash_from_image(image: Image.Image) -> str:
    pixels = _image_to_grayscale(image, (9, 8))
    hash_value = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row][col]
            right = pixels[row][col + 1]
            hash_value = (hash_value << 1) | (1 if left > right else 0)
    return f"{hash_value:016x}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    return _sha256_file(path)


def perceptual_hashes_for_file(path: Path) -> tuple[str, str]:
    image = Image.open(path)
    image = image.convert("RGB")
    return _phash_from_image(image), _dhash_from_image(image)


def perceptual_hashes_for_bytes(data: bytes) -> tuple[str, str]:
    from io import BytesIO

    image = Image.open(BytesIO(data))
    image = image.convert("RGB")
    return _phash_from_image(image), _dhash_from_image(image)


def apply_watermark_to_file(path: Path, owner_name: str | None) -> str:
    image = Image.open(path)
    image = image.convert("RGB")
    watermark_text, watermark_hash = _build_watermark_payload(owner_name)
    watermarked = _apply_invisible_watermark(image, watermark_text)
    watermarked.save(path, "JPEG", quality=90, progressive=True, comment=f"SkyFrame {watermark_hash}".encode())
    return watermark_hash


def regenerate_thumbnail(image_path: Path, thumb_path: Path) -> None:
    thumb = Image.open(image_path)
    thumb.thumbnail(Config.THUMB_SIZE, Image.LANCZOS)
    thumb.save(thumb_path, "JPEG", quality=80, progressive=True)


def read_watermark_comment_bytes(data: bytes) -> str | None:
    marker = b"SkyFrame "
    idx = 0
    length = len(data)
    while idx + 4 < length:
        if data[idx] != 0xFF:
            idx += 1
            continue
        marker_id = data[idx + 1]
        if marker_id == 0xDA or marker_id == 0xD9:
            break
        if idx + 4 > length:
            break
        segment_length = int.from_bytes(data[idx + 2 : idx + 4], "big")
        segment_start = idx + 4
        segment_end = segment_start + segment_length - 2
        if segment_end > length:
            break
        if marker_id == 0xFE:
            segment = data[segment_start:segment_end]
            pos = segment.find(marker)
            if pos != -1:
                comment = segment[pos:].decode("utf-8", "ignore")
                match = re.search(r"SkyFrame\\s+([0-9a-fA-F]+)", comment)
                if match:
                    return match.group(1).lower()
        idx = segment_end
    try:
        from io import BytesIO

        image = Image.open(BytesIO(data))
        comment = image.info.get("comment")
        if isinstance(comment, bytes):
            comment = comment.decode("utf-8", "ignore")
        if isinstance(comment, str):
            match = re.search(r"SkyFrame\\s+([0-9a-fA-F]+)", comment)
            if match:
                return match.group(1).lower()
    except Exception:
        return None
    return None


def read_watermark_comment(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except Exception:
        return None
    return read_watermark_comment_bytes(data)


def process_image_upload(
    file_storage: FileStorage, owner_name: str | None = None
) -> tuple[str, str, str, str, str, str]:
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
    watermark_text, watermark_hash = _build_watermark_payload(owner_name)
    watermarked = _apply_invisible_watermark(image, watermark_text)
    watermarked.save(img_path, "JPEG", quality=90, progressive=True, comment=f"SkyFrame {watermark_hash}".encode())
    signature_sha256 = _sha256_file(img_path)
    signature_phash, signature_dhash = perceptual_hashes_for_file(img_path)

    thumb = Image.open(img_path)
    thumb.thumbnail(Config.THUMB_SIZE, Image.LANCZOS)
    thumb.save(thumb_path, "JPEG", quality=80, progressive=True)

    return (
        str(img_path.relative_to(Config.UPLOAD_PATH)),
        str(thumb_path.relative_to(Config.UPLOAD_PATH)),
        watermark_hash,
        signature_sha256,
        signature_phash,
        signature_dhash,
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
