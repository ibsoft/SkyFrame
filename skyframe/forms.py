from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateTimeField,
    FileField,
    FloatField,
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

from .config import Config
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

SEEING_CHOICES = [
    ("5", "5 — Excellent: No blur, Milky Way bright, extreme contrast."),
    ("4", "4 — Good: Slight contrast loss, still excellent."),
    ("3", "3 — Average: Mild blur, brighter background."),
    ("2", "2 — Poor: Humidity, thin clouds, fuzziness."),
    ("1", "1 — Very poor: Milky Way milky, not useful for high-res."),
]

TRANSPARENCY_CHOICES = [
    ("5", "5 — Excellent: Crystal clear, excellent stars."),
    ("4", "4 — Good: Minor haze, still solid detail."),
    ("3", "3 — Average: Light haze, moderate glow."),
    ("2", "2 — Poor: Noticeable haze or dust."),
    ("1", "1 — Very poor: Thick haze or light pollution."),
]

BORTLE_CHOICES = [
    ("1", "1 — Excellent dark-sky (pristine)."),
    ("2", "2 — Very dark sky."),
    ("3", "3 — Rural sky."),
    ("4", "4 — Rural/suburban transition."),
    ("5", "5 — Suburban sky."),
    ("6", "6 — Bright suburban."),
    ("7", "7 — Urban sky."),
    ("8", "8 — City sky."),
    ("9", "9 — Inner-city with heavy light pollution."),
]


def password_complexity(form, field):
    password = field.data or ""
    if len(password) < Config.PASSWORD_MIN_LENGTH:
        raise ValidationError("Password must be at least 12 characters.")
    tests = []
    if Config.PASSWORD_REQUIRE_LOWER:
        tests.append(any(c.islower() for c in password))
    if Config.PASSWORD_REQUIRE_UPPER:
        tests.append(any(c.isupper() for c in password))
    if Config.PASSWORD_REQUIRE_DIGIT:
        tests.append(any(c.isdigit() for c in password))
    if Config.PASSWORD_REQUIRE_SYMBOL:
        tests.append(any(c in "!@#$%^&*()-_+=" for c in password))
    if tests and not all(tests):
        raise ValidationError("Password must include upper, lower, number, and symbol.")


def password_requirements_summary():
    requirements = []
    if Config.PASSWORD_REQUIRE_UPPER:
        requirements.append("uppercase")
    if Config.PASSWORD_REQUIRE_LOWER:
        requirements.append("lowercase")
    if Config.PASSWORD_REQUIRE_DIGIT:
        requirements.append("a digit")
    if Config.PASSWORD_REQUIRE_SYMBOL:
        requirements.append("a symbol")
    base = f"Password must be at least {Config.PASSWORD_MIN_LENGTH} characters"
    if requirements:
        if len(requirements) == 1:
            req_str = requirements[0]
        else:
            req_str = ", ".join(requirements[:-1]) + " and " + requirements[-1]
        base += f" and include {req_str}"
    return base + "."


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
    location = StringField("Location / Observatory", validators=[DataRequired(), Length(max=128)])
    filter = StringField("Filter", validators=[DataRequired(), Length(max=64)])
    telescope = StringField("Telescope", validators=[DataRequired(), Length(max=128)])
    camera = StringField("Camera", validators=[DataRequired(), Length(max=128)])
    notes = TextAreaField("Notes / Tags", validators=[DataRequired(), Length(max=512)])
    derotation_time = FloatField("Derotation time (minutes)", validators=[Optional()])
    max_exposure_time = FloatField("Max exposure time (seconds)", validators=[Optional()])
    seeing_rating = SelectField(
        "Seeing (Pickering 1–5)",
        choices=SEEING_CHOICES,
        validators=[DataRequired()],
    )
    transparency_rating = SelectField(
        "Transparency (1–5)",
        choices=TRANSPARENCY_CHOICES,
        validators=[DataRequired()],
    )
    bortle_rating = SelectField(
        "Bortle scale (1–9)",
        choices=BORTLE_CHOICES,
        validators=[Optional()],
    )
    allow_scientific_use = BooleanField("Allow scientific reuse to all organizations and papers")
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
        choices=[("default", "Default icon"), ("gravatar", "Gravatar"), ("upload", "Upload")],
        validators=[DataRequired()],
    )
    avatar_upload = FileField("Upload Avatar", validators=[Optional()])
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=500)])
    observatory_name = StringField("Observatory Name", validators=[Optional(), Length(max=128)])
    observatory_location = StringField(
        "Observatory Location", validators=[Optional(), Length(max=128)]
    )
    observatory_latitude = FloatField("Observatory Latitude", validators=[Optional()])
    observatory_longitude = FloatField("Observatory Longitude", validators=[Optional()])
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
    location = StringField("Location / Observatory", validators=[DataRequired(), Length(max=128)])
    filter = StringField("Filter", validators=[DataRequired(), Length(max=64)])
    telescope = StringField("Telescope", validators=[DataRequired(), Length(max=128)])
    camera = StringField("Camera", validators=[DataRequired(), Length(max=128)])
    notes = TextAreaField("Notes / Tags", validators=[DataRequired(), Length(max=512)])
    derotation_time = FloatField("Derotation time (minutes)", validators=[Optional()])
    max_exposure_time = FloatField("Max exposure time (seconds)", validators=[Optional()])
    seeing_rating = SelectField(
        "Seeing (Pickering 1–5)",
        choices=SEEING_CHOICES,
        validators=[DataRequired()],
    )
    transparency_rating = SelectField(
        "Transparency (1–5)",
        choices=TRANSPARENCY_CHOICES,
        validators=[DataRequired()],
    )
    bortle_rating = SelectField(
        "Bortle scale (1–9)",
        choices=BORTLE_CHOICES,
        validators=[Optional()],
    )
    allow_scientific_use = BooleanField("Allow scientific reuse to all organizations and papers")
    submit = SubmitField("Save changes")
