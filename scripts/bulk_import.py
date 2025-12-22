import argparse
import mimetypes
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from werkzeug.datastructures import FileStorage

from skyframe import create_app
from skyframe.config import Config
from skyframe.extensions import db
from skyframe.forms import CATEGORY_CHOICES
from skyframe.models import Image, User
from skyframe.storage import process_image_upload

FILENAME_RE = re.compile(
    r"^(?:[A-Za-z])?(?P<date>\d{4}-\d{2}-\d{2})_"
    r"(?P<time>\d{2}-\d{2}-\d{2})(?:_(?P<filter>[^_]+))?(?:_(?P<observer>.+))?$"
)


def parse_filename(stem: str):
    match = FILENAME_RE.match(stem)
    if not match:
        return None, None, None
    date_part = match.group("date")
    time_part = match.group("time")
    observed_at = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H-%M-%S")
    return observed_at, match.group("filter"), match.group("observer")


def build_parser():
    categories = [choice[0] for choice in CATEGORY_CHOICES]
    parser = argparse.ArgumentParser(
        description="Bulk import a folder of images into SkyFrame."
    )
    parser.add_argument("folder", help="Folder containing image files.")
    parser.add_argument("--object", required=True, help="Object name for all images.")
    parser.add_argument("--username", required=True, help="Username to assign images to.")
    parser.add_argument(
        "--category",
        default="Other",
        choices=categories,
        help="Category for all images (default: Other).",
    )
    parser.add_argument(
        "--default-filter",
        default="RGB",
        help="Fallback filter when filename does not include one (default: RGB).",
    )
    parser.add_argument(
        "--env",
        default=os.getenv("FLASK_ENV", "default"),
        help="Flask config environment (default: FLASK_ENV or 'default').",
    )
    return parser


def iter_images(folder: Path):
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        ext = path.suffix.lower().lstrip(".")
        if ext not in Config.ALLOWED_IMAGE_EXTENSIONS:
            continue
        yield path


def main():
    parser = build_parser()
    args = parser.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        print(f"Folder not found: {folder}", file=sys.stderr)
        return 2

    app = create_app(args.env)
    imported = 0
    skipped = 0
    errors = 0

    with app.app_context():
        user = User.query.filter_by(username=args.username).first()
        if not user:
            print(f"User not found: {args.username}", file=sys.stderr)
            return 2

        for path in iter_images(folder):
            observed_at, filter_value, observer_name = parse_filename(path.stem)
            if not observed_at:
                print(f"Skipping (unmatched filename): {path.name}", file=sys.stderr)
                skipped += 1
                continue
            if not observer_name:
                observer_name = user.username
            if not filter_value:
                filter_value = args.default_filter

            try:
                with path.open("rb") as handle:
                    content_type, _ = mimetypes.guess_type(path.name)
                    file_storage = FileStorage(
                        stream=handle,
                        filename=path.name,
                        content_type=content_type or "application/octet-stream",
                    )
                    image_path, thumb_path, watermark_hash = process_image_upload(
                        file_storage, user.username
                    )
                image = Image(
                    user_id=user.id,
                    file_path=image_path,
                    thumb_path=thumb_path,
                    category=args.category,
                    object_name=args.object,
                    observer_name=observer_name,
                    observed_at=observed_at,
                    filter=filter_value,
                    watermark_hash=watermark_hash,
                )
                db.session.add(image)
                db.session.commit()
                imported += 1
            except Exception as exc:
                db.session.rollback()
                print(f"Error importing {path.name}: {exc}", file=sys.stderr)
                errors += 1

    print(
        f"Import complete. Imported: {imported}, skipped: {skipped}, errors: {errors}."
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
