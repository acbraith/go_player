from go import Go

from typing import Tuple, List

import re

def sgf_moves(sgf: str) -> List[Tuple[int, Tuple[int,int]]]:
    moves = []
    for move in re.findall(r';([WB])\[(\w{0,2})\]\n' , sgf):
        p, move = move
        if p == 'W': p = Go.WHITE
        else       : p = Go.BLACK
        if move == '':
            move = Go.PASS
        else:
            x,y = move[0], move[1]
            i,j = ord(x) - ord('a'), ord(y) - ord('a')
            move = (i,j)
        moves += [(p,move)]
    return moves

def sgf_add_stones(sgf: str) -> Tuple[List[Tuple[int,int]]]:
    black = []
    black_moves = re.search(r'\nAB(\[.*\])\n' , sgf)
    if black_moves:
        locs = black_moves[1]
        for move in re.findall(r'(\w\w)', locs):
            x,y = move[0], move[1]
            i,j = ord(x) - ord('a'), ord(y) - ord('a')
            black += [(i,j)]
    white = []
    white_moves = re.search(r'\nAW(\[.*\])\n' , sgf)
    if white_moves:
        locs = white_moves[1]
        for move in re.findall(r'(\w\w)', locs):
            x,y = move[0], move[1]
            i,j = ord(x) - ord('a'), ord(y) - ord('a')
            white += [(i,j)]
    return black, white

def winner(sgf: str) -> str:
    try:
        winner = re.search(r'RE\[([^\]]*)\]', sgf)[1]
        return winner
    except:
        return '?'

def size(sgf: str) -> str:
    size = re.search(r'SZ\[([^\]]*)\]', sgf)[1]
    return size

def b_rating(sgf: str) -> str:
    try:
        br = re.search(r'BR\[([^\]]*)\]', sgf)[1]
        return br
    except:
        return '?'

def w_rating(sgf: str) -> str:
    try:
        wr = re.search(r'WR\[([^\]]*)\]', sgf)[1]
        return wr
    except:
        return '?'

def play_sgf(sgf: str) -> Tuple[List[Go], int]:
    go = Go()
    black,white = sgf_add_stones(sgf)
    for loc in black: go._board[loc] = Go.BLACK
    for loc in white: go._board[loc] = Go.WHITE
    for p,move in sgf_moves(sgf):
        go._turn = p
        go = go.place(move)
    return (go, winner(sgf))
    
import os
import codecs
from tqdm import tqdm
if __name__ == '__main__':
    sgfs = [codecs.open('sgfs/downloads/%s' % game_id, 'r', 'utf-8').read() for game_id in os.listdir('sgfs/downloads/')]
    sizes, b_ratings, w_ratings, winners = list(map(size, sgfs)), list(map(b_rating, sgfs)), list(map(w_rating, sgfs)), list(map(winner, sgfs))
    import numpy as np
    
    unique, counts = np.unique(sizes, return_counts=True)
    print([(v,c) for v,c in zip(unique, counts)])
    unique, counts = np.unique(b_ratings, return_counts=True)
    print([(v,c) for v,c in zip(unique, counts)])
    unique, counts = np.unique(w_ratings, return_counts=True)
    print([(v,c) for v,c in zip(unique, counts)])
    unique, counts = np.unique(winners, return_counts=True)
    print([(v,c) for v,c in zip(unique, counts)])

    print(len(sgfs))
    finished_9x9 = lambda sgf: size(sgf) == '9' and winner(sgf)[0] in ['B', 'W']
    sgfs = [sgf for sgf in sgfs if finished_9x9(sgf)]
    print(len(sgfs))


    # sgf = open('sgfs/594193/15594332.sgf', 'r').read()
    # go, winner = play_sgf(sgf)
    # history = [go]
    # while history[-1]._prev is not None: 
    #     history += [history[-1]._prev]
    # for board in reversed(history):
    #     print(board)
    # print(winner)