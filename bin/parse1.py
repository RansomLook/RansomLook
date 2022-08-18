#!/usr/bin/env python3
#from ransomlook import ransomlook
import importlib
from os.path import dirname, basename, isfile, join
import glob
import json

from datetime import datetime
from datetime import timedelta

from ransomlook.sharedutils import openjson
from ransomlook.sharedutils import dbglog, stdlog

def posttemplate(victim, group_name, timestamp):
    '''
    assuming we have a new post - form the template we will use for the new entry in posts.json
    '''
    schema = {
        'post_title': victim,
        'group_name': group_name,
        'discovered': timestamp
    }
    stdlog('new post: ' + victim)
    dbglog(schema)
    return schema

def existingpost(post_title, group_name):
    '''
    check if a post already exists in posts.json
    '''
    posts = openjson('data/posts.json')
    for post in posts:
        dbglog('checking post: ' + post['post_title'])
        if post['post_title'] == post_title and post['group_name'] == group_name:
            stdlog('post already exists: ' + post_title)
            print('post already exists: ' + post_title)
            return True
    stdlog('post does not exist: ' + post_title)
    return False

def appender(post_title, group_name):
    '''
    append a new post to posts.json
    '''
    if len(post_title) == 0:
        errlog('post_title is empty')
        return
    # limit length of post_title to 90 chars
    if len(post_title) > 90:
        post_title = post_title[:90]
    if existingpost(post_title, group_name) is False:
        posts = openjson('data/posts.json')
        newpost = posttemplate(post_title, group_name, str(datetime.today()))
        stdlog('adding new post: ' + 'group:' + group_name + 'title:' + post_title)
        posts.append(newpost)
        with open('data/posts.json', 'w') as outfile:
            '''
            use ensure_ascii to mandate utf-8 in the case the post contains cyrillic 🇷🇺
            https://pynative.com/python-json-encode-unicode-and-non-ascii-characters-as-is/
            '''
            dbglog('writing changes to posts.json')
            json.dump(posts, outfile, indent=4, ensure_ascii=False)

def main():
    modules = glob.glob(join(dirname('ransomlook/parserstest/'), "*.py"))
    __all__ = [ basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]
    for parser in __all__:
        module = importlib.import_module(f'ransomlook.parserstest.{parser}')
        print('\nParser : '+parser)

        try:
            for entry in module.main():
                print(entry)
                appender(entry, parser)
        except:
            print("Error with : " + parser)
            pass


if __name__ == '__main__':
    main()

