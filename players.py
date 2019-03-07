from joblib import Parallel, delayed
import itertools
import numpy as np
import traceback
import random

from go import Go

class Player:
    def __init__(self, name='Random', n_jobs=1):
        self.name = name
        self.n_jobs = n_jobs
    def eval_move(self, go, move) -> float:
        go.place(move)
        return 1
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
    def __init__(self, name, rollout_iters=20, rollouts=500, rollout_policy = None, eval_function = None):
        super().__init__(name)
        self.rollout_iters = rollout_iters
        self.rollouts = rollouts
        self.rollout_policy = rollout_policy
        self.eval_function = eval_function
        if self.rollout_policy is None:
            self.rollout_policy = lambda go: Player().get_move(go)
        if self.eval_function is None:
            self.eval_function = lambda go, p: go._score(p) - go._score(p*-1)
    def get_move(self, go):
        p = go._turn
        def rollout(go) -> bool:
            moves = []
            for _ in range(self.rollout_iters):
                if go._over: break
                try:
                    move = self.rollout_policy(go)
                    go = go.place(move)
                except Exception as e:
                    print(e)
                    move = Go.PASS
                    go = go.place(move)
                moves.append(move)
            return moves, go
        rollouts = [rollout(go) for _ in range(self.rollouts)]
        scores = [(self.eval_function(go, p), moves[0]) for moves,go in rollouts]
        return max(scores)[1]

from train import single_go_to_x

class ValueFunctionGreedy(Player):
    def __init__(self, name, model):
        self.model = model
        self.name = name
        self.n_jobs = 1
    def eval_move(self, go, move) -> float:
        is_black = go._turn == Go.BLACK
        x = single_go_to_x(go.place(move))
        value, probs = self.model.predict(x)
        if is_black:
            return value[0]
        else:
            return 1-value[0]
    def get_move(self, go):
        moves = list(itertools.product(range(go._size), range(go._size))) + [Go.PASS]
        scores = self.eval_moves(go, moves)
        return self.select_move(moves, scores)
class PolicyNetworkArgmax(Player):
    def __init__(self, name, model):
        self.model = model
        self.name = name
        self.n_jobs = 1
        self.epsilon = 0
    def get_move(self, go):
        x = single_go_to_x(go)
        value, probs = self.model.predict(x)
        def get_move(probs):
            if np.argmax(probs) == 9*9:
                return Go.PASS
            return np.unravel_index(np.argmax(probs), (9,9))
        while True:
            move = get_move(probs)
            try: 
                go.place(move)
                return move
            except: 
                probs[0][np.argmax(probs)] = 0

from mcts import MCTS, State
class MCTS_Player:
    class GoState(State):
        def __init__(self, go):
            self.go                 = go
            self.prev_action        = self.gomove_to_action(go._last_move)
            self.turn               = go._turn
            self.terminal           = go._over
            self.available_actions  = range(self.go._size**2+1)
            def valid_action(action):
                try:
                    self.go.place(self.action_to_gomove(action))
                    return True
                except:
                    return False
            self.available_actions  = [i for i in range(82) if valid_action(i)]
        def action_to_gomove(self, action):
            try:
                return np.unravel_index(action, (self.go._size, self.go._size))
            except ValueError:
                return Go.PASS
        def gomove_to_action(self, gomove):
            try:
                return np.ravel_multi_index(gomove, (self.go._size, self.go._size))
            except ValueError:
                return 81
        def __eq__(self, other):
            return self.go == other.go and self.prev_action == other.prev_action
        def step(self, action):
            return MCTS_Player.GoState(self.go.place(self.action_to_gomove(action)))
    def __init__(self, model, time_limit=1):
        self.name = 'MCTS_Player'
        self.model = model
        translations = [
            lambda x: x,
            lambda x: np.rot90(x, k=1, axes=(1,2)),
            lambda x: np.rot90(x, k=2, axes=(1,2)),
            lambda x: np.rot90(x, k=3, axes=(1,2)),
            lambda x: np.flip(x, axis=1),
            lambda x: np.rot90(np.flip(x, axis=1), k=1, axes=(1,2)),
            lambda x: np.rot90(np.flip(x, axis=1), k=2, axes=(1,2)),
            lambda x: np.rot90(np.flip(x, axis=1), k=3, axes=(1,2)),
        ]
        inv_translations = [
            lambda x: x,
            lambda x: np.rot90(x, k=-1, axes=(1,2)),
            lambda x: np.rot90(x, k=-2, axes=(1,2)),
            lambda x: np.rot90(x, k=-3, axes=(1,2)),
            lambda x: np.flip(x, axis=1),
            lambda x: np.flip(np.rot90(x, k=-1, axes=(1,2)), axis=1),
            lambda x: np.flip(np.rot90(x, k=-2, axes=(1,2)), axis=1),
            lambda x: np.flip(np.rot90(x, k=-3, axes=(1,2)), axis=1),
        ]
        def val_policy_fn(gostates):
            x = np.concatenate(
                [single_go_to_x(gostate.go) for gostate in gostates],
                axis=0
            )
            idx = random.choice(range(len(translations)))
            x_trans = translations[idx](x)
            val, pi_trans = self.model.predict(x_trans)
            pi_moves_trans = pi_trans[:,:-1].reshape(-1,9,9,1)
            pi_moves = inv_translations[idx](pi_moves_trans)
            pi = np.append(pi_moves.reshape(pi_trans[:,:-1].shape), pi_trans[:,-1:], axis=1)
            return val, pi
        self.mcts = MCTS(
            c_puct = 0.1,
            val_policy_fn = val_policy_fn,
            time_limit = time_limit,
        )
    def black_win_prob(self, go):
        val, pi = self.mcts.val_policy_fn([MCTS_Player.GoState(go)])
        return val[0]
    def get_move(self, go):
        state = MCTS_Player.GoState(go)
        return state.action_to_gomove(self.mcts.get_action(state))