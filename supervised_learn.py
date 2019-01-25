
import os

import numpy as np
from go import Go

from sgf_converter import play_sgf

import resnet

def single_go_to_x(go):
    return go._board.reshape(1,9,9,1)
    # try:
    #     return np.stack([
    #         go._board.reshape(1,9,9),
    #         go._prev._board.reshape(1,9,9),
    #         go._prev._prev._board.reshape(1,9,9),
    #     ], axis=3)
    # except: pass
    # try:
    #     return np.stack([
    #         go._board.reshape(1,9,9),
    #         go._prev._board.reshape(1,9,9),
    #         np.zeros(shape=(1,9,9)),
    #     ], axis=3)
    # except: pass
    # try:
    #     return np.stack([
    #         go._board.reshape(1,9,9),
    #         np.zeros(shape=(1,9,9)),
    #         np.zeros(shape=(1,9,9)),
    #     ], axis=3)
    # except: pass
def full_go_to_x(go):
    if go._prev is not None:
        return np.concatenate(
            [full_go_to_x(go._prev), single_go_to_x(go)],
            axis=0
        )
    return single_go_to_x(go)
def augment_data(x,y=None):
    x = np.concatenate([x, np.flip(x, axis=(1))], axis=0)
    x = np.concatenate([x, np.rot90(x, axes=(1,2))], axis=0)
    x = np.concatenate([x, np.rot90(x, k=2, axes=(1,2))], axis=0)
    if y is not None:
        y = np.concatenate([y]*8, axis=0)
        return x,y
    return x

if __name__ == '__main__':
    import codecs
    from sgf_converter import size, winner
    from tqdm import tqdm

    print("Loading SGFs...")
    sgfs            = [codecs.open('sgfs/downloads/%s' % game_id, 'r', 'utf-8').read() for game_id in os.listdir('sgfs/downloads/')]
    finished_9x9    = lambda sgf: size(sgf) == '9' and winner(sgf)[0] in ['B', 'W']
    sgfs            = [sgf for sgf in sgfs if finished_9x9(sgf)]

    print("Playing games...")
    games           = [play_sgf(sgf) for sgf in tqdm(sgfs, ncols=80)]

    print("Generating data...")
    def game_to_xy(game):
        x = full_go_to_x(game[0])
        y = np.full(
            shape=(len(x),1), 
            fill_value=1 if game[1][0] == 'B' else 0
        )
        return x,y
    x = np.zeros(shape=(0,9,9,1))
    y = np.zeros(shape=(0,1))
    for game in tqdm(games, ncols=80):
        x_,y_ = game_to_xy(game)
        x = np.concatenate([x, x_], axis=0)
        y = np.concatenate([y, y_], axis=0)
    # Rotate and flip x,y
    x,y = augment_data(x,y)

    print("Building model...")
    model = resnet.ResnetBuilder.build(
        input_shape=(1,9,9), 
        num_outputs=1, 
        block_fn=resnet.basic_block, 
        repetitions=[2,2],
        output_activation='sigmoid'
    )
    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',
        metrics=['accuracy', 'mse', 'mae']
    )
    print("Training model...")
    model.fit(x, y, epochs=1, batch_size=128, verbose=1)

    for go,res in games:
        print(go)
        print(res, np.mean(model.predict(augment_data(single_go_to_x(go)))))
        print('************************************************************')

    from learn import autoplay
    from players import NeuralNetwork, MaxScoreDiff
    autoplay(NeuralNetwork('p1', model), MaxScoreDiff(), pause=0.01)
    autoplay(MaxScoreDiff(), NeuralNetwork('p1', model), pause=0.01)