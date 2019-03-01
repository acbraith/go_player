
import os
import requests
import time
import codecs
import random
from requests.exceptions import ProxyError

from joblib import Parallel, delayed

# https://www.proxy-list.download/HTTPS
proxies = open('Proxy List.txt').read().split('\n')

def user_games(user_id: int) -> str:
    '''
    {
        'annulled': False,
        'black': 594193,
        'black_lost': False,
        'black_player_rank': 11,
        'black_player_rating': '227.031',
        'creator': 594193,
        'disable_analysis': False,
        'ended': '2018-12-29T11:12:20.424166Z',
        'handicap': 0,
        'height': 9,
        'historical_ratings': {   'black': {   'country': 'abraith93',
                                                'icon': 'https://b0c2ddc39d13e1c0ddad-93a52a5bc9e7cc06050c1a999beb3694.ssl.cf1.rackcdn.com/201b0950c21ca70478047d87178e2a11-32.png',
                                                'id': 594193,
                                                'professional': False,
                                                'ranking': 13,
                                                'ratings': {   'overall': {   'deviation': 89.38227844238281,
                                                                            'rating': 1250.7325439453125,
                                                                            'volatility': 0.0600135363638401}},
                                                'ui_class': '',
                                                'username': 'abraith93'},
                                    'white': {   'country': 'MarianoGarcia',
                                                'icon': 'https://secure.gravatar.com/avatar/871ca7ac44097d53afc202c26fe5235e?s=32&d=retro',
                                                'id': 600633,
                                                'professional': False,
                                                'ranking': 8,
                                                'ratings': {   'overall': {   'deviation': 276.2551574707031,
                                                                            'rating': 1167.34521484375,
                                                                            'volatility': 0.06000926345586777}},
                                                'ui_class': 'timeout '
                                                            'provisional',
                                                'username': 'MarianoGarcia'}},
        'id': 15853605,
        'komi': '5.50',
        'ladder': 315,
        'mode': 'game',
        'name': 'Ladder Challenge: abraith93(#696) vs '
                'MarianoGarcia(#689)',
        'outcome': 'Timeout',
        'pause_on_weekends': False,
        'players': {   'black': {   'country': 'gb',
                                    'icon': 'https://b0c2ddc39d13e1c0ddad-93a52a5bc9e7cc06050c1a999beb3694.ssl.cf1.rackcdn.com/201b0950c21ca70478047d87178e2a11-32.png',
                                    'id': 594193,
                                    'professional': False,
                                    'ranking': 13,
                                    'ratings': {   'overall': {   'deviation': 86.5495894018104,
                                                                    'games_played': 40,
                                                                    'rating': 1367.4698926608785,
                                                                    'volatility': 0.060434656605577466}},
                                    'ui_class': '',
                                    'username': 'abraith93'},
                        'white': {   'country': 'un',
                                    'icon': 'https://secure.gravatar.com/avatar/871ca7ac44097d53afc202c26fe5235e?s=32&d=retro',
                                    'id': 600633,
                                    'professional': False,
                                    'ranking': 8,
                                    'ratings': {   'overall': {   'deviation': 234.6100508099094,
                                                                    'games_played': 2,
                                                                    'rating': 1018.5221900590969,
                                                                    'volatility': 0.06002467062280495}},
                                    'ui_class': 'timeout '
                                                'provisional',
                                    'username': 'MarianoGarcia'}},
        'ranked': True,
        'related': {'detail': '/api/v1/games/15853605'},
        'rules': 'japanese',
        'sgf_filename': None,
        'source': 'play',
        'started': '2018-12-25T10:58:02.224138Z',
        'time_control': 'fischer',
        'time_control_parameters': '{"time_control": "fischer", '
                                    '"initial_time": 259200, '
                                    '"max_time": 259200, '
                                    '"time_increment": 86400}',
        'time_per_move': 89280,
        'tournament': None,
        'tournament_round': 0,
        'white': 600633,
        'white_lost': True,
        'white_player_rank': 0,
        'white_player_rating': '0.000',
        'width': 9
    }
    '''
    url = "https://online-go.com/api/v1/players/%s/games/?format=json" % (user_id)
    while url is not None:
        try:
            response = requests.get(url, proxies={'https': random.choice(proxies)}, timeout=5)
            response.raise_for_status()
        except (ProxyError, requests.Timeout):
            continue
        except requests.HTTPError as e:
            status_code = e.response.status_code
            if status_code == 429: # rate limit
                # time.sleep(5)
                continue
            else:
                url = None
                continue
        data = response.json()
        for r in data['results']:
            yield r
        url = data['next']

def game_sgf(game_id: int) -> str:
    url = 'https://online-go.com/api/v1/games/%s/sgf' % (game_id)
    try:
        response = requests.get(url, proxies={'https': random.choice(proxies)}, timeout=5)
        response.raise_for_status()
        return response.text
    except (ProxyError, requests.Timeout):
        return game_sgf(game_id)
    except requests.HTTPError as e:
        status_code = e.response.status_code
        if status_code == 429: # rate limit
            # time.sleep(5)
            return game_sgf(game_id)
        else:
            return None

def save_user_sgfs(user_id: int) -> None:
    for game in user_games(user_id):
        if not os.path.exists('sgfs/%s' % user_id):
            os.makedirs('sgfs/%s' % user_id)
        if game['width'] == game['height'] == 9 and \
            not game['annulled'] and \
            game['outcome'] != '' and \
            game['handicap'] == 0:
            sgf = game_sgf(game['id'])
            if sgf:
                with codecs.open(
                    'sgfs/%s/%s.sgf' % (user_id, game['id']), 
                    'w', 'utf-8'
                ) as f:
                    f.write(sgf)

def games():
    url = 'http://online-go.com/v1/games/?format=json'
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.HTTPError as e:
        status_code = e.response.status_code
        if status_code == 429: # rate limit
            time.sleep(5)
            return games()
        else:
            return None

def download_sgfs(end_game_id = 16287929, n = 10000, name = 'downloads', criteria = lambda sgf: True):
    if not os.path.exists('sgfs/%s' % name):
        os.makedirs('sgfs/%s' % name)
    downloaded  = {int(gid.split('.')[0]) for gid in os.listdir('sgfs/%s/' % (name))}
    game_ids    = [gid for gid in range(end_game_id-n, end_game_id+1) if gid not in downloaded]
    random.shuffle(game_ids)
    def get_sgf(game_id):
        try:
            sgf = game_sgf(game_id)
            if sgf and criteria(sgf):
                with codecs.open(
                    'sgfs/%s/%s.sgf' % (name, game_id), 
                    'w', 'utf-8'
                ) as f:
                    f.write(sgf)
        except:
            pass

    Parallel(n_jobs=500, backend='threading')(
        delayed(get_sgf)(game_id) for game_id in tqdm(game_ids, ncols=80)
    )

from sgf_converter import *
from tqdm import tqdm
import traceback
if __name__ == '__main__':
    def rank_to_int(rank):
        if rank[-1].lower() == 'k':
            return -int(rank[:-1])
        elif rank[-1].lower() == 'd':
            return int(rank[:-1])
        elif rank[-1].lower() == 'p':
            return int(rank[:-1]) + 10
        return -60
    criteria = lambda sgf: \
        RE(sgf)[0] in {'B','W'} and \
        SZ(sgf) == '9' and \
        rank_to_int(BR(sgf)) >= rank_to_int('9k') and \
        rank_to_int(WR(sgf)) >= rank_to_int('9k') and \
        HA(sgf) in {'0','?'}
    download_sgfs(name='sdk_9x9', criteria=criteria, n=1000000)
    #save_user_sgfs(user_id = 594193) # abraith93