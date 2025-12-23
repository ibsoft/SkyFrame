#!/usr/bin/env python3
import argparse
from pathlib import Path

from skyframe import create_app
from skyframe.extensions import db
from skyframe.models import Image
from skyframe.storage import (
    apply_watermark_to_file,
    perceptual_hashes_for_file,
    regenerate_thumbnail,
    sha256_file,
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="skyframe_backfill_signatures",
        description="Backfill watermark and SHA-256 signatures for existing images",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    parser.add_argument("--force", action="store_true", help="Re-apply watermark and signature even if present")
    parser.add_argument(
        "--skip-watermark",
        action="store_true",
        help="Only compute SHA-256 without applying watermark",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most this many images (0 = no limit)",
    )
    return parser


def main():
    args = build_parser().parse_args()
    app = create_app()

    with app.app_context():
        base_path = Path(app.config["UPLOAD_PATH"])
        images = Image.query.order_by(Image.id.asc()).all()
        changed = 0
        scanned = 0

        for image in images:
            if args.limit and scanned >= args.limit:
                break
            scanned += 1
            file_path = base_path / image.file_path
            thumb_path = base_path / image.thumb_path
            if not file_path.exists():
                app.logger.warning("Missing image file for id=%s", image.id)
                continue

            updated = False
            watermark_hash = image.watermark_hash
            signature_sha256 = image.signature_sha256
            signature_phash = image.signature_phash
            signature_dhash = image.signature_dhash

            apply_watermark = not args.skip_watermark and (args.force or not watermark_hash)
            if apply_watermark:
                watermark_hash = apply_watermark_to_file(file_path, image.uploader.username)
                regenerate_thumbnail(file_path, thumb_path)
                updated = True

            if args.force or not signature_sha256 or not signature_phash or not signature_dhash or updated:
                signature_sha256 = sha256_file(file_path)
                signature_phash, signature_dhash = perceptual_hashes_for_file(file_path)
                updated = True

            if updated:
                changed += 1
                if not args.dry_run:
                    image.watermark_hash = watermark_hash
                    image.signature_sha256 = signature_sha256
                    image.signature_phash = signature_phash
                    image.signature_dhash = signature_dhash
                    db.session.add(image)

            if not args.dry_run and scanned % 50 == 0:
                db.session.commit()

        if not args.dry_run:
            db.session.commit()

        print(f"Scanned: {scanned}")
        print(f"Updated: {changed}")


if __name__ == "__main__":
    main()
