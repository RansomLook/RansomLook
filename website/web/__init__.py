from flask import Flask, render_template, redirect, url_for
import flask_moment
from flask import request
from flask_bootstrap import Bootstrap5  # type: ignore

from datetime import datetime as dt
import glob
from os.path import dirname, basename, isfile, join
import os
import json
from redis import Redis

from ransomlook.sharedutils import createfile
from ransomlook.sharedutils import groupcount, hostcount, onlinecount, postslast24h, mounthlypostcount, currentmonthstr, postssince, poststhisyear,postcount,parsercount
from ransomlook.default.config import get_homedir
from ransomlook.default import get_socket_path
from .helpers import get_secret_key, sri_load

app = Flask(__name__)

app.config['SECRET_KEY'] = get_secret_key()

Bootstrap5(app)
app.config['BOOTSTRAP_SERVE_LOCAL'] = True
app.config['SESSION_COOKIE_NAME'] = 'ransomlook'
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'

flask_moment.Moment(app=app)

def get_sri(directory: str, filename: str) -> str:
    sha512 = sri_load()[directory][filename]
    return f'sha512-{sha512}'

app.jinja_env.globals.update(get_sri=get_sri)

def suffix(d: int) -> str :
    return 'th' if 11<=d<=13 else {1:'st',2:'nd',3:'rd'}.get(d%10, 'th')

def custom_strftime(fmt, t):
    return t.strftime(fmt).replace('{S}', str(t.day) + suffix(t.day))

@app.route("/")
def home():
        date = custom_strftime('%B {S}, %Y', dt.now()).lower()
        data = {}
        data['nbgroups'] = groupcount()
        data['nblocations'] = hostcount()
        data['online'] = onlinecount()
        data['24h'] = postslast24h()
        data['monthlypost'] = mounthlypostcount()
        data['month'] = currentmonthstr()
        data['90d'] = postssince(90)
        data['yearlypost'] = poststhisyear()
        data['year'] = dt.now().year
        data['nbposts'] = postcount()
        data['nbparsers'] = parsercount()
        return render_template("index.html", date=date, data=data)

@app.route("/recent")
def recent():
        posts = []
        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        for key in red.keys():
                entries = json.loads(red.get(key))
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

@app.route("/status")
def status():
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        groups = []
        for key in red.keys():
                entry= json.loads(red.get(key))
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
                entry= json.loads(red.get(key))
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

def alive():
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        groups = []
        for key in red.keys():
                entry= json.loads(red.get(key))
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
                entry= json.loads(red.get(key))
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
def groups():
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        redpost = Redis(unix_socket_path=get_socket_path('cache'), db=2)

        groups = []
        for key in red.keys():
                entry= json.loads(red.get(key))
                entry['name']=key.decode()
                if key in redpost.keys():
                    posts=json.loads(redpost.get(key))
                    sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
                    entry['posts']= sorted_posts
                else:
                    entry['posts']={}
                groups.append(entry)
        groups.sort(key=lambda x: x["name"].lower())
        for group in groups:
            for location in group['locations']:
                screenfile = '/screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                if os.path.exists(str(get_homedir()) + '/source' + screenfile):
                    location['screen']=screenfile
        modules = glob.glob(join(dirname(str(get_homedir())+'/ransomlook/parsers/'), "*.py"))
        parserlist = [ basename(f)[:-3].split('.')[0] for f in modules if isfile(f) and not f.endswith('__init__.py')]
        return render_template("groups.html", data=groups, parser=parserlist)

@app.route("/group/<name>")
def group(name):
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        groups = []
        for key in red.keys():
                if key.decode().lower() == name.lower():
                        group= json.loads(red.get(key))
                        group['name']=key.decode()
                        redpost = Redis(unix_socket_path=get_socket_path('cache'), db=2)
                        if key in redpost.keys():
                            posts=json.loads(redpost.get(key))
                            sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
                        else:
                            sorted_posts = {}
                        return render_template("group.html", group = group, posts=sorted_posts)

        return redirect(url_for("home"))

@app.route("/markets")
def markets():
        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        redpost = Redis(unix_socket_path=get_socket_path('cache'), db=2)

        groups = []
        for key in red.keys():
                entry= json.loads(red.get(key))
                entry['name']=key.decode()
                if key in redpost.keys():
                    posts=json.loads(redpost.get(key))
                    sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
                    entry['posts']= sorted_posts
                else:
                    entry['posts']={}
                groups.append(entry)
        groups.sort(key=lambda x: x["name"].lower())
        for group in groups:
            for location in group['locations']:
                screenfile = '/screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                if os.path.exists(str(get_homedir()) + '/source' + screenfile):
                    location['screen']=screenfile
        modules = glob.glob(join(dirname(str(get_homedir())+'/ransomlook/parsers/'), "*.py"))
        parserlist = [ basename(f)[:-3].split('.')[0] for f in modules if isfile(f) and not f.endswith('__init__.py')]
        return render_template("groups.html", data=groups, parser=parserlist)

@app.route("/market/<name>")
def market(name):
        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        groups = []
        for key in red.keys():
                if key.decode().lower() == name.lower():
                        group= json.loads(red.get(key))
                        group['name']=key.decode()
                        red2 = Redis(unix_socket_path=get_socket_path('cache'), db=2)
                        posts=json.loads(red2.get(key))
                        groupposts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
                        return render_template("group.html", group = group, posts=groupposts)
        return redirect(url_for("home"))

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        query = request.form.get('search')
        red = Redis(unix_socket_path=get_socket_path('cache'), db=0)
        groups = []
        for key in red.keys():
            group = json.loads(red.get(key))
            if query.lower() in key.decode().lower() or group['meta'] is not None and query.lower() in group['meta'].lower():
                group['name']=key.decode().lower()
                groups.append(group)
        groups.sort(key=lambda x: x["name"].lower())

        red = Redis(unix_socket_path=get_socket_path('cache'), db=3)
        markets = []
        for key in red.keys():
            group = json.loads(red.get(key))
            if query.lower() in key.decode().lower() or group['meta'] is not None and query.lower() in group['meta'].lower():
                group['name'] = key.decode().lower()
                markets.append(group)
        groups.sort(key=lambda x: x["name"].lower())

        red = Redis(unix_socket_path=get_socket_path('cache'), db=2)
        posts = []
        for key in red.keys():
                entries = json.loads(red.get(key))
                for entry in entries:
                    if query.lower() in entry['post_title'] or 'description' in entry and entry['description'] is not None and query.lower() in entry['description'].lower():
                        entry['group_name']=key.decode()
                        posts.append(entry)
        posts.sort(key=lambda x: x["group_name"].lower())

        return render_template("search.html", query=query,groups=groups, markets=markets, posts=posts)
    return redirect(url_for("home"))

if __name__ == "__main__":
	app.run(debug=True)
