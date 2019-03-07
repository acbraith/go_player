
#%%
import numpy as np
import requests
import websocket
import json
import time
import logging
import traceback
import yaml
import uuid
import threading
import multiprocessing
import random

from go import Go
from players import Player, MCTS_Player, PolicyNetworkArgmax
from model import Gen_Model

import concurrent.futures as futures

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

def run(game_id, ogs_api, player, logger):
    def _start_msg():
        msgs = [
            'glhf!',
            'hey :)',
            'good luck!',
            'have fun',
            'hi!',
            'hello',
            'hi! glhf',
        ]
        return random.choice(msgs)
    def _end_msg():
        msgs = [
            'gg',
            'good game',
            'gg thanks',
            'thx',
        ]
        return random.choice(msgs)
    def _losing_msg():
        msgs = [
            'ow',
            'oops',
            ':(',
        ]
        return random.choice(msgs)
    def _winning_msg():
        msgs = [
            'ye',
            ':)',
            'hehe',
        ]
        return random.choice(msgs)
    def gamedata():
        return ogs_api.gamedata[game_id]
    def _move_count():
        return len(gamedata()['moves'])
    def _playing_black():
        return int(gamedata()['clock']['black_player_id']) == int(ogs_api.config['user']['id'])
    def _game_over():
        return gamedata()['phase'] == 'finished'
    def _my_turn():
        return gamedata()['phase'] == 'play' and \
            int(gamedata()['clock']['current_player']) == int(ogs_api.config['user']['id'])
    def _time_left():
        time_left       = gamedata()['clock']['black_time'] if _playing_black() else gamedata()['clock']['white_time']
        total_time      = time_left['thinking_time']
        try: total_time += time_left['periods'] * time_left['period_time']
        except: pass
        if _my_turn():
            time_elapsed = (time.time() - gamedata()['clock']['last_move'] / 1000)
            total_time  -= time_elapsed
        return total_time
    def _get_move_time():
        move_time = np.clip(player.mcts.time_limit, 0.25, _time_left() - 1)
        return move_time
    def _get_go():
        try:
            go = Go(board_size=gamedata()['width'])
            for x,y,_ in gamedata()['moves']:
                go = go.place((x,y))
            return go
        except:
            return Go()
    def _get_move(go, move_time):
        try:
            player.mcts.time_limit = move_time
            move = player.get_move(go)
            player.mcts.time_limit = move_time
        except:
            logger.warning('%s : %s' % (game_id, traceback.format_exc()))
            move = Go.PASS
        return move
    def _win_prob(go):
        black_win_prob = player.black_win_prob(go)
        return black_win_prob if _playing_black() else 1-black_win_prob
    def _do_turn():
        logger.info('%s : _do_turn' % game_id)
        go   = _get_go()
        win_prob = _win_prob(go)
        win_probs.append(win_prob)
        logger.info('%s : win_prob=%.2f' % (game_id, win_prob))
        if len(win_probs) > 3 and all([wp < 0.05 for wp in win_probs[-3:]]):
            logger.info('%s : resign' % (game_id))
            ogs_api._game_resign(game_id)
        else:
            mt   = _get_move_time()
            move = _get_move(go, mt)
            logger.info('%s : move %s' % (game_id, move))
            ogs_api._game_move(game_id, move)
    logger.info('%s : start' % (game_id))
    win_probs = []
    sent_msgs = [0]
    if _move_count() < 2:
        ogs_api._game_chat(game_id, _start_msg())
        sent_msgs.append(_move_count())
    while not _game_over():
        logger.info('%s : sleep' % (game_id))
        while not _my_turn() and not _game_over():
            try:    player.mcts.run_simulation()
            except: pass
        logger.info('%s : wake' % (game_id))
        if _game_over():
            logger.info('%s : game over' % (game_id))
            ogs_api._game_chat(game_id, _end_msg())
            sent_msgs.append(_move_count())
            return
        _do_turn()
        time.sleep(0.5)
        if _move_count() - sent_msgs[-1] > 10 and len(win_probs) > 4:
            delta_wp = win_probs[-1] - np.mean(win_probs[-5:-1])
            if delta_wp > 0.4 and win_probs[-1] > 0.6:
                ogs_api._game_chat(game_id, _winning_msg())
                sent_msgs.append(_move_count())
            if delta_wp < -0.4 and win_probs[-1] < 0.4:
                ogs_api._game_chat(game_id, _losing_msg())
                sent_msgs.append(_move_count())

if __name__ == '__main__':
    logger  = make_logger('debug')
    model  = Gen_Model().load('Go', '0.1')
    def new_player():
        return MCTS_Player(model, time_limit=10)
    # Initialise TF session
    MCTS_Player(model, time_limit=1).get_move(Go())
    max_concurrent_games = 2
    run_threads = {}
    config  = yaml.load(open('config.yml', 'r'))
    ogs_api = OnlineGoAPI(config['username'], config['password'])
    ogs_api.logon()
    time.sleep(1)
    while True:
        time.sleep(5)
        play_games    = [g for g in ogs_api.gamedata if ogs_api.gamedata[g]['phase'] == 'play']
        for game_id in play_games:
            if game_id not in run_threads:
                logger.info("start thread for %s" % game_id)
                # run(game_id, ogs_api, new_player())
                threading.Thread(target=run, args=(game_id, ogs_api, new_player(), logger)).start()
                # multiprocessing.Process(target=run, args=(game_id, ogs_api, new_player(), logger)).start()
                run_threads[game_id] = True
        if ogs_api.automatch is None and len(play_games) < max_concurrent_games:
            logger.info("FIND AUTOMATCH")
            ogs_api._find_automatch()
