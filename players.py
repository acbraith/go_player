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
                go_next = None
                while not go_next:
                    move = player.get_move(go)
                    go_next = go.place(move)
                go = go_next
            return go._score(p) - go._score(p*-1)
        return np.mean([rollout_win(go.place(move), turns=10) for _ in range(50)])

class NeuralNetwork(Player):
    def __init__(self, name, network, epsilon=0):
        self.network = network
        self.name = name
        self.n_jobs = 1
        self.epsilon = 0
    def eval_move(self, go, move) -> float:
        go_next = go.place(move)
        try:    board_prev  = go._prev._board.reshape(9,9)
        except: board_prev  = np.zeros(shape=(9,9))
        board               = go._board.reshape(9,9)
        board_next          = go_next._board.reshape(9,9)
        #print(board_prev.shape, board.shape, board_next.shape)
        if go._turn == Go.WHITE:
            board_prev  = board_prev * -1
            board       = board * -1
            board_next  = board_next * -1
        board = np.stack([board_prev, board, board_next], axis=2)
        #print(board.shape)
        boards = []
        for i in [0,1,2,3]:
            rot_board = np.rot90(board, k=i, axes=(0,1))
            boards += [
                rot_board, 
                np.flip(rot_board, axis=0),
            ]
        boards = np.stack(boards, axis=0)
        win_probs = self.network.predict(boards)
        win_prob = np.mean(win_probs[:,1])
        return win_prob
    def get_move(self, go):
        moves = list(itertools.product(range(go._size), range(go._size))) + [Go.PASS]
        if np.random.rand() < self.epsilon:                 # epsilon-greedy exploration
            idx = np.random.choice(len(moves))
            return moves[idx]
        scores = self.eval_moves(go, moves)
        #print(scores)
        return self.select_move(moves, scores)