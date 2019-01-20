from joblib import Parallel, delayed
import itertools
import numpy as np
import traceback

from go import Go

class Player:
    def __init__(self, name='Random', n_jobs=1):
        self.name = name
        self.n_jobs = n_jobs
    def eval_move(self, go, move) -> float:
        return 0
    def eval_moves(self, go, moves):
        def wrapped_eval_move(*args, **kwargs):
            try:    return self.eval_move(*args, **kwargs)
            except: return -1e8
        if self.n_jobs != 1:
            res = Parallel(n_jobs=self.n_jobs)(
                delayed(wrapped_eval_move)(go, m) for m in moves
            )
        else:
            res = [wrapped_eval_move(go, m) for m in moves]
        return res
    def select_move(self, moves, scores):
        rand_argmax = lambda a: np.random.choice(np.flatnonzero(a == a.max()))
        idx_max = rand_argmax(np.array(scores))
        return moves[idx_max]
    def get_move(self, go):
        moves = list(itertools.product(range(go._size), range(go._size))) + [Go.PASS]
        scores = self.eval_moves(go, moves)
        return self.select_move(moves, scores)
        
class MaxMyScore(Player):
    def eval_move(self, go, move) -> float:
        p = go._turn
        return go.place(move)._score(p)
class MinOpponentScore(Player):
    def eval_move(self, go, move) -> float:
        p = go._turn
        return -go.place(move)._score(p*-1)
class MaxScoreDiff(Player):
    def eval_move(self, go, move) -> float:
        p = go._turn
        go_next = go.place(move)
        return go_next._score(p)-go_next._score(p*-1)

class MonteCarlo(Player):
    def eval_move(self, go, move) -> float:
        p = go._turn
        def rollout_win(go, player=Player(), turns=5) -> bool:
            for _ in range(turns):
                if go._over: break
                move = player.get_move(go)
                go_next = go.place(move)
                if go_next is None:
                    go_next = go.place(Go.PASS)
                go = go_next
            return go._score(p) - go._score(p*-1)
        return np.mean([rollout_win(go.place(move), turns=10) for _ in range(50)])

from supervised_learn import single_go_to_x, augment_data

class NeuralNetwork(Player):
    def __init__(self, name, model, epsilon=0):
        self.model = model
        self.name = name
        self.n_jobs = 1
        self.epsilon = 0
    def eval_move(self, go, move) -> float:
        is_black = go._turn == Go.BLACK
        x = augment_data(single_go_to_x(go.place(move)))
        if is_black:
            return np.mean(self.model.predict(x))
        else:
            return 1-np.mean(self.model.predict(x))
    def get_move(self, go):
        moves = list(itertools.product(range(go._size), range(go._size))) + [Go.PASS]
        if np.random.rand() < self.epsilon: # epsilon-greedy exploration
            idx = np.random.choice(len(moves))
            return moves[idx]
        scores = self.eval_moves(go, moves)
        return self.select_move(moves, scores)