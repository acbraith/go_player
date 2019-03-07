import numpy as np
import time
import itertools

class State:
    def __init__(self):
        self.prev_action        = None
        self.terminal           = False
        self.available_actions  = []
        self.turn               = 1 # {1, -1}
    def step(self, action):
        # TODO take action
        return State()

class Node:
    def __init__(self, state, parent):
        self.state          = state
        self.parent         = parent
        self.children       = {}
        self.action_probs   = {}
        self.num_visits     = 0
        self.total_reward   = 0

from tqdm import tqdm

class MCTS:
    def __init__(self, c_puct, val_policy_fn, iteration_limit = None, time_limit = None):
        self.iteration_limit    = iteration_limit
        self.time_limit         = time_limit # sec
        self.c_puct             = c_puct
        self.val_policy_fn      = val_policy_fn
        self.root               = None

    def _select_action(self, node, c_puct):
        def value(action):
            try:             child = node.children[action]
            except KeyError: child = Node(node.state, node)
            try:             p = node.action_probs[action]
            except KeyError: p = 1 / len(node.state.available_actions)
            try:
                Q = child.total_reward / child.num_visits
            except ZeroDivisionError:
                Q = 0.5
            try:
                U = c_puct * p * np.sqrt(node.num_visits) / (1+child.num_visits)
            except (KeyError, ZeroDivisionError):
                U = c_puct * p * np.sqrt(node.num_visits) / (1+child.num_visits)
            if node.state.turn == -1: Q = 1 - Q
            return Q + U
        action_values = {
            action: value(action) for action in node.state.available_actions
        }
        return max(action_values, key=lambda action: action_values[action])

    def _select_leaf_node(self, node):
        if node.state.terminal:
            return node
        action = self._select_action(node, self.c_puct)
        if action not in node.children:
            new_state = node.state.step(action)
            child = Node(new_state, node)
            node.children[action] = child
            return child
        return self._select_leaf_node(node.children[action])

    def _backpropagate(self, node, reward):
        if node is None: return
        node.num_visits += 1
        node.total_reward += reward
        self._backpropagate(node.parent, reward)

    def _evaluate(self, nodes):
        value, action_probs = self.val_policy_fn([node.state for node in nodes])
        return value, action_probs

    def run_simulation(self, iteration_limit=None, time_limit=None):
        start_time      = time.time()
        eval_batch_size = 1
        updates         = 0
        while True:
            updates += eval_batch_size
            # 1. Selection
            leafs                   = [self._select_leaf_node(self.root) for _ in range(eval_batch_size)]
            # 2. Evaluation
            vals, pis               = self._evaluate(leafs)
            for leaf, val, pi in zip(leafs, vals, pis):
                leaf.action_probs   = pi
                # 3. Backpropagation
                self._backpropagate(leaf, val)
            if (time_limit is None or time.time() - start_time > time_limit) and (iteration_limit is None or updates > iteration_limit):
                break
        # print('%d iter in %.2f sec = %.2f iter/sec' % (
        #     updates, time.time() - start_time, updates / (time.time() - start_time)
        # ))

    def get_action(self, state, update_root=True):
        try:
            # Update Root
            prev_action = state.prev_action
            self.root   = self.root.children[prev_action]
            assert(self.root.state == state)
            # print("Updated root with %s visits" % self.root.num_visits)
        except (AttributeError, KeyError, AssertionError) as e:
            # print("Failed to update root: %s" % type(e))
            # print(type(e))
            # print()
            # Create New Tree
            self.root = Node(state, None)
            value, action_probs = self._evaluate([self.root])
            self.root.action_probs = action_probs[0]
            self._backpropagate(self.root, value[0])

        # Run Simulation
        self.run_simulation(self.iteration_limit, self.time_limit)

        # Select Action
        action = max(self.root.children, key=lambda action: self.root.children[action].num_visits)
        if update_root:
            try:    self.root = self.root.children[action]; #print("VALUE: %s" % (self.root.total_reward / self.root.num_visits))
            except: pass
        
        return action
