
from time import sleep

import itertools
import numpy as np
from typing import Union, List, Tuple, Set, Optional
from copy import copy

class Go:
    _ns = {9:{}, 13:{}, 21:{}}
    WHITE = -1
    BLACK = +1
    PASS  = (-1,-1)
    def __init__(self, board_size:int=9, komi=6.5):
        self._size      = board_size
        self._board     = np.zeros(shape=(self._size,self._size), dtype=np.int8)
        self._turn      = Go.BLACK
        self._stones    = {Go.BLACK: 0, Go.WHITE: 0}
        self._komi      = komi
        self._prev      = None
        self._last_move = None
        self._over      = False

    def copy(self):
        go          = Go(self._size, self._komi)
        go._board   = self._board.copy()
        go._turn    = self._turn
        go._stones  = copy(self._stones)
        go._over    = self._over
        return go

    def winner(self) -> Optional[int]:
        if self._over:
            return 1 if self._score(1) > self._score(-1) else -1
        return None

    def place(self, pos: Tuple[int, int]) -> Optional['Go']:
        after                   = self.copy() # handwritten copy function faster than deepcopy
        after._prev             = self
        # both pass => game over
        if pos == Go.PASS and self._last_move == Go.PASS or self._over:
            after._over = True
            return after
        elif pos != Go.PASS:
            # must place on empty intersection
            if self._board[pos] != 0:
                return None
            after._board[pos] = after._turn
            after._stones[after._turn] += 1
            # capture enemy stones
            for n in after._neighbors(pos):
                if after._board[pos] == after._board[n] * -1 and len(after._liberties(n)) == 0:
                    group = after._group(n)
                    after._stones[after._turn * -1] -= len(group)
                    for p in group: after._board[p] = 0
            # no self capture
            if len(after._liberties(pos)) == 0:
                return None
            # no ko
            # TODO does this work?
            try:
                if np.array_equal(after._board, after._prev._prev._board):
                    return None
            except AttributeError:
                pass
        after._turn             *= -1
        after._last_move        = pos
        return after

    def _neighbors(self, pos: Tuple[int, int]) -> Set[Tuple[int, int]]:
        if pos not in Go._ns[self._size]:
            x,y = pos
            ns = {(x+1,y),(x-1,y),(x,y+1),(x,y-1)}
            ns = {(x,y) for x,y in ns if 0<=x<self._size and 0<=y<self._size}
            Go._ns[self._size][pos] = ns
        return Go._ns[self._size][pos]

    def _group(self, pos: Tuple[int, int]) -> int:
        player = self._board[pos]
        def rec_group(pos, group):
            group.add(pos)
            [rec_group(n, group) for n in self._neighbors(pos) if n not in group and self._board[n] == player]
            return group
        return rec_group(pos, set())

    def _group_neighbors(self, group: Set[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        n = set.union(*[self._neighbors(pos) for pos in group])
        return n - group

    def _liberties(self, pos: Tuple[int, int]) -> Set[Tuple[int, int]]:
        group = self._group(pos)
        return {n for n in self._group_neighbors(group) if self._board[n] == 0}

    def _score(self, player:int) -> int:
        return self._territory(player) + self._stones[player] + (self._komi if player == Go.WHITE else 0)

    def _territory(self, player:int) -> int:
        territory = 0
        poss = set(itertools.product(range(self._size), range(self._size)))
        while poss:
            pos = poss.pop()
            if self._board[pos] == 0:
                group = self._group(pos)
                borders = self._group_neighbors(group)
                if all([self._board[p] == player for p in borders]):
                    territory += len(group)
                poss -= group
        return territory

    def __str__(self) -> str:
        board = ''
        if self._over:
            board = '\nGAME OVER: %s WINS' % ('BLACK' if self.winner() == Go.BLACK else 'WHITE')
        board += '\nBLACK %.1f - %.1f WHITE' % (self._score(Go.BLACK), self._score(Go.WHITE))
        board += '\n   A  B  C  D  E  F  G  H  I '
        for y in reversed(range(self._size)):
            board += '\n%d ' % (y+1)
            for x in range(self._size):
                board += '╴⏺╶' if self._board[x,y] == Go.WHITE else '╴🞅╶' if self._board[x,y] == Go.BLACK else '─┼─'
        if not self._over:
            board += '\n%s to play' % ('BLACK' if self._turn == Go.BLACK else 'WHITE')
        return board

def play():
    def cmd_to_coords(cmd: str) -> Tuple[int, int]:
        if cmd == 'pass':
            return Go.PASS
        x = ord(cmd[0].upper()) - ord('A')
        y = int(cmd[1]) - 1
        return (x,y)

    go = Go()
    print(go)
    while not go._over:
        cmd = input()
        if cmd == 'q':
            break
        go = go.place(cmd_to_coords(cmd))
        print(go)

if __name__ == '__main__':
    play()