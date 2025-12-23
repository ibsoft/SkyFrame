import hashlib
from datetime import datetime

from argon2 import PasswordHasher
from flask import url_for
from flask_login import UserMixin

from .extensions import db

ph = PasswordHasher(time_cost=2, memory_cost=102400, parallelism=8, hash_len=32)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    avatar_type = db.Column(db.String(64), default="gravatar", nullable=False)
    avatar_path = db.Column(db.String(255))
    bio = db.Column(db.Text)
    observatory_name = db.Column(db.String(128))
    observatory_location = db.Column(db.String(128))
    observatory_latitude = db.Column(db.Float)
    observatory_longitude = db.Column(db.Float)
    active = db.Column(db.Boolean, default=True, nullable=False)

    uploads = db.relationship("Image", backref="uploader", lazy="dynamic")
    likes = db.relationship("Like", backref="user", lazy="dynamic")
    favorites = db.relationship("Favorite", backref="user", lazy="dynamic")
    following = db.relationship(
        "Follow",
        foreign_keys="[Follow.follower_id]",
        backref="follower",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    followers = db.relationship(
        "Follow",
        foreign_keys="[Follow.followed_id]",
        backref="followed",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    comments = db.relationship("Comment", backref="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = ph.hash(password)

    def check_password(self, password: str) -> bool:
        try:
            return ph.verify(self.password_hash, password)
        except Exception:
            return False

    @property
    def is_active(self) -> bool:
        return self.active

    def likes_count(self):
        return self.likes.count()

    def favorites_count(self):
        return self.favorites.count()

    def uploads_count(self):
        return self.uploads.count()

    def following_count(self):
        return self.following.count()

    def followers_count(self):
        return self.followers.count()

    @property
    def avatar_url(self) -> str:
        if self.avatar_type == "upload" and self.avatar_path:
            return url_for("main.uploads", filename=self.avatar_path)
        if self.avatar_type == "gravatar" and self.email:
            digest = hashlib.md5(self.email.strip().lower().encode()).hexdigest()
            return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s=96"
        return url_for("static", filename="icons/user.png")


class Image(db.Model):
    __tablename__ = "images"
    __table_args__ = (
        db.Index("ix_images_category", "category"),
        db.Index("ix_images_object", "object_name"),
        db.Index("ix_images_observer", "observer_name"),
        db.Index("ix_images_observed_at", "observed_at"),
        db.Index("ix_images_created_at", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    thumb_path = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(64), nullable=False)
    object_name = db.Column(db.String(128), nullable=False)
    observer_name = db.Column(db.String(128), nullable=False)
    observed_at = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(128))
    filter = db.Column(db.String(64))
    telescope = db.Column(db.String(128))
    camera = db.Column(db.String(128))
    notes = db.Column(db.Text)
    allow_scientific_use = db.Column(db.Boolean, default=False, nullable=False)
    watermark_hash = db.Column(db.String(64))
    signature_sha256 = db.Column(db.String(64))
    signature_phash = db.Column(db.String(16))
    signature_dhash = db.Column(db.String(16))
    seeing_rating = db.Column(db.Integer, nullable=True)
    transparency_rating = db.Column(db.Integer, nullable=True)
    bortle_rating = db.Column(db.Integer, nullable=True)
    max_exposure_time = db.Column(db.Float, nullable=True)
    derotation_time = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    likes = db.relationship("Like", backref="image", lazy="dynamic", cascade="all, delete-orphan")
    favorites = db.relationship(
        "Favorite", backref="image", lazy="dynamic", cascade="all, delete-orphan"
    )
    comments = db.relationship("Comment", backref="image", lazy="dynamic", cascade="all, delete-orphan")

    def like_count(self):
        return self.likes.count()

    def favorite_count(self):
        return self.favorites.count()


class Like(db.Model):
    __tablename__ = "likes"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey("images.id"), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Favorite(db.Model):
    __tablename__ = "favorites"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey("images.id"), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Follow(db.Model):
    __tablename__ = "follows"
    follower_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey("images.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Motd(db.Model):
    __tablename__ = "motd"
    __table_args__ = (
        db.Index("ix_motd_published", "published"),
        db.Index("ix_motd_window", "starts_at", "ends_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    body = db.Column(db.Text, nullable=False)
    published = db.Column(db.Boolean, default=False, nullable=False)
    starts_at = db.Column(db.DateTime, nullable=True)
    ends_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class MotdSeen(db.Model):
    __tablename__ = "motd_seen"
    __table_args__ = (
        db.UniqueConstraint("user_id", "motd_id", name="uq_motd_seen_user"),
        db.Index("ix_motd_seen_user", "user_id", "seen_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    motd_id = db.Column(db.Integer, db.ForeignKey("motd.id"), nullable=False)
    seen_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class FeedSeen(db.Model):
    __tablename__ = "feed_seen"
    __table_args__ = (
        db.UniqueConstraint("user_id", "image_id", name="uq_feed_seen_user_image"),
        db.Index("ix_feed_seen_user_seen_at", "user_id", "seen_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    image_id = db.Column(db.Integer, db.ForeignKey("images.id"), nullable=False)
    seen_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
