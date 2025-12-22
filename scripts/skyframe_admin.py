#!/usr/bin/env python3
import argparse
from datetime import datetime

from sqlalchemy import func

from skyframe import create_app
from skyframe.extensions import db
from skyframe.models import Image, Motd, User


def parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Invalid datetime format (use ISO 8601)") from exc


def with_app_context(fn):
    def wrapper(*args, **kwargs):
        app = create_app()
        with app.app_context():
            return fn(*args, **kwargs)

    return wrapper


@with_app_context
def cmd_users_list(_args):
    users = User.query.order_by(User.id.asc()).all()
    for user in users:
        status = "active" if user.active else "disabled"
        print(f"{user.id}\t{user.username}\t{user.email}\t{status}")


@with_app_context
def cmd_users_create(args):
    user = User(email=args.email.lower(), username=args.username.lower(), avatar_type="default")
    user.set_password(args.password)
    user.active = not args.disabled
    db.session.add(user)
    db.session.commit()
    print(f"Created user {user.username} (id={user.id})")


@with_app_context
def cmd_users_disable(args):
    user = None
    if args.id:
        user = User.query.get(args.id)
    elif args.username:
        user = User.query.filter_by(username=args.username.lower()).first()
    if not user:
        print("User not found")
        return
    user.active = False
    db.session.commit()
    print(f"Disabled user {user.username}")


@with_app_context
def cmd_motd_add(args):
    motd = Motd(
        title=args.title,
        body=args.body,
        published=args.publish,
        starts_at=parse_dt(args.starts_at),
        ends_at=parse_dt(args.ends_at),
    )
    db.session.add(motd)
    db.session.commit()
    print(f"Created MOTD {motd.id}")


@with_app_context
def cmd_motd_publish(args):
    motd = Motd.query.get(args.id)
    if not motd:
        print("MOTD not found")
        return
    motd.published = True
    if args.starts_at:
        motd.starts_at = parse_dt(args.starts_at)
    if args.ends_at:
        motd.ends_at = parse_dt(args.ends_at)
    db.session.commit()
    print(f"Published MOTD {motd.id}")


@with_app_context
def cmd_motd_expire(args):
    motd = Motd.query.get(args.id)
    if not motd:
        print("MOTD not found")
        return
    motd.published = False
    motd.ends_at = datetime.utcnow()
    db.session.commit()
    print(f"Expired MOTD {motd.id}")


@with_app_context
def cmd_stats(_args):
    total_users = db.session.query(func.count(User.id)).scalar() or 0
    total_images = db.session.query(func.count(Image.id)).scalar() or 0
    print(f"Total users: {total_users}")
    print(f"Total images: {total_images}")

    top_objects = (
        db.session.query(Image.object_name, func.count(Image.id))
        .group_by(Image.object_name)
        .order_by(func.count(Image.id).desc())
        .limit(10)
        .all()
    )
    print("Top objects:")
    for name, count in top_objects:
        print(f"- {name}: {count}")


def build_parser():
    parser = argparse.ArgumentParser(prog="skyframe_admin", description="SkyFrame admin CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    users_parser = subparsers.add_parser("users")
    users_sub = users_parser.add_subparsers(dest="users_command", required=True)

    users_list = users_sub.add_parser("list")
    users_list.set_defaults(func=cmd_users_list)

    users_create = users_sub.add_parser("create")
    users_create.add_argument("--email", required=True)
    users_create.add_argument("--username", required=True)
    users_create.add_argument("--password", required=True)
    users_create.add_argument("--disabled", action="store_true")
    users_create.set_defaults(func=cmd_users_create)

    users_disable = users_sub.add_parser("disable")
    users_disable_group = users_disable.add_mutually_exclusive_group(required=True)
    users_disable_group.add_argument("--id", type=int)
    users_disable_group.add_argument("--username")
    users_disable.set_defaults(func=cmd_users_disable)

    motd_parser = subparsers.add_parser("motd")
    motd_sub = motd_parser.add_subparsers(dest="motd_command", required=True)

    motd_add = motd_sub.add_parser("add")
    motd_add.add_argument("--title", required=True)
    motd_add.add_argument("--body", required=True)
    motd_add.add_argument("--starts-at")
    motd_add.add_argument("--ends-at")
    motd_add.add_argument("--publish", action="store_true")
    motd_add.set_defaults(func=cmd_motd_add)

    motd_publish = motd_sub.add_parser("publish")
    motd_publish.add_argument("--id", type=int, required=True)
    motd_publish.add_argument("--starts-at")
    motd_publish.add_argument("--ends-at")
    motd_publish.set_defaults(func=cmd_motd_publish)

    motd_expire = motd_sub.add_parser("expire")
    motd_expire.add_argument("--id", type=int, required=True)
    motd_expire.set_defaults(func=cmd_motd_expire)

    stats_parser = subparsers.add_parser("stats")
    stats_parser.set_defaults(func=cmd_stats)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
