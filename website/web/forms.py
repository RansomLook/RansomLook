from flask_wtf import FlaskForm # type: ignore
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, TextAreaField # type: ignore
from flask_wtf.file import FileField # type: ignore
from wtforms.validators import DataRequired # type: ignore

class AddForm(FlaskForm): # type: ignore
    category = SelectField('Database', choices=[('','Select a database'),(0, 'Group'),(3,'Market'),(5,'Telegram'),(8,'Twitter')],  default='', validators=[DataRequired()])
    groupname = StringField('Group name', validators=[DataRequired()])
    url = StringField('Url', validators=[DataRequired()])
    fs = BooleanField('File server')
    private = BooleanField('Private DLS')
    submit = SubmitField('Add')

class AlertForm(FlaskForm): # type: ignore
    keywords = TextAreaField()
    submit = SubmitField('Update Keywords')

class DeleteForm(FlaskForm): # type: ignore
    delete = BooleanField('Check to delete', validators=[DataRequired()])
    submit = SubmitField('Delete this group')

class EditForm(FlaskForm): # type: ignore
    groupname = StringField(validators=[DataRequired()])
    galaxy = StringField()
    description = TextAreaField()
    profiles = TextAreaField()
    links = TextAreaField()
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

