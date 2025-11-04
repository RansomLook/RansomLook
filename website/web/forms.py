from flask_wtf import FlaskForm # type: ignore
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, TextAreaField, FieldList, Form, FormField, IntegerField # type: ignore
from flask_wtf.file import FileField # type: ignore
from wtforms.validators import DataRequired, Optional # type: ignore

class AddForm(FlaskForm): # type: ignore
    category = SelectField('Database', choices=[('','Select a database'),(0, 'Group'),(3,'Market')],  default='', validators=[DataRequired()])
    groupname = StringField('Group name', validators=[DataRequired()])
    url = StringField('Url', validators=[Optional()])
    browser = SelectField('Browser', choices=[('','Select a browser'),('chrome', 'chrome'),('firefix','firefox'),('webkit','webkit')],  default='')
    init_script = TextAreaField(render_kw={'cols': 96, 'rows': 10})
    fs = BooleanField('File server')
    chat = BooleanField('Chat')
    admin = BooleanField('Admin')
    private = BooleanField('Private DLS')
    submit = SubmitField('Add')

class AlertForm(FlaskForm): # type: ignore
    keywords = TextAreaField()
    submit = SubmitField('Update Keywords')

class DeleteForm(FlaskForm): # type: ignore
    delete = BooleanField('Check to delete', validators=[DataRequired()])
    submit = SubmitField('Delete this group')

class LinkForm(Form): # type: ignore
    slug = StringField(validators=[DataRequired()], render_kw={'size': 96})
    fqdn = StringField(validators=[DataRequired()], render_kw={'size': 96})
    timeout= IntegerField(validators=[Optional()])
    delay = IntegerField(validators=[Optional()])
    fs = BooleanField('File Server')
    chat = BooleanField('Chat')
    admin = BooleanField('Admin')
    browser = SelectField('Browser', choices=[('','Select a browser'),('chrome', 'chrome'),('firefix','firefox'),('webkit','webkit')],  default='')
    init_script = TextAreaField(render_kw={'cols': 96, 'rows': 10})
    header = StringField(render_kw={'size': 96})
    version = IntegerField(validators=[Optional()])
    available = BooleanField()
    updated = StringField()
    lastscrape = StringField()
    title = StringField()
    private = BooleanField('Private Link')
    file = FileField('File')
    fixedfile = BooleanField('Don\'t update screen')
    delete = BooleanField('Check to delete')

class EditForm(FlaskForm): # type: ignore
    groupname = StringField(validators=[DataRequired()])
    captcha = BooleanField('Captcha')
    raas = BooleanField('RaaS')
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
    affiliates = TextAreaField()
    other = TextAreaField()
    links = FieldList(FormField(LinkForm), min_entries=0)
    private = BooleanField('Private Group')
    submit = SubmitField('Save changes')

class LogoForm(Form): # type: ignore
    link = StringField()
    delete = BooleanField('Check to delete')

class EditLogo(FlaskForm): # type: ignore
    logos = FieldList(FormField(LogoForm), min_entries=0)
    file = FileField('File')
    submit = SubmitField('Save changes')

class LoginForm(FlaskForm): # type: ignore
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class SelectForm(FlaskForm): # type: ignore
    group = SelectField('Group to edit', coerce=str, validate_choice=True, validators=[DataRequired()])
    submit = SubmitField('Edit this group')

class AddPostForm(FlaskForm): # type: ignore
    groupname = StringField()
    title = StringField(validators=[DataRequired()])
    description = TextAreaField()
    date = StringField()
    link = StringField()
    magnet = StringField()
    file = FileField('File')
    submit = SubmitField('Add post')

class EditPostForm(Form): # type: ignore
    post_title = StringField(validators=[DataRequired()])
    description = TextAreaField()
    discovered = StringField(validators=[DataRequired()])
    link = StringField()
    magnet = StringField()
    screen = StringField()
    file = FileField('File')
    delete = BooleanField('Delete')

class EditPostsForm(FlaskForm): # type: ignore
    postslist = FieldList(FormField(EditPostForm), min_entries=0)
    submit = SubmitField('Save changes')


# --- Threat Actors ---

class ActorSelectForm(FlaskForm):  # type: ignore
    actor = SelectField('Actor to edit', coerce=str, validate_choice=True, validators=[DataRequired()])  # type: ignore
    submit = SubmitField('Edit this actor')

class AddActorForm(FlaskForm):  # type: ignore
    # Identité / base
    name = StringField('Pseudonyme principal', validators=[DataRequired()])  # type: ignore
    aliases = StringField('Pseudos alternatifs (séparés par des virgules)')  # type: ignore
    bio = TextAreaField('Description générale', render_kw={'rows': 6})  # type: ignore
    private = BooleanField('Privé')  # type: ignore
    noactive = BooleanField('No more active')  # type: ignore
    tags = StringField('Tags (séparés par des virgules)')  # type: ignore

    # Infos personnelles
    first_name = StringField('Prénom')  # type: ignore
    last_name  = StringField('Nom')  # type: ignore
    age        = IntegerField('Âge', validators=[Optional()])  # type: ignore
    dob        = StringField('Date de naissance (YYYY-MM-DD)')  # type: ignore
    nationality= StringField('Nationalité')  # type: ignore
    location   = StringField('Localisation')  # type: ignore
    id_notes   = StringField('Notes identité')  # type: ignore

    # Wanted
    fbi_url      = StringField('FBI Most Wanted URL')  # type: ignore
    europol_url  = StringField('Europol Most Wanted URL')  # type: ignore
    interpol_url = StringField('INTERPOL Red Notice URL')  # type: ignore

    # Contacts / réseaux (un par ligne)
    tox       = TextAreaField('Tox (un par ligne)', render_kw={'rows': 2})  # type: ignore
    telegram  = TextAreaField('Telegram (un par ligne)', render_kw={'rows': 2})  # type: ignore
    x         = TextAreaField('X/Twitter (un par ligne)', render_kw={'rows': 2})  # type: ignore
    bluesky   = TextAreaField('Bluesky (un par ligne)', render_kw={'rows': 2})  # type: ignore
    email     = TextAreaField('Email (un par ligne)', render_kw={'rows': 2})  # type: ignore

    # Relations (séparés par virgules)
    groups = StringField('Relations Group (clés db=0, séparées par des virgules)')  # type: ignore
    forums = StringField('Relations Forum/Market (clés db=3, séparées par des virgules)')  # type: ignore
    peers  = StringField('Autres acteurs (noms, séparés par des virgules)')  # type: ignore

    # Sources (un URL par ligne — titre/notes optionnels seront gérés plus tard)
    sources = TextAreaField('Liens de documentation/source (un par ligne)', render_kw={'rows': 4})  # type: ignore

    submit = SubmitField('Save')  # type: ignore

class EditActorForm(AddActorForm):  # type: ignore
    # même champs ; on désactivera "name" côté template pour éviter de renommer la clé
    pass
