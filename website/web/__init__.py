from flask import Flask, render_template, redirect, url_for, flash
import flask_moment # type: ignore
from flask import request, send_from_directory
from flask_bootstrap import Bootstrap5  # type: ignore
from flask_login import current_user # type: ignore
from urllib.parse import quote

from datetime import datetime as dt
from datetime import timedelta
from dateutil import parser
import glob
from os.path import dirname, basename, isfile, join
import os
import json
from redis import Redis

import ast
import flask_login
from werkzeug.security import check_password_hash
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

from flask_cors import CORS
from flask_restx import Api  # type: ignore

from importlib.metadata import version

import hashlib

import imghdr

from collections import OrderedDict
from collections import defaultdict
from collections import namedtuple

from ransomlook.posts import appender

from ransomlook.ransomlook import adder
from ransomlook.sharedutils import createfile
from ransomlook.sharedutils import groupcount, hostcount, hostcountdls, hostcountfs, hostcountchat, onlinecount, postslast24h, mounthlypostcount, currentmonthstr, postssince, poststhisyear, postcount, parsercount, statsgroup, run_data_viz
from ransomlook.default.config import get_homedir
from ransomlook.default.config import get_config
from ransomlook.default import get_socket_path
from ransomlook.telegram import teladder
from ransomlook.twitter import twiadder
from .helpers import get_secret_key, sri_load, User, build_users_table, load_user_from_request
from .forms import AddForm, LoginForm, SelectForm, EditForm, DeleteForm, AlertForm, AddPostForm, EditPostForm, EditPostsForm
from .ldap import global_ldap_authentication

from typing import Dict, Any, Optional

from .api.genericapi import api as generic_api
from .api.telegramapi import api as telegram_api
from .api.rfapi import api as rf_api
from .api.leaksapi import api as leaks_api

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_for=1) # type: ignore
app.jinja_env.filters['quote_plus'] = lambda u: quote(u)
app.config['SECRET_KEY'] = get_secret_key()
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.config['UPLOAD_EXTENSIONS'] = ['.png', '.jpg']

Bootstrap5(app)
app.config['BOOTSTRAP_SERVE_LOCAL'] = True
app.config['SESSION_COOKIE_NAME'] = 'RansomLook'
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
if get_config('generic','darkmode'):
    app.config['BOOTSTRAP_BOOTSWATCH_THEME'] = 'slate'
app.debug = False

pkg_version = version('ransomlook')

flask_moment.Moment(app=app)

def validate_image(stream): # type: ignore[no-untyped-def]
    header = stream.read(512)
    stream.seek(0) 
    format = imghdr.what(None, header)
    if not format:
        return None
    return '.' + (format if format != 'jpeg' else 'jpg')

@app.context_processor
def inject_global_vars() -> Dict[str, bool]:
    darkmode = False
    activatedRF = False
    if get_config('generic','darkmode'):
        darkmode = True
    if get_config('generic','rf') != "" :
        activatedRF = True
    return {'darkmode': darkmode, 'activatedRF': activatedRF}
# Getting the error
#@app.errorhandler(Exception)
def handle_error(e): # type: ignore[no-untyped-def]
    code = 500
    if isinstance(e, HTTPException):
        return render_template('40x.html', error=e.name, message=e.description), code
    print(e)
    return render_template("500_generic.html", e=e), 500

@app.route('/favicon.ico')
def favicon(): # type: ignore[no-untyped-def]
    return send_from_directory(os.path.join(get_homedir(), 'website/web/static'),
                               'ransomlook.svg', mimetype='image/svg+xml')

ldap_config = get_config('generic','ldap')
ldap = ldap_config['enable']
# Auth stuff
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

@login_manager.user_loader # type: ignore[misc]
def user_loader(username: str) -> Optional[str]:
    if not ldap:
        if username not in build_users_table():
            return None
    user = User()
    user.id = username
    return user


@login_manager.request_loader
def _load_user_from_request(request): # type: ignore
    return load_user_from_request(request) # type: ignore[no-untyped-call]


@app.route('/login', methods=['GET', 'POST'])
def login(): # type: ignore[no-untyped-def]
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        if not ldap_config['enable']:
            users_table = build_users_table()
            if username in users_table and check_password_hash(users_table[username]['password'], form.password.data): # type: ignore[no-untyped-call]
                user = User()
                user.id = username
                flask_login.login_user(user)
                flash(f'Logged in as: {flask_login.current_user.id}', 'success')
                return redirect(url_for('admin'))
            else:
                flash(f'Unable to login as: {username}', 'error')
        else:
            if global_ldap_authentication(username, form.password.data, ldap_config):
                user = User()
                user.id = username
                flask_login.login_user(user)
                flash(f'Logged in as: {flask_login.current_user.id}', 'success')
                return redirect(url_for('admin'))
            else:
                flash(f'Unable to login as: {username}', 'error')
    return render_template('login.html', form=form)


@app.route('/logout')
@flask_login.login_required # type: ignore[no-untyped-def]
def logout():
    flask_login.logout_user()
    flash('Successfully logged out.', 'success')
    return redirect(url_for('home'))

# End auth

def get_sri(directory: str, filename: str) -> str:
    sha512 = sri_load()[directory][filename]
    return f'sha512-{sha512}'

app.jinja_env.globals.update(get_sri=get_sri)

def suffix(d: int) -> str :
    return 'th' if 11<=d<=13 else {1:'st',2:'nd',3:'rd'}.get(d%10, 'th')

def custom_strftime(fmt, t) -> str: # type: ignore
    return t.strftime(fmt).replace('{S}', str(t.day) + suffix(t.day))

@app.route('/')
def home(): # type: ignore[no-untyped-def]
        date = custom_strftime('%B {S}, %Y', dt.now()).lower()
        data = {}
        data['nbgroups'] = groupcount(0)
        data['nblocations'] = hostcount(0)
        data['nbdls'] = hostcountdls(0)
        data['nbfs'] = hostcountfs(0)
        data['nbchat'] = hostcountchat(0)
        data['online'] = onlinecount(0)
        data['nbforum'] = groupcount(3)
        data['nbforumlocations'] = hostcount(3)
        data['forumonline'] = onlinecount(3)
        data['nbtelegram'] = groupcount(5)
        data['24h'] = postslast24h()
        data['monthlypost'] = mounthlypostcount()
        data['month'] = currentmonthstr() # type: ignore
        data['90d'] = postssince(90)
        data['yearlypost'] = poststhisyear()
        data['year'] = dt.now().year
        data['nbposts'] = postcount()
        data['nbparsers'] = parsercount()
        alertposts= defaultdict(list)
        alert=get_config('generic','alertondashboard')
        if alert is True:
            red = Redis(unix_socket_path=get_socket_path('cache'), db=12)
            groups = red.keys()
            for entry in groups:
                post = json.loads(red.get(entry)) # type: ignore
                alertposts[post['type']].append(post)
        return render_template("index.html", date=date, data=data,alert=alert, posts=alertposts)

@app.route("/recent")
def recent(): # type: ignore[no-untyped-def]
        posts = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    entry['group_name']=key.decode()
                    posts.append(entry)
        sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
        recentposts = []
        for post in sorted_posts:
                recentposts.append(post)
                if len(recentposts) == 100:
                        break
        return render_template("recent.html", data=recentposts)

@app.route("/rss.xml")
def feeds(): # type: ignore[no-untyped-def]
        posts = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    entry['group_name']=key.decode()
                    posts.append(entry)
        sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
        recentposts = []
        for post in sorted_posts:
                post['discovered'] = dt.strptime(post['discovered'].split('.')[0], "%Y-%m-%d %H:%M:%S").strftime("%a, %d %b %Y %T")
                post['guid'] = hashlib.sha256(post['post_title'].encode()+post['group_name'].encode()).hexdigest()
                recentposts.append(post)
                if len(recentposts) == 50:
                        break
        return render_template("rss.xml", posts=recentposts, build_date=dt.now()), {'Content-Type': 'application/xml'}

@app.route("/stats")
def stats(): # type: ignore[no-untyped-def]
        return render_template("stats.html")

@app.route("/about")
def about(): # type: ignore[no-untyped-def]
        return render_template("about.html")

@app.route("/status")
def status(): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        groups = []
        for key in red.keys():
                entry= json.loads(red.get(key)) # type: ignore
                if not current_user.is_authenticated and 'private' in entry and entry['private'] is True:
                    continue
                entry['name']=key.decode()
                groups.append(entry)
        groups.sort(key=lambda x: x["name"].lower())
        for group in groups:
            for location in group['locations']:
                screenfile = '/screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                if os.path.exists(str(get_homedir()) + '/source' + screenfile):
                    location['screen']=screenfile
        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        markets = []
        for key in red.keys():
                entry= json.loads(red.get(key)) # type: ignore
                entry['name']=key.decode()
                markets.append(entry)
        markets.sort(key=lambda x: x["name"].lower())
        for group in markets:
            for location in group['locations']:
                screenfile = '/screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                if os.path.exists(str(get_homedir()) + '/source' + screenfile):
                    location['screen']=screenfile

        return render_template("status.html", data=groups, markets=markets)

@app.route("/alive")

def alive(): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        groups = []
        for key in red.keys():
                entry= json.loads(red.get(key)) # type: ignore
                if not current_user.is_authenticated and 'private' in entry and entry['private'] is True:
                    continue
                entry['name']=key.decode()
                groups.append(entry)
        groups.sort(key=lambda x: x["name"].lower())
        for group in groups:
            for location in group['locations']:
                screenfile = '/screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                if os.path.exists(str(get_homedir()) + '/source' + screenfile):
                    location['screen']=screenfile
        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        markets = []
        for key in red.keys():
                entry= json.loads(red.get(key)) # type: ignore
                entry['name']=key.decode()
                markets.append(entry)
        markets.sort(key=lambda x: x["name"].lower())
        for group in markets:
            for location in group['locations']:
                screenfile = '/screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                if os.path.exists(str(get_homedir()) + '/source' + screenfile):
                    location['screen']=screenfile

        return render_template("alive.html", data=groups, markets=markets)


@app.route("/groups")
def groups(): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)

        groups = []
        for key in red.keys():
                entry= json.loads(red.get(key)) # type: ignore
                if not current_user.is_authenticated and 'private' in entry and entry['private'] is True:
                    continue
                entry['name']=key.decode()
                groups.append(entry)
        groups.sort(key=lambda x: x["name"].lower())
        for group in groups:
            for location in group['locations']:
                screenfile = '/screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                if os.path.exists(str(get_homedir()) + '/source' + screenfile):
                    location['screen']=screenfile
        modules = glob.glob(join(dirname(str(get_homedir())+'/ransomlook/parsers/'), "*.py"))
        parserlist = [ basename(f)[:-3].split('.')[0] for f in modules if isfile(f) and not f.endswith('__init__.py')]
        return render_template("groups.html", data=groups, parser=parserlist, type="groups")

@app.route("/group/<name>")
def group(name: str): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        for key in red.keys():
                if key.decode().lower() == name.lower():
                        group= json.loads(red.get(key)) # type: ignore
                        if not current_user.is_authenticated and 'private' in group and group['private'] is True:
                            return redirect(url_for("home"))

                        group['name']=key.decode()
                        if group['meta'] is not None:
                            group['meta']=group['meta'].replace('\n', '<br/>')
                        for location in group['locations']:
                            screenfile = '/screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                            if os.path.exists(str(get_homedir()) + '/source' + screenfile):
                                location['screen']=screenfile
                        redpost = Redis(unix_socket_path=get_socket_path('cache'), db=2)
                        if key in redpost.keys():
                            posts=json.loads(redpost.get(key)) # type: ignore
                            sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
                        else:
                            sorted_posts = []
                        modules = glob.glob(join(dirname(str(get_homedir())+'/ransomlook/parsers/'), "*.py"))
                        parserlist = [ basename(f)[:-3].split('.')[0] for f in modules if isfile(f) and not f.endswith('__init__.py')]

                        return render_template("group.html", group = group, posts=sorted_posts, parser=parserlist)

        return redirect(url_for("home"))

@app.route("/markets")
def markets(): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)

        groups = []
        for key in red.keys():
                entry= json.loads(red.get(key)) # type: ignore
                if not current_user.is_authenticated and 'private' in entry and entry['private'] is True:
                    continue
                entry['name']=key.decode()
                groups.append(entry)
        groups.sort(key=lambda x: x["name"].lower())
        for group in groups:
            for location in group['locations']:
                screenfile = '/screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                if os.path.exists(str(get_homedir()) + '/source' + screenfile):
                    location['screen']=screenfile
        modules = glob.glob(join(dirname(str(get_homedir())+'/ransomlook/parsers/'), "*.py"))
        parserlist = [ basename(f)[:-3].split('.')[0] for f in modules if isfile(f) and not f.endswith('__init__.py')]
        return render_template("groups.html", data=groups, parser=parserlist, type="markets")

@app.route("/market/<name>")
def market(name: str): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        for key in red.keys():
                if key.decode().lower() == name.lower():
                        group= json.loads(red.get(key)) # type: ignore
                        if not current_user.is_authenticated and 'private' in group and group['private'] is True:
                            return redirect(url_for("home"))

                        group['name']=key.decode()
                        redpost = Redis(unix_socket_path=get_socket_path('cache'), db=2)
                        if key in redpost.keys():
                            posts=json.loads(redpost.get(key)) # type: ignore
                            sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
                        else:
                            sorted_posts = []
                        return render_template("group.html", group = group, posts=sorted_posts)
        return redirect(url_for("home"))

@app.route("/leaks")
def leaks(): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=4)

        leaks = []
        for key in red.keys():
                entry= json.loads(red.get(key)) # type: ignore
                entry['id']=key
                leaks.append(entry)
        leaks.sort(key=lambda x: x["name"].lower())
        return render_template("leaks.html", data=leaks)

@app.route("/leak/<name>")
def leak(name: str): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=4) 
        for key in red.keys(): 
                if key.decode().lower() == name.lower():
                        group= json.loads(red.get(key)) # type: ignore
                        if 'meta' in group and group['meta'] is not None:
                            group['meta']=group['meta'].replace('\n', '<br/>')
                        return render_template("leak.html", group = group)

        return redirect(url_for("home"))

@app.route("/notes")
def notes(): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=11)
        data = []
        keys = []
        for key in red.keys():
            keys.append(key.decode())
        keys.sort()
        for i in range(0,len(keys),3):
            data.append(keys[i:i+3])
        return render_template("notes.html", data=data)

@app.route("/notes/<name>")
def notesdetails(name: str): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=11)
        data = []
        data = json.loads(red.get(name.lower())) # type: ignore
        return render_template("notesdetails.html", data=data)


@app.route("/RF")
def rf(): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=10)
        leaks = []
        for key in red.keys():
                entry= json.loads(red.get(key)) # type: ignore
                leaks.append(entry)
        leaks.sort(key=lambda x: x["name"].lower())
        return render_template("RF.html", data=leaks)

@app.route("/RF/<name>")
def rfdetails(name: str): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=10)
        for key in red.keys():
                if key.decode().lower() == name.lower():
                        group= json.loads(red.get(key)) # type: ignore
                        return render_template("RFdetails.html", group = group)

        return redirect(url_for("home"))


@app.route("/telegrams")
def telegrams(): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=5)

        telegram = []
        for key in red.keys():
                entry= json.loads(red.get(key)) # type: ignore
                screenfile = '/screenshots/telegram/' + entry['name'] + '.png'
                if os.path.exists(str(get_homedir()) + '/source' + screenfile):
                    entry['screen']=screenfile
                telegram.append(entry)
        telegram.sort(key=lambda x: x["name"].lower())
        return render_template("telegrams.html", data=telegram)

@app.route("/telegram/<name>")
def telegram(name: str): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=6)
        for key in red.keys():
                if key.decode() == name:
                        posts= json.loads(red.get(key)) # type: ignore
                        for post in posts:
                            if isinstance(posts[post], str):
                               posttmp = {}
                               posttmp['message']=posts[post]
                               posts[post]=posttmp
                        sorted_posts = OrderedDict(sorted(posts.items(),reverse=True))
                        return render_template("telegram.html", posts = sorted_posts, name=name)

        return redirect(url_for("home"))

@app.route("/twitters")
def twitters(): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=8)
        twitter = []
        for key in red.keys():
                entry= json.loads(red.get(key)) # type: ignore
                screenfile = '/screenshots/twitter/' + entry['name'] + '.png'
                if os.path.exists(str(get_homedir()) + '/source' + screenfile):
                    entry['screen']=screenfile
                twitter.append(entry)
        twitter.sort(key=lambda x: x["name"].lower())
        return render_template("twitters.html", data=twitter)

@app.route("/twitter/<name>")
def twitter(name: str): # type: ignore[no-untyped-def]
        redprofile = Redis(unix_socket_path=get_socket_path('cache'), db=8)
        red = Redis(unix_socket_path=get_socket_path('cache'), db=9)
        profile = redprofile.get(name)
        if profile is None:
            return redirect(url_for("home"))
        posts = red.get(name)
        sorted_posts : Dict[Any, Any]= {}
        if posts is not None:
            posts = json.loads(posts)
            sorted_posts = OrderedDict(sorted(posts.items(),reverse=True)) # type: ignore
        return render_template("twitter.html", posts = sorted_posts, name=json.loads(profile))

@app.route("/crypto")
def crypto(): # type: ignore[no-untyped-def]
        red = Redis(unix_socket_path=get_socket_path('cache'), db=7)
        groups = {}
        for key in red.keys():
                groups[key.decode()]=json.loads(red.get(key)) # type: ignore
        crypto = OrderedDict(sorted(groups.items()))
        return render_template("crypto.html", data=crypto)

@app.route('/search', methods=['GET', 'POST'])
def search(): # type: ignore[no-untyped-def]
    if request.method == 'POST':
        query = request.form.get('search')
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        groups = []
        for key in red.keys():
            group = json.loads(red.get(key)) # type: ignore
            if not current_user.is_authenticated and 'private' in group and group['private'] is True:
                continue

            if query.lower() in key.decode().lower() or group['meta'] is not None and query.lower() in group['meta'].lower(): # type: ignore
                group['name']=key.decode().lower()
                groups.append(group)
        groups.sort(key=lambda x: x["name"].lower())

        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        markets = []
        for key in red.keys():
            group = json.loads(red.get(key)) # type: ignore
            if not current_user.is_authenticated and 'private' in group and group['private'] is True:
                continue

            if query.lower() in key.decode().lower() or group['meta'] is not None and query.lower() in group['meta'].lower(): # type: ignore
                group['name'] = key.decode().lower()
                markets.append(group)
        markets.sort(key=lambda x: x["name"].lower())

        red = Redis(unix_socket_path=get_socket_path('cache'), db=4)
        leaks = []
        for key in red.keys():
            group = json.loads(red.get(key)) # type: ignore
            if query.lower() in group['name']: # type: ignore
                group['key'] = key.decode().lower()
                leaks.append(group)
        leaks.sort(key=lambda x: x["name"].lower())

        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        posts = []
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if query.lower() in entry['post_title'].lower() or 'description' in entry and entry['description'] is not None and query.lower() in entry['description'].lower(): # type: ignore
                        entry['group_name']=key.decode()
                        posts.append(entry)
        posts.sort(key=lambda x: x["group_name"].lower())

        red = Redis(unix_socket_path=get_socket_path('cache'), db=5)
        channels = []
        for key in red.keys():
            group = json.loads(red.get(key)) # type: ignore
            if query.lower() in key.decode().lower() or group['meta'] is not None and query.lower() in group['meta'].lower(): # type: ignore
                channels.append(group)
        channels.sort(key=lambda x: x["name"].lower())

        red = Redis(unix_socket_path=get_socket_path('cache'), db=6)
        messages = []
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if isinstance(entries[entry], str):
                        if query.lower() in entries[entry].lower() : # type: ignore
                            myentry={}
                            myentry["group_name"] = key.decode()
                            myentry["message"] = entries[entry]
                            myentry["date"] = entry
                            messages.append(myentry)
                    else:
                        if entries[entry]['message'] is not None and query.lower() in entries[entry]['message'].lower() : # type: ignore
                            myentry={}
                            myentry["group_name"] = key.decode()
                            myentry["message"] = entries[entry]['message']
                            myentry["date"] = entry
                            messages.append(myentry)
        messages.sort(key=lambda x: x["date"].lower(),reverse=True)

        red = Redis(unix_socket_path=get_socket_path('cache'), db=11)
        notes = []
        for key in red.keys():
                entries = json.loads(red.get(key)) # type: ignore
                for entry in entries:
                    if query.lower() in entry['name'].lower() or query.lower() in entry['content'].lower(): # type: ignore
                        entry['group_name']=key.decode()
                        notes.append(entry)
        notes.sort(key=lambda x: x["group_name"].lower())


        return render_template("search.html", query=query,groups=groups, markets=markets, posts=posts, leaks=leaks, channels=channels, messages=messages, notes=notes)
    return redirect(url_for("home"))

@app.route("/stats/<file>")
def screenshotsstats(file: str): # type: ignore[no-untyped-def]
    return send_from_directory( str(get_homedir())+ '/source/screenshots/stats', file, mimetype='image/gif')

@app.route("/screenshots/<file>")
def screenshots(file: str): # type: ignore[no-untyped-def]
    return send_from_directory( str(get_homedir())+ '/source/screenshots', file, mimetype='image/gif')

@app.route("/screenshots/<group>/<file>")
def screenshotspost(group: str, file: str): # type: ignore[no-untyped-def]
    fullpath = os.path.normpath(os.path.join(str(get_homedir())+ '/source/screenshots/', group))
    if not fullpath.startswith(str(get_homedir())):
        raise Exception("not allowed")
    if file.endswith('.txt'):
        return send_from_directory( fullpath, file, as_attachment=True)
    return send_from_directory( fullpath, file, mimetype='image/gif')

@app.route("/screenshots/telegram/<file>")
def screenshotstelegram(file: str): # type: ignore[no-untyped-def]
    return send_from_directory( str(get_homedir())+ '/source/screenshots/telegram', file, mimetype='image/gif')

@app.route("/screenshots/telegram/img/<file>")
def screenshotstelegramimg(file: str): # type: ignore[no-untyped-def]
    return send_from_directory( str(get_homedir())+ '/source/screenshots/telegram/img', file, mimetype='image/gif')

@app.route("/screenshots/twitter/<file>")
def screenshotstwitter(file: str): # type: ignore[no-untyped-def]
    return send_from_directory( str(get_homedir())+ '/source/screenshots/twitter/', file, mimetype='image/gif')

@app.route("/screenshots/twitter/img/<file>")
def screenshotstwitterimg(file: str): # type: ignore[no-untyped-def]
    return send_from_directory( str(get_homedir())+ '/source/screenshots/twitter/img', file, mimetype='image/gif')

# Admin Zone

@app.route('/admin/')
@app.route('/admin')
@flask_login.login_required
def admin(): # type: ignore[no-untyped-def]
    return render_template('admin.html')

@app.route('/admin/add', methods=['GET', 'POST'])
@flask_login.login_required
def addgroup(): # type: ignore[no-untyped-def]
    score = int(round(dt.now().timestamp()))
    form = AddForm()
    if form.validate_on_submit():
        if int(form.category.data) == 5:
           res = teladder(form.groupname.data, form.url.data)
        elif int(form.category.data) == 8:
           res = twiadder(form.groupname.data, form.url.data)
        else:
           res = adder(form.groupname.data.lower(), form.url.data, form.category.data, form.fs.data, form.private.data, form.chat.data, form.browser.data)
        if res > 1:
           flash(f'Fail to add: {form.url.data} to {form.groupname.data}.  Url already exists for this group', 'error')
           return render_template('add.html',form=form)
        else:
           flash(f'Success to add: {form.url.data} to {form.groupname.data}', 'success')
           redlogs = Redis(unix_socket_path=get_socket_path('cache'), db=1)
           redlogs.zadd("logs", {f"{flask_login.current_user.id} add : {form.groupname.data}, {form.url.data}": score})
           return redirect(url_for('admin'))
    return render_template('add.html',form=form)

@app.route('/admin/edit', methods=['GET', 'POST'])
@flask_login.login_required
def edit(): # type: ignore[no-untyped-def]
    formSelect = SelectForm()
    formMarkets = SelectForm()
    red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
    keys = red.keys()
    choices=[('','Please select your group')]
    keys.sort(key=lambda x: x.lower())
    for key in keys:
        choices.append((key.decode(), key.decode()))
    formSelect.group.choices=choices

    red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
    keys = red.keys()
    choices=[('','Please select your Market')]
    keys.sort(key=lambda x: x.lower())
    for key in keys:
        choices.append((key.decode(), key.decode()))
    formMarkets.group.choices=choices

    if formSelect.validate_on_submit():
        return redirect('/admin/edit/'+'0'+'/'+formSelect.group.data)
    if formMarkets.validate_on_submit():
        return redirect('/admin/edit/'+'3'+'/'+formMarkets.group.data)
    return render_template('edit.html', form=formSelect, formMarkets=formMarkets)

@app.route('/admin/edit/<database>/<name>', methods=['GET', 'POST'])
@flask_login.login_required # type: ignore
def editgroup(database: int, name: str): 
    score = dt.now().timestamp()
    deleteButton = DeleteForm()

    red = Redis(unix_socket_path=get_socket_path('cache'), db=database)
    datagroup = json.loads(red.get(name)) # type: ignore
    locations = namedtuple('locations',['slug', 'fqdn', 'timeout', 'delay', 'fs', 'chat', 'browser', 'private', 'version', 'available', 'title', 'updated', 'lastscrape', 'header'])
    locationlist = []
    for entry in datagroup['locations']:
        locationlist.append(locations(entry['slug'], entry['fqdn'], entry['timeout'] if 'timeout' in entry else '', entry['delay'] if 'delay' in entry else '', entry['fs'] if 'fs' in entry else False, entry['chat'] if 'chat' in entry else False, entry['browser'] if 'browser' in entry else '', entry['private'] if 'private' in entry else False, entry['version'], entry['available'], entry['title'], entry['updated'], entry['lastscrape'], entry['header'] if 'header' in entry else '' ))
    data = {'groupname': name,
            'description' : datagroup['meta'],
            'ransomware_galaxy_value': datagroup['ransomware_galaxy_value'] if 'ransomware_galaxy_value' in datagroup else '',
            'captcha' : datagroup['captcha'] if 'captcha' in datagroup else False,
            'profiles' : datagroup['profile'],
            'private' : datagroup['private'] if 'private' in datagroup else False,
            'links' : locationlist
           }

    form = EditForm(data=data)
    form.groupname.label=name

    redlogs = Redis(unix_socket_path=get_socket_path('cache'), db=1)
    if deleteButton.validate_on_submit():
        red.delete(name)
        redlogs.zadd('logs', {f'{flask_login.current_user.id} deleted : {name}': score})
        flash(f'Success to delete : {name}', 'success')
        return redirect(url_for('admin'))
    if form.validate_on_submit():
        data = json.loads(red.get(name)) # type: ignore
        data['meta']=form.description.data
        data['captcha']=form.captcha.data
        data['ransomware_galaxy_value'] = form.galaxy.data
        data['profile'] = ast.literal_eval(form.profiles.data)
        data['private'] = form.private.data
        data['captcha'] = form.captcha.data
        newlocations = []
        for entry in form.links:
            if entry.delete.data is True:
                continue
            location = {'slug' : entry.slug.data,
                        'fqdn' : entry.fqdn.data,
                        'timeout': entry.timeout.data,
                        'delay': entry.delay.data,
                        'fs': entry.fs.data,
                        'chat': entry.chat.data,
                        'browser': entry.browser.data,
                        'private': entry.private.data,
                        'version': entry.version.data,
                        'available': entry.available.data,
                        'title': entry.title.data,
                        'updated': entry.updated.data,
                        'lastscrape': entry.lastscrape.data,
                        'header': entry.header.data
                       }
            newlocations.append(location)
        data['locations'] = newlocations
        red.set(name, json.dumps(data))
        redlogs.zadd('logs', {f'{flask_login.current_user.id} modified : {name}, {data["meta"]}, {data["profile"]}, {data["locations"]}': score})
        if name != form.groupname.data:
            red.rename(name, form.groupname.data.lower()) # type: ignore[no-untyped-call]
            redlogs.zadd('logs', {f'{flask_login.current_user.id} renamed : {name} to {form.groupname.data}': score})
        flash(f'Success to edit : {form.groupname.data}', 'success')
        return redirect(url_for('admin'))

    return render_template('editentry.html', form=form , deleteform=deleteButton) 

@app.route('/admin/addpost', methods=['GET', 'POST'])
@flask_login.login_required
def addpost(): # type: ignore[no-untyped-def]
    formSelect = SelectForm()
    formMarkets = SelectForm()
    red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
    keys = red.keys()
    choices=[('','Please select your group')]
    keys.sort(key=lambda x: x.lower())
    for key in keys:
        choices.append((key.decode(), key.decode()))
    formSelect.group.choices=choices

    red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
    keys = red.keys()
    choices=[('','Please select your Market')]
    keys.sort(key=lambda x: x.lower())
    for key in keys:
        choices.append((key.decode(), key.decode()))
    formMarkets.group.choices=choices

    if formSelect.validate_on_submit():
        return redirect('/admin/addpost/'+'0'+'/'+formSelect.group.data)
    if formMarkets.validate_on_submit():
        return redirect('/admin/addpost/'+'3'+'/'+formMarkets.group.data)
    return render_template('addpost.html', form=formSelect, formMarkets=formMarkets)

@app.route('/admin/addpost/<database>/<name>', methods=['GET', 'POST'])
@flask_login.login_required # type: ignore
def addpostentry(database: int, name: str): 
    score = dt.now().timestamp()
    form = AddPostForm()
    redlogs = Redis(unix_socket_path=get_socket_path('cache'), db=1)

    if form.validate_on_submit():
        entry: Dict[str, str|None] = {}
        entry['slug']= None
        entry['title'] = form.title.data
        if form.description.data:
            entry['description']=form.description.data
        else:
            entry['description'] = ''
        if form.link.data:
            entry['link'] = form.link.data
        if form.magnet.data:
            entry['magnet'] = form.magnet.data
        if form.link.data and form.magnet.data:
            flash(f'Error to add post to : {name} - You should select Magnet or Link not both', 'error')
            return render_template('addpostentry.html', form=form)
        if form.date.data:
            entry['date'] = str(parser.parse(form.date.data))
        uploaded_file = request.files['file']
        filename = secure_filename(uploaded_file.filename)
        if filename != '':
            file_ext = os.path.splitext(filename)[1]
            if file_ext not in app.config['UPLOAD_EXTENSIONS'] or \
              file_ext != validate_image(uploaded_file.stream): # type: ignore
                flash(f'Error to add post to : {name} - Screen should be a PNG', 'error')
                return render_template('addpostentry.html', form=form)
            filenamepng = createfile(form.title.data) + file_ext
            path = os.path.normpath(str(get_homedir()) +  '/source/screenshots/' + name)
            if not os.path.exists(path):
                os.mkdir(path)
            namepng = os.path.normpath(path +'/' +filenamepng)
            uploaded_file.save(namepng)
            entry['screen'] = str(os.path.join('screenshots', name, filenamepng))
        if appender(entry, name):
            flash(f'Error to add post to : {name} - The entry already exists', 'error')
            return render_template('addpostentry.html', form=form)
        else:
            statsgroup(name.encode())
            run_data_viz(7)
            run_data_viz(14)
            run_data_viz(30)
            run_data_viz(90)
            redlogs.zadd('logs', {f'{flask_login.current_user.id} added {form.title.data} to : {name}': score})
            flash(f'Success to add post to : {name}', 'success')
        return redirect(url_for('admin'))

    form.groupname.label=name
    return render_template('addpostentry.html', form=form)

@app.route('/admin/editpost', methods=['GET', 'POST'])
@flask_login.login_required
def editpost(): # type: ignore[no-untyped-def]
    formSelect = SelectForm()
    formMarkets = SelectForm()
    red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
    keys = red.keys()
    choices=[('','Please select your group')]
    keys.sort(key=lambda x: x.lower())
    for key in keys:
        choices.append((key.decode(), key.decode()))
    formSelect.group.choices=choices

    red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
    keys = red.keys()
    choices=[('','Please select your Market')]
    keys.sort(key=lambda x: x.lower())
    for key in keys:
        choices.append((key.decode(), key.decode()))
    formMarkets.group.choices=choices

    if formSelect.validate_on_submit():
        return redirect('/admin/editpost/'+formSelect.group.data)
    if formMarkets.validate_on_submit():
        return redirect('/admin/editpost/'+formMarkets.group.data)
    return render_template('edit.html', form=formSelect, formMarkets=formMarkets)

@app.route('/admin/editpost/<name>', methods=['GET', 'POST'])
@flask_login.login_required # type: ignore
def editpostentry(name: str):
    red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
    try:
        posts = json.loads(red.get(name)) # type: ignore
    except:
        return redirect('/admin/editpost')
    postdata = namedtuple('posts', ['post_title', 'discovered', 'description', 'link', 'magnet', 'screen']) # type: ignore
    postlist=[]
    for entry in posts:
       postlist.append(postdata(entry['post_title'], entry['discovered'], entry['description'], entry['link'], entry['magnet'], entry['screen'] if 'screen' in entry else ''))
    data = {'postslist': postlist}
    form = EditPostsForm(data=data, files=request.files)
    if form.validate_on_submit():
        posts=[]
        for field in form.postslist:
            if field.delete.data is True:
                continue
            post = { 
        'post_title': field.post_title.data.strip(),
        'discovered': field.discovered.data.strip(),
        'description': field.description.data.strip() if field.description else '',
        'link': field.link.data.strip() if field.link.data else '',
        'magnet': field.magnet.data.strip() if field.magnet.data else ''
            }
            if field.file.data != None:
                filename = field.file.data.filename
                file_ext = os.path.splitext(filename)[1]
                if file_ext not in app.config['UPLOAD_EXTENSIONS'] or \
                  file_ext != validate_image(field.file.data): # type: ignore
                    flash(f'Error to add post to : {name} - Screen should be a PNG', 'error')
                    return render_template('editpost.html', form=form)
                filenamepng = createfile(post['post_title']) + file_ext
                path = os.path.normpath(str(get_homedir()) +  '/source/screenshots/' + name)
                if not os.path.exists(path):
                    os.mkdir(path)
                namepng = os.path.normpath(path +'/' +filenamepng)
                field.file.data.save(namepng)
                post['screen'] = str(os.path.join('screenshots', name, filenamepng))
            else:
                if field.screen.data :
                    post['screen'] =  field.screen.data.strip() if field.screen.data else ''
            posts.append(post)
        red.set(name, json.dumps(posts))
        flash(f'Success to add post to : {name}', 'success')
        return redirect(url_for('admin'))

    return render_template('editpost.html', form=form)

@app.route('/export/<database>')
def exportdb(database: int): # type: ignore[no-untyped-def]
    if str(database) not in ['0','2','3','4','5','6','7']:
        flash(f'You are not allowed to dump this DataBase', 'error')
        return redirect(url_for('home'))
    red = Redis(unix_socket_path=get_socket_path('cache'), db=database)
    dump={}
    for key in red.keys():
        if str(database) != '0' and str(database) != '3':
            dump[key.decode()]=json.loads(red.get(key)) # type: ignore
        else:
            temp = json.loads(red.get(key)) # type: ignore
            if not current_user.is_authenticated and 'private' in temp and temp['private'] is True:
                continue

            if 'locations' in temp:
                for location in temp['locations']:
                    if 'private' in location and location['private'] is True:
                        temp['locations'].remove(location)
            dump[key.decode()]=temp
    return dump

@app.route('/admin/logs')
@flask_login.login_required
def logs(): # type: ignore[no-untyped-def]
    red = Redis(unix_socket_path=get_socket_path('cache'), db=1)
    logs = red.zrange('logs', 0, -1, desc=True, withscores=True)
    log = []
    for i,s in enumerate(logs):
       log.append((s[0].decode(), dt.fromtimestamp(s[1]).strftime('%Y-%m-%d')))
    return render_template('logs.html', logs=log)

@app.route('/admin/alerting', methods=['GET', 'POST'])
@flask_login.login_required
def alerting(): # type: ignore[no-untyped-def]
    form = AlertForm()
    red = Redis(unix_socket_path=get_socket_path('cache'), db=1)
    keywordsred = red.get('keywords')
    keywords= None
    if keywordsred is not None:
        keywords = keywordsred.decode()
    if form.validate_on_submit():
        keywordstmp = str(form.keywords.data).splitlines()
        keywordslist = list(dict.fromkeys(keywordstmp))
        keywords = '\n'.join(keywordslist)
        red.set('keywords',str(keywords))
        flash(f'Success to update keywords', 'success')
    form.keywords.data=keywords
    return render_template('alerts.html', form=form)

if __name__ == "__main__":
	app.run()


authorizations = {
    'apikey': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization'
    }
}

api = Api(app, title='RansomLook API',
          description='API to query a RansomLook instance.',
          doc='/doc/',
          authorizations=authorizations,
          version=pkg_version)

api.add_namespace(generic_api)
api.add_namespace(leaks_api)
api.add_namespace(rf_api)
api.add_namespace(telegram_api)
