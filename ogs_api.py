
import requests
import websocket
import json
import time
import logging
import uuid
import threading

from logging.handlers import RotatingFileHandler

'''
gamedata:
{'handicap': 0,
 'disable_analysis': False,
 'private': False,
 'height': 19,
 'time_control': {'system': 'fischer',
  'pause_on_weekends': True,
  'time_control': 'fischer',
  'initial_time': 259200,
  'max_time': 604800,
  'time_increment': 86400},
 'ranked': True,
 'meta_groups': [],
 'komi': 6.5,
 'game_id': 16796717,
 'width': 19,
 'rules': 'japanese',
 'black_player_id': 619703,
 'pause_on_weekends': True,
 'white_player_id': 612079,
 'players': {'white': {'username': 'loversmirror',
   'professional': False,
   'egf': 0,
   'rank': 0,
   'id': 612079},
  'black': {'username': 'Pasbot',
   'professional': False,
   'egf': 0,
   'rank': 0,
   'id': 619703}},
 'game_name': 'Pasbot vs. loversmirror',
 'phase': 'play',
 'history': [],
 'initial_player': 'black',
 'moves': [[15, 3, 1476942]],
 'allow_self_capture': False,
 'automatic_stone_removal': False,
 'free_handicap_placement': False,
 'aga_handicap_scoring': False,
 'allow_ko': False,
 'allow_superko': True,
 'superko_algorithm': 'ssk',
 'score_territory': True,
 'score_territory_in_seki': False,
 'score_stones': False,
 'score_handicap': False,
 'score_prisoners': True,
 'score_passes': True,
 'white_must_pass_last': False,
 'opponent_plays_first_after_resume': True,
 'strict_seki_mode': False,
 'initial_state': {'black': '', 'white': ''},
 'start_time': 1551438997,
 'original_disable_analysis': False,
 'clock': {'game_id': 16796717,
  'current_player': 612079,
  'black_player_id': 619703,
  'white_player_id': 612079,
  'title': 'Pasbot vs. loversmirror',
  'last_move': 1551440473942,
  'expiration': 1551699673942,
  'black_time': {'thinking_time': 259200, 'skip_bonus': False},
  'white_time': {'thinking_time': 259200, 'skip_bonus': False}}}
'''

def make_logger(name):
    logger      = logging.getLogger(name)
    handler     = RotatingFileHandler(
        'log/%s.log' % name, maxBytes=1*1024*1024, backupCount=2, encoding='utf-8'
    )
    formatter   = logging.Formatter(
        '%(asctime)s - %(levelname)-8s - %(message)s'
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.debug('')
    logger.debug('-----')
    logger.debug('START')
    logger.debug('-----')
    return logger

class OnlineGoAPI:
    # https://forums.online-go.com/t/ogs-api-notes/17136
    def __init__(self, username, password):
        self.session    = requests.session()
        self.username   = username
        self.password   = password

        self.logger     = make_logger('OnlineGoAPI')
        self.ws_log     = make_logger('OnlineGoAPI_ws')
        self.http_log   = make_logger('OnlineGoAPI_http')

        self.gamedata   = {}
        self.automatch  = None

    def logon(self):
        def http_logon():
            # Logon
            res = self._http_send(
                'POST',
                'https://online-go.com/api/v0/login', 
                {'username': self.username, 'password': self.password}
            )
            # Load startup page
            res = self._http_send(
                'GET',
                'https://online-go.com/api/v1/ui/config', 
            )
            return res.json()
        def ws_logon():
            # Connect Websocket
            self.ws = websocket.WebSocketApp(
                'wss://online-go.com/socket.io/?transport=websocket',
                on_open=self._ws_on_open, on_close=self._ws_on_close, on_error=self._ws_on_error,
                on_message=self._ws_on_message, 
            )
            def send_pings():
                while True:
                    time.sleep(20)
                    self._ws_send('net/ping', int(time.time()*1000))
            ws_thread = threading.Thread(target=self.ws.run_forever, kwargs={'ping_interval': 20})
            ws_thread.start()
            ping_thread = threading.Thread(target=send_pings)
            ping_thread.start()
            time.sleep(1)
            self._ws_send(
                'notification/connect',
                {'player_id': str(self.config['user']['id']), 'username': self.username, 'auth': self.config['notification_auth']}
            )
            self._ws_send(
                'chat/connect',
                {'player_id': str(self.config['user']['id']), 'username': self.username, 'auth': self.config['chat_auth']}
            )
            self._ws_send(
                'authenticate',
                {'player_id': str(self.config['user']['id']), 'username': self.username, 'auth': self.config['chat_auth']}
            )
        def connect_to_games():
            res = self._http_send(
                'GET',
                'https://online-go.com/api/v1/players/%s/full' % self.config['user']['id']
            )
            for game in res.json()['active_games']:
                self._game_connect(game['id'])
        self.config = http_logon()
        ws_logon()
        connect_to_games()

    def _find_automatch(self):
        self.logger.info('_find_automatch')
        self._ws_send(
            'automatch/find_match',
            {
                "uuid": str(uuid.uuid4()),
                "size_speed_options": [{
                    "size": "9x9",
                    "speed": "live" 
                }], 
                "lower_rank_diff": 9, 
                "upper_rank_diff": 9, 
                "rules": {
                    "condition": "preferred",
                    "value": "chinese" 
                },
                "time_control": {
                    "condition": "required",
                    "value": { "system": "byoyomi" }
                }, 
                "handicap": {
                    "condition": "required",
                    "value": "disabled"
                }
            }
        )
    def _cancel_automatch(self, match_id):
        self.logger.info('_cancel_automatch %s' % match_id)
        self._ws_send(
            'automatch/cancel',
            self.automatch
        )

    def _game_chat(self, game_id, message):
        self.logger.info('_game_chat %s %s' % (game_id, message))
        self._ws_send(
            'game/chat',
            {  
                'auth': self.config['chat_auth'],
                'game_id': game_id,
                'player_id': str(self.config['user']['id']),
                'body': message,
                'type': "discussion",
                'move_number': len(self.gamedata[game_id]['moves']),
                'username': self.username,
                'is_player': True,
                'ranking': self.gamedata[game_id]['players']['black']['rank'] if int(self.gamedata[game_id]['black_player_id']) == int(self.config['user']['id']) else self.gamedata[game_id]['players']['white']['rank'],
                'ui_class': "",
            }
        )

    def _game_connect(self, game_id):
        self.logger.info('_game_connect %s' % game_id)
        self._ws_send('game/connect', {'player_id': str(self.config['user']['id']), 'game_id': str(game_id), 'chat': True})
    def _game_disconnect(self, game_id):
        self.logger.info('_game_disconnect %s' % game_id)
        self._ws_send('game/disconnect', {'game_id': str(game_id)})
    def _game_wait(self, game_id):
        self.logger.info('_game_wait %s' % game_id)
        self._ws_send('game/wait', {'game_id': str(game_id)})
    def _game_move(self, game_id, move):
        self.logger.info('_game_move %s %s' % (game_id, move))
        move = [int(p) for p in move]
        self._ws_send(
            'game/move', 
            {
                'auth': self.config['chat_auth'],
                'game_id': str(game_id),
                'player_id': str(self.config['user']['id']),
                'move': move,
            }
        )
    def _game_resign(self, game_id):
        self.logger.info('_game_resign %s' % game_id)
        self._ws_send(
            'game/resign', 
            {
                'auth': self.config['chat_auth'],
                'game_id': str(game_id),
                'player_id': str(self.config['user']['id']),
            }
        )
    def _removed_stones_accept(self, game_id, stones):
        self.logger.info('_removed_stones_accept %s' % game_id)
        self._ws_send(
            ' game/removed_stones/accept',
            {
                'auth': self.config['chat_auth'],
                'game_id': str(game_id),
                'player_id': str(self.config['user']['id']),
                'stones': stones,
                'strict_seki_mode': self.gamedata[game_id]['strict_seki_mode'],
            }
        )

    def _process_message(self, message):
        endpoint, data = message[0], message[1]

        if endpoint == 'active_game':
            game_id = str(data['id'])
            if game_id not in self.gamedata:
                self.logger.info('new active_game %s' % game_id)
                self._game_connect(game_id)

        elif endpoint.split('/')[0] == 'automatch':
            automatch_endpoint = endpoint.split('/')[-1]
            automatch_id = data['uuid']
            if automatch_endpoint == 'entry':
                self.logger.info('automatch/entry %s' % automatch_id)
                self.automatch = data
            elif automatch_endpoint == 'cancel':
                self.logger.info('automatch/cancel %s' % automatch_id)
                self.automatch = None
            elif automatch_endpoint == 'start':
                self.logger.info('automatch/start %s' % automatch_id)
                self.automatch = None

        elif endpoint.split('/')[0] == 'game':
            game_id = endpoint.split('/')[1]
            game_endpoint = endpoint.split('/')[2]
            if game_id not in self.gamedata:
                self.logger.info('new game_id %s' % game_id)
                self._game_connect(game_id)
            if game_endpoint == 'gamedata':
                self.gamedata[game_id] = data
            elif game_endpoint == 'clock':
                self.gamedata[game_id]['clock'] = data
            elif game_endpoint == 'phase':
                self.gamedata[game_id]['phase'] = data
                if data == 'play':
                    del self.gamedata[game_id]
                    self._game_disconnect(game_id)
                    self._game_connect(game_id)
            elif game_endpoint == 'move':
                self.gamedata[game_id]['moves'].append(data['move'])
            elif game_endpoint == 'removed_stones':
                pass
            elif game_endpoint == 'removed_stones_accepted':
                if int(data['player_id']) != int(self.config['user']['id']):
                    time.sleep(1)
                    self._removed_stones_accept(game_id, data['stones'])
            elif game_endpoint == 'reset':
                self.logger.warning('game/reset %s' % game_id)
                del self.gamedata[game_id]
                self._game_connect(game_id)

    def _ws_on_open(self):
        self.ws_log.info(' O  on_open')
    def _ws_on_close(self):
        self.ws_log.info(' C  on_close')
    def _ws_on_error(self, err):
        self.ws_log.info('!!! %s' % err)
    def _ws_on_message(self, message):
        self.ws_log.info(' <  %s' % message.encode('utf-8'))
        msg = json.loads(message[2:])
        self._process_message(msg)
    def _ws_send(self, endpoint, message):
        msg = '42'+json.dumps([endpoint, message], separators=(',',':'))
        self.ws_log.info(' >  %s' % msg)
        self.ws.send(msg)

    def _http_send(self, method, url, data=None):
        self.http_log.info(' > %s' % url)
        res = None
        if method == 'POST':
            res = self.session.post(url, data=data)
        elif method == 'GET':
            res = self.session.get(url, data=data)
        try:
            self.http_log.info(' < %s' % res.json())
        except json.decoder.JSONDecodeError:
            self.http_log.info(' < %s' % res.text)
        res.raise_for_status()
        return res

