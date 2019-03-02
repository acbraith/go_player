
#%%
import numpy as np
import requests
import websocket
import threading
import json
import time
import logging
import traceback
import yaml
import uuid

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
        pass # TODO
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
    def _removed_stones_accept(self, game_id):
        self.logger.info('_removed_stones_accept %s' % game_id)
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
                if data == 'stone removal':
                    self._game_chat(game_id, "I dunno how to do this bit")
                elif data == 'play':
                    del self.gamedata[game_id]
                    self._game_disconnect(game_id)
                    self._game_connect(game_id)
            elif game_endpoint == 'move':
                self.gamedata[game_id]['moves'].append(data['move'])
            elif game_endpoint == 'removed_stones':
                # TODO
                self.logger.debug('removed_stones %s' % game_id)
                self.logger.debug(str(data))
                pass
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
        msg = '42'+json.dumps([endpoint, message]).replace(' ','')
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

from go import Go
from players import Player, MCTS_Player, PolicyNetworkArgmax
from model import Gen_Model

if __name__ == '__main__':
    logger = make_logger('debug')
    model  = Gen_Model().load('Go', '0.1')
    move_max_time = 20
    move_min_time = 0.5
    def make_player():
        player  = Player()
        player = MCTS_Player(model, time_limit=move_max_time)
        return player
    players = {}

    config = yaml.load(open('config.yml', 'r'))
    ogs_api = OnlineGoAPI(config['username'], config['password'])
    ogs_api.logon()

    time.sleep(1)

    while True:
        time.sleep(0.5)
        games = list(ogs_api.gamedata)
        # Moves
        def time_left(game_id):
            clock = ogs_api.gamedata[game_id]['clock']
            time_left = clock['black_time'] if clock['black_player_id'] == ogs_api.config['user']['id'] else clock['white_time']
            total_time = time_left['thinking_time'] + time_left['periods'] * time_left['period_time']
            if clock['current_player'] == ogs_api.config['user']['id']:
                total_time = total_time - (time.time() - clock['last_move'] / 1000)
            return total_time
        play_games = [g for g in games if ogs_api.gamedata[g]['phase'] == 'play']
        my_turn_games = [g for g in play_games if ogs_api.gamedata[g]['clock']['current_player'] == ogs_api.config['user']['id']]
        if len(my_turn_games) == 0 or len(play_games) < 3:
            if ogs_api.automatch is None:
                logger.info("FIND AUTOMATCH")
                ogs_api._find_automatch()
                time.sleep(0.5)
        if len(my_turn_games) > 0:
            game_id = min(my_turn_games, key=lambda game_id: time_left(game_id))
            logger.info("GAME ID %s" % game_id)
            logger.info("  %.1fs remaining" % time_left(game_id))
            logger.debug('games time remaining: %s' % [time_left(g) for g in play_games])
            data = ogs_api.gamedata[game_id]
            go = Go(board_size=data['width'])
            moves = data['moves']
            for x,y,_ in moves:
                pos = (x,y)
                go = go.place(pos)
            if game_id not in players:
                players[game_id] = make_player()
            try:
                # Move time management
                def get_move_time(clock_left):
                    clock_left = np.array(sorted(clock_left))
                    move_times = np.clip(clock_left - 1, move_min_time, move_max_time)
                    cum_move_times = np.cumsum(move_times)
                    move_time = [
                        np.clip(
                            clock_left[0] - move_min_time,
                            move_min_time, move_max_time,
                        )
                    ]
                    try:
                        idx_timeout = np.where(cum_move_times > clock_left)[0][0]
                        move_time.append(np.clip(
                            clock_left[idx_timeout] / (idx_timeout+1) - move_min_time,
                            move_min_time, move_max_time,
                        ))
                    except:
                        pass
                    return min(move_time)
                move_time = get_move_time([time_left(g) for g in play_games])
                if move_time < move_max_time:
                    logger.debug('reduce move time -> %s' % move_time)
                    players[game_id].mcts.time_limit = move_time
                move = players[game_id].get_move(go)
                players[game_id].mcts.time_limit = move_max_time
            except:
                logger.error(traceback.format_exc())
                move = Go.PASS
            logger.info("MOVE:::%s" % str(move))
            ogs_api._game_move(game_id, move)

        # Stone Removal
        stone_removals = [g for g in games if ogs_api.gamedata[g]['phase'] == 'stone removal']
        # print("stone_removals: %s" % stone_removals)
        # for game_id in stone_removals:
        #     ogs_api._removed_stones_accept(game_id)
