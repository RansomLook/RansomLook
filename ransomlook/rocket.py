from rocketchat_API.rocketchat import RocketChat # type: ignore

def rocketnotify(config, group, post):
    rocket = RocketChat(user_id=config['user_id'], auth_token=config['auth_token'], server_url=config['server'], ssl_verify=config['ssl_verify'])
    rocket.chat_post_message('New post from '+group+' : '+post, room_id=config['channel_name'])
