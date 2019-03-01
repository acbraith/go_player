
#%%
import requests
import websocket
import threading
import json
import time
import logging
import traceback

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
    logger          = logging.getLogger(name)
    fh              = logging.FileHandler('%s.log' % name)
    ch              = logging.StreamHandler()
    formatter       = logging.Formatter('%(asctime)s - %(levelname)-8s - %(message)s')
    fh.setLevel(logging.DEBUG)
    ch.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)
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

        self.gamedata   = {}

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
                'https://online-go.com/api/v1/players/%s/games' % self.config['user']['id']
            )
            for game in res.json()['results']:
                self.logger.debug(str(game))
                self._game_connect(game['id'])
        self.config = http_logon()
        ws_logon()
        connect_to_games()

    def _make_challenge(self):
        self._http_send(
            'POST',
            'http://online-go.com/api/v1/challenges/',
            {
                "game": {
                    "name": "game",
                    "rules": "japanese",
                    "ranked": False,
                    "handicap": 0,
                    "time_control_parameters": {
                        "time_control": "byoyomi",
                        "main_time": 600,
                        "period_time": 60,
                    },
                    "pause_on_weekends": False,
                    "width": 9,
                    "height": 9,
                    "disable_analysis": False
                },
                "challenger_color": "automatic",
                "min_ranking": 0,
                "max_ranking": 0
            }
        )

    def _game_connect(self, game_id):
        self._ws_send('game/connect', {'player_id': str(self.config['user']['id']), 'game_id': str(game_id), 'chat': True})
    def _game_disconnect(self, game_id):
        self._ws_send('game/disconnect', {'game_id': str(game_id)})
    def _game_wait(self, game_id):
        self._ws_send('game/wait', {'game_id': str(game_id)})
    def _game_move(self, game_id, move):
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
        self._ws_send(
            'game/resign', 
            {
                'auth': self.config['chat_auth'],
                'game_id': str(game_id),
                'player_id': str(self.config['user']['id']),
            }
        )
    def _removed_stones_accept(self, game_id):
        self._ws_send(
            ' game/removed_stones/accept',
            {
                'auth': self.config['chat_auth'],
                'game_id': str(game_id),
                'player_id': str(self.config['user']['id']),
                'stones': self.gamedata[game_id]['removed'],
                'strict_seki_mode': self.gamedata[game_id]['strict_seki_mode'],
            }
        )

    def _ws_on_open(self):
        self.logger.info(' WS  O  on_open')
    def _ws_on_close(self):
        self.logger.info(' WS  C  on_close')
    def _ws_on_error(self, err):
        self.logger.info(' WS !!! %s' % err)
    def _ws_on_message(self, message):
        self.logger.info(' WS  <  %s' % message.encode('utf-8'))
        msg = json.loads(message[2:])
        endpoint, data = msg[0], msg[1]
        if endpoint == 'active_game':
            game_id = str(data['id'])
            if game_id not in self.gamedata:
                self._game_connect(game_id)
        elif endpoint == 'pong':
            pass
        elif endpoint.split('/')[0] == 'game':
            game_id = endpoint.split('/')[1]
            game_endpoint = endpoint.split('/')[2]
            if game_endpoint == 'gamedata':
                self.gamedata[game_id] = data
            elif game_endpoint == 'clock':
                self.gamedata[game_id]['clock'] = data
            elif game_endpoint == 'phase':
                self.gamedata[game_id]['phase'] = data
            elif game_endpoint == 'move':
                self.gamedata[game_id]['moves'].append(data['move'])
            elif game_endpoint == 'removed_stones':
                # TODO
                pass
            elif game_endpoint == 'reset':
                del self.gamedata[game_id]
                self._game_connect(game_id)
    def _ws_send(self, endpoint, message):
        msg = '42'+json.dumps([endpoint, message]).replace(' ','')
        self.logger.info(" WS  >  %s" % msg)
        self.ws.send(msg)

    def _http_send(self, method, url, data=None):
        self.logger.info("HTTP > %s" % url)
        res = None
        if method == 'POST':
            res = self.session.post(url, data=data)
        elif method == 'GET':
            res = self.session.get(url, data=data)
        try:
            self.logger.info("HTTP < %s" % res.json())
        except json.decoder.JSONDecodeError:
            self.logger.info("HTTP < %s" % res.text)
        res.raise_for_status()
        return res

from go import Go
from players import Player, MCTS_Player, PolicyNetworkArgmax
from model import Gen_Model

if __name__ == '__main__':
    logger = make_logger('debug')
    player  = Player()
    # model  = Gen_Model().load('Go', '0.1')
    # player = MCTS_Player(model, time_limit=1)
    #player = PolicyNetworkArgmax('AI', model)
    ogs_api = OnlineGoAPI('Pasbot', 'password')
    ogs_api.logon()
    time.sleep(1)
    ogs_api._make_challenge()
    while True:
        time.sleep(1)
        games = list(ogs_api.gamedata)
        # Moves
        play_games = [g for g in games if ogs_api.gamedata[g]['phase'] == 'play']
        my_turn_games = [g for g in play_games if ogs_api.gamedata[g]['clock']['current_player'] == ogs_api.config['user']['id']]
        for game_id in my_turn_games:
            logger.info(game_id)
            data = ogs_api.gamedata[game_id]
            go = Go(board_size=data['width'])
            moves = data['moves']
            for x,y,_ in moves:
                pos = (x,y)
                go = go.place(pos)
            print(go)
            try:
                move = player.get_move(go)
            except:
                logger.error(traceback.format_exc())
                move = Go.PASS
            logger.info("MOVE:::%s" % str(move))
            ogs_api._game_move(game_id, move)
        # Stone Removal
        stone_removals = [g for g in games if ogs_api.gamedata[g]['phase'] == 'stone removal']
        for game_id in stone_removals:
            ogs_api._removed_stones_accept(game_id)