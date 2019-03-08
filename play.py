import random
import time
import yaml
import threading
import traceback

import numpy as np

from ogs_api import OnlineGoAPI, make_logger
from go import Go
from players import MCTS_Player
from model import Gen_Model

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
        return MCTS_Player(model, time_limit=2)
    # Initialise TF session
    MCTS_Player(model, time_limit=1).get_move(Go())
    max_concurrent_games = 0
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
