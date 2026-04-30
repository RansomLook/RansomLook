from flask_wtf import FlaskForm  # type: ignore
from flask_wtf.file import FileAllowed, FileField  # type: ignore
from wtforms import (  # type: ignore
    BooleanField,
    FieldList,
    Form,
    FormField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Optional  # type: ignore


class AnalysisSelectForm(FlaskForm):  # type: ignore[misc]
    """Selector for the group whose Markdown analysis we want to edit/add."""
    group = SelectField("Group", coerce=str, validate_choice=True, validators=[DataRequired()])
    submit = SubmitField("Edit analysis")


class AnalysisForm(FlaskForm):  # type: ignore[misc]
    """Upload or paste a Markdown technical analysis for a group.

    Either ``upload`` (a .md file) or ``content`` (textarea body) must be set;
    if both are provided, the uploaded file wins.
    """
    content = TextAreaField(
        "Markdown content",
        # Explicit id avoids collision with base.html's <main id="content">.
        render_kw={"id": "md-content", "cols": 100, "rows": 30, "spellcheck": "false"},
        validators=[Optional()],
    )
    upload = FileField(
        "or upload a .md file",
        validators=[
            Optional(),
            FileAllowed(["md", "markdown", "txt"], "Markdown files only"),
        ],
    )
    sha256 = StringField(
        "Sample SHA-256",
        validators=[Optional()],
        render_kw={"placeholder": "64 hex chars (optional)", "spellcheck": "false", "autocomplete": "off"},
    )
    author = StringField(
        "Analyst",
        validators=[Optional()],
        render_kw={"placeholder": "e.g. fkz, John Doe…"},
    )
    analysis_date = StringField(
        "Analysis date (YYYY-MM-DD)",
        validators=[Optional()],
        render_kw={"placeholder": "2026-04-25"},
    )
    analysis_type = SelectField(
        "Document type",
        choices=[("full", "Full technical analysis"), ("cti", "CTI report")],
        default="full",
        validators=[Optional()],
    )
    private = BooleanField("Private (visible to authenticated users only)", default=False)
    submit = SubmitField("Save")


class AddForm(FlaskForm):  # type: ignore[misc]
    category = SelectField(
        "Database",
        choices=[("", "Select a database"), (0, "Group"), (3, "Market")],
        default="",
        validators=[DataRequired()],
    )
    groupname = StringField("Group name", validators=[DataRequired()])
    url = StringField("Url", validators=[Optional()])
    browser = SelectField(
        "Browser",
        choices=[("", "Select a browser"), ("chrome", "chrome"), ("firefix", "firefox"), ("webkit", "webkit")],
        default="",
    )
    init_script = TextAreaField(render_kw={"cols": 96, "rows": 10})
    fs = BooleanField("File server")
    chat = BooleanField("Chat")
    admin = BooleanField("Admin")
    private = BooleanField("Private DLS")
    submit = SubmitField("Add")


class AlertForm(FlaskForm):  # type: ignore[misc]
    keywords = TextAreaField()
    submit = SubmitField("Update Keywords")


class DeleteForm(FlaskForm):  # type: ignore[misc]
    delete = BooleanField("Check to delete", validators=[DataRequired()])
    submit = SubmitField("Delete this group")


class LinkForm(Form):  # type: ignore[misc]
    slug = StringField(validators=[DataRequired()], render_kw={"size": 96})
    fqdn = StringField(validators=[DataRequired()], render_kw={"size": 96})
    timeout = IntegerField(validators=[Optional()])
    delay = IntegerField(validators=[Optional()])
    fs = BooleanField("File Server")
    chat = BooleanField("Chat")
    admin = BooleanField("Admin")
    browser = SelectField(
        "Browser",
        choices=[("", "Select a browser"), ("chrome", "chrome"), ("firefix", "firefox"), ("webkit", "webkit")],
        default="",
    )
    init_script = TextAreaField(render_kw={"cols": 96, "rows": 10})
    header = StringField(render_kw={"size": 96})
    version = IntegerField(validators=[Optional()])
    available = BooleanField()
    updated = StringField()
    lastscrape = StringField()
    title = StringField()
    private = BooleanField("Private Link")
    file = FileField("File")
    fixedfile = BooleanField("Don't update screen")
    delete = BooleanField("Check to delete")


class EditForm(FlaskForm):  # type: ignore[misc]
    groupname = StringField(validators=[DataRequired()])
    captcha = BooleanField("Captcha")
    raas = BooleanField("RaaS")
    galaxy = StringField()
    description = TextAreaField()
    profiles = TextAreaField()
    jabber = TextAreaField()
    mail = TextAreaField()
    pgp = TextAreaField()
    hash = TextAreaField()
    matrix = TextAreaField()
    session = TextAreaField()
    telegram = TextAreaField()
    tox = TextAreaField()
    simplex = TextAreaField()
    max = TextAreaField()
    sonar = TextAreaField()
    affiliates = TextAreaField()
    other = TextAreaField()
    links = FieldList(FormField(LinkForm), min_entries=0)
    private = BooleanField("Private Group")
    submit = SubmitField("Save changes")


class LogoForm(Form):  # type: ignore[misc]
    link = StringField()
    delete = BooleanField("Check to delete")


class EditLogo(FlaskForm):  # type: ignore[misc]
    logos = FieldList(FormField(LogoForm), min_entries=0)
    file = FileField("File")
    submit = SubmitField("Save changes")


class LoginForm(FlaskForm):  # type: ignore[misc]
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign In")


class SelectForm(FlaskForm):  # type: ignore[misc]
    group = SelectField("Group to edit", coerce=str, validate_choice=True, validators=[DataRequired()])
    submit = SubmitField("Edit this group")


class AddPostForm(FlaskForm):  # type: ignore[misc]
    groupname = StringField()
    title = StringField(validators=[DataRequired()])
    description = TextAreaField()
    date = StringField()
    link = StringField()
    magnet = StringField()
    file = FileField("File")
    submit = SubmitField("Add post")


class EditPostForm(Form):  # type: ignore[misc]
    post_title = StringField(validators=[DataRequired()])
    description = TextAreaField()
    discovered = StringField(validators=[DataRequired()])
    link = StringField()
    magnet = StringField()
    screen = StringField()
    file = FileField("File")
    delete = BooleanField("Delete")


class EditPostsForm(FlaskForm):  # type: ignore[misc]
    postslist = FieldList(FormField(EditPostForm), min_entries=0)
    submit = SubmitField("Save changes")


# --- Threat Actors ---


class ActorSelectForm(FlaskForm):  # type: ignore[misc]
    actor = SelectField("Actor to edit", coerce=str, validate_choice=True, validators=[DataRequired()])
    submit = SubmitField("Edit this actor")


class AddActorForm(FlaskForm):  # type: ignore[misc]
    # Identité / base
    name = StringField("Pseudonyme principal", validators=[DataRequired()])
    aliases = StringField("Pseudos alternatifs (séparés par des virgules)")
    bio = TextAreaField("Description générale", render_kw={"rows": 6})
    private = BooleanField("Privé")
    noactive = BooleanField("No more active")
    tags = StringField("Tags (séparés par des virgules)")

    # Infos personnelles
    first_name = StringField("Prénom")
    last_name = StringField("Nom")
    age = IntegerField("Âge", validators=[Optional()])
    dob = StringField("Date de naissance (YYYY-MM-DD)")
    nationality = StringField("Nationalité")
    location = StringField("Localisation")
    id_notes = StringField("Notes identité")

    # Wanted
    fbi_url = StringField("FBI Most Wanted URL")
    europol_url = StringField("Europol Most Wanted URL")
    interpol_url = StringField("INTERPOL Red Notice URL")

    # Contacts / réseaux (un par ligne)
    jabber = TextAreaField("Jabber (un par ligne)", render_kw={"rows": 2})
    email = TextAreaField("Email (un par ligne)", render_kw={"rows": 2})
    pgp = TextAreaField("PGP (un par ligne)", render_kw={"rows": 2})
    matrix = TextAreaField("Matrix (un par ligne)", render_kw={"rows": 2})
    session = TextAreaField("Session (un par ligne)", render_kw={"rows": 2})
    telegram = TextAreaField("Telegram (un par ligne)", render_kw={"rows": 2})
    tox = TextAreaField("Tox (un par ligne)", render_kw={"rows": 2})
    simplex = TextAreaField("Simplex (un par ligne)", render_kw={"rows": 2})
    max = TextAreaField("Max (un par ligne)", render_kw={"rows": 2})
    sonar = TextAreaField("Sonar (un par ligne)", render_kw={"rows": 2})
    x = TextAreaField("X/Twitter (un par ligne)", render_kw={"rows": 2})
    bluesky = TextAreaField("Bluesky (un par ligne)", render_kw={"rows": 2})

    # Relations (séparés par virgules)
    groups = StringField("Relations Group (clés db=0, séparées par des virgules)")
    forums = StringField("Relations Forum/Market (clés db=3, séparées par des virgules)")
    peers = StringField("Autres acteurs (noms, séparés par des virgules)")

    # Sources (un URL par ligne — titre/notes optionnels seront gérés plus tard)
    sources = TextAreaField("Liens de documentation/source (un par ligne)", render_kw={"rows": 4})

    submit = SubmitField("Save")


class EditActorForm(AddActorForm):
    # même champs ; on désactivera "name" côté template pour éviter de renommer la clé
    pass
