from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import (
    DateTimeField,
    FileField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.fields import EmailField, PasswordField
from wtforms.validators import (
    DataRequired,
    EqualTo,
    Length,
    Optional,
    Regexp,
    ValidationError,
)

from .models import User


CATEGORY_CHOICES = [
    ("Planets", "Planets"),
    ("Deep Sky", "Deep Sky"),
    ("Comets", "Comets"),
    ("Sun", "Sun"),
    ("Moon", "Moon"),
    ("Other", "Other"),
]

SEARCH_CATEGORY_CHOICES = [("", "Any")] + CATEGORY_CHOICES


def password_complexity(form, field):
    password = field.data or ""
    if len(password) < 12:
        raise ValidationError("Password must be at least 12 characters.")
    tests = [any(c.islower() for c in password), any(c.isupper() for c in password)]
    tests.extend([any(c.isdigit() for c in password), any(c in "!@#$%^&*()-_+=" for c in password)])
    if not all(tests):
        raise ValidationError("Password must include upper, lower, number, and symbol.")


class RegistrationForm(FlaskForm):
    email = EmailField(
        "Email",
        validators=[DataRequired(), Length(max=255)],
        render_kw={"autocomplete": "email"},
    )
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=80), Regexp(r"^[A-Za-z0-9_]+$")],
        render_kw={"autocomplete": "username"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), password_complexity],
        render_kw={"autocomplete": "new-password"},
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("Create account")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError("Registration paused; try unique credential.")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data.lower()).first():
            raise ValidationError("Choose another handle.")


class LoginForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[DataRequired()],
        render_kw={"autocomplete": "username"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired()],
        render_kw={"autocomplete": "current-password"},
    )
    submit = SubmitField("Log in")


class UploadForm(FlaskForm):
    category = SelectField(
        "Category",
        choices=CATEGORY_CHOICES,
        validators=[DataRequired()],
    )
    object_name = StringField("Object Name", validators=[DataRequired(), Length(max=128)])
    observer_name = StringField("Observer Handle", validators=[DataRequired(), Length(max=128)])
    observed_at = DateTimeField(
        "Observed (UTC)",
        default=datetime.utcnow,
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()],
    )
    location = StringField("Location / Observatory", validators=[Optional(), Length(max=128)])
    filter = StringField("Filter", validators=[Optional(), Length(max=64)])
    telescope = StringField("Telescope", validators=[Optional(), Length(max=128)])
    camera = StringField("Camera", validators=[Optional(), Length(max=128)])
    notes = TextAreaField("Notes / Tags", validators=[Optional(), Length(max=512)])
    file = FileField("Image File", validators=[DataRequired()])
    submit = SubmitField("Upload")


class CommentForm(FlaskForm):
    body = TextAreaField("Comment", validators=[DataRequired(), Length(min=1, max=500)])
    submit = SubmitField("Post")


class SearchForm(FlaskForm):
    observer = StringField("Observer", validators=[Optional(), Length(max=128)])
    object_name = StringField("Object", validators=[Optional(), Length(max=128)])
    category = SelectField(
        "Category",
        choices=SEARCH_CATEGORY_CHOICES,
        validators=[Optional()],
    )
    date_from = DateTimeField("From (UTC)", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    date_to = DateTimeField("To (UTC)", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    query = StringField("Notes or Tags", validators=[Optional(), Length(max=256)])
    submit = SubmitField("Filter")


class ProfileForm(FlaskForm):
    avatar_type = SelectField(
        "Avatar Source",
        choices=[("gravatar", "Gravatar"), ("upload", "Upload")],
        validators=[DataRequired()],
    )
    avatar_upload = FileField("Upload Avatar", validators=[Optional()])
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Save Profile")


class ImageEditForm(FlaskForm):
    category = SelectField("Category", choices=CATEGORY_CHOICES, validators=[DataRequired()])
    object_name = StringField("Object Name", validators=[DataRequired(), Length(max=128)])
    observer_name = StringField("Observer Handle", validators=[DataRequired(), Length(max=128)])
    observed_at = DateTimeField(
        "Observed (UTC)",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()],
    )
    location = StringField("Location / Observatory", validators=[Optional(), Length(max=128)])
    filter = StringField("Filter", validators=[Optional(), Length(max=64)])
    telescope = StringField("Telescope", validators=[Optional(), Length(max=128)])
    camera = StringField("Camera", validators=[Optional(), Length(max=128)])
    notes = TextAreaField("Notes / Tags", validators=[Optional(), Length(max=512)])
    submit = SubmitField("Save changes")
