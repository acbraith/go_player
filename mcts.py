import numpy as np
import time

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
    def __init__(self, exploration_constant, policy_fn, value_fn, iteration_limit = None, time_limit = None):
        self.iteration_limit    = iteration_limit
        self.time_limit         = time_limit # sec
        self.exploration_constant = exploration_constant
        self.policy_fn          = policy_fn
        self.value_fn           = value_fn
        self.root               = None

    def _select_action(self, node, exploration_value):
        def value(action):
            try:
                child = node.children[action]
                Q = child.total_reward / child.num_visits
                U = exploration_value * \
                    node.action_probs[action] * np.sqrt(node.num_visits) / (1+child.num_visits)
            except KeyError:
                Q = 0.5
                U = exploration_value * \
                    node.action_probs[action] * np.sqrt(node.num_visits)
            if node.state.turn == -1: Q = 1 - Q
            return Q + U
        action_values = {
            action: value(action) for action in node.state.available_actions
        }
        return max(action_values, key=lambda action: action_values[action])

    def _select_leaf_node(self, node):
        if node.state.terminal:
            return node
        action = self._select_action(node, self.exploration_constant)
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

    def _evaluate(self, node):
        value, action_probs = self.value_fn(node.state), self.policy_fn(node.state)
        return value, action_probs

    def run_simulation(self, iteration_limit=None, time_limit=None):
        start_time = time.time()

        for _ in range(iteration_limit) if iteration_limit else iter(int, 1):
            if time_limit and time.time() - start_time > time_limit: break
            # 1. Selection
            leaf                = self._select_leaf_node(self.root)
            # 2. Evaluation
            value, action_probs = self._evaluate(leaf)
            leaf.action_probs   = action_probs
            # 3. Backpropagation
            self._backpropagate(leaf, value)

            if time_limit is None and iteration_limit is None:
                break

    def get_action(self, state):
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
            value, action_probs = self._evaluate(self.root)
            self.root.action_probs = action_probs
            self._backpropagate(self.root, value)

        # Run Simulation
        self.run_simulation(self.iteration_limit, self.time_limit)

        # Select Action
        action = max(self.root.children, key=lambda action: self.root.children[action].num_visits)
        try:    self.root = self.root.children[action]; #print("VALUE: %s" % (self.root.total_reward / self.root.num_visits))
        except: pass
        
        return action
