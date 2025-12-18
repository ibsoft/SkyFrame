from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from ..extensions import db, limiter
from ..forms import LoginForm, RegistrationForm
from ..models import User
from . import bp


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.feed"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower(),
            username=form.username.data.lower(),
            avatar_type="default",
        )
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
            flash("Welcome to SkyFrame!", "success")
            login_user(user)
            return redirect(url_for("main.feed"))
        except Exception:
            db.session.rollback()
            flash("Unable to create account right now.", "danger")
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("6 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.feed"))
    form = LoginForm()
    if form.validate_on_submit():
        user = (
            User.query.filter_by(username=form.username.data.lower()).first()
            if form.username.data
            else None
        )
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Welcome back", "success")
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("main.feed"))
        flash("Invalid credentials supplied.", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
def logout():
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("auth.login"))
