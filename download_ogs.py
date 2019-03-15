
import os
import requests
import time
import codecs
import random
from requests.exceptions import ProxyError

from joblib import Parallel, delayed

from tqdm import tqdm

# https://www.proxy-list.download/HTTPS
proxies = open('Proxy List.txt').read().split('\n')

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

def save_sgf(game_id: int) -> None:
    try:
        sgf = game_sgf(game_id)
        if sgf:
            with codecs.open(
                'data/ogs/%s.sgf' % game_id, 
                'w', 'utf-8'
            ) as f:
                f.write(sgf)
    except:
        pass

import tarfile
def make_tarfile(output_filename, source_dir):
    # make_tarfile('data/ogs.tar.gz', 'data/ogs')
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.sep)

if __name__ == '__main__':
    end_game_id     = 16898710
    start_game_id   = end_game_id - 1*10**6

    if not os.path.exists('data/ogs'):
        os.makedirs('data/ogs')
    downloaded  = {int(gid.split('.')[0]) for gid in os.listdir('data/ogs/')}
    game_ids    = [gid for gid in range(start_game_id, end_game_id+1) if gid not in downloaded]
    random.shuffle(game_ids)

    Parallel(n_jobs=100, backend='threading')(
        delayed(save_sgf)(game_id) for game_id in tqdm(game_ids, ncols=80)
    )