from flask import Flask, render_template, redirect, url_for
import flask_moment 
from flask_bootstrap import Bootstrap5  # type: ignore

from datetime import datetime as dt
import glob
from os.path import dirname, basename, isfile, join
import os

from ransomlook.sharedutils import openjson, createfile
from ransomlook.sharedutils import groupcount, hostcount, onlinecount, postslast24h, mounthlypostcount, currentmonthstr, postssince, poststhisyear,postcount,parsercount
from ransomlook.default.config import get_homedir

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
        posts = openjson('data/posts.json')
        sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
        recentposts = []
        for post in sorted_posts:
                recentposts.append(post)
                if len(recentposts) == 100:
                        break
        return render_template("recent.html", data=recentposts)

@app.route("/status")
def status():
        groups = openjson('data/groups.json')
        groups.sort(key=lambda x: x["name"].lower())
        for group in groups:
            for location in group['locations']:
                screenfile = '/screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                if os.path.exists(str(get_homedir()) + screenfile):
                    location['screen']=screenfile
        markets = openjson('data/markets.json')
        markets.sort(key=lambda x: x["name"].lower())
        for group in markets:
            for location in group['locations']:
                screenfile = '/screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                if os.path.exists(str(get_homedir()) + screenfile):
                    location['screen']=screenfile

        return render_template("status.html", data=groups, markets=markets)

@app.route("/groups")
def groups():
        groups = openjson('data/groups.json')
        groups.sort(key=lambda x: x["name"].lower())
        for group in groups:
            for location in group['locations']:
                screenfile = 'screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                if os.path.exists(screenfile):
                    location['screen']=screenfile
        posts = openjson('data/posts.json')
        sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
        modules = glob.glob(join(dirname(str(get_homedir())+'/ransomlook/parsers/'), "*.py"))
        parserlist = [ basename(f)[:-3].split('.')[0] for f in modules if isfile(f) and not f.endswith('__init__.py')]
        return render_template("groups.html", data=groups, posts=sorted_posts, parser=parserlist)

@app.route("/group/<name>")
def group(name):
        groups = openjson('data/groups.json')
        for group in groups:
                if group['name'].lower() == name.lower():
                        posts = openjson('data/posts.json')
                        groupposts = []
                        for post in posts:
                                if post['group_name'].lower() == name.lower():
                                         groupposts.append(post)
                        groupposts = sorted(groupposts, key=lambda x: x['discovered'], reverse=True)
                        print(len(groupposts))
                        return render_template("group.html", group = group, posts=groupposts)
        return redirect(url_for("home"))

@app.route("/markets")
def markets():
        groups = openjson('data/markets.json')
        groups.sort(key=lambda x: x["name"].lower())
        for group in groups:
            for location in group['locations']:
                screenfile = 'screenshots/' + group['name'] + '-' + createfile(location['slug']) + '.png'
                if os.path.exists(screenfile):
                    location['screen']=screenfile
        posts = openjson('data/posts.json')
        sorted_posts = sorted(posts, key=lambda x: x['discovered'], reverse=True)
        return render_template("groups.html", data=groups, posts=sorted_posts)

@app.route("/market/<name>")
def market(name):
        groups = openjson('data/markets.json')
        for group in groups:
                if group['name'].lower() == name.lower():
                        posts = openjson('data/posts.json')
                        groupposts = []
                        for post in posts:
                                if post['group_name'].lower() == name.lower():
                                         groupposts.append(post)
                        groupposts = sorted(groupposts, key=lambda x: x['discovered'], reverse=True)
                        return render_template("group.html", group = group, posts=groupposts)
        return redirect(url_for("home"))

if __name__ == "__main__":
	app.run(debug=True)
