
import os

import numpy as np
from go import Go

import functools as ft

import traceback

from sgf_converter import play_sgf

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

class DataGenerator(Sequence):
    def __init__(self, sgfs, batch_size):
        self.sgfs       = sgfs
        self.batch_size = batch_size
        self.data       = self._prepare_data(sgfs)
    def _prepare_data(self, sgfs):
        def process_sgf(sgf):
            game = play_sgf(sgf)
            def full_go_to_x(go):
                if go._prev is not None:
                    return np.concatenate(
                        [full_go_to_x(go._prev), single_go_to_x(go)],
                        axis=0
                    )
                return single_go_to_x(go)
            def full_go_to_y_policy(go):
                reversed_moves = [Go.PASS]
                while go._prev is not None:
                    reversed_moves.append(go._last_move)
                    go = go._prev
                ys = np.zeros(shape=(len(reversed_moves),go._size*go._size+1))
                for i,move in enumerate(reversed(reversed_moves)):
                    if move != Go.PASS:
                        idx = np.ravel_multi_index(move, (9,9))
                        ys[i][idx] = 1
                    else:
                        ys[i][-1] = 1
                return ys
            go = game['board']
            winner = game['RE']
            x = full_go_to_x(go)
            y_value = np.full(
                shape=(len(x),1), 
                fill_value=1 if winner[0] == 'B' else 0
            )
            y_policy = full_go_to_y_policy(go)
            return x,y_value,y_policy
        return Parallel(n_jobs=4)(
            delayed(process_sgf)(sgf) for sgf in tqdm(sgfs, ncols=80)
        )
    def __len__(self):
        return int(np.ceil(len(self.sgfs) / float(self.batch_size)))
    #@ft.lru_cache(maxsize=None)
    def __getitem__(self, idx):
        batch_data  = self.data[idx * self.batch_size:(idx + 1) * self.batch_size]
        xs, y_values, y_policies = [], [], []
        for x,y,yy in batch_data:
            idx = np.random.randint(0, len(x))
            xs.append(x[idx])
            y_values.append(y[idx])
            y_policies.append(yy[idx])
        return np.stack(xs, axis=0), {'value_head': np.stack(y_values, axis=0), 'policy_head': np.stack(y_policies, axis=0)}

if __name__ == '__main__':
    # SUPERVISED LEARNING

    # Load Data
    import codecs
    from tqdm import tqdm
    sgfs = []
    path = 'sgfs/sdk_9x9/'
    n_games = len(os.listdir(path))
    for game_id in tqdm(os.listdir(path)[:n_games], ncols=80):
        sgfs.append(codecs.open('sgfs/sdk_9x9/%s' % game_id, 'r', 'utf-8').read())

    # Sequence Generator for Training
    data_generator = DataGenerator(sgfs, batch_size = 128)

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
        loss_weights={'value_head': 0.5, 'policy_head': 0.5},
        metrics={'value_head': 'accuracy', 'policy_head': 'accuracy'},
    )
    model.model.fit_generator(
        generator = data_generator,
        epochs = 100, verbose = 1,
    )

    # Save Model
    model.save('Go', '0.1')