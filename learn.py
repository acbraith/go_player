import numpy as np

import tensorflow as tf
from tensorflow.keras import utils, layers
from tensorflow.keras.models import load_model
import resnet

import time
import datetime as dt

from go import Go
from players import NeuralNetwork, Player, MaxScoreDiff, MaxMyScore, MinOpponentScore

from glicko2 import Glicko2, WIN, DRAW, LOSS

def autoplay(black=Player(), white=Player(), pause=0.1, **kwargs):
    ps = {-1: white, 1: black}
    go = Go(**kwargs)
    if pause:
        print(go)
    board_history = [go._board]
    for t in range(100):
        if go._over: break
        p = ps[go._turn]
        move = p.get_move(go)
        go_next = go.place(move)
        if not go_next:
            move = Go.PASS
            go_next = go.place(move)
        go = go_next
        board_history += [go._board]
        if pause:
            print('%s : %s' % (p.name, move))
            print("Turn %d" % t)
            print(go)
            time.sleep(pause)
    if pause:
        print(go)
    black_win = go._score(1) > go._score(-1)
    return black_win, board_history

import os
from tqdm import tqdm

HISTORY             = 3
EPSILON             = .05
MOVES_PER_GAME      = 100
DATA_PER_GAME       = 8*MOVES_PER_GAME
BATCH_GAMES         = 10
EVAL_GAMES          = 5
REPLAY_BUFFER       = DATA_PER_GAME*500
MINIBATCH_SIZE      = DATA_PER_GAME*BATCH_GAMES*5

if __name__ == '__main__':
    models = os.listdir('models')
    if len(models) > 0:
        print("Loading %s" % models[-1])
        curr_model = load_model('models/%s' % models[-1])
        copy_model = tf.keras.models.clone_model(curr_model)
        copy_model.set_weights(curr_model.get_weights())
        latest_p = NeuralNetwork('Loaded', copy_model)
    else:
        curr_model = resnet.ResnetBuilder.build((HISTORY,9,9), 2, resnet.basic_block, [2,2]) # Note: input shape is actually (9,9,HISTORY)
        copy_model = tf.keras.models.clone_model(curr_model)
        copy_model.set_weights(curr_model.get_weights())
        latest_p = NeuralNetwork('Iter 0', copy_model)
    curr_model.compile(
        optimizer='adam',
        loss='binary_crossentropy',
        metrics=['accuracy']
    )

    glicko2 = Glicko2()
    playerbase = {
        latest_p                    : glicko2.create_rating(1500),
        Player()                    : glicko2.create_rating(1500),
        MaxScoreDiff('Diff')        : glicko2.create_rating(1500),
        MaxMyScore('MaxMe')         : glicko2.create_rating(1500),
        MinOpponentScore('MinYou')  : glicko2.create_rating(1500),
    }
    komi = 5.5
    xs = np.zeros(shape=(0,9,9,HISTORY))
    ys = np.zeros(shape=(0,2))
    for i in range(1000000):

        best = max(playerbase, key=lambda p: playerbase[p].mu - 2.5*playerbase[p].phi if isinstance(p, NeuralNetwork) else 0)
        best.epsilon = EPSILON
        
        print("Rankings:")
        for p in sorted(playerbase.keys(), key=lambda p: playerbase[p].mu - 2.5*playerbase[p].phi, reverse=True):
            print('  - %7s (%4d = %4d ± %3d)' % (p.name, playerbase[p].mu - 2.5*playerbase[p].phi, playerbase[p].mu, playerbase[p].phi))
        print("Komi         : %.1f" % (komi))
        print("Replay Buffer: %d" % (len(xs)))
        print("Best         : %s" % (best.name))

        # Play Games
        n_games = 1
        b_wins = 0
        w_wins = 0
        print("* * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * ")
        print("Iteration %d" % (i+1))
        print("Self-play...")
        for j in tqdm(range(BATCH_GAMES), ncols=80):
            y_, xs_ = autoplay(best, best, pause=0, komi=komi)
            b_wins += y_
            w_wins += not y_
            # print("Iter %2d/%2d : Training Game %2d/%2d : %s WIN (%d-%d)" % (
            #     i+1, 100,
            #     j+1, BATCH_GAMES,
            #     'BLACK' if y_ else 'WHITE',
            #     b_wins, w_wins,
            # ))
            xs_ = np.concatenate([np.zeros_like(xs_)[:HISTORY-1], xs_], axis=0)
            xs_ = np.stack([xs_[:-2],xs_[1:-1],xs_[2:]], axis=3)
            ys_ = np.zeros(shape=(len(xs_),1)); ys_.fill(y_)
            ys_ = utils.to_categorical(ys_, 2)
            for k in [0,1,2,3]:
                rot_xs_ = np.rot90(xs_, k=k, axes=(1,2))
                xs = np.append(xs, rot_xs_, axis=0)
                xs = np.append(xs, np.flip(rot_xs_, axis=1), axis=0)
                ys = np.append(ys, ys_, axis=0)
                ys = np.append(ys, ys_, axis=0)

        best.epsilon = 0
        print("BLACK %d - %d WHITE" % (b_wins, w_wins))

        if b_wins < n_games / 10 and komi > 1.5:
            print('Adj Komi: %.1f -> %.1f' % (komi, komi-1))
            komi -= 1
        elif w_wins < n_games / 10 and komi < 7.5:
            print('Adj Komi: %.1f -> %.1f' % (komi, komi+1))
            komi += 1


        # Retrain model
        if len(xs) > REPLAY_BUFFER:
            print("Trimming replay buffer : %d -> %d" % (len(xs), REPLAY_BUFFER))
            xs = xs[-REPLAY_BUFFER:]
            ys = ys[-REPLAY_BUFFER:]
        idx = np.random.choice(len(xs), min(MINIBATCH_SIZE, len(xs)))
        print("Training...")
        curr_model.fit(xs[idx], ys[idx], epochs=1, batch_size=128, verbose=1)
        print("Saving model...")
        curr_model.save('models/%s.h5' % (dt.datetime.now().strftime('%Y%m%d_%H-%M-%S')))
        print("Saved model")
        copy_model = tf.keras.models.clone_model(curr_model)
        copy_model.set_weights(curr_model.get_weights())
        latest_p = NeuralNetwork('Iter %s' % (i+1), copy_model)
        curr_rating = glicko2.create_rating(playerbase[best].mu)

        # Mini Tournament
        sorted_ps = sorted(playerbase.keys(), key=lambda p: playerbase[p].mu, reverse=True)
        n_games = min(EVAL_GAMES, len(playerbase))
        ws = []
        print("Evaluating performance...")
        for j in tqdm(range(n_games), ncols=80):
            b = latest_p
            w = max(playerbase, key=lambda w: glicko2.quality_1vs1(playerbase[w], curr_rating) if w.name not in ws else 0)
            ws += [w.name]
            y_, xs_ = autoplay(b, w, pause=0, komi=komi)
            # print("Iter %2d/%2d : Tourney Game %2d/%2d : (%4d±%3d) B %7s v %-7s W (%4d±%3d) : %7s (%s) WIN after %3d moves" % (
            #     i+1, 100,
            #     j+1, n_games,
            #     curr_rating.mu, curr_rating.phi, b.name, 
            #     w.name, playerbase[w].mu, playerbase[w].phi,
            #     b.name if y_ else w.name,
            #     'BLACK' if y_ else 'WHITE',
            #     len(xs_),
            # ))
            b_ranking       = glicko2.rate(curr_rating, [(WIN if y_ else LOSS, playerbase[w])])
            w_ranking       = glicko2.rate(playerbase[w], [(LOSS if y_ else WIN, curr_rating)])
            curr_rating     = b_ranking
            playerbase[w]   = w_ranking
        playerbase[latest_p] = curr_rating


        
