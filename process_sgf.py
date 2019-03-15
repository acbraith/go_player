from go import Go

from typing import Tuple, List, Optional, Dict

import re

def sgf_moves(sgf: str) -> List[Tuple[int, Tuple[int,int]]]:
    moves = []
    move_regex = r'([WB])\[(\w{0,2})\]'
    move_num_regex = r'MN\[\d+\]'
    for move in re.findall(r';(?:%s)?\n?%s' % (move_num_regex, move_regex), sgf):
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
    black_moves = re.search(r'\n\s*AB(\[.*\])\n' , sgf)
    if black_moves:
        locs = black_moves[1]
        for move in re.findall(r'\[(\w\w)\]', locs):
            x,y = move[0], move[1]
            i,j = ord(x) - ord('a'), ord(y) - ord('a')
            black += [(i,j)]
    white = []
    white_moves = re.search(r'\n\s*AW(\[.*\])\n' , sgf)
    if white_moves:
        locs = white_moves[1]
        for move in re.findall(r'\[(\w\w)\]', locs):
            x,y = move[0], move[1]
            i,j = ord(x) - ord('a'), ord(y) - ord('a')
            white += [(i,j)]
    return black, white

def RE(sgf: str) -> str:
    try:
        RE = re.search(r'RE\[([^\]]*)\]', sgf)[1]
        return RE
    except:
        return '?'

def SZ(sgf: str) -> str:
    try:
        SZ = re.search(r'SZ\[([^\]]*)\]', sgf)[1]
        return SZ
    except:
        return '?'

def BR(sgf: str) -> str:
    try:
        BR = re.search(r'BR\[([^\]]*)\]', sgf)[1]
        return BR
    except:
        return '?'

def WR(sgf: str) -> str:
    try:
        WR = re.search(r'WR\[([^\]]*)\]', sgf)[1]
        return WR
    except:
        return '?'

def HA(sgf: str) -> str:
    try:
        HA = re.search(r'HA\[([^\]]*)\]', sgf)[1]
        return HA
    except:
        return '?'

def play_sgf(sgf: str) -> Optional[Dict]:
    try:
        board_size = int(SZ(sgf))
    except:
        raise Exception('Illegal Board Size %s' % SZ(sgf))
    if '(;W[' in sgf or '(;B[' in sgf:
        raise Exception('Analysis Currently Unsupported')
    go = Go(board_size)
    black,white = sgf_add_stones(sgf)
    print(black, white)
    for loc in black: go._board[loc] = Go.BLACK
    for loc in white: go._board[loc] = Go.WHITE
    # print(go)
    for p,move in sgf_moves(sgf):
        # print(p,move)
        go._turn = p
        go = go.place(move)
        # print(go)
    return {
        'board' : go,
        'RE'    : RE(sgf),
        'WR'    : WR(sgf),
        'BR'    : BR(sgf),
        'SZ'    : SZ(sgf),
    }
    