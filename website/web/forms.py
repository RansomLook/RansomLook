from flask_wtf import FlaskForm # type: ignore
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, TextAreaField, FieldList, Form, FormField, IntegerField # type: ignore
from flask_wtf.file import FileField # type: ignore
from wtforms.validators import DataRequired, Optional, ReadOnly # type: ignore

class AddForm(FlaskForm): # type: ignore
    category = SelectField('Database', choices=[('','Select a database'),(0, 'Group'),(3,'Market'),(5,'Telegram'),(8,'Twitter')],  default='', validators=[DataRequired()])
    groupname = StringField('Group name', validators=[DataRequired()])
    url = StringField('Url', validators=[Optional()])
    browser = SelectField('Browser', choices=[('','Select a browser'),('chrome', 'chrome'),('firefix','firefox'),('webkit','webkit')],  default='')
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
    matrix = TextAreaField()
    session = TextAreaField()
    telegram = TextAreaField()
    tox = TextAreaField()
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
