import tweepy
from .sharedutils import errlog

def twitternotify(config, group, title) -> None :
    '''
    Posting message to Twitter
    '''
    try:
        client = tweepy.Client(
             consumer_key=config['consumer_key'], consumer_secret=config['consumer_secret'],
             access_token=config['access_token'], access_token_secret=config['access_token_secret']
        )
        client.create_tweet(text="New post from " + group.title() + " : " + title.title())
    except:
        errlog('Can not tweet :(')

def twitternotifyleak(config, name) -> None :
    '''
    Posting message to Twitter
    '''
    try:
        client = tweepy.Client(
             consumer_key=config['consumer_key'], consumer_secret=config['consumer_secret'],
             access_token=config['access_token'], access_token_secret=config['access_token_secret']
        )
        client.create_tweet(text="New data breach detected " + name.title())
    except:
        errlog('Can not tweet :(')

