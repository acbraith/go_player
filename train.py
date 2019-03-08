
#%%
import os
import tarfile

import codecs
from tqdm import tqdm

import numpy as np

import h5py

from go import Go

import functools as ft

import traceback
import random

from process_sgf import play_sgf, WR, BR

from tensorflow.keras.utils import Sequence

from joblib import Parallel, delayed

from model import Residual_CNN

def single_go_to_x(go):
    # return go._board.reshape(1,9,9,1)
    try:
        return np.concatenate([
            Go.BLACK==go._board.reshape(1,9,9,1),
            Go.BLACK==go._prev._board.reshape(1,9,9,1),
            Go.BLACK==go._prev._prev._board.reshape(1,9,9,1),
            Go.WHITE==go._board.reshape(1,9,9,1),
            Go.WHITE==go._prev._board.reshape(1,9,9,1),
            Go.WHITE==go._prev._prev._board.reshape(1,9,9,1),
            np.ones(shape=(1,9,9,1))*(go._turn == Go.BLACK),
        ], axis=3)
    except: pass
    try:
        return np.concatenate([
            Go.BLACK==go._board.reshape(1,9,9,1),
            Go.BLACK==go._prev._board.reshape(1,9,9,1),
            np.zeros(shape=(1,9,9,1)),
            Go.WHITE==go._board.reshape(1,9,9,1),
            Go.WHITE==go._prev._board.reshape(1,9,9,1),
            np.zeros(shape=(1,9,9,1)),
            np.ones(shape=(1,9,9,1))*(go._turn == Go.BLACK),
        ], axis=3)
    except: pass
    return np.concatenate([
        Go.BLACK==go._board.reshape(1,9,9,1),
        np.zeros(shape=(1,9,9,1)),
        np.zeros(shape=(1,9,9,1)),
        Go.WHITE==go._board.reshape(1,9,9,1),
        np.zeros(shape=(1,9,9,1)),
        np.zeros(shape=(1,9,9,1)),
        np.ones(shape=(1,9,9,1))*(go._turn == Go.BLACK),
    ], axis=3)

def get_x(go):
    if go._prev is not None:
        return np.concatenate(
            [get_x(go._prev), single_go_to_x(go)],
            axis=0
        )
    return single_go_to_x(go)

def get_y_policy(go):
    reversed_moves = [Go.PASS]
    while go._prev is not None:
        reversed_moves.append(go._last_move)
        go = go._prev
    y_policy = np.zeros(shape=(len(reversed_moves),go._size*go._size+1))
    for i,move in enumerate(reversed(reversed_moves)):
        if move != Go.PASS:
            idx = np.ravel_multi_index(move, (go._size, go._size))
            y_policy[i][idx] = 1
        else:
            y_policy[i][-1] = 1
    return y_policy

def get_y_value(winner, n):
    y_value = np.full(
        shape=(n,1), 
        fill_value=1 if winner[0] == 'B' else 0
    )
    return y_value

def process_sgf(sgf):
    game = play_sgf(sgf)
    go = game['board']
    winner = game['RE']
    x           = get_x(go)
    y_policy    = get_y_policy(go)
    y_value     = get_y_value(winner, len(x))
    return x, y_policy, y_value

def get_sgfs():
    datasets = os.listdir('data/aya')
    for d in sorted(datasets, reverse=True): # most recent first
        with tarfile.open('data/aya/%s' % d, 'r:bz2') as tar:
            for member in tar.getmembers():
                if member.isfile():
                    f = tar.extractfile(member)
                    content = f.read()
                    yield content.decode('utf-8')

def len_sgfs():
    # 187316 for 9x9_2015_11 -> 9x9_2018_12
    datasets = os.listdir('data/aya')
    total_len = 0
    for d in datasets:
        with tarfile.open('data/aya/%s' % d, 'r:bz2') as tar:
            total_len +=  len([m for m in tar.getmembers() if m.isfile()])
    return total_len

if __name__ == '__main__':
    # n_games = len_sgfs()
    mem_size = 500000

    # SUPERVISED LEARNING
    sgfs = get_sgfs()
    demo_sgf = sgfs.__next__()
    x, y_policy, y_value = process_sgf(demo_sgf)

    memory = h5py.File('data/memory.h5', 'w')
    memory.close()
    memory = h5py.File('data/memory.h5', 'r+')
    memory['x']         = np.zeros(shape=(mem_size,)+x.shape[1:])
    memory['y_value']   = np.zeros(shape=(mem_size,)+y_value.shape[1:])
    memory['y_policy']  = np.zeros(shape=(mem_size,)+y_policy.shape[1:])

    # Load Data
    def to_int(s):
        return int(''.join(c for c in s if c.isdigit()))
    ratings     = []
    print("Loading data into memory...")
    idx_start   = 0
    n_games     = 0
    tot_games   = 0
    with tqdm(
        total=mem_size, ncols=120,
    ) as pbar:
        for i,sgf in enumerate(sgfs):
            if idx_start >= mem_size: break
            # Ignore games not in top x% of ratings
            wr,br = to_int(WR(sgf)), to_int(BR(sgf))
            ratings += [min(wr,br)]
            if len(ratings) < 100 or min(wr,br) < np.percentile(ratings[-500:], 90):
                continue
            x, y_policy, y_value = process_sgf(sgf)
            idx_end = idx_start + len(x)
            if idx_end > mem_size: # overflow beyond end of memory
                x        = x[:mem_size - idx_end]
                y_policy = y_policy[:mem_size - idx_end]
                y_value  = y_value[:mem_size - idx_end]
                idx_end = mem_size
            memory['x'][idx_start:idx_end]          = x
            memory['y_policy'][idx_start:idx_end]   = y_policy
            memory['y_value'][idx_start:idx_end]    = y_value
            idx_start   += len(x)
            n_games     += 1
            pbar.update(len(x))
            pbar.set_postfix(game=n_games, tot_games=i+1)

    # Build Model
    model = Residual_CNN(
        reg_const       = 0.0001,
        learning_rate   = 0.01,
        input_dim       = (9,9,7),
        output_dim      = 9*9+1,
        hidden_layers   = [{'filters':128, 'kernel_size': (3,3)}]*10,
    )
    try:    model.load('Go', '0.1'); print("Loaded Model")
    except: print("Training New Model")

    # Train Model
    model.model.compile(
        loss={'value_head': 'binary_crossentropy', 'policy_head': 'categorical_crossentropy'},#softmax_cross_entropy_with_logits},
        optimizer='adam',
        loss_weights={'value_head': 0.2, 'policy_head': 0.8},
        metrics={'value_head': 'accuracy', 'policy_head': 'accuracy'},
    ) # states, targets, epochs, verbose, validation_split, batch_size
    model.model.fit(
        memory['x'],#[:idx_end], 
        {
            'value_head'    : memory['y_value'],#[:idx_end], 
            'policy_head'   : memory['y_policy'],#[:idx_end],
        },
        epochs=1, verbose=1, batch_size=64, shuffle='batch',
    )

    # Save Model
    model.save('Go', '0.1')